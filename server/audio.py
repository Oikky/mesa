"""Mixer do Windows: saídas (dispositivos), microfones, canais por app e medidores de pico.

Todo acesso COM roda numa thread própria (COM não gosta de trocar de thread).
O resto do servidor conversa com ela por uma fila de comandos e callbacks.
"""
import queue
import re
import threading
import time

import comtypes
import psutil
from comtypes import CLSCTX_ALL
from pycaw.constants import DEVICE_STATE, EDataFlow
from pycaw.api.audioclient import IChannelAudioVolume
from pycaw.pycaw import (AudioUtilities, IAudioMeterInformation, IAudioSessionControl2,
                         IAudioSessionManager2, ISimpleAudioVolume)

import icons
from routing import Routing

# Nomes amigáveis pros executáveis mais comuns; o resto vira "Nome.exe" -> "Nome".
NICE_NAMES = {
    "chrome.exe": "Chrome", "msedge.exe": "Edge", "firefox.exe": "Firefox", "opera.exe": "Opera",
    "brave.exe": "Brave", "spotify.exe": "Spotify", "discord.exe": "Discord", "vlc.exe": "VLC",
    "wmplayer.exe": "Media Player", "microsoft.media.player.exe": "Media Player", "teams.exe": "Teams",
    "ms-teams.exe": "Teams", "zoom.exe": "Zoom", "whatsapp.exe": "WhatsApp", "steam.exe": "Steam",
    "obs64.exe": "OBS",
}

HEADPHONES = re.compile(r"fone|head|buds|airpods|earphone", re.I)

SCAN_EVERY = 1.0   # s entre varreduras de dispositivos/sessões
METER_HZ = 24      # taxa dos medidores


def nice_name(exe: str) -> str:
    low = exe.lower()
    if low in NICE_NAMES:
        return NICE_NAMES[low]
    base = exe.rsplit(".", 1)[0]
    return base[:1].upper() + base[1:]


def short_device(name: str) -> str:
    """'Alto-falantes (G06-BT)' -> 'G06-BT': o que vai entre parênteses é o que a pessoa reconhece."""
    if "(" in name and name.endswith(")"):
        inner = name[name.index("(") + 1:-1]
        return inner.replace("(R)", "").replace("VB-Audio ", "").strip()
    return name


class Device:
    def __init__(self, dev, sessions=True):
        self.id = dev.id
        self.name = dev.FriendlyName or "Saída"
        self.vol = dev.EndpointVolume
        iface = dev._dev.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
        self.meter = iface.QueryInterface(IAudioMeterInformation)
        if sessions:
            iface = dev._dev.Activate(IAudioSessionManager2._iid_, CLSCTX_ALL, None)
            self.sessions = iface.QueryInterface(IAudioSessionManager2)


class Channel:
    def __init__(self, key, name):
        self.key = key
        self.name = name
        self.sessions = []  # [(pid, ISimpleAudioVolume, IAudioMeterInformation, IChannelAudioVolume|None)]
        self.pids = set()
        self.output = None  # saída escolhida só pra esse app (None = padrão do Windows)
        self.exe = None     # caminho do executável (pro ícone)


class Mixer:
    def __init__(self, on_state, on_meters):
        self.on_state = on_state
        self.on_meters = on_meters
        self.cmds = queue.Queue()
        self.devices = {}       # id -> Device
        self.dev_order = []
        self.default_id = None
        self.mics = {}          # id -> Device (entradas: microfones)
        self.mic_order = []
        self.default_mic = None
        self.channels = {}
        self.order = []
        self._last_state = None
        self._peaks = {}
        self.exes = {}          # chave do canal -> caminho do .exe (fica mesmo depois que o app fecha)
        threading.Thread(target=self._run, name="mixer", daemon=True).start()

    # ---- API usada pelo servidor (thread-safe) ----
    def set_volume(self, key, value):
        self.cmds.put(("vol", key, max(0.0, min(1.0, float(value)))))

    def set_mute(self, key, muted):
        self.cmds.put(("mute", key, bool(muted)))

    def set_balance(self, key, b):
        """Balanço esquerda/direita: -1 = só esquerda, 0 = centro, 1 = só direita."""
        self.cmds.put(("bal", key, max(-1.0, min(1.0, float(b)))))

    def set_default(self, device_id):
        self.cmds.put(("default", device_id, None))

    def set_default_mic(self, device_id):
        self.cmds.put(("defaultmic", device_id, None))

    def route(self, key, device_id):
        """Manda o app `key` tocar na saída `device_id` (None = segue o padrão do Windows)."""
        self.cmds.put(("route", key, device_id))

    def state(self):
        return self._last_state

    def find_device(self, name_or_id):
        """Acha uma saída pelo id ou por parte do nome (usado pelos pads)."""
        for d in self.devices.values():
            if d.id == name_or_id:
                return d.id
        low = (name_or_id or "").lower()
        for d in self.devices.values():
            if low and low in d.name.lower():
                return d.id
        return None

    # ---- thread COM ----
    def _run(self):
        comtypes.CoInitialize()
        self.routing = Routing()
        last_scan = 0.0
        while True:
            now = time.monotonic()
            try:
                if now - last_scan > SCAN_EVERY:
                    self._scan()
                    last_scan = now
                self._drain_cmds()
                self._publish_state()
                self._read_meters()
            except Exception as e:  # dispositivo trocou, app fechou etc.
                print("[mixer]", repr(e))
                last_scan = 0.0
                time.sleep(0.5)
            time.sleep(1 / METER_HZ)

    def _scan(self):
        default = AudioUtilities.GetSpeakers()
        self.default_id = default.id if default else None
        found = AudioUtilities.GetAllDevices(data_flow=EDataFlow.eRender.value,
                                             device_state=DEVICE_STATE.ACTIVE.value)
        devices = {}
        for d in found:
            devices[d.id] = self.devices.get(d.id) or Device(d)
        self.devices = devices
        self.dev_order = [d.id for d in found]

        mic = AudioUtilities.GetMicrophone()
        try:
            self.default_mic = mic.GetId() if mic else None
        except Exception:
            self.default_mic = None
        found = AudioUtilities.GetAllDevices(data_flow=EDataFlow.eCapture.value,
                                             device_state=DEVICE_STATE.ACTIVE.value)
        mics = {}
        for d in found:
            try:
                mics[d.id] = self.mics.get(d.id) or Device(d, sessions=False)
            except Exception:
                continue
        self.mics = mics
        self.mic_order = [i for i in (d.id for d in found) if i in mics]

        channels = {}
        for dev in devices.values():
            enum = dev.sessions.GetSessionEnumerator()
            for i in range(enum.GetCount()):
                ctl = enum.GetSession(i)
                if ctl is None:
                    continue
                ctl2 = ctl.QueryInterface(IAudioSessionControl2)
                pid = ctl2.GetProcessId()
                if pid == 0:
                    key, name = "system", "Sistema"
                else:
                    try:
                        proc = psutil.Process(pid)
                        exe = proc.name()
                    except psutil.Error:
                        continue
                    key, name = exe.lower(), nice_name(exe)
                    if key not in self.exes:
                        try:
                            self.exes[key] = proc.exe()
                        except psutil.Error:
                            self.exes[key] = None
                ch = channels.setdefault(key, Channel(key, name))
                vol = ctl2.QueryInterface(ISimpleAudioVolume)
                meter = ctl2.QueryInterface(IAudioMeterInformation)
                try:
                    chan = ctl2.QueryInterface(IChannelAudioVolume)
                except comtypes.COMError:
                    chan = None
                ch.sessions.append((pid, vol, meter, chan))
                ch.pids.add(pid)
        for k, ch in channels.items():
            if k != "system":
                ch.output = next((o for o in map(self.routing.get, ch.pids) if o), None)
        order = [k for k in self.order if k in channels]
        order += [k for k in channels if k not in order]
        order.sort(key=lambda k: 0 if k == "system" else 1)
        self.channels, self.order = channels, order

    def _device(self, key):
        if key == "master":
            return self.devices.get(self.default_id)
        if key.startswith("dev:"):
            return self.devices.get(key[4:])
        if key == "mic":
            return self.mics.get(self.default_mic)
        if key.startswith("mic:"):
            return self.mics.get(key[4:])
        return None

    def _drain_cmds(self):
        while True:
            try:
                op, key, val = self.cmds.get_nowait()
            except queue.Empty:
                return
            if op == "default":
                if key in self.devices:
                    AudioUtilities.SetDefaultDevice(key)
                    self.default_id = key
                continue
            if op == "defaultmic":
                if key in self.mics:
                    AudioUtilities.SetDefaultDevice(key)
                    self.default_mic = key
                continue
            if op == "route":
                ch = self.channels.get(key)
                if ch and key != "system":
                    for pid in ch.pids:
                        self.routing.set(pid, val)
                    # a sessão muda de dispositivo: varrer de novo logo
                    time.sleep(0.15)
                    self._scan()
                continue
            if op == "bal":
                left, right = (1.0, 1.0 + val) if val < 0 else (1.0 - val, 1.0)
                dev = self._device(key)
                try:
                    if dev and dev.vol.GetChannelCount() >= 2:
                        dev.vol.SetChannelVolumeLevelScalar(0, left, None)
                        dev.vol.SetChannelVolumeLevelScalar(1, right, None)
                    elif not dev and key in self.channels:
                        for _, _, _, c in self.channels[key].sessions:
                            if c and c.GetChannelCount() >= 2:
                                c.SetChannelVolume(0, left, None)
                                c.SetChannelVolume(1, right, None)
                except comtypes.COMError:
                    pass
                continue
            dev = self._device(key)
            if dev:
                if op == "vol":
                    dev.vol.SetMasterVolumeLevelScalar(val, None)
                else:
                    dev.vol.SetMute(val, None)
                continue
            ch = self.channels.get(key)
            if not ch:
                continue
            for _, v, _, _ in ch.sessions:
                if op == "vol":
                    v.SetMasterVolume(val, None)
                else:
                    v.SetMute(val, None)

    def _mic_state(self, dev):
        st = self._dev_state(dev, "mic:" + dev.id)
        st["icon"] = "mic"
        st["default"] = dev.id == self.default_mic
        return st

    def _dev_state(self, dev, key):
        return {
            "id": key,
            "icon": icons.choice(key, "headphones" if HEADPHONES.search(dev.name) else "speaker"),
            "device": dev.id,
            "name": dev.name,
            "short": short_device(dev.name),
            "vol": round(dev.vol.GetMasterVolumeLevelScalar(), 3),
            "mute": bool(dev.vol.GetMute()),
            "db": round(dev.vol.GetMasterVolumeLevel(), 1),
            "bal": self._bal(dev.vol, endpoint=True),
            "default": dev.id == self.default_id,
        }

    @staticmethod
    def _bal(c, endpoint=False):
        """Balanço atual a partir do volume dos canais esquerdo/direito (0 se não der pra saber)."""
        try:
            if not c or c.GetChannelCount() < 2:
                return 0
            get = c.GetChannelVolumeLevelScalar if endpoint else c.GetChannelVolume
            return round(get(1) - get(0), 2)
        except comtypes.COMError:
            return 0

    def _publish_state(self):
        chans = []
        for k in self.order:
            ch = self.channels[k]
            _, v0, _, c0 = ch.sessions[0]
            routed = ch.output
            chans.append({
                "id": k,
                "name": ch.name,
                "vol": round(v0.GetMasterVolume(), 3),
                "mute": bool(v0.GetMute()),
                "bal": self._bal(c0),
                "output": routed if routed in self.devices else None,
                "icon": icons.choice(k, "monitor" if k == "system" else "app"),
            })
        default = self.devices.get(self.default_id)
        state = {
            "master": self._dev_state(default, "master") if default else None,
            "devices": [self._dev_state(self.devices[i], "dev:" + i) for i in self.dev_order],
            "channels": chans,
            "mics": [self._mic_state(self.mics[i]) for i in self.mic_order],
            "routing": self.routing.ok,
            "iconv": icons.version(),
        }
        if state != self._last_state:
            self._last_state = state
            self.on_state(state)

    def _read_meters(self):
        peaks = {}
        for i in self.dev_order:
            peaks["dev:" + i] = self.devices[i].meter.GetPeakValue()
        if self.default_id in self.devices:
            peaks["master"] = peaks["dev:" + self.default_id]
        for i in self.mic_order:
            peaks["mic:" + i] = self.mics[i].meter.GetPeakValue()
        for k in self.order:
            peaks[k] = max(m.GetPeakValue() for _, _, m, _ in self.channels[k].sessions)
        out = {k: round(v, 2) for k, v in peaks.items()}
        if out != self._peaks:
            self._peaks = out
            self.on_meters(out)

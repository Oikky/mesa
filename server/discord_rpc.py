"""Discord pelo RPC local (o mesmo canal que o plugin do Stream Deck usa).

Conversa com o app do Discord aberto no notebook pelo pipe \\\\?\\pipe\\discord-ipc-N.
Mostra quem está na call, quem está falando, o volume de cada um (dá pra mudar) e, fora de
call, as notificações de mensagem que chegarem. Precisa de um app em discord.com/developers
(client_id + client_secret em config/secrets.json); na primeira vez o Discord pede pra autorizar.
"""
import ctypes
import json
import msvcrt
import os
import queue
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import secrets_store

SCOPES = ["rpc", "rpc.voice.read", "rpc.voice.write", "rpc.notifications.read", "identify"]
REDIRECT = "http://127.0.0.1"
OP_HANDSHAKE, OP_FRAME, OP_CLOSE = 0, 1, 2
MAX_NOTES = 25


class Discord:
    def __init__(self, on_change):
        self.on_change = on_change
        self.pipe = None
        self._out = queue.Queue()  # escrever e ler no mesmo pipe em threads diferentes trava no Windows
        self._pending = {}       # nonce -> [Event, resposta]
        self._authed = False
        self._channel_id = None
        self.state = {"status": "off"}  # off | setup | auth | ok
        self.members = {}        # user_id -> dados
        self.channel = None
        self.me = {"mute": False, "deaf": False}
        self.notes = []
        self._authorize_wanted = threading.Event()
        threading.Thread(target=self._run, name="discord", daemon=True).start()

    # ---------------------------------------------------------------- estado pro tablet
    def snapshot(self):
        st = dict(self.state)
        if st.get("status") == "ok":
            st["channel"] = self.channel
            st["members"] = sorted(self.members.values(), key=lambda m: m["name"].lower())
            st["me"] = self.me
            st["notes"] = self.notes
        return st

    def _changed(self):
        try:
            self.on_change(self.snapshot())
        except Exception as e:
            print("[discord] aviso:", repr(e))

    def _set_status(self, status, **extra):
        new = {"status": status, **extra}
        if new != self.state:
            self.state = new
            self._changed()

    # ---------------------------------------------------------------- pipe
    def _open(self):
        for i in range(10):
            try:
                return open(rf"\\?\pipe\discord-ipc-{i}", "r+b", buffering=0)
            except OSError:
                continue
        return None

    def _write(self, op, payload):
        data = json.dumps(payload).encode()
        self._out.put(struct.pack("<II", op, len(data)) + data)

    def _flush(self):
        while True:
            try:
                self.pipe.write(self._out.get_nowait())
            except queue.Empty:
                return

    def _available(self):
        n = ctypes.c_ulong(0)
        h = msvcrt.get_osfhandle(self.pipe.fileno())
        if not ctypes.windll.kernel32.PeekNamedPipe(h, None, 0, None, ctypes.byref(n), None):
            raise ConnectionError("Discord fechou")
        return n.value

    def _read(self):
        head = self.pipe.read(8)
        if len(head) < 8:
            raise ConnectionError("Discord fechou")
        op, size = struct.unpack("<II", head)
        body = b""
        while len(body) < size:
            chunk = self.pipe.read(size - len(body))
            if not chunk:
                raise ConnectionError("Discord fechou")
            body += chunk
        return op, json.loads(body)

    def _call(self, cmd, args=None, evt=None, timeout=60):
        nonce = str(uuid.uuid4())
        slot = [threading.Event(), None]
        self._pending[nonce] = slot
        msg = {"cmd": cmd, "args": args or {}, "nonce": nonce}
        if evt:
            msg["evt"] = evt
        self._write(OP_FRAME, msg)
        if not slot[0].wait(timeout):
            self._pending.pop(nonce, None)
            raise TimeoutError(cmd)
        res = slot[1]
        if res.get("evt") == "ERROR":
            raise RuntimeError(res.get("data", {}).get("message", "erro do Discord"))
        return res.get("data")

    # ---------------------------------------------------------------- laço principal
    def _run(self):
        while True:
            cfg = secrets_store.get("discord")
            if not cfg.get("client_id") or not cfg.get("client_secret"):
                self._set_status("setup")
                time.sleep(10)
                continue
            self.pipe = self._open()
            if not self.pipe:
                self._set_status("off")
                time.sleep(8)
                continue
            try:
                self._out = queue.Queue()
                self._write(OP_HANDSHAKE, {"v": 1, "client_id": cfg["client_id"]})
                self._flush()
                op, msg = self._read()
                if op == OP_CLOSE or msg.get("evt") != "READY":
                    raise ConnectionError(msg.get("message", "Discord recusou"))
                threading.Thread(target=self._setup, args=(cfg,), daemon=True).start()
                while True:
                    self._flush()
                    if not self._available():
                        time.sleep(0.02)
                        continue
                    op, msg = self._read()
                    if op == OP_CLOSE:
                        raise ConnectionError(msg.get("message", "fechado"))
                    self._dispatch(msg)
            except Exception as e:
                print("[discord]", repr(e))
            finally:
                try:
                    self.pipe.close()
                except Exception:
                    pass
                self.pipe = None
                self._authed = False
                self.members, self.channel, self._channel_id = {}, None, None
                for slot in self._pending.values():
                    slot[1] = {"evt": "ERROR", "data": {"message": "desconectado"}}
                    slot[0].set()
                self._pending.clear()
                self._set_status("off")
            time.sleep(5)

    def _dispatch(self, msg):
        nonce = msg.get("nonce")
        if nonce and nonce in self._pending:
            slot = self._pending.pop(nonce)
            slot[1] = msg
            slot[0].set()
            return
        if msg.get("cmd") != "DISPATCH":
            return
        evt, data = msg.get("evt"), msg.get("data") or {}
        if evt == "VOICE_CHANNEL_SELECT":
            threading.Thread(target=self._join, args=(data.get("channel_id"),), daemon=True).start()
        elif evt in ("VOICE_STATE_CREATE", "VOICE_STATE_UPDATE"):
            self._member(data)
            self._changed()
        elif evt == "VOICE_STATE_DELETE":
            self.members.pop((data.get("user") or {}).get("id"), None)
            self._changed()
        elif evt in ("SPEAKING_START", "SPEAKING_STOP"):
            m = self.members.get(data.get("user_id"))
            if m:
                m["speaking"] = evt == "SPEAKING_START"
                self._changed()
        elif evt == "VOICE_SETTINGS_UPDATE":
            self.me = self._me(data)
            self._changed()
        elif evt == "NOTIFICATION_CREATE":
            m = data.get("message") or {}
            author = m.get("author") or {}
            self.notes.insert(0, {
                "id": m.get("id") or str(time.time()),
                "title": data.get("title") or author.get("global_name") or author.get("username") or "Discord",
                "body": data.get("body") or m.get("content") or "",
                "icon": data.get("icon_url"),
                "at": time.time(),
            })
            del self.notes[MAX_NOTES:]
            self._changed()

    # ---------------------------------------------------------------- login e assinaturas
    def _token(self, cfg, form):
        form = {"client_id": cfg["client_id"], "client_secret": cfg["client_secret"], **form}
        req = urllib.request.Request("https://discord.com/api/oauth2/token", urllib.parse.urlencode(form).encode(),
                                     {"Content-Type": "application/x-www-form-urlencoded",
                                      "User-Agent": "Mesa (local, 1.0)"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        secrets_store.update("discord", refresh_token=data.get("refresh_token"), access_token=data["access_token"],
                             expires_at=time.time() + data.get("expires_in", 604800) - 3600)
        return data["access_token"]

    def authorize(self):
        """Chamado pelo tablet (botão Conectar): o Discord no notebook mostra a janela de autorização."""
        self._authorize_wanted.set()

    def _setup(self, cfg):
        try:
            token = cfg.get("access_token") if time.time() < cfg.get("expires_at", 0) else None
            if not token and cfg.get("refresh_token"):
                try:
                    token = self._token(cfg, {"grant_type": "refresh_token", "refresh_token": cfg["refresh_token"]})
                except urllib.error.HTTPError:
                    token = None
            while not token:
                self._set_status("auth")
                self._authorize_wanted.clear()
                self._authorize_wanted.wait()
                self._set_status("auth", waiting=True)
                data = self._call("AUTHORIZE", {"client_id": cfg["client_id"], "scopes": SCOPES}, timeout=180)
                token = self._token(cfg, {"grant_type": "authorization_code", "code": data["code"],
                                          "redirect_uri": REDIRECT})
            self._call("AUTHENTICATE", {"access_token": token})
            self._authed = True
            self._set_status("ok")
            for evt in ("VOICE_CHANNEL_SELECT", "VOICE_SETTINGS_UPDATE", "NOTIFICATION_CREATE"):
                try:
                    self._call("SUBSCRIBE", {}, evt=evt)
                except Exception as e:
                    print("[discord] assinar", evt, repr(e))
            vs = self._call("GET_VOICE_SETTINGS") or {}
            self.me = self._me(vs)
            ch = self._call("GET_SELECTED_VOICE_CHANNEL")
            self._join(ch["id"] if ch else None, ch)
        except Exception as e:
            print("[discord] login:", repr(e))
            self._set_status("auth", error=str(e))

    def _me(self, vs):
        """Meu mic/fone no Discord: mudo, ensurdecido e qual entrada/saída com que volume."""
        def io(d, old):
            d = d or {}
            devs = d.get("available_devices")
            return {
                "device": d.get("device_id", old.get("device")),
                "volume": round(d["volume"]) if d.get("volume") is not None else old.get("volume"),
                "devices": [{"id": x.get("id"), "name": x.get("name")} for x in devs] if devs else old.get("devices", []),
            }
        old = self.me or {}
        return {"mute": bool(vs.get("mute")), "deaf": bool(vs.get("deaf")),
                "input": io(vs.get("input"), old.get("input") or {}),
                "output": io(vs.get("output"), old.get("output") or {})}

    def _member(self, vs):
        u = vs.get("user") or {}
        if not u.get("id"):
            return
        old = self.members.get(u["id"], {})
        av = u.get("avatar")
        self.members[u["id"]] = {
            "id": u["id"],
            "name": vs.get("nick") or u.get("global_name") or u.get("username") or "?",
            "avatar": f"https://cdn.discordapp.com/avatars/{u['id']}/{av}.png?size=128" if av else None,
            "volume": round(vs.get("volume", 100)),
            "mute": bool(vs.get("mute")),
            "self_mute": bool((vs.get("voice_state") or {}).get("self_mute") or (vs.get("voice_state") or {}).get("mute")),
            "self_deaf": bool((vs.get("voice_state") or {}).get("self_deaf") or (vs.get("voice_state") or {}).get("deaf")),
            "speaking": old.get("speaking", False),
        }

    def _join(self, channel_id, data=None):
        old = self._channel_id
        if old and old != channel_id:
            for evt in ("VOICE_STATE_CREATE", "VOICE_STATE_UPDATE", "VOICE_STATE_DELETE", "SPEAKING_START", "SPEAKING_STOP"):
                try:
                    self._call("UNSUBSCRIBE", {"channel_id": old}, evt=evt)
                except Exception:
                    pass
        self._channel_id = channel_id
        self.members = {}
        self.channel = None
        if channel_id:
            data = data or self._call("GET_CHANNEL", {"channel_id": channel_id}) or {}
            self.channel = {"id": channel_id, "name": data.get("name") or "Call"}
            for vs in data.get("voice_states") or []:
                self._member(vs)
            if channel_id != old:
                for evt in ("VOICE_STATE_CREATE", "VOICE_STATE_UPDATE", "VOICE_STATE_DELETE", "SPEAKING_START", "SPEAKING_STOP"):
                    try:
                        self._call("SUBSCRIBE", {"channel_id": channel_id}, evt=evt)
                    except Exception as e:
                        print("[discord] assinar", evt, repr(e))
        self._changed()

    # ---------------------------------------------------------------- comandos do tablet
    def _bg(self, fn):
        if self._authed:
            threading.Thread(target=fn, daemon=True).start()

    def set_user(self, user_id, volume=None, mute=None):
        args = {"user_id": user_id}
        if volume is not None:
            args["volume"] = max(0, min(200, int(volume)))
        if mute is not None:
            args["mute"] = bool(mute)
        m = self.members.get(user_id)
        if m:
            m.update({k: v for k, v in args.items() if k != "user_id"})
        self._bg(lambda: self._call("SET_USER_VOICE_SETTINGS", args))

    def set_self(self, mute=None, deaf=None):
        args = {k: bool(v) for k, v in (("mute", mute), ("deaf", deaf)) if v is not None}
        self._bg(lambda: self._call("SET_VOICE_SETTINGS", args))

    def set_io(self, kind, device=None, volume=None):
        """Entrada (mic) ou saída do Discord: qual dispositivo e/ou volume (mic 0–100, saída 0–200)."""
        if kind not in ("input", "output"):
            return
        io = {}
        if device:
            io["device_id"] = str(device)
        if volume is not None:
            io["volume"] = max(0, min(100 if kind == "input" else 200, float(volume)))
        if io:
            cur = (self.me or {}).get(kind)
            if cur is not None:
                cur.update({"device": io.get("device_id", cur.get("device")), "volume": io.get("volume", cur.get("volume"))})
            self._bg(lambda: self._call("SET_VOICE_SETTINGS", {kind: io}))


def running():
    return any(os.path.exists(rf"\\?\pipe\discord-ipc-{i}") for i in range(3))

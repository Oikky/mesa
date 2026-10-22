"""Pads de automação (estilo Stream Deck).

A configuração fica em config/pads.json — dá pra editar pelo tablet ou direto no arquivo.
Cada pad: {"id", "label", "icon", "action": {...}, "bg"?, "home"?}.
  "bg"   = fundo pronto "preset:<nome>" (lista em web/app.js, PRESETS; desenho em styles.css),
           imagem pronta "/pad-presets/youtube.png", imagem "/padimg/x.jpg" (enviada pelo tablet),
           um link "https://..." ou um
           caminho no notebook "C:\\imagens\\fundo.png"
  "home" = true pra aparecer na fileira do início, embaixo da tela
Ações:
  {"type": "open",   "target": "https://youtube.com" | "spotify:" | "C:\\pasta" | "C:\\app.exe"}
  {"type": "keys",   "keys": "ctrl+shift+m"}
  {"type": "output", "device": "<id da saída ou parte do nome, ex. G06-BT>"}
"""
import ctypes
import json
import os
import threading
import time
from ctypes import wintypes
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "config" / "pads.json"
IMAGES = PATH.parent / "pad-images"
SLOTS = 15  # grade 5 × 3

DEFAULT = [  # primeira vez num PC novo (cada um muda pelo tablet: segurar o pad)
    {"id": "p1", "slot": 0, "label": "YouTube", "icon": "video", "bg": "/pad-presets/youtube.png",
     "action": {"type": "open", "target": "https://www.youtube.com"}},
    {"id": "p2", "slot": 1, "label": "Spotify", "icon": "music", "bg": "/pad-presets/spotify.png",
     "action": {"type": "open", "target": "spotify:"}},
    {"id": "p3", "slot": 2, "label": "Discord", "icon": "message-circle", "bg": "/pad-presets/discord.png",
     "action": {"type": "open", "target": "discord:"}},
    {"id": "p4", "slot": 3, "label": "Área de trabalho", "icon": "monitor", "bg": "preset:grafite",
     "action": {"type": "keys", "keys": "win+d"}},
    {"id": "p5", "slot": 4, "label": "Mutar tudo", "icon": "volume-x", "bg": "preset:vermelho",
     "action": {"type": "keys", "keys": "volumemute"}},
]

_lock = threading.Lock()


def load():
    try:
        pads = json.loads(PATH.read_text(encoding="utf-8"))
        if isinstance(pads, list):
            return pads
    except FileNotFoundError:
        save(DEFAULT)
        return list(DEFAULT)
    except Exception as e:
        print("[pads] config inválida:", repr(e))
    return []


def save(pads):
    with _lock:
        PATH.parent.mkdir(exist_ok=True)
        tmp = PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(pads, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(PATH)


def upsert(pad):
    pads = [p for p in load() if p.get("id") != pad["id"]]
    if pad.get("slot") is None:
        used = {p.get("slot") for p in pads}
        pad["slot"] = next((i for i in range(SLOTS) if i not in used), SLOTS)
    pads.append(pad)
    pads.sort(key=lambda p: p.get("slot", 99))
    save(pads)
    clean_images(pads)
    return pads


def move(src, dst):
    """Pad do lugar src vai pro lugar dst; se já tinha um pad lá, os dois trocam."""
    if not (0 <= src < SLOTS and 0 <= dst < SLOTS) or src == dst:
        return load()
    pads = load()
    for p in pads:
        if p.get("slot") == src:
            p["slot"] = dst
        elif p.get("slot") == dst:
            p["slot"] = src
    pads.sort(key=lambda p: p.get("slot", 99))
    save(pads)
    return pads


def clean_images(pads=None):
    """Apaga fundos enviados pelo tablet que nenhum pad usa mais."""
    used = {Path(p["bg"]).name for p in (pads or load()) if str(p.get("bg", "")).startswith("/padimg/")}
    for f in IMAGES.glob("*") if IMAGES.exists() else []:
        if f.name not in used:
            f.unlink(missing_ok=True)


def remove(pad_id):
    pads = [p for p in load() if p.get("id") != pad_id]
    save(pads)
    clean_images(pads)
    return pads


# ------------------------------------------------------------ ações
def run(pad, mixer):
    a = pad.get("action") or {}
    t = a.get("type")
    if t == "open" and a.get("target"):
        os.startfile(a["target"])
    elif t == "keys" and a.get("keys"):
        send_keys(a["keys"])
    elif t == "output" and a.get("device"):
        dev = mixer.find_device(a["device"])
        if dev:
            mixer.set_default(dev)
        else:
            raise LookupError(f"saída “{a['device']}” não encontrada")
    else:
        raise ValueError("pad sem ação")


VK = {
    "ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B, "cmd": 0x5B,
    "enter": 0x0D, "esc": 0x1B, "escape": 0x1B, "tab": 0x09, "space": 0x20, "backspace": 0x08,
    "delete": 0x2E, "del": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "printscreen": 0x2C, "prtsc": 0x2C, "capslock": 0x14,
    "volumeup": 0xAF, "volumedown": 0xAE, "volumemute": 0xAD,
    "playpause": 0xB3, "nexttrack": 0xB0, "prevtrack": 0xB1, "stop": 0xB2,
    "-": 0xBD, "=": 0xBB, ",": 0xBC, ".": 0xBE, "/": 0xBF, ";": 0xBA, "'": 0xDE,
    "[": 0xDB, "]": 0xDD, "\\": 0xDC, "`": 0xC0,
}
VK.update({f"f{i}": 0x6F + i for i in range(1, 25)})
EXTENDED = {0x2E, 0x2D, 0x24, 0x23, 0x21, 0x22, 0x26, 0x28, 0x25, 0x27, 0x5B, 0x2C}


def vk_of(name):
    name = name.strip().lower()
    if name in VK:
        return VK[name]
    if len(name) == 1 and (name.isalpha() or name.isdigit()):
        return ord(name.upper())
    raise ValueError(f"tecla desconhecida: {name}")


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def _key(vk, up):
    flags = (0x0002 if up else 0) | (0x0001 if vk in EXTENDED else 0)
    i = INPUT(type=1)
    i.ki = KEYBDINPUT(vk, 0, flags, 0, 0)
    return i


def send_keys(combo):
    """'ctrl+shift+m' -> aperta tudo em ordem e solta ao contrário."""
    vks = [vk_of(k) for k in combo.replace(" ", "").split("+") if k]
    seq = [_key(v, False) for v in vks] + [_key(v, True) for v in reversed(vks)]
    arr = (INPUT * len(seq))(*seq)
    ctypes.windll.user32.SendInput(len(seq), arr, ctypes.sizeof(INPUT))
    time.sleep(0.02)

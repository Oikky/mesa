"""Config de cada canal (ícone, nome meu, escondido) e o ícone do próprio .exe.

Fica em config/channels.json (dá pra mudar pelo tablet ou no arquivo):
  {"spotify.exe": {"icon": "music", "name": "Música"}, "master": {"hidden": true},
   "site:youtube.com": {"name": "YT"}, "discord.exe": {"icon": "C:\\\\img\\\\dc.png"}}
Chaves: .exe do app, "master", o id da saída, "site:<domínio>" (aba do navegador).
Ícone:
  "app"   = ícone do executável (padrão)
  "none"  = sem ícone
  nome    = ícone Lucide do sprite (music, video, headphones…)
  caminho = imagem qualquer (png, jpg, svg, ico)
"""
import ctypes
import io
import json
import threading
import time
from ctypes import wintypes
from pathlib import Path

from PIL import Image

PATH = Path(__file__).resolve().parent.parent / "config" / "channels.json"
SIZE = 64

_lock = threading.Lock()
_cfg = {}
_mtime = None
_checked = 0.0


def config():
    """Lê o channels.json (confere no máximo 1x por segundo; relê só quando o arquivo muda)."""
    global _cfg, _mtime, _checked
    now = time.monotonic()
    if now - _checked < 1:
        return _cfg
    _checked = now
    try:
        m = PATH.stat().st_mtime
    except FileNotFoundError:
        _cfg, _mtime = {}, None
        return _cfg
    if m != _mtime:
        try:
            data = json.loads(PATH.read_text(encoding="utf-8"))
            _cfg = data if isinstance(data, dict) else {}
        except Exception as e:
            print("[icons] channels.json inválido:", repr(e))
            _cfg = {}
        _mtime = m
    return _cfg


def version():
    """Muda quando a config muda: o tablet usa isso pra não pegar imagem velha do cache."""
    config()
    return int((_mtime or 0) * 1000) % 10_000_000


def choice(key, default="app"):
    return (config().get(key) or {}).get("icon") or default


def set_choice(key, icon):
    set_field(key, "icon", icon)


def set_field(key, field, value):
    """Muda um campo de um canal; None/""/False apaga o campo (e o canal, se ficar vazio)."""
    global _checked
    with _lock:
        cfg = dict(config())
        entry = dict(cfg.get(key) or {})
        if value in (None, "", False):
            entry.pop(field, None)
        else:
            entry[field] = value
        if entry:
            cfg[key] = entry
        else:
            cfg.pop(key, None)
        PATH.parent.mkdir(exist_ok=True)
        tmp = PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(PATH)
        _checked = 0.0


def is_file(icon):
    return "\\" in icon or "/" in icon or ":" in icon


# ------------------------------------------------------------ ícone do .exe
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.PrivateExtractIconsW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                        ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.UINT),
                                        wintypes.UINT, wintypes.UINT]
user32.DestroyIcon.argtypes = [wintypes.HICON]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HBITMAP), ("hbmColor", wintypes.HBITMAP)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(ICONINFO)]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                            ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT]
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]

_exe_cache = {}  # caminho do exe -> png (ou None)


def _bits(hdc, hbm, size):
    bih = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), size, -size, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(size * size * 4)
    if not gdi32.GetDIBits(hdc, hbm, 0, size, buf, ctypes.byref(bih), 0):
        return None
    return buf.raw


def exe_png(exe):
    """PNG do ícone do executável, ou None se não der pra extrair."""
    if exe in _exe_cache:
        return _exe_cache[exe]
    png = None
    hicon = wintypes.HICON()
    got = user32.PrivateExtractIconsW(exe, 0, SIZE, SIZE, ctypes.byref(hicon), None, 1, 0)
    if got and got != 0xFFFFFFFF and hicon:
        info = ICONINFO()
        hdc = user32.GetDC(None)
        try:
            if user32.GetIconInfo(hicon, ctypes.byref(info)) and info.hbmColor:
                color = _bits(hdc, info.hbmColor, SIZE)
                if color:
                    img = Image.frombuffer("RGBA", (SIZE, SIZE), color, "raw", "BGRA", 0, 1)
                    if img.getchannel("A").getextrema()[1] == 0:
                        # ícone antigo sem alfa: a transparência vem da máscara
                        mask = _bits(hdc, info.hbmMask, SIZE)
                        if mask:
                            m = Image.frombuffer("RGBA", (SIZE, SIZE), mask, "raw", "BGRA", 0, 1).convert("L")
                            img.putalpha(m.point(lambda p: 0 if p else 255))
                    out = io.BytesIO()
                    img.save(out, "PNG")
                    png = out.getvalue()
        finally:
            user32.ReleaseDC(None, hdc)
            if info.hbmColor:
                gdi32.DeleteObject(info.hbmColor)
            if info.hbmMask:
                gdi32.DeleteObject(info.hbmMask)
            user32.DestroyIcon(hicon)
    _exe_cache[exe] = png
    return png

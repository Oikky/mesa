"""Sugestões dos pads (segurar o pad no tablet): o que já tocou, playlists, mundos, pastas recentes.

Cada pad vira um "tipo" pelo que ele abre (YouTube, Spotify, instância do CurseForge, VS Code).
YouTube: a Mesa guarda os vídeos que passaram no notebook (config/history.json).
Minecraft: lista os mundos da instância; escolher um marca ele como o último jogado (fica em
primeiro na lista do jogo) e abre o jogo. O level.dat ganha uma cópia (level.dat_mesa) antes.
VS Code: pastas abertas recentemente (workspaceStorage) e abre a escolhida.
"""
import gzip
import io
import json
import os
import struct
import subprocess
import threading
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "config" / "history.json"
CF = Path(os.path.expandvars(r"%USERPROFILE%\curseforge\minecraft\Instances"))
VSC = Path(os.path.expandvars(r"%APPDATA%\Code\User\workspaceStorage"))


def kind(pad):
    act = pad.get("action") or {}
    t = str(act.get("target") or "").lower()
    proc = str(pad.get("process") or "").lower()
    if act.get("type") != "open":
        return None
    if "youtube.com" in t or "youtu.be" in t:
        return "youtube"
    if t.startswith("spotify:") or "open.spotify.com" in t:
        return "spotify"
    if t.startswith("curseforge://launch-game"):
        return "minecraft"
    if proc == "code.exe" or t.endswith("\\code.exe"):
        return "vscode"
    return None


# ------------------------------------------------------------ YouTube: o que passou no notebook
_hist_lock = threading.Lock()
_hist = None


def _load_hist():
    global _hist
    if _hist is None:
        try:
            _hist = json.loads(HIST.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _hist = []
    return _hist


def yt_seen(vid, title):
    """Vídeo tocando no notebook: vai pro topo do histórico (sem repetir)."""
    if not vid or not title:
        return
    with _hist_lock:
        h = _load_hist()
        if h and h[0]["id"] == vid:
            return
        h[:] = [x for x in h if x["id"] != vid]
        h.insert(0, {"id": vid, "title": title[:200], "at": int(time.time())})
        del h[60:]
        HIST.parent.mkdir(exist_ok=True)
        tmp = HIST.with_suffix(".tmp")
        tmp.write_text(json.dumps(h, ensure_ascii=False), encoding="utf-8")
        tmp.replace(HIST)


def _ago(ts):
    s = max(0, int(time.time() - ts))
    if s < 3600:
        return f"há {max(1, s // 60)} min"
    if s < 86400:
        return f"há {s // 3600} h"
    d = s // 86400
    return "ontem" if d == 1 else f"há {d} dias"


def youtube():
    with _hist_lock:
        h = list(_load_hist())
    items = [{"id": x["id"], "title": x["title"], "sub": _ago(x["at"]),
              "img": f"https://i.ytimg.com/vi/{x['id']}/mqdefault.jpg", "wide": True} for x in h[:24]]
    return {"sections": [{"title": "Passou por aqui", "items": items}] if items else [],
            "note": None if items else "Ainda não passou nada. Os vídeos que tocarem no notebook aparecem aqui."}


# ------------------------------------------------------------ Spotify
def spotify(sp):
    if sp.status() != "ok":
        return {"sections": [], "note": "Falta ligar o Spotify na Mesa (painel do Spotify)."}
    out, note = [], None
    try:
        rec = sp.recent()
        if rec:
            out.append({"title": "Tocou agora há pouco", "items": rec})
    except Exception as e:  # conta autorizada antes desta versão: falta a permissão do histórico
        if "scope" in str(e).lower() or "recusou" in str(e).lower():
            note = "Pra ver o que tocou antes, autorize a Mesa de novo no Spotify (uma vez)."
        else:
            note = str(e)
    try:
        pls = sp.playlists()
        if pls:
            out.append({"title": "Suas playlists", "items": pls})
    except Exception as e:
        note = note or str(e)
    return {"sections": out, "note": note, "relogin": bool(note and "autorize" in note)}


# ------------------------------------------------------------ Minecraft (CurseForge)
def _instance(target):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(target).query)
    want = (q.get("instanceId") or [""])[0].lower()
    if not CF.is_dir():
        return None
    for d in CF.iterdir():
        try:
            meta = json.loads((d / "minecraftinstance.json").read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if str(meta.get("guid", "")).lower() == want:
            return d
    return None


# NBT mínimo (o formato do level.dat): lê tudo e escreve de volta igual, só trocando o LastPlayed
def _nbt_read(f, tag):
    r = lambda fmt: struct.unpack(">" + fmt, f.read(struct.calcsize(">" + fmt)))[0]
    if tag == 1: return r("b")
    if tag == 2: return r("h")
    if tag == 3: return r("i")
    if tag == 4: return r("q")
    if tag == 5: return r("f")
    if tag == 6: return r("d")
    if tag == 7: return f.read(r("i"))
    if tag == 8: return f.read(r("H")).decode("utf-8", "surrogatepass")
    if tag == 9:
        sub, n = r("b"), r("i")
        return (sub, [_nbt_read(f, sub) for _ in range(n)])
    if tag == 10:
        out = []
        while True:
            t = r("b")
            if t == 0:
                return out
            name = f.read(r("H")).decode("utf-8", "surrogatepass")
            out.append([t, name, _nbt_read(f, t)])
    if tag == 11:
        n = r("i"); return list(struct.unpack(f">{n}i", f.read(4 * n)))
    if tag == 12:
        n = r("i"); return list(struct.unpack(f">{n}q", f.read(8 * n)))
    raise ValueError(f"tag NBT {tag}")


def _nbt_write(f, tag, v):
    w = lambda fmt, x: f.write(struct.pack(">" + fmt, x))
    if tag == 1: w("b", v)
    elif tag == 2: w("h", v)
    elif tag == 3: w("i", v)
    elif tag == 4: w("q", v)
    elif tag == 5: w("f", v)
    elif tag == 6: w("d", v)
    elif tag == 7: w("i", len(v)); f.write(v)
    elif tag == 8:
        b = v.encode("utf-8", "surrogatepass"); w("H", len(b)); f.write(b)
    elif tag == 9:
        sub, items = v; w("b", sub); w("i", len(items))
        for x in items: _nbt_write(f, sub, x)
    elif tag == 10:
        for t, name, x in v:
            w("b", t); b = name.encode("utf-8", "surrogatepass"); w("H", len(b)); f.write(b); _nbt_write(f, t, x)
        w("b", 0)
    elif tag == 11: w("i", len(v)); f.write(struct.pack(f">{len(v)}i", *v))
    elif tag == 12: w("i", len(v)); f.write(struct.pack(f">{len(v)}q", *v))


def _level(path):
    f = io.BytesIO(gzip.decompress(path.read_bytes()))
    t = struct.unpack(">b", f.read(1))[0]
    name = f.read(struct.unpack(">H", f.read(2))[0]).decode()
    return t, name, _nbt_read(f, t)


def _field(comp, key):
    return next((x for x in comp if x[1] == key), None)


def minecraft(target):
    inst = _instance(target)
    if not inst:
        return {"sections": [], "note": "Não achei essa instância do CurseForge."}
    worlds = []
    for d in (inst / "saves").iterdir() if (inst / "saves").is_dir() else []:
        lvl = d / "level.dat"
        if not lvl.is_file():
            continue
        last, name = lvl.stat().st_mtime, d.name
        try:
            data = _field(_level(lvl)[2], "Data")[2]
            lp = _field(data, "LastPlayed")
            nm = _field(data, "LevelName")
            if lp: last = lp[2] / 1000
            if nm and nm[2]: name = nm[2]
        except Exception:
            pass
        worlds.append({"id": d.name, "title": name, "sub": f"jogado {_ago(last)}", "at": last,
                       "img": f"/mcicon/{urllib.parse.quote(inst.name)}/{urllib.parse.quote(d.name)}" if (d / "icon.png").is_file() else None})
    worlds.sort(key=lambda w: -w["at"])
    return {"sections": [{"title": f"Mundos · {inst.name}", "items": worlds}] if worlds else [],
            "note": None if worlds else "Esse modpack ainda não tem mundo salvo."}


def mc_icon(inst, world):
    p = (CF / inst / "saves" / world / "icon.png").resolve()
    return p if p.is_file() and CF.resolve() in p.parents else None


def mc_pick(target, world):
    """Marca o mundo como o último jogado (o jogo lista ele em primeiro) e abre o modpack."""
    inst = _instance(target)
    lvl = inst / "saves" / world / "level.dat" if inst else None
    if not lvl or not lvl.is_file() or (inst / "saves").resolve() not in lvl.resolve().parents:
        raise ValueError("mundo não encontrado")
    t, name, root = _level(lvl)
    data = _field(root, "Data")[2]
    lp = _field(data, "LastPlayed")
    if lp:
        lp[2] = int(time.time() * 1000)
    else:
        data.append([4, "LastPlayed", int(time.time() * 1000)])
    buf = io.BytesIO()
    buf.write(struct.pack(">b", t))
    b = name.encode()
    buf.write(struct.pack(">H", len(b)) + b)
    _nbt_write(buf, t, root)
    (lvl.parent / "level.dat_mesa").write_bytes(lvl.read_bytes())  # cópia antes de mexer
    tmp = lvl.with_suffix(".mesa_tmp")
    tmp.write_bytes(gzip.compress(buf.getvalue()))
    _level(tmp)  # confere que dá pra ler de volta antes de trocar
    tmp.replace(lvl)
    os.startfile(target)


# ------------------------------------------------------------ VS Code
def _uri_path(uri):
    p = urllib.parse.unquote(urllib.parse.urlparse(uri).path)
    return p[1:].replace("/", "\\") if len(p) > 2 and p[2] == ":" else p


def vscode():
    seen, items = set(), []
    for d in sorted(VSC.glob("*/workspace.json") if VSC.is_dir() else [], key=lambda p: -p.parent.stat().st_mtime):
        try:
            uri = json.loads(d.read_text(encoding="utf-8")).get("folder")
        except (OSError, ValueError):
            continue
        if not uri or not uri.startswith("file://"):
            continue
        path = _uri_path(uri)
        if path.lower() in seen or not os.path.isdir(path):
            continue
        seen.add(path.lower())
        items.append({"id": path, "title": os.path.basename(path.rstrip("\\")) or path,
                      "sub": f"{os.path.dirname(path)} · {_ago(d.parent.stat().st_mtime)}"})
        if len(items) >= 16:
            break
    return {"sections": [{"title": "Pastas recentes", "items": items}] if items else [],
            "note": None if items else "Nenhuma pasta aberta recentemente."}


def vscode_pick(target, folder):
    if not os.path.isdir(folder):
        raise ValueError("pasta não existe mais")
    exe = target if str(target).lower().endswith("code.exe") else "code"
    subprocess.Popen([exe, folder], creationflags=subprocess.CREATE_NO_WINDOW)

"""Mesa: controla o som do notebook pela rede.

HTTPS (porta 8443): o app em si (PWA instalável no tablet).
HTTP  (porta 8080): só a página de configuração, pra baixar o certificado.
"""
import asyncio
import ctypes
import hashlib
import json
import mimetypes
import os
import socket
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

# COM da thread principal em modo MTA: sem isso o comtypes abre em STA e as
# chamadas assíncronas do WinRT (painel de mídia) nunca terminam.
sys.coinit_flags = 0
sys.path.insert(0, str(Path(__file__).parent))

ROOT = Path(__file__).resolve().parent.parent
HTTPS_PORT = 8443
HTTP_PORT = 8080

# Rodando com pythonw (sem janela, ao iniciar o Windows) não existe console: vai tudo pro log.
if sys.stdout is None or sys.stderr is None:
    (ROOT / "logs").mkdir(exist_ok=True)
    log = ROOT / "logs" / "mesa.log"
    if log.exists() and log.stat().st_size > 1_000_000:
        log.replace(log.with_suffix(".old.log"))
    sys.stdout = sys.stderr = open(log, "a", encoding="utf-8", buffering=1)
from audio import Mixer  # noqa: E402
from certs import DIR as CERT_DIR, ensure_certs, lan_ips  # noqa: E402
import icons  # noqa: E402
from media import Media  # noqa: E402
import pads  # noqa: E402
import psutil  # noqa: E402
from discord_rpc import Discord  # noqa: E402
from spotify import Spotify, SpotifyError  # noqa: E402
from tabs import Tabs  # noqa: E402
import updates  # noqa: E402
from video import Video  # noqa: E402

WEB = ROOT / "web"

clients: set[WebSocket] = set()
loop: asyncio.AbstractEventLoop | None = None


async def broadcast(msg: dict):
    data = json.dumps(msg, separators=(",", ":"))
    for ws in list(clients):
        try:
            await ws.send_text(data)
        except Exception:
            clients.discard(ws)


def from_thread(kind):
    def cb(payload):
        if loop and clients:
            asyncio.run_coroutine_threadsafe(broadcast({"t": kind, "d": payload}), loop)
    return cb


mixer = Mixer(on_state=from_thread("mix"), on_meters=from_thread("lvl"))
media = Media(on_change=lambda s: loop and asyncio.ensure_future(broadcast({"t": "media", "d": s})))
video = Video()
tabs = Tabs()
discord = Discord(on_change=from_thread("discord"))
spotify = Spotify()
upd = {"behind": 0, "ext": updates.extension_changed()}  # versão nova no git / extensão mudou
ext_clients: set[WebSocket] = set()  # extensão do navegador (canal de volta pro YouTube)


async def send_ext(msg: dict):
    data = json.dumps(msg)
    for ws in list(ext_clients):
        try:
            await ws.send_text(data)
        except Exception:
            ext_clients.discard(ws)


# ---------------- pads que abrem um painel quando o app já está aberto ----------------
def pad_app(pad):
    """Qual painel esse pad abre: spotify, youtube, discord, app:<exe> ou None (só executa)."""
    a = pad.get("action") or {}
    if a.get("type") != "open":
        return None
    if pad.get("process"):
        return "app:" + str(pad["process"]).lower()
    t = str(a.get("target") or "").lower()
    if "spotify" in t:
        return "spotify"
    if "youtube.com" in t or "youtu.be" in t:
        return "youtube"
    if "discord" in t:
        return "discord"
    if t.endswith(".exe"):
        return "app:" + Path(t).name
    # pad com o mesmo nome de um canal do mixer (ex.: "Brawlhalla")
    label = str(pad.get("label") or "").strip().lower()
    for ch in (mixer.state() or {}).get("channels", []):
        if label and ch["name"].lower() == label:
            return "app:" + ch["id"]
    return None


def app_running(key):
    if key == "youtube":
        return bool(video.tabs)
    exe = {"spotify": "spotify.exe", "discord": "discord.exe"}.get(key) or key.removeprefix("app:")
    return any((p.info["name"] or "").lower() == exe for p in psutil.process_iter(["name"]))


async def panel_data(key):
    if key == "youtube":
        return video.queue()
    if key == "spotify":
        try:
            return await asyncio.to_thread(spotify.panel)
        except SpotifyError as e:
            return {"status": "error", "error": str(e)}
    if key == "discord":
        return discord.snapshot()
    return None


async def send_panel(ws, key):
    await ws.send_text(json.dumps({"t": "panel", "d": {"app": key, "data": await panel_data(key)}}))


def system_action(action):
    if action == "lock":
        ctypes.windll.user32.LockWorkStation()
    elif action == "restart":
        subprocess.Popen(["shutdown", "/r", "/t", "0"], creationflags=subprocess.CREATE_NO_WINDOW)
    elif action == "shutdown":
        subprocess.Popen(["shutdown", "/s", "/t", "0"], creationflags=subprocess.CREATE_NO_WINDOW)

# ---------------- app (HTTPS) ----------------
@asynccontextmanager
async def lifespan(_):
    global loop
    loop = asyncio.get_running_loop()
    tasks = [asyncio.create_task(media.run()), asyncio.create_task(watch_pads()),
             asyncio.create_task(prune_video()), asyncio.create_task(watch_web()),
             asyncio.create_task(watch_channels()), asyncio.create_task(watch_updates())]
    yield
    for t in tasks:
        t.cancel()


async def watch_updates():
    """Confere o repositório 30 s depois de ligar e depois a cada 3 h."""
    await asyncio.sleep(30)
    while True:
        n = await asyncio.to_thread(updates.behind)
        if n != upd["behind"]:
            upd["behind"] = n
            await broadcast({"t": "upd", "d": upd})
        await asyncio.sleep(3 * 3600)


async def watch_channels():
    """channels.json mudou (pelo tablet ou à mão): todo mundo recebe nomes/escondidos novos."""
    last = icons.version()
    while True:
        await asyncio.sleep(1)
        v = icons.version()
        if v != last:
            last = v
            await broadcast({"t": "cfg", "d": icons.config()})


async def watch_pads():
    """Se o pads.json for editado na mão (por mim ou pelo Claude), o tablet atualiza sozinho."""
    pads.load()
    last = None
    while True:
        try:
            m = pads.PATH.stat().st_mtime
            if m != last:
                if last is not None:
                    await broadcast({"t": "pads", "d": pads.load()})
                last = m
        except FileNotFoundError:
            pass
        await asyncio.sleep(1)


async def watch_web():
    """Mudei o app no notebook: todo tablet aberto recarrega sozinho."""
    last = web_version()
    while True:
        await asyncio.sleep(1.5)
        v = web_version()
        if v != last:
            last = v
            await asyncio.sleep(0.5)  # espera terminar de salvar tudo
            await broadcast({"t": "ver", "d": web_version()})


async def prune_video():
    while True:
        await asyncio.sleep(5)
        if video.prune():
            await broadcast({"t": "video", "d": video.snapshot()})


async def run_pad(ws, pad_id, force=False):
    pad = next((p for p in pads.load() if p.get("id") == pad_id), None)
    try:
        if not pad:
            raise LookupError("pad não existe mais")
        key = pad_app(pad)
        # app já aberto: em vez de abrir de novo, mostra o painel dele (fila, call, volume...)
        if key and not force and await asyncio.to_thread(app_running, key):
            await ws.send_text(json.dumps({"t": "padResult", "d": {"id": pad_id, "ok": True, "panel": key}}))
            await send_panel(ws, key)
            return
        await asyncio.to_thread(pads.run, pad, mixer)
        res = {"id": pad_id, "ok": True, "app": key}
    except Exception as e:
        res = {"id": pad_id, "ok": False, "error": str(e)}
    await ws.send_text(json.dumps({"t": "padResult", "d": res}))


app = FastAPI(lifespan=lifespan)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        if mixer.state():
            await ws.send_text(json.dumps({"t": "mix", "d": mixer.state()}))
        await ws.send_text(json.dumps({"t": "media", "d": media.snapshot()}))
        await ws.send_text(json.dumps({"t": "pads", "d": pads.load()}))
        await ws.send_text(json.dumps({"t": "video", "d": video.snapshot()}))
        await ws.send_text(json.dumps({"t": "ver", "d": web_version()}))
        await ws.send_text(json.dumps({"t": "discord", "d": discord.snapshot()}))
        await ws.send_text(json.dumps({"t": "ytq", "d": video.queue()}))
        await ws.send_text(json.dumps({"t": "tabs", "d": tabs.snapshot()}))
        await ws.send_text(json.dumps({"t": "cfg", "d": icons.config()}))
        await ws.send_text(json.dumps({"t": "upd", "d": upd}))
        while True:
            msg = json.loads(await ws.receive_text())
            t = msg.get("t")
            if t == "vol":
                mixer.set_volume(msg["id"], msg["v"])
            elif t == "mute":
                mixer.set_mute(msg["id"], msg["m"])
            elif t == "media":
                asyncio.create_task(media.command(msg["a"], msg.get("v")))
            elif t == "default":
                mixer.set_default(msg["device"])
            elif t == "defaultmic":
                mixer.set_default_mic(msg["device"])
            elif t == "route":
                mixer.route(msg["id"], msg.get("device"))
            elif t == "pad":
                asyncio.create_task(run_pad(ws, msg["id"], bool(msg.get("force"))))
            elif t == "panel":
                asyncio.create_task(send_panel(ws, str(msg.get("app") or "")))
            elif t == "ytplay":
                q = video.queue()
                if q and msg.get("id"):
                    await send_ext({"cmd": "ytplay", "tab": q["tab"], "id": str(msg["id"])})
            elif t == "tabsink":
                tb = tabs.get(str(msg.get("id") or ""))
                if tb:
                    await send_ext({"cmd": "tabsink", "tab": tb["tab"], "name": str(msg.get("device") or "")[:200]})
            elif t in ("tabvol", "tabmute"):
                tb = tabs.get(str(msg.get("id") or ""))
                if tb:
                    if t == "tabvol":
                        tb["vol"] = min(1.0, max(0.0, float(msg.get("v") or 0)))
                        await send_ext({"cmd": "tabvol", "tab": tb["tab"], "v": tb["vol"]})
                    else:
                        await send_ext({"cmd": "tabmute", "tab": tb["tab"], "m": bool(msg.get("m"))})
            elif t == "spplay":
                async def sp_play(uri=msg.get("uri"), ctx=msg.get("context")):
                    try:
                        await asyncio.to_thread(spotify.play, uri, ctx)
                        await asyncio.sleep(0.6)
                    except SpotifyError as e:
                        await ws.send_text(json.dumps({"t": "toast", "d": str(e)}))
                    await send_panel(ws, "spotify")
                asyncio.create_task(sp_play())
            elif t == "splogin":
                # abre o login do Spotify no navegador do próprio notebook
                os.startfile(f"http://127.0.0.1:{HTTP_PORT}/spotify/login")
            elif t == "dcauth":
                discord.authorize()
            elif t == "dcuser":
                discord.set_user(str(msg.get("user")), msg.get("volume"), msg.get("mute"))
            elif t == "dcio":
                discord.set_io(str(msg.get("kind")), msg.get("device"), msg.get("volume"))
            elif t == "dcself":
                discord.set_self(msg.get("mute"), msg.get("deaf"))
            elif t == "system":
                a = msg.get("a")
                # reiniciar e desligar só com confirmação (o tablet manda depois de segurar o botão)
                if a == "lock" or (a in ("restart", "shutdown") and msg.get("confirm") is True):
                    await asyncio.to_thread(system_action, a)
            elif t == "padSave":
                pads.upsert(msg["d"])  # o watcher avisa todo mundo
            elif t == "update":
                if upd["behind"]:
                    updates.run_update()  # o tablet reconecta e recarrega sozinho quando a Mesa volta
            elif t == "padMove":
                pads.move(int(msg["from"]), int(msg["to"]))  # o watcher avisa todo mundo
            elif t == "padDelete":
                pads.remove(msg["id"])
            elif t == "chname":
                # nome meu pro canal; vazio volta pro nome original
                if msg.get("id"):
                    icons.set_field(str(msg["id"])[:300], "name", str(msg.get("name") or "").strip()[:40])
            elif t == "chhide":
                if msg.get("id"):
                    icons.set_field(str(msg["id"])[:300], "hidden", bool(msg.get("hidden")))
            elif t == "icon":
                icon = str(msg.get("icon") or "")[:300]
                if msg.get("id") and icon:
                    icons.set_choice(str(msg["id"]), icon)  # o mixer manda o estado novo sozinho
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        clients.discard(ws)


@app.get("/art/{h}")
async def art(h: str):
    item = media.art.get(h)
    if not item:
        return Response(status_code=404)
    data, ctype = item
    return Response(data, media_type=ctype, headers={"Cache-Control": "public, max-age=86400"})


@app.post("/pad-image")
async def pad_image(req: Request):
    """Fundo de pad mandado pelo tablet (já vem reduzido pra 288 px)."""
    data = await req.body()
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(req.headers.get("content-type", ""))
    if not ext or not data or len(data) > 3_000_000:
        return Response(status_code=400)
    pads.IMAGES.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha1(data).hexdigest()[:16] + ext
    (pads.IMAGES / name).write_bytes(data)
    return {"url": f"/padimg/{name}"}


@app.get("/padimg/{name}")
async def pad_img(name: str):
    f = pads.IMAGES / Path(name).name
    if not f.is_file():
        return Response(status_code=404)
    return FileResponse(f, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/padbg/{pad_id}")
async def pad_bg_file(pad_id: str):
    """Fundo que aponta pra um arquivo do notebook (escrito à mão no pads.json)."""
    pad = next((p for p in pads.load() if p.get("id") == pad_id), None)
    f = Path(str((pad or {}).get("bg", "")))
    if not pad or not f.is_absolute() or not f.is_file():
        return Response(status_code=404)
    return FileResponse(f, media_type=mimetypes.guess_type(f.name)[0] or "image/png")


@app.get("/icon/{key}")
async def channel_icon(key: str, src: str = ""):
    icon = icons.choice(key)
    if src != "app" and icons.is_file(icon):
        f = Path(icon)
        if f.is_file():
            return FileResponse(f, media_type=mimetypes.guess_type(f.name)[0] or "image/png",
                                headers={"Cache-Control": "public, max-age=86400"})
        return Response(status_code=404)
    exe = mixer.exes.get(key)
    png = exe and await asyncio.to_thread(icons.exe_png, exe)
    if not png:
        return Response(status_code=404)
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/sw.js")
async def sw():
    # service worker precisa ser servido da raiz pra controlar o app todo
    return FileResponse(WEB / "sw.js", media_type="text/javascript",
                        headers={"Cache-Control": "no-cache"})


def web_version():
    """Muda sempre que algum arquivo do app (web/) muda."""
    return format(int(max(f.stat().st_mtime for f in WEB.rglob("*") if f.is_file()) * 1000) % 0xFFFFFFF, "x")


@app.get("/")
async def index():
    # CSS/JS com a versão no endereço: o tablet nunca fica preso numa versão velha do cache
    v = web_version()
    html = (WEB / "index.html").read_text(encoding="utf-8")
    html = html.replace('href="/styles.css"', f'href="/styles.css?v={v}"').replace('src="/app.js"', f'src="/app.js?v={v}"')
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


@app.middleware("http")
async def revalidate(req, call_next):
    res = await call_next(req)
    if not req.url.path.startswith(("/art/", "/icon/", "/padimg/")):
        res.headers.setdefault("Cache-Control", "no-cache")
    return res


app.mount("/", StaticFiles(directory=WEB), name="web")

# ---------------- configuração (HTTP) ----------------
setup = FastAPI()


@setup.get("/")
async def setup_page():
    html = (WEB / "setup.html").read_text(encoding="utf-8")
    ip = (lan_ips() or ["127.0.0.1"])[0]
    return HTMLResponse(html.replace("{{APP_URL}}", f"https://{ip}:{HTTPS_PORT}/"))


@setup.get("/mesa-ca.crt")
async def ca():
    return FileResponse(CERT_DIR / "ca.cer", media_type="application/x-x509-ca-cert",
                        filename="mesa-ca.crt")


@setup.post("/yt")
async def yt_state(req: Request):
    """Estado do YouTube mandado pela extensão do navegador. Só aceita do próprio notebook."""
    if req.client is None or req.client.host not in ("127.0.0.1", "::1"):
        return Response(status_code=403)
    msg = await req.json()
    video.update(msg)
    if msg.get("kind") == "queue":
        await broadcast({"t": "ytq", "d": video.queue()})
    else:
        await broadcast({"t": "video", "d": video.snapshot()})
    return Response(status_code=204)


@setup.post("/tabs")
async def tabs_state(req: Request):
    """Abas com som e o volume de cada uma (da extensão). Só aceita do próprio notebook."""
    if not local_only(req):
        return Response(status_code=403)
    tabs.update(await req.json())
    await broadcast({"t": "tabs", "d": tabs.snapshot()})
    return Response(status_code=204)


@setup.websocket("/ext")
async def ext_ws(ws: WebSocket):
    """Canal de volta pra extensão do navegador (só do próprio notebook)."""
    if ws.client is None or ws.client.host not in ("127.0.0.1", "::1"):
        await ws.close()
        return
    await ws.accept()
    ext_clients.add(ws)
    try:
        while True:
            text = await ws.receive_text()  # "ping" ou {"lvl": {aba: pico}} (medidor das abas)
            if text.startswith("{"):
                try:
                    lvl = json.loads(text).get("lvl") or {}
                    d = {f"tab:{int(k)}": min(1.0, max(0.0, float(v))) for k, v in lvl.items()}
                except (ValueError, TypeError, AttributeError):
                    continue
                if d and clients:
                    await broadcast({"t": "lvl", "d": d})
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        ext_clients.discard(ws)


def local_only(req: Request):
    return req.client is not None and req.client.host in ("127.0.0.1", "::1")


@setup.get("/spotify/login")
async def spotify_login(req: Request):
    if not local_only(req):
        return HTMLResponse("Abra este endereço no próprio notebook: http://127.0.0.1:8080/spotify/login", 403)
    try:
        return RedirectResponse(spotify.login_url())
    except SpotifyError as e:
        return HTMLResponse(f"<p style='font:16px sans-serif'>{e}</p>", 400)


@setup.get("/spotify/callback")
async def spotify_callback(req: Request, code: str = "", error: str = ""):
    if not local_only(req):
        return Response(status_code=403)
    if error or not code:
        return HTMLResponse(f"<p style='font:16px sans-serif'>Spotify não autorizou ({error}).</p>", 400)
    try:
        await asyncio.to_thread(spotify.finish_login, code)
    except SpotifyError as e:
        return HTMLResponse(f"<p style='font:16px sans-serif'>{e}</p>", 400)
    return HTMLResponse("<p style='font:18px sans-serif;padding:40px'>Spotify conectado na Mesa. Pode fechar esta aba.</p>")


setup.mount("/", StaticFiles(directory=WEB), name="web")


def already_running():
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", HTTPS_PORT)) == 0


async def main():
    if already_running():
        print(f"  A Mesa já está rodando (porta {HTTPS_PORT} ocupada).")
        return
    # tablet que some da rede (tela apagou, Wi-Fi caiu) gera esse erro no Windows: não é problema
    def quiet(lp, ctx):
        if not isinstance(ctx.get("exception"), (ConnectionResetError, ConnectionAbortedError)):
            lp.default_exception_handler(ctx)
    asyncio.get_running_loop().set_exception_handler(quiet)
    crt, key = ensure_certs()
    https = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=HTTPS_PORT,
                                          ssl_certfile=crt, ssl_keyfile=key,
                                          log_level="warning", ws_ping_interval=10))
    http = uvicorn.Server(uvicorn.Config(setup, host="0.0.0.0", port=HTTP_PORT, log_level="warning"))
    http.install_signal_handlers = lambda: None
    print(f"\n  Mesa rodando em {socket.gethostname()}")
    for ip in lan_ips():
        print(f"    app:          https://{ip}:{HTTPS_PORT}/")
        print(f"    configurar:   http://{ip}:{HTTP_PORT}/")
    print("  Ctrl+C pra parar.\n")
    await asyncio.gather(https.serve(), http.serve())


if __name__ == "__main__":
    asyncio.run(main())

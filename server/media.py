"""O que está tocando no Windows (Spotify, YouTube no navegador, etc.).

Usa o mesmo painel de mídia do Windows (GlobalSystemMediaTransportControls),
então qualquer app que aparece no controle de mídia do Windows aparece aqui.
"""
import asyncio
import hashlib
import time

from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as Manager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
)
from winrt.windows.storage.streams import Buffer, InputStreamOptions

TICKS = 10_000_000  # TimeSpan do WinRT vem em unidades de 100 ns

SOURCE_NAMES = {
    "spotify": "Spotify",
    "chrome": "Chrome",
    "msedge": "Edge",
    "firefox": "Firefox",
    "opera": "Opera",
    "brave": "Brave",
    "vlc": "VLC",
    "zunemusic": "Media Player",
}


def source_name(app_id: str) -> str:
    low = (app_id or "").lower()
    for k, v in SOURCE_NAMES.items():
        if k in low:
            return v
    return app_id.split("!")[0].split(".")[-1] if app_id else ""


def seconds(ts) -> float:
    # o winrt do Python devolve datetime.timedelta
    return ts.total_seconds() if hasattr(ts, "total_seconds") else ts / TICKS


class Media:
    def __init__(self, on_change):
        self.on_change = on_change
        self.state = {"active": False}
        self.art = {}          # hash -> (bytes, content-type)
        self._art_key = None   # (título, artista) da última capa lida
        self._art_id = None
        self._sent_at = 0.0
        self.manager = None

    async def run(self):
        self.manager = await Manager.request_async()
        while True:
            try:
                await self._poll()
            except Exception as e:
                print("[media]", repr(e))
            await asyncio.sleep(0.5)

    def snapshot(self):
        """Estado com a posição corrigida pro agora (pra quem acabou de conectar)."""
        st = dict(self.state)
        if st.get("active") and st["playing"]:
            st["position"] = round(st["position"] + time.monotonic() - self._sent_at, 1)
        return st

    def _session(self):
        return self.manager.get_current_session() if self.manager else None

    async def _poll(self):
        s = self._session()
        if s is None:
            new = {"active": False}
        else:
            props = await s.try_get_media_properties_async()
            info = s.get_playback_info()
            tl = s.get_timeline_properties()
            key = (props.title, props.artist)
            if key != self._art_key:
                self._art_key = key
                self._art_id = await self._read_art(props.thumbnail)
            pos = seconds(tl.position)
            # a posição só atualiza quando o app avisa; corrige pelo tempo decorrido
            if info.playback_status == Status.PLAYING:
                updated = tl.last_updated_time.timestamp()
                pos += max(0.0, time.time() - updated)
            dur = seconds(tl.end_time) - seconds(tl.start_time)
            ctrl = info.controls
            new = {
                "active": True,
                "title": props.title or "",
                "artist": props.artist or props.album_artist or "",
                "album": props.album_title or "",
                "source": source_name(s.source_app_user_model_id),
                "playing": info.playback_status == Status.PLAYING,
                "position": round(min(pos, dur) if dur > 0 else pos, 1),
                "duration": round(dur, 1) if dur > 0 else 0,
                "art": f"/art/{self._art_id}" if self._art_id else None,
                "can": {
                    "prev": ctrl.is_previous_enabled,
                    "next": ctrl.is_next_enabled,
                    "seek": ctrl.is_playback_position_enabled,
                },
            }
        # posição muda o tempo todo; o cliente interpola, então só reenvia se o resto
        # mudou ou se a posição pulou (seek, propaganda) mais de 2 s do esperado
        old, now = self.state, time.monotonic()
        if new == old:
            return
        if old.get("active") and new.get("active"):
            expected = old["position"] + (now - self._sent_at if old["playing"] else 0)
            rest = lambda d: {k: v for k, v in d.items() if k != "position"}
            if rest(new) == rest(old) and abs(new["position"] - expected) < 2:
                return
        self._sent_at = now
        self.state = new
        self.on_change(new)

    async def _read_art(self, ref):
        if ref is None:
            return None
        try:
            stream = await ref.open_read_async()
            size = stream.size
            if not size:
                return None
            buf = Buffer(size)
            await stream.read_async(buf, size, InputStreamOptions.READ_AHEAD)
            data = bytes(buf)
            ctype = stream.content_type or "image/png"
        except Exception as e:
            print("[media] capa:", repr(e))
            return None
        h = hashlib.sha1(data).hexdigest()[:12]
        self.art = {h: (data, ctype)}  # guarda só a atual
        return h

    async def command(self, action, value=None):
        s = self._session()
        if s is None:
            return
        if action == "toggle":
            await s.try_toggle_play_pause_async()
        elif action == "next":
            await s.try_skip_next_async()
        elif action == "prev":
            await s.try_skip_previous_async()
        elif action == "seek" and value is not None:
            await s.try_change_playback_position_async(int(float(value) * TICKS))
        await asyncio.sleep(0.15)
        await self._poll()

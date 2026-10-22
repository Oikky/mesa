"""Spotify: fila e playlist do que está tocando, e tocar uma faixa escolhida no tablet.

Usa a Web API oficial com login PKCE (não precisa de senha do app, só do client_id).
Configurar uma vez: criar um app em developer.spotify.com, pôr o redirect
http://127.0.0.1:8080/spotify/callback, colar o client_id em config/secrets.json e abrir
http://127.0.0.1:8080/spotify/login no notebook.
"""
import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

import secrets_store

REDIRECT = "http://127.0.0.1:8080/spotify/callback"
SCOPES = ("user-read-playback-state user-modify-playback-state user-read-currently-playing "
          "playlist-read-private playlist-read-collaborative")
API = "https://api.spotify.com/v1"


class SpotifyError(Exception):
    pass


class Spotify:
    def __init__(self):
        self._verifier = None
        self._token = None
        self._token_until = 0.0
        self._playlist_cache = {}  # id -> (quando, dados)

    # ---------------------------------------------------------------- login
    def status(self):
        cfg = secrets_store.get("spotify")
        if not cfg.get("client_id"):
            return "setup"
        if not cfg.get("refresh_token"):
            return "login"
        return "ok"

    def login_url(self):
        cid = secrets_store.get("spotify").get("client_id")
        if not cid:
            raise SpotifyError("falta o client_id em config/secrets.json")
        self._verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self._verifier.encode()).digest()).rstrip(b"=").decode()
        q = urllib.parse.urlencode({
            "client_id": cid, "response_type": "code", "redirect_uri": REDIRECT, "scope": SCOPES,
            "code_challenge_method": "S256", "code_challenge": challenge,
        })
        return f"https://accounts.spotify.com/authorize?{q}"

    def finish_login(self, code):
        cid = secrets_store.get("spotify").get("client_id")
        data = self._token_request({
            "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
            "client_id": cid, "code_verifier": self._verifier or "",
        })
        secrets_store.update("spotify", refresh_token=data["refresh_token"])

    def _token_request(self, form):
        req = urllib.request.Request("https://accounts.spotify.com/api/token",
                                     urllib.parse.urlencode(form).encode(),
                                     {"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise SpotifyError(f"login recusado ({e.code})") from e
        self._token = data["access_token"]
        self._token_until = time.time() + data.get("expires_in", 3600) - 60
        return data

    def _access(self):
        if self._token and time.time() < self._token_until:
            return self._token
        cfg = secrets_store.get("spotify")
        if not cfg.get("refresh_token"):
            raise SpotifyError("Spotify não conectado")
        data = self._token_request({"grant_type": "refresh_token", "refresh_token": cfg["refresh_token"],
                                    "client_id": cfg["client_id"]})
        if data.get("refresh_token"):
            secrets_store.update("spotify", refresh_token=data["refresh_token"])
        return self._token

    def _api(self, method, path, body=None):
        req = urllib.request.Request(API + path, json.dumps(body).encode() if body is not None else None,
                                     {"Authorization": f"Bearer {self._access()}",
                                      "Content-Type": "application/json"}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code == 401:
                self._token = None
            if e.code == 403:
                # 403 tem motivos diferentes: o Spotify diz qual no corpo da resposta
                try:
                    err = json.loads(e.read() or b"{}").get("error") or {}
                except ValueError:
                    err = {}
                why = f"{err.get('message', '')} {err.get('reason', '')}".lower()
                if "premium" in why:
                    raise SpotifyError("o Spotify só deixa controlar (tocar faixa) com conta Premium") from e
                if "regist" in why or "dashboard" in why or "developer" in why:
                    raise SpotifyError("essa conta do Spotify não está liberada no app: em developer.spotify.com › "
                                       "seu app › User Management, adicione o e-mail da conta (ou crie o app com "
                                       "a própria conta e use o Client ID dele)") from e
                raise SpotifyError(f"o Spotify recusou ({err.get('message') or 403})") from e
            if e.code == 404 and method != "GET":
                raise SpotifyError("abra o Spotify no notebook primeiro") from e
            if e.code == 404:
                return None
            raise SpotifyError(f"Spotify respondeu {e.code}") from e

    # ---------------------------------------------------------------- dados pro painel
    @staticmethod
    def _track(t):
        if not t:
            return None
        imgs = (t.get("album") or {}).get("images") or t.get("images") or []
        return {
            "uri": t.get("uri"),
            "title": t.get("name") or "",
            "sub": ", ".join(a.get("name", "") for a in t.get("artists") or []) or (t.get("show") or {}).get("name", ""),
            "img": imgs[-1]["url"] if imgs else None,
            "dur": round((t.get("duration_ms") or 0) / 1000),
        }

    def _playlist(self, pid):
        hit = self._playlist_cache.get(pid)
        if hit and time.time() - hit[0] < 120:
            return hit[1]
        meta = self._api("GET", f"/playlists/{pid}?fields=name,tracks.total")
        if not meta:
            return None  # playlists feitas pelo Spotify (Daily Mix etc.) não abrem pra apps novos
        items = self._api("GET", f"/playlists/{pid}/tracks?limit=100&fields=items(track(uri,name,duration_ms,artists(name),album(images)))") or {}
        data = {"name": meta.get("name") or "Playlist",
                "total": (meta.get("tracks") or {}).get("total") or 0,
                "items": [self._track(i.get("track")) for i in items.get("items") or [] if i.get("track")]}
        self._playlist_cache[pid] = (time.time(), data)
        return data

    def panel(self):
        st = self.status()
        if st != "ok":
            return {"status": st}
        player = self._api("GET", "/me/player") or {}
        q = self._api("GET", "/me/player/queue") or {}
        now = self._track(q.get("currently_playing"))
        ctx = player.get("context") or {}
        out = {"status": "ok", "now": now, "playing": bool(player.get("is_playing")),
               "queue": [self._track(t) for t in (q.get("queue") or [])[:20]],
               "context": None}
        if ctx.get("type") == "playlist":
            pl = self._playlist(ctx["uri"].split(":")[-1])
            if pl:
                out["context"] = {"uri": ctx["uri"], "kind": "playlist", **pl}
        elif ctx.get("type") == "album":
            alb = self._api("GET", f"/albums/{ctx['uri'].split(':')[-1]}") or {}
            imgs = alb.get("images") or []
            out["context"] = {"uri": ctx["uri"], "kind": "album", "name": alb.get("name", "Álbum"),
                              "items": [{**self._track(t), "img": imgs[-1]["url"] if imgs else None}
                                        for t in (alb.get("tracks") or {}).get("items") or []]}
        return out

    def now_playing(self):
        """Se a conta está tocando algo agora, em qualquer aparelho (app, Spotify Web, celular)."""
        if self.status() != "ok":
            return None
        cur = self._api("GET", "/me/player/currently-playing") or {}
        item = cur.get("item") or {}
        return {"playing": bool(cur.get("is_playing")), "title": item.get("name") or ""}

    def play(self, uri, context=None):
        body = {"context_uri": context, "offset": {"uri": uri}} if context else {"uris": [uri]}
        self._api("PUT", "/me/player/play", body)

"""Chaves das integrações (Spotify, Discord) em config/secrets.json.

Fica fora do resto da config de propósito: é o único arquivo que não dá pra compartilhar.
"""
import json
import threading
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "config" / "secrets.json"
TEMPLATE = {
    "spotify": {"client_id": ""},
    "discord": {"client_id": "", "client_secret": ""},
}
_lock = threading.Lock()


def load():
    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        save(TEMPLATE)
        return json.loads(json.dumps(TEMPLATE))
    except Exception as e:
        print("[secrets] secrets.json inválido:", repr(e))
        return {}


def save(data):
    with _lock:
        PATH.parent.mkdir(exist_ok=True)
        tmp = PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(PATH)


ENV = PATH.parent.parent / ".env"


def env():
    """Chaves do .env (MESA_SPOTIFY_CLIENT_ID etc.). Valem por cima do secrets.json."""
    out = {}
    try:
        for line in ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"')
    except FileNotFoundError:
        pass
    return out


def get(service):
    entry = dict(load().get(service) or {})
    e = env()
    for key in ("client_id", "client_secret"):
        v = e.get(f"MESA_{service.upper()}_{key.upper()}")
        if v:
            entry[key] = v
    return entry


def update(service, **values):
    data = load()
    entry = dict(data.get(service) or {})
    entry.update(values)
    data[service] = entry
    save(data)

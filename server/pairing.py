"""Pareamento do tablet (opcional): código secreto em config/pair.txt, fora do git.

Desligado por padrão. Liga pela página de setup no próprio notebook, que passa a mostrar o código;
o tablet digita uma vez e guarda num cookie. Ligado, sem o cookie o /ws e as imagens recusam.
"""
import hmac
import secrets
from pathlib import Path
from urllib.parse import urlsplit

PATH = Path(__file__).resolve().parent.parent / "config" / "pair.txt"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O e 1/I, que confundem
COOKIE = "mesa_pair"
MAX_AGE = 400 * 86400  # teto do Chrome; renovado toda vez que o app abre


def enabled():
    return PATH.is_file()


def disable():
    PATH.unlink(missing_ok=True)


def code():
    """Código atual; cria um (e liga o pareamento) se ainda não existir."""
    try:
        c = PATH.read_text(encoding="utf-8").strip()
        if c:
            return c
    except FileNotFoundError:
        pass
    c = "".join(secrets.choice(ALPHABET) for _ in range(8))  # 40 bits; o /pair aceita 1 erro por segundo
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(c, encoding="utf-8")
    return c


def pretty():
    c = code()
    return f"{c[:4]}-{c[4:]}"


def ok(text):
    if not enabled():
        return False
    t = "".join(ch for ch in str(text or "").upper() if ch.isalnum())
    return bool(t) and hmac.compare_digest(t.encode(), code().encode())


def same_origin(origin, *hosts):
    """Página da própria Mesa: o Origin tem o mesmo host:porta que o navegador pediu."""
    netloc = urlsplit(origin or "").netloc
    return bool(netloc) and netloc in {h for h in hosts if h}


def from_extension(origin):
    """Endpoints só do notebook: aceita a extensão (ou programa local sem Origin), nunca um site."""
    return not origin or not origin.startswith(("http:", "https:", "null"))

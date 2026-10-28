"""Pareamento do tablet: código secreto gerado na primeira vez (config/pair.txt, fora do git).

A página de setup mostra o código só no próprio notebook; o tablet digita uma vez e guarda num
cookie. Sem o cookie, o /ws e as rotas que leem arquivos do notebook recusam.
"""
import hmac
import secrets
from pathlib import Path
from urllib.parse import urlsplit

PATH = Path(__file__).resolve().parent.parent / "config" / "pair.txt"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O e 1/I, que confundem
COOKIE = "mesa_pair"
MAX_AGE = 400 * 86400  # teto do Chrome; renovado toda vez que o app abre


def code():
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
    t = "".join(ch for ch in str(text or "").upper() if ch.isalnum())
    return bool(t) and hmac.compare_digest(t.encode(), code().encode())


def same_origin(origin, *hosts):
    """Página da própria Mesa: o Origin tem o mesmo host:porta que o navegador pediu."""
    netloc = urlsplit(origin or "").netloc
    return bool(netloc) and netloc in {h for h in hosts if h}


def from_extension(origin):
    """Endpoints só do notebook: aceita a extensão (ou programa local sem Origin), nunca um site."""
    return not origin or not origin.startswith(("http:", "https:", "null"))

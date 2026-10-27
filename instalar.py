"""Instalador da Mesa (roda pelo Instalar.bat).

Faz tudo que precisa num PC novo: ambiente Python (.venv), dependências, chaves do Spotify e do
Discord (.env), ligar com o Windows e já abrir. Pode rodar de novo quando quiser: o que já está
preenchido fica (Enter mantém).

  instalar.py            instalação completa
  instalar.py --chaves     só trocar as chaves do Spotify/Discord
  instalar.py --tailscale  só (re)configurar o acesso pelo Tailscale
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PY = VENV / "Scripts" / "python.exe"
PYW = VENV / "Scripts" / "pythonw.exe"
ENV = ROOT / ".env"
TS_PORT = 10443  # porta do Tailscale que aponta pra Mesa (https://<pc>.<tailnet>.ts.net:10443)

os.system("")  # liga as cores ANSI no console do Windows
B, D, G, Y, R, X = "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"


def title(t):
    print(f"\n{B}── {t} {'─' * max(0, 60 - len(t))}{X}")


def ok(t):
    print(f"  {G}✓{X} {t}")


def warn(t):
    print(f"  {Y}!{X} {t}")


def ask(q, default=""):
    shown = f" {D}[{default}]{X}" if default else ""
    try:
        v = input(f"  {q}{shown}: ").strip()
    except EOFError:
        v = ""
    return v or default


def yes(q, default=True):
    v = ask(f"{q} ({'S/n' if default else 's/N'})").lower()
    return default if not v else v.startswith("s") or v.startswith("y")


def mask(v):
    return f"{v[:4]}…{v[-3:]}" if len(v) > 10 else ("•" * len(v) if v else "")


# ------------------------------------------------------------------ .env
def read_env():
    out = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"')
    return out


def write_env(vals):
    lines = ["# Chaves das integrações da Mesa (não compartilhar, não vai pro git).",
             "# Pra trocar: Instalar.bat --chaves (ou editar aqui e reiniciar a Mesa)."]
    lines += [f"{k}={v}" for k, v in vals.items() if v]
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ask_key(env, key, label):
    cur = env.get(key, "")
    v = ask(label + (f" {D}(Enter mantém {mask(cur)}){X}" if cur else f" {D}(Enter pula){X}"))
    if v:
        env[key] = v


def keys():
    env = read_env()
    title("Spotify (opcional: fila e playlist no painel)")
    print(f"""  1. Entre em {B}https://developer.spotify.com/dashboard{X} › Create app (nome qualquer).
  2. Redirect URI: {B}http://127.0.0.1:8070/spotify/callback{X} · marque {B}Web API{X} · Save.
  3. Em Settings, copie o {B}Client ID{X}.
  {D}Depois, no tablet: painel do Spotify › "Autorizar no notebook". Controlar o Spotify exige Premium.{X}""")
    ask_key(env, "MESA_SPOTIFY_CLIENT_ID", "Client ID do Spotify")

    title("Discord (opcional: call, quem fala, volume de cada um, mic)")
    print(f"""  1. Entre em {B}https://discord.com/developers/applications{X} › New Application (ex.: Mesa).
  2. Em {B}OAuth2{X}: copie o {B}Client ID{X}, clique {B}Reset Secret{X} e copie o {B}Client Secret{X}.
  3. Ainda em OAuth2 › Redirects: adicione {B}http://127.0.0.1{X} e salve.
  {D}Depois, no tablet: painel do Discord › "Conectar" e aprove a janela no Discord do PC.{X}""")
    ask_key(env, "MESA_DISCORD_CLIENT_ID", "Client ID do Discord")
    ask_key(env, "MESA_DISCORD_CLIENT_SECRET", "Client Secret do Discord")
    write_env(env)
    ok(f"chaves salvas em {ENV.name}")


# ------------------------------------------------------------------ passos
def check_system():
    title("Conferindo o PC")
    if os.name != "nt":
        print(f"  {R}A Mesa só roda no Windows (usa o mixer de som do Windows).{X}")
        sys.exit(1)
    if sys.version_info < (3, 11):
        print(f"  {R}Precisa do Python 3.11 ou mais novo (este é {sys.version.split()[0]}).{X}")
        print("  Baixe em https://www.python.org/downloads/ e marque “Add python.exe to PATH”.")
        sys.exit(1)
    ok(f"Windows + Python {sys.version.split()[0]}")


def install_deps():
    title("Instalando (pode levar uns minutos na primeira vez)")
    if not PY.exists():
        venv.create(VENV, with_pip=True)
        ok("ambiente .venv criado")
    r = subprocess.run([str(PY), "-m", "pip", "install", "-q", "--disable-pip-version-check",
                        "-r", str(ROOT / "requirements.txt")])
    if r.returncode:
        print(f"  {R}Deu erro instalando as dependências (veja acima).{X}")
        sys.exit(1)
    ok("dependências instaladas")


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "IP-DO-PC"


def startup():
    title("Ligar sozinha")
    if yes("Ligar a Mesa sozinha quando o Windows iniciar?"):
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "Iniciar com o Windows.ps1")])


def start_now():
    subprocess.run(["cmd", "/c", str(ROOT / "Parar Mesa.bat")], stdout=subprocess.DEVNULL)
    subprocess.Popen([str(PYW), str(ROOT / "server" / "app.py")], cwd=ROOT,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    ok("Mesa ligada (sem janela; log em logs\\mesa.log)")


# ------------------------------------------------------------------ Tailscale
def ts_exe():
    exe = shutil.which("tailscale")
    if exe:
        return exe
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", "")):
        p = Path(base) / "Tailscale" / "tailscale.exe"
        if base and p.exists():
            return str(p)
    return None


def ts_json(exe, *args):
    r = subprocess.run([exe, *args, "--json"], capture_output=True, text=True, encoding="utf-8")
    try:
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}
    except ValueError:
        return {}


def tailscale():
    """Publica a Mesa só pros aparelhos da sua rede Tailscale, com HTTPS de verdade (sem certificado
    pra instalar no tablet): https://<este-pc>.<sua-tailnet>.ts.net:10443"""
    title("Tailscale (acesso de qualquer lugar, só pros seus aparelhos)")
    exe = ts_exe()
    if not exe:
        warn("Tailscale não está instalado neste PC.")
        print(f"  Instale em {B}https://tailscale.com/download/windows{X}, entre na sua conta e rode {B}Instalar.bat --tailscale{X}.")
        return None
    while True:
        st = ts_json(exe, "status")
        if st.get("BackendState") != "Running":
            warn("O Tailscale não está conectado. Abra o Tailscale (ícone perto do relógio) e entre na sua conta.")
        elif not st.get("CertDomains"):
            warn("Falta ligar o HTTPS na sua rede Tailscale (uma vez só).")
            print(f"  Abra {B}https://login.tailscale.com/admin/dns{X}: ligue {B}MagicDNS{X} e, embaixo, {B}Enable HTTPS{X}.")
        else:
            break
        if not yes("Já fez? Tentar de novo", True):
            print(f"  Sem problema: depois rode {B}Instalar.bat --tailscale{X}.")
            return None
    host = st["Self"]["DNSName"].rstrip(".")
    url = f"https://{host}:{TS_PORT}"
    # não passa por cima se a porta já serve outra coisa
    web = (ts_json(exe, "serve", "status").get("Web") or {}).get(f"{host}:{TS_PORT}") or {}
    proxy = ((web.get("Handlers") or {}).get("/") or {}).get("Proxy", "")
    if proxy and "localhost:8443" not in proxy and "127.0.0.1:8443" not in proxy:
        warn(f"A porta {TS_PORT} do Tailscale já aponta pra outra coisa ({proxy}); deixei como está.")
        return None
    if not proxy:
        r = subprocess.run([exe, "serve", "--bg", f"--https={TS_PORT}", "https+insecure://localhost:8443"],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode:
            warn("Não deu pra configurar o Tailscale:")
            for line in (r.stderr or r.stdout).strip().splitlines():
                print("  " + line)
            print(f"  Se pedir administrador, rode o Instalar.bat como administrador uma vez ({B}--tailscale{X}).")
            return None
    ok(f"Mesa no Tailscale: {B}{url}{X} (só aparelhos da sua rede)")
    return url


def finish(ts_url=None):
    ip = lan_ip()
    title("Pronto! Falta só no tablet e no navegador")
    if ts_url:
        print(f"""  {B}Tablet{X} (com o app do Tailscale instalado e logado na mesma conta):
    Abra {B}{ts_url}{X} no Chrome › menu › {B}Instalar app{X}. Funciona em qualquer rede.
""")
    else:
        print(f"""  {B}Tablet{X} (mesmo Wi-Fi do PC):
    1. Abra {B}http://{ip}:8070{X} e siga a página: instala o certificado da Mesa (uma vez).
    2. Depois abra {B}https://{ip}:8443{X} › menu do Chrome › {B}Instalar app{X}.
    {D}Se o Windows perguntar do firewall na primeira vez, permita em rede privada.{X}
""")
    print(f"""
  {B}Extensão do navegador{X} (vídeo do YouTube na tela + volume/saída por aba):
    edge://extensions (ou chrome://extensions) › ligue o {B}Modo de desenvolvedor{X} ›
    {B}Carregar sem pacote{X} › escolha a pasta {B}{ROOT / 'extension'}{X}

  {B}Atualizar{X}: dê dois cliques em {B}Atualizar.bat{X} (ou toque no aviso que aparece no tablet).
  {B}Trocar chaves{X}: {B}Instalar.bat --chaves{X}""")


def main():
    if "--tailscale" in sys.argv:
        url = tailscale()
        if url:
            finish(url)
        return
    if "--chaves" in sys.argv:
        keys()
        if PYW.exists() and yes("Reiniciar a Mesa pra usar as chaves novas?"):
            start_now()
        return
    print(f"\n{B}MESA{X}CONTROL · instalação\n{D}controle de som do PC pelo tablet{X}")
    check_system()
    install_deps()
    keys()
    ts_url = tailscale() if yes("Usar o Tailscale pra abrir no tablet? (recomendado)", True) else None
    startup()
    start_now()
    finish(ts_url)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Cancelado.")

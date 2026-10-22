"""Avisa o tablet quando tem versão nova no repositório (git) e atualiza a pedido.

De tempos em tempos faz `git fetch` e conta quantos commits o PC está atrás. O tablet mostra a tecla
de atualizar; tocar nela roda o Atualizar.bat (git pull, dependências, reinicia a Mesa).
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLAG = ROOT / "logs" / "extensao-mudou.txt"  # o Atualizar.bat cria quando a extensão mudou
NO_WINDOW = subprocess.CREATE_NO_WINDOW


def _git(*args, timeout=30):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                       creationflags=NO_WINDOW)
    return r.stdout.strip() if r.returncode == 0 else None


def behind():
    """Quantos commits novos tem no remoto (0 se não for repositório git, sem internet etc.)."""
    if not (ROOT / ".git").exists():
        return 0
    try:
        if _git("fetch", "--quiet") is None:
            return 0
        n = _git("rev-list", "--count", "HEAD..@{u}")
        return int(n) if n and n.isdigit() else 0
    except (OSError, subprocess.SubprocessError):
        return 0


def extension_changed():
    """True uma vez depois de uma atualização que mexeu na extensão (o aviso some depois)."""
    if FLAG.exists():
        FLAG.unlink(missing_ok=True)
        return True
    return False


def run_update():
    """Roda o Atualizar.bat solto (ele para e liga a Mesa de novo, então não pode ser filho dela)."""
    subprocess.Popen(["cmd", "/c", str(ROOT / "Atualizar.bat"), "--silencioso"], cwd=ROOT,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | NO_WINDOW)

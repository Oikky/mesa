"""Equalizador da saída pelo Equalizer APO (programa grátis que processa o som do Windows).

A Mesa escreve `mesa.txt` na pasta de configuração do APO e põe um `Include: mesa.txt` no
`config.txt` dele; o APO relê sozinho quando o arquivo muda. Sem o APO instalado, o painel do
tablet só explica como instalar. O ajuste fica salvo em `config/eq.json`.
"""
import json
import os
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAVE = ROOT / "config" / "eq.json"
FREQS = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
MAX_DB = 12.0
INCLUDE = "Include: mesa.txt"


def _apo_dir():
    """Pasta `config` do Equalizer APO (None se não estiver instalado)."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\EqualizerAPO") as k:
            path = Path(winreg.QueryValueEx(k, "ConfigPath")[0])
            if path.is_dir():
                return path
    except OSError:
        pass
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432")):
        if base and (Path(base) / "EqualizerAPO" / "config").is_dir():
            return Path(base) / "EqualizerAPO" / "config"
    return None


class Equalizer:
    def __init__(self):
        self.on = True
        self.bands = [0.0] * len(FREQS)
        self.error = None
        try:
            data = json.loads(SAVE.read_text(encoding="utf-8"))
            self.on = bool(data.get("on", True))
            bands = [float(x) for x in data.get("bands", [])]
            if len(bands) == len(FREQS):
                self.bands = [max(-MAX_DB, min(MAX_DB, b)) for b in bands]
        except (OSError, ValueError):
            pass

    def state(self):
        return {"available": _apo_dir() is not None, "on": self.on, "bands": self.bands,
                "freqs": FREQS, "max": MAX_DB, "error": self.error}

    def set(self, bands=None, on=None):
        if bands is not None and len(bands) == len(FREQS):
            self.bands = [round(max(-MAX_DB, min(MAX_DB, float(b))), 1) for b in bands]
        if on is not None:
            self.on = bool(on)
        try:
            SAVE.parent.mkdir(exist_ok=True)
            SAVE.write_text(json.dumps({"on": self.on, "bands": self.bands}), encoding="utf-8")
        except OSError:
            pass
        self._write()
        return self.state()

    def _write(self):
        cfg = _apo_dir()
        if not cfg:
            self.error = None
            return
        try:
            lines = ["# feito pela Mesa (tablet); é reescrito a cada ajuste"]
            if self.on and any(self.bands):
                # pré-ganho negativo do tamanho do maior reforço, pra não distorcer
                lines.append(f"Preamp: {-max(0.0, max(self.bands)):.1f} dB")
                lines.append("GraphicEQ: " + "; ".join(f"{f} {g:.1f}" for f, g in zip(FREQS, self.bands, strict=True)))
            (cfg / "mesa.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            main = cfg / "config.txt"
            text = main.read_text(encoding="utf-8", errors="replace") if main.exists() else ""
            if INCLUDE not in text:
                main.write_text(text.rstrip("\n") + ("\n" if text else "") + INCLUDE + "\n", encoding="utf-8")
            self.error = None
        except OSError as e:
            self.error = f"não deu pra escrever na pasta do Equalizer APO ({e.strerror or e})"

"""Testes das partes que não mexem no Windows de verdade (sem som, sem teclas, sem apps).

Cada teste aponta os arquivos de config pra uma pasta temporária: nunca toca no config/ real.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

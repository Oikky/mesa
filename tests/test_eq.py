import pytest

import eq


@pytest.fixture
def apo(tmp_path, monkeypatch):
    """Finge um Equalizer APO instalado numa pasta temporária."""
    cfg = tmp_path / "apo"
    cfg.mkdir()
    (cfg / "config.txt").write_text("Device: fones\n", encoding="utf-8")
    monkeypatch.setattr(eq, "SAVE", tmp_path / "eq.json")
    monkeypatch.setattr(eq, "_apo_dir", lambda: cfg)
    return cfg


def test_bandas_ficam_dentro_do_limite(apo):
    e = eq.Equalizer()
    st = e.set(bands=[99] + [0] * 9)
    assert st["bands"][0] == eq.MAX_DB


def test_numero_errado_de_bandas_e_ignorado(apo):
    e = eq.Equalizer()
    e.set(bands=[3] * 10)
    assert e.set(bands=[1, 2, 3])["bands"] == [3.0] * 10


def test_escreve_mesa_txt_e_inclui_uma_vez_so(apo):
    e = eq.Equalizer()
    e.set(bands=[6] + [0] * 9)
    e.set(bands=[4] + [0] * 9)
    mesa = (apo / "mesa.txt").read_text(encoding="utf-8")
    assert "Preamp: -4.0 dB" in mesa and "GraphicEQ: 31 4.0;" in mesa
    assert (apo / "config.txt").read_text(encoding="utf-8").count(eq.INCLUDE) == 1


def test_desligado_nao_aplica_nada(apo):
    e = eq.Equalizer()
    e.set(bands=[6] * 10, on=False)
    assert "GraphicEQ" not in (apo / "mesa.txt").read_text(encoding="utf-8")


def test_ajuste_salvo_volta_ao_reabrir(apo):
    eq.Equalizer().set(bands=[2] * 10, on=False)
    e = eq.Equalizer()
    assert e.bands == [2.0] * 10 and e.on is False

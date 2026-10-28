import pytest

import pairing


@pytest.fixture(autouse=True)
def cfg(tmp_path, monkeypatch):
    monkeypatch.setattr(pairing, "PATH", tmp_path / "pair.txt")


def test_codigo_nasce_uma_vez_e_fica():
    c = pairing.code()
    assert len(c) == 8 and set(c) <= set(pairing.ALPHABET)
    assert pairing.code() == c and pairing.PATH.read_text() == c


def test_aceita_com_traco_e_minusculo_e_recusa_o_resto():
    c = pairing.code()
    assert pairing.ok(pairing.pretty().lower())
    assert pairing.ok(c)
    for errado in ("", None, c[:-1], c + "A", "ÁÁÁÁÁÁÁÁ"):
        assert not pairing.ok(errado)


def test_origin_so_do_proprio_endereco():
    assert pairing.same_origin("https://mesa.ts.net:10443", "mesa.ts.net:10443")
    assert pairing.same_origin("https://mesa.ts.net:10443", "127.0.0.1:8443", "mesa.ts.net:10443")
    assert not pairing.same_origin("https://site.example", "mesa.ts.net:10443")
    assert not pairing.same_origin(None, "mesa.ts.net:10443")
    assert not pairing.same_origin("https://x", None)


def test_endpoints_do_notebook_recusam_sites():
    assert pairing.from_extension("chrome-extension://abc")
    assert pairing.from_extension(None)
    for site in ("https://site.example", "http://127.0.0.1:8070", "null"):
        assert not pairing.from_extension(site)


def test_desligado_por_padrao_e_desligar_apaga_o_codigo():
    assert not pairing.enabled() and not pairing.ok("QUALQUER")
    c = pairing.code()
    assert pairing.enabled() and pairing.ok(c)
    pairing.disable()
    assert not pairing.enabled() and not pairing.ok(c)

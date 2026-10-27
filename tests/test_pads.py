import pytest

import pads


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setattr(pads, "PATH", tmp_path / "pads.json")
    monkeypatch.setattr(pads, "IMAGES", tmp_path / "pad-images")
    return tmp_path


def test_primeira_vez_cria_os_pads_padrao(cfg):
    assert pads.load() == pads.DEFAULT
    assert (cfg / "pads.json").exists()


def test_config_quebrada_nao_derruba(cfg):
    (cfg / "pads.json").write_text("{nao é json", encoding="utf-8")
    assert pads.load() == []


def test_pad_novo_vai_pro_primeiro_lugar_livre(cfg):
    pads.save([{"id": "a", "slot": 0}, {"id": "b", "slot": 2}])
    out = pads.upsert({"id": "c"})
    assert {p["id"]: p["slot"] for p in out} == {"a": 0, "c": 1, "b": 2}


def test_mover_pra_lugar_ocupado_troca_os_dois(cfg):
    pads.save([{"id": "a", "slot": 0}, {"id": "b", "slot": 4}])
    out = pads.move(0, 4)
    assert {p["id"]: p["slot"] for p in out} == {"a": 4, "b": 0}


@pytest.mark.parametrize("src,dst", [(-1, 0), (0, pads.SLOTS), (3, 3)])
def test_mover_invalido_nao_muda_nada(cfg, src, dst):
    pads.save([{"id": "a", "slot": 3}])
    assert pads.move(src, dst) == [{"id": "a", "slot": 3}]


def test_remover_apaga_imagem_que_ninguem_usa(cfg):
    img = cfg / "pad-images"
    img.mkdir()
    (img / "usada.jpg").write_bytes(b"x")
    (img / "solta.jpg").write_bytes(b"x")
    pads.save([{"id": "a", "slot": 0, "bg": "/padimg/usada.jpg"}, {"id": "b", "slot": 1, "bg": "/padimg/solta.jpg"}])
    pads.remove("b")
    assert sorted(f.name for f in img.iterdir()) == ["usada.jpg"]


def test_nomes_de_tecla():
    assert pads.vk_of("Ctrl") == 0x11
    assert pads.vk_of("m") == ord("M")
    assert pads.vk_of("f12") == 0x7B
    with pytest.raises(ValueError):
        pads.vk_of("tecla-que-nao-existe")

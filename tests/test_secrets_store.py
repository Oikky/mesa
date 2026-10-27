import pytest

import secrets_store as s


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "PATH", tmp_path / "config" / "secrets.json")
    monkeypatch.setattr(s, "ENV", tmp_path / ".env")
    return tmp_path


def test_primeira_vez_cria_o_modelo_vazio(cfg):
    assert s.load() == s.TEMPLATE
    assert (cfg / "config" / "secrets.json").exists()


def test_env_vale_por_cima_do_secrets(cfg):
    s.update("spotify", client_id="do-json", token="t")
    (cfg / ".env").write_text('# comentário\nMESA_SPOTIFY_CLIENT_ID="do-env"\nLIXO\n', encoding="utf-8")
    assert s.get("spotify") == {"client_id": "do-env", "token": "t"}


def test_env_vazio_nao_apaga_o_do_json(cfg):
    s.update("discord", client_id="x")
    (cfg / ".env").write_text("MESA_DISCORD_CLIENT_ID=\n", encoding="utf-8")
    assert s.get("discord")["client_id"] == "x"

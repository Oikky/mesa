import video


def test_prefere_a_aba_que_esta_tocando():
    v = video.Video()
    v.update({"tab": 1, "id": "parado", "playing": False})
    v.update({"tab": 2, "id": "tocando", "playing": True})
    v.update({"tab": 3, "id": "outro-parado", "playing": False})
    assert v.snapshot()["id"] == "tocando"


def test_aba_que_saiu_some_com_a_fila():
    v = video.Video()
    v.update({"tab": 1, "id": "abc", "playing": True})
    v.update({"tab": 1, "kind": "queue", "list": {"items": [{"id": "x"}]}})
    v.update({"tab": 1, "gone": True})
    assert v.snapshot() is None and v.queue() is None


def test_fila_corta_itens_sem_id_e_tipo_estranho():
    v = video.Video()
    v.update({"tab": 1, "id": "abc", "playing": True})
    v.update({"tab": 1, "kind": "queue", "list": {"kind": "hack", "items": [{"id": ""}, {"id": "ok"}]}})
    q = v.queue()
    assert q["kind"] == "next" and [i["id"] for i in q["items"]] == ["ok"]


def test_aba_sem_noticia_expira(monkeypatch):
    v = video.Video()
    v.update({"tab": 1, "id": "abc"})
    agora = video.time.monotonic()
    monkeypatch.setattr(video.time, "monotonic", lambda: agora + video.STALE + 1)
    assert v.prune() is True and v.snapshot() is None

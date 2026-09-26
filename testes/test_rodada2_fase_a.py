"""
Rodada 2, Fase A: preços decididos pelo Nicolas, Índice no card, e o combo
"casal + 2 mapas" também na versão ocidental (página e webhook).
"""
import json
import urllib.parse

import pytest

from test_app import _postar_webhook, app_mod, cliente

import acesso  # noqa: E402
import cakto  # noqa: E402
import ofertas  # noqa: E402
import textos  # noqa: E402


def test_precos_da_versao_ocidental():
    assert ofertas.preco("mapa", "ocidental") == "37"
    assert ofertas.preco("compat", "ocidental") == "127"
    assert ofertas.oferta("compat", "ocidental")["preco_cupom"] == 97
    assert ofertas.preco("bump_mapas_casal", "ocidental") == "167"
    assert ofertas.preco("numerologia", "ocidental") == "27"
    assert ofertas.preco("tarot", "ocidental") == "19"


def test_precos_da_vedica_nao_mudaram():
    assert ofertas.preco("mapa") == "47" and ofertas.preco("compat") == "127"


def test_card_mostra_indice_com_rotulo_de_metodo_proprio():
    assert textos.da_pagina("compatibilidade", "ocidental")["card"]["mostra_indice"] is True


@pytest.fixture
def ocidental_com_bump(monkeypatch):
    novas = json.loads(json.dumps(ofertas.POR_SISTEMA["ocidental"]))
    novas["compat"].update(checkout="https://pay.cakto.com.br/occasa1_1", codigo="occasa1")
    novas["bump_mapas_casal"].update(checkout="https://pay.cakto.com.br/ocbump1_2", codigo="ocbump1")
    monkeypatch.setitem(ofertas.POR_SISTEMA, "ocidental", novas)
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    app_mod._paginas_prontas.clear()
    yield novas
    app_mod._paginas_prontas.clear()


def test_combo_na_pagina_anuncia_a_diferenca_do_preco_de_tabela(ocidental_com_bump):
    html = cliente.get("/compatibilidade").text
    assert 'const PRECO_BUMP_MAPAS = "R$40";' in html  # 167 − 127
    assert 'const PRECO = "127";' in html and 'const PRECO_CUPOM = "97";' in html
    assert "ÍNDICE PADMINI · MÉTODO PRÓPRIO" in html and "const CARD_MOSTRA_INDICE = true;" in html


def test_sem_checkout_do_bump_a_linha_do_combo_some(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    app_mod._paginas_prontas.clear()
    assert 'const PRECO_BUMP_MAPAS = "";' in cliente.get("/compatibilidade").text
    app_mod._paginas_prontas.clear()


SCK = "c~1990-05-15~~-23.5505~-46.6333~Ana~SP~1992-03-10~08:00~-22.9068~-43.1729~Bruno~RJ"


def _bump(oferta, pid):
    return {"event": "purchase_approved", "secret": "segredo-de-teste-webhook",
            "data": {"id": pid, "status": "paid", "offer_type": "orderbump", "sck": SCK,
                     "offer": {"id": oferta}, "customer": {"email": "c@teste.com", "name": "Ana"}}}


def test_bump_ocidental_entrega_dois_mapas_natais(ocidental_com_bump):
    assert cakto.versao_do_bump_mapas(_bump("ocbump1", "x")) == "ocidental"
    c = _postar_webhook(_bump("ocbump1", "bump-oc-1")).json()
    assert c["produto"] == "ocidental:mapas_casal" and len(c["links"]) == 2
    for link in c["links"]:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(link).query, keep_blank_values=True)
        assert q["token"][0].startswith("oc-")
        chave = acesso.chave_mapa(q["data"][0], q["hora"][0], q["lat"][0], q["lon"][0])
        assert acesso.completo_liberado("mapa", chave, q["token"][0], "ocidental")


def test_bump_desconhecido_nao_entrega_nada(ocidental_com_bump):
    assert cakto.versao_do_bump_mapas(_bump("outrobump", "y")) == ""
    c = _postar_webhook(_bump("outrobump", "bump-x")).json()
    assert "ignorado" in c

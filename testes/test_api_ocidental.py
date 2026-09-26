"""
API e páginas da versão ocidental (Fase 1): /api/ocidental/mapa, /api/ocidental/pdf,
o /live ocidental e a entrega pelo webhook (inclusive sem hora de nascimento).
"""
import json

import pytest

from test_app import PESSOA, _postar_webhook, app_mod, cliente

import acesso  # noqa: E402
import entrega  # noqa: E402
import ofertas  # noqa: E402

SEM_HORA = {**PESSOA, "hora": ""}


def _token(p, versao="ocidental"):
    return acesso.emitir_token("mapa", acesso.chave_mapa(p["data"], p["hora"], p["lat"], p["lon"]), versao)


@pytest.fixture
def versao(monkeypatch):
    def ligar(valor):
        monkeypatch.setenv("PADMINI_SISTEMA", valor)
        app_mod._paginas_prontas.clear()
    yield ligar
    app_mod._paginas_prontas.clear()


# ------------------------------------------------------------------ amostra
def test_amostra_e_gratis_e_so_tem_a_triade():
    r = cliente.post("/api/ocidental/mapa", json={**PESSOA, "nivel": "amostra"})
    assert r.status_code == 200, r.text
    c = r.json()
    assert [i["ponto"] for i in c["amostra"]["triade"]] == ["sol", "lua", "ascendente"]
    assert c["amostra"]["aspecto"]["texto"]
    assert "pontos" not in c and "secoes" not in c  # o detalhe é pago


def test_amostra_sem_hora_avisa_e_nao_tem_ascendente():
    c = cliente.post("/api/ocidental/mapa", json={**SEM_HORA, "nivel": "amostra"}).json()
    assert c["tem_hora"] is False
    assert [i["ponto"] for i in c["amostra"]["triade"]] == ["sol", "lua"]
    assert any("hora" in a for a in c["amostra"]["avisos"])


def test_ia_nao_sai_na_amostra():
    r = cliente.post("/api/ocidental/mapa", json={**PESSOA, "nivel": "amostra", "texto_ia": True})
    assert r.status_code == 402


# ------------------------------------------------------------------ completo (402)
@pytest.mark.parametrize("token", [None, "falso", "oc-" + "0" * 32])
def test_completo_trancado_sem_token_valido(token):
    r = cliente.post("/api/ocidental/mapa", json={**PESSOA, "nivel": "completo", "token": token})
    assert r.status_code == 402


def test_token_vedico_nao_abre_o_ocidental():
    r = cliente.post("/api/ocidental/mapa", json={**PESSOA, "nivel": "completo", "token": _token(PESSOA, "vedica")})
    assert r.status_code == 402


def test_completo_com_token():
    r = cliente.post("/api/ocidental/mapa", json={**PESSOA, "nivel": "completo", "token": _token(PESSOA)})
    assert r.status_code == 200, r.text
    c = r.json()
    ids = [p["id"] for p in c["pontos"]]
    assert ids[:10] == ["sol", "lua", "mercurio", "venus", "marte", "jupiter", "saturno", "urano", "netuno", "plutao"]
    assert {"nodo_norte", "ascendente", "meio_do_ceu"} <= set(ids)
    assert c["casas"]["sistema"] == "placidus" and len(c["casas"]["cuspides"]) == 12
    assert "Os planetas nas casas" in c["secoes"] and "O regente do Ascendente" in c["secoes"]


def test_completo_sem_hora():
    r = cliente.post("/api/ocidental/mapa", json={**SEM_HORA, "nivel": "completo", "token": _token(SEM_HORA)})
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["casas"] is None and "Os planetas nas casas" not in c["secoes"]
    assert "Antes de começar" in c["secoes"]


def test_token_com_hora_nao_abre_sem_hora():
    """A hora faz parte da chave assinada: não dá para trocar os dados do link."""
    r = cliente.post("/api/ocidental/mapa", json={**SEM_HORA, "nivel": "completo", "token": _token(PESSOA)})
    assert r.status_code == 402


# ------------------------------------------------------------------ PDF
def test_pdf_trancado_sem_token():
    assert cliente.post("/api/ocidental/pdf", json={**PESSOA, "nivel": "completo"}).status_code == 402


@pytest.mark.parametrize("p", [PESSOA, SEM_HORA], ids=["com_hora", "sem_hora"])
def test_pdf_com_token(p):
    r = cliente.post("/api/ocidental/pdf", json={**p, "nivel": "completo", "token": _token(p)})
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF" and len(r.content) > 20_000
    assert "mapa-natal-ana.pdf" in r.headers["content-disposition"]


# ------------------------------------------------------------------ páginas
def test_pagina_do_mapa_na_versao_ocidental(versao):
    versao("ocidental")
    html = cliente.get("/mapa").text
    assert "/api/ocidental/mapa" in html and "Mapa Natal" in html
    assert "védic" not in html.lower() and "पद्मिनी" not in html
    assert f"R${ofertas.preco('mapa', 'ocidental')}" in html


def test_sem_checkout_o_botao_fica_em_breve(versao):
    versao("ocidental")
    assert ofertas.checkout("mapa", "ocidental") == ""
    html = cliente.get("/mapa").text
    assert 'const LINK_CHECKOUT_INDIVIDUAL = "";' in html and "Em breve" in html


def test_live_ocidental(versao, monkeypatch):
    versao("ocidental")
    html = cliente.get("/live").text
    assert "/api/live/ocidental/token/mapa" in html
    assert cliente.post("/api/live/ocidental/token/mapa", json=PESSOA).status_code == 401
    cookie = acesso.emitir_sessao("live", 2_000_000_000)
    r = cliente.post("/api/live/ocidental/token/mapa", json=SEM_HORA, cookies={"pad_live": cookie})
    assert r.status_code == 200 and r.json()["token"] == _token(SEM_HORA)


# ------------------------------------------------------------------ webhook
@pytest.fixture
def oferta_mapa_ocidental(monkeypatch):
    novas = json.loads(json.dumps(ofertas.POR_SISTEMA["ocidental"]))
    novas["mapa"].update(checkout="https://pay.cakto.com.br/ocmapa9_1", codigo="ocmapa9")
    monkeypatch.setitem(ofertas.POR_SISTEMA, "ocidental", novas)


def _evento(sck, pid):
    return {"event": "purchase_approved", "secret": "segredo-de-teste-webhook",
            "data": {"id": pid, "status": "paid", "sck": sck, "offer": {"id": "ocmapa9"},
                     "customer": {"email": "comprador@teste.com", "name": "Ana"}}}


def test_webhook_entrega_mapa_ocidental_sem_hora(oferta_mapa_ocidental):
    """Na ocidental, 'não sei a hora' é um pedido válido (sck com a hora vazia)."""
    c = _postar_webhook(_evento("m~1990-05-15~~-23.5505~-46.6333~Ana~Sao Paulo", "oc-sem-hora")).json()
    assert c["produto"] == "mapa" and "token=oc-" in c["link"] and "hora=&" in c["link"]
    tok = c["link"].split("token=")[1]
    r = cliente.post("/api/ocidental/mapa", json={**SEM_HORA, "nivel": "completo", "token": tok})
    assert r.status_code == 200


def test_webhook_vedico_continua_exigindo_hora():
    import ofertas as o
    ev = _evento("m~1990-05-15~~-23.5505~-46.6333~Ana~Sao Paulo", "ve-sem-hora")
    ev["data"]["offer"]["id"] = o.codigo("mapa")
    c = _postar_webhook(ev).json()
    assert "pendente" in c


def test_email_de_entrega_ocidental():
    html = entrega.email_completo_html("mapa", "https://x/mapa?token=oc-1", "Ana", "", "ocidental")
    assert "mapa natal" in html and "védica" not in html

"""
Rodada 13, Fase 3: a página e o PDF de "O seu ano" (/seu-ano, /api/ocidental/previsao).
Critérios do brief: a página mostra resumo, linha do tempo, áreas, eclipses e Revolução
Solar; sem hora, o aviso e nada do que depende de casa; amostra sem texto pago no JSON;
produto oculto = 404 até ligar (link pago abre sempre).
"""
import json
from datetime import date, datetime

import pytest

from test_app import app_mod, cliente  # primeiro: define os segredos de teste

import acesso
import catalogo
import mapa_ocidental as mo
import marketing
import montar_previsao as mp
import previsao as pv
import sequencias

pytestmark = pytest.mark.catalogo_real
HTML = {"accept": "text/html"}
PESSOA = {"nome": "Ana", "data": "1995-01-10", "hora": "21:40", "lat": -22.9068, "lon": -43.1729,
          "cidade": "Rio de Janeiro, RJ"}
INICIO = "2026-10"


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("PADMINI_PREVIA_CHAVE", "chave-de-previa")
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


def _token(p=PESSOA, inicio=INICIO):
    return acesso.emitir_token("previsao", acesso.chave_previsao(p["data"], p["hora"], p["lat"], p["lon"], inicio),
                               "ocidental")


def _completo(p=PESSOA, inicio=INICIO):
    r = cliente.post("/api/ocidental/previsao", json={**p, "nivel": "completo", "inicio": inicio, "token": _token(p, inicio)})
    assert r.status_code == 200, r.text
    return r.json()


def _previsao_local(p=PESSOA, inicio=INICIO):
    dt = datetime.fromisoformat(p["data"] + "T" + (p["hora"] or "12:00"))
    natal = (mo.calcular_mapa_ocidental(dt, p["lat"], p["lon"]) if p["hora"]
             else mo.calcular_mapa_ocidental(None, p["lat"], p["lon"], data=dt.date()))
    return pv.calcular_previsao(natal, dt.date(), p["lat"], p["lon"], date.fromisoformat(inicio + "-01"))


# ------------------------------------------------------------------ o produto oculto
def test_oculto_responde_404_sem_previa_nem_token(ocidental):
    assert catalogo.estado("previsao") == "oculto" and not catalogo.vende("previsao")
    assert cliente.get("/seu-ano", headers=HTML).status_code == 404


def test_previa_e_link_pago_abrem(ocidental):
    r = cliente.get("/seu-ano?previa=chave-de-previa", headers=HTML)
    assert r.status_code == 200 and "próximos 12 meses" in r.text
    assert cliente.get(f"/seu-ano?token={_token()}", headers=HTML).status_code == 200


def test_oculto_some_do_menu_rodape_e_leituras(ocidental):
    for rota in ("/", "/mapa", "/leituras"):
        assert "/seu-ano" not in cliente.get(rota, headers=HTML).text, rota


def test_previa_nao_abre_outros_ocultos(ocidental):
    """A exceção da prévia vale só para oculto com página própria."""
    assert cliente.get("/comunidade?previa=chave-de-previa", headers=HTML).status_code == 404


def test_pagina_oculta_nao_mostra_preco_nem_compra(ocidental):
    html = cliente.get("/seu-ano?previa=chave-de-previa", headers=HTML).text
    assert "data-comprar" not in html and 'const LINK_CHECKOUT = "";' in html


# ------------------------------------------------------------------ amostra
def test_amostra_pede_email(ocidental):
    r = cliente.post("/api/ocidental/previsao", json={**PESSOA, "nivel": "amostra"})
    assert r.status_code == 422


def test_amostra_sem_texto_pago_no_json(ocidental, monkeypatch):
    """Com o e-mail saindo, a tela recebe os títulos dos 3 temas e o começo do primeiro;
    nada dos textos dos outros temas, das áreas, dos eclipses ou da Revolução."""
    import entrega
    monkeypatch.setenv("RESEND_API_KEY", "re_teste")
    monkeypatch.setattr(entrega, "enviar_email", lambda *a, **k: True)
    monkeypatch.setattr(app_mod.db, "registrar_amostra_email", lambda *a, **k: None, raising=False)
    import rotas_ocidental
    monkeypatch.setattr(rotas_ocidental.db, "registrar_amostra_email", lambda *a, **k: None)
    monkeypatch.setattr(rotas_ocidental.db, "amostras_enviadas_hoje", lambda *a, **k: 0)
    r = cliente.post("/api/ocidental/previsao", json={**PESSOA, "nivel": "amostra", "email": "ana@teste.com"})
    assert r.status_code == 200, r.text
    corpo = r.text
    a = r.json()["amostra"]
    assert len(a["temas"]) == 3 and all(t["titulo"] and t["periodo"] for t in a["temas"])
    assert "texto" not in a and a["trecho"]
    # o completo do mesmo mês (o pago) não vaza: texto inteiro do 1º tema e de todo o resto
    inicio = a["inicio"][:7]
    c = mp.completo(_previsao_local(inicio=inicio))
    assert c["temas"][0]["texto"].startswith(a["trecho"]) and c["temas"][0]["texto"] not in corpo
    pagos = [t["texto"] for t in c["temas"][1:]] + [i["texto"] for x in c["areas"] for i in x["itens"]]
    pagos += [e["texto"] for e in c["eclipses"] if e["texto"]]
    if c["revolucao"] and "texto_sol" in c["revolucao"]:
        pagos += [c["revolucao"]["texto_sol"], c["revolucao"]["texto_ascendente"]]
    for t in pagos:
        if t not in (a["abertura"], c["temas"][0]["texto"]):  # o 1º tema: só o começo, conferido acima
            assert t[:80] not in corpo, t[:80]


def test_amostra_comeca_no_mes_corrente(ocidental):
    r = cliente.post("/api/ocidental/previsao", json={**PESSOA, "nivel": "amostra", "email": "ana2@teste.com"})
    hoje = datetime.now(pv.FUSO_DATAS).date()
    assert r.json()["amostra"]["inicio"] == hoje.replace(day=1).isoformat()


def test_email_da_amostra_traz_o_primeiro_tema_inteiro():
    a = mp.amostra(_previsao_local())
    html = marketing.email_amostra_html("previsao", a, {**PESSOA, "inicio": INICIO}, "ana@teste.com", "Ana",
                                        "ocidental")
    assert a["temas"][0]["titulo"] in html and marketing._e(a["texto"]) in html
    assert all(marketing._e(t["titulo"]) in html for t in a["temas"])
    assert "/seu-ano" in html and "R$" not in html  # oculto: sem preço


def test_sequencia_de_boas_vindas_nao_pega_previsao():
    assert "previsao" not in sequencias.ESCADA


# ------------------------------------------------------------------ completo
def test_completo_so_com_token_do_mesmo_ano(ocidental):
    base = {**PESSOA, "nivel": "completo", "inicio": INICIO}
    assert cliente.post("/api/ocidental/previsao", json=base).status_code == 402
    assert cliente.post("/api/ocidental/previsao", json={**base, "token": "oc-" + "0" * 32}).status_code == 402
    # o token do mapa natal não abre a previsão; o de outubro não abre novembro
    tk_mapa = acesso.emitir_token("mapa", acesso.chave_mapa(PESSOA["data"], PESSOA["hora"], PESSOA["lat"], PESSOA["lon"]),
                                  "ocidental")
    assert cliente.post("/api/ocidental/previsao", json={**base, "token": tk_mapa}).status_code == 402
    assert cliente.post("/api/ocidental/previsao", json={**base, "inicio": "2026-11", "token": _token()}).status_code == 402
    assert cliente.post("/api/ocidental/previsao", json={**base, "token": _token()}).status_code == 200


def test_completo_tem_todas_as_secoes(ocidental):
    d = _completo()
    assert d["periodo"] == "de 1 de outubro de 2026 a 30 de setembro de 2027"
    assert len(d["temas"]) == 3 and all(t["texto"] for t in d["temas"])
    assert [m["mes"] for m in d["linha_do_tempo"]][0] == "2026-10" and len(d["linha_do_tempo"]) == 12
    assert d["areas"] and all(i["texto"] for a in d["areas"] for i in a["itens"])
    assert {a["chave"] for a in d["areas"]} <= {x["chave"] for x in catalogo.dimensoes_mapa()}
    assert len(d["eclipses"]) == 5 and all(e["texto"] and e["casa"] for e in d["eclipses"])
    assert d["revolucao"]["ascendente"] == "gemeos" and d["revolucao"]["casa_do_sol"] == 8
    assert d["revolucao"]["texto_ascendente"] and d["revolucao"]["texto_sol"]
    assert d["abertura"] and d["como_ler"] and d["fechamento"]
    # retrogradação: um item só, com as datas exatas
    jasc = [t for a in d["areas"] for t in a["itens"] if t.get("ponto") == "ascendente" and t["planeta"] == "jupiter"]
    assert jasc and jasc[0]["exatas"] == ["2026-10-26", "2027-01-29", "2027-06-22"] and jasc[0]["retrogrado"]
    assert "em breve" not in json.dumps(d, ensure_ascii=False).lower()


def test_sem_hora_mostra_o_aviso_e_esconde_o_que_depende_de_casa(ocidental):
    p = {**PESSOA, "hora": ""}
    d = _completo(p)
    assert mp.aviso("sem_hora") in d["avisos"]
    itens = [i for a in d["areas"] for i in a["itens"]]
    assert not any(i.get("ponto") in ("ascendente", "meio_do_ceu", "lua") for i in itens)
    assert not any("casa" in i for i in itens)  # sem ingressos em casa
    assert all(e["casa"] is None and e["texto"] == "" for e in d["eclipses"])
    assert "ascendente" not in d["revolucao"] and d["revolucao"]["aviso"] == mp.aviso("sem_revolucao")


def test_pdf(ocidental):
    base = {**PESSOA, "nivel": "completo", "inicio": INICIO}
    assert cliente.post("/api/ocidental/previsao/pdf", json=base).status_code == 402
    r = cliente.post("/api/ocidental/previsao/pdf", json={**base, "token": _token()})
    assert r.status_code == 200 and r.content[:4] == b"%PDF" and len(r.content) > 20_000
    assert 'filename="o-seu-ano-ana.pdf"' in r.headers["content-disposition"]


def test_secoes_do_pdf_sem_em_breve():
    s = mp.secoes(_previsao_local())
    assert list(s)[:4] == ["O seu ano", "Os temas do seu ano", "Mês a mês", "Por área da vida"]
    assert "Eclipses" in s and "Revolução Solar" in s and "Para fechar" in s
    assert "em breve" not in json.dumps(s, ensure_ascii=False).lower()


def test_pagina_desenha_cada_secao(ocidental):
    html = cliente.get("/seu-ano?previa=chave-de-previa", headers=HTML).text
    for marca in ('id="sec-temas"', 'id="sec-meses"', 'id="sec-areas"', 'id="sec-eclipses"', 'id="sec-rs"',
                  "/api/ocidental/previsao/pdf", "inicio"):
        assert marca in html, marca

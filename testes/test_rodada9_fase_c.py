"""
Rodada 9, Fase C: páginas de produto (em breve e ocultas), Todas as leituras,
leitura completa com a roda desenhada no servidor, Minhas leituras, Privacidade e
Termos, e-mails e PDF com a marca nova.
"""
import copy
import re
from datetime import datetime

import pytest

from test_app import RAIZ, app_mod, cliente  # primeiro: define os segredos de teste

import acesso
import catalogo
import entrega
import mapa_ocidental as mo
import marketing
import montar_texto_ocidental as mt
import produtos_ocidental
import roda_mapa

pytestmark = pytest.mark.catalogo_real
HTML = {"accept": "text/html"}
PESSOA = {"nome": "Ana", "data": "1994-05-14", "hora": "15:40", "lat": -30.0331, "lon": -51.23,
          "cidade": "Porto Alegre, RS", "email": "ana@teste.com"}
OCULTOS = ("/comunidade", "/cursos", "/cursos/astrologia-do-zero", "/consulta")
EM_BREVE = ("/compatibilidade", "/numerologia", "/tarot")


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


@pytest.fixture
def ocultos_ligados(ocidental):
    """Os produtos ocultos passam a `em_breve` (como o Nicolas faria no YAML)."""
    original = catalogo.dados()
    d = copy.deepcopy(original)
    for p in d["produtos"]:
        if p["estado"] == "oculto":
            p["estado"] = "em_breve"
    catalogo.usar(d)
    app_mod._paginas_prontas.clear()
    yield
    catalogo.usar(original)


def _mapa(p=PESSOA):
    return mo.calcular_mapa_ocidental(datetime.fromisoformat(f"{p['data']}T{p['hora']}"), p["lat"], p["lon"])


def _completo(p=PESSOA):
    token = acesso.emitir_token("mapa", acesso.chave_mapa(p["data"], p["hora"], p["lat"], p["lon"]), "ocidental")
    r = cliente.post("/api/ocidental/mapa", json={**p, "nivel": "completo", "token": token})
    assert r.status_code == 200, r.text
    return r.json()


def _sem_preco(html):
    return not re.search(r"R\$\s?\d", html) and "pay.cakto" not in html and "__CHECKOUT" not in html


# ------------------------------------------------------------------ páginas de produto
@pytest.mark.parametrize("rota", EM_BREVE)
def test_produto_em_breve_tem_o_modelo_completo_sem_preco(ocidental, rota):
    r = cliente.get(rota, headers=HTML)
    assert r.status_code == 200 and '<body class="vz">' in r.text
    for trecho in ("produto-topo", 'class="secao trecho"', "perguntas-produto", 'data-me-avise="'):
        assert trecho in r.text, (rota, trecho)
    assert _sem_preco(r.text), rota


def test_trecho_real_sai_da_base_de_textos():
    assert produtos_ocidental.trecho_real("numerologia")["texto"]
    assert produtos_ocidental.trecho_real("tarot")["texto"]
    sin = produtos_ocidental.trecho_real("compat")
    assert sin["texto"] and "fictícios" in sin.get("nota", "")


@pytest.mark.parametrize("rota", OCULTOS)
def test_oculto_responde_404_e_some_do_menu(ocidental, rota):
    assert cliente.get(rota, headers=HTML).status_code == 404
    home = cliente.get("/").text
    assert f'href="{rota}"' not in home
    assert rota not in cliente.get("/sitemap.xml").text


@pytest.mark.parametrize("rota", OCULTOS)
def test_oculto_pronto_quando_ligado_e_sem_preco(ocultos_ligados, rota):
    r = cliente.get(rota, headers=HTML)
    assert r.status_code == 200 and '<body class="vz">' in r.text, rota
    assert _sem_preco(r.text), rota


def test_textos_dos_ocultos_estao_como_rascunho():
    for chave in ("comunidade", "astrologia-do-zero", "consulta"):
        assert produtos_ocidental.pagina(chave)["rascunho"] is True, chave
    assert produtos_ocidental.cursos()["rascunho"] is True


def test_vitrine_de_cursos_tem_filtros(ocultos_ligados):
    html = cliente.get("/cursos", headers=HTML).text
    assert 'data-area=""' in html and html.count('class="cartao capa" data-area=') == len(produtos_ocidental.cursos()["itens"])


def test_todas_as_leituras_so_ativos_e_em_breve(ocidental):
    html = cliente.get("/leituras").text
    for p in catalogo.produtos():
        assert (f"<h2 class=\"t3\">{p['nome']}</h2>" in html) == (p["estado"] != "oculto"), p["chave"]
    assert 'id="quem-revisa"' in html and _sem_preco(html)


# ------------------------------------------------------------------ leitura completa
def test_roda_desenha_os_aspectos_do_proprio_mapa():
    mapa = _mapa()
    maiores = [a for a in mapa["aspectos"] if a["tipo"] in roda_mapa.HARMONIA + roda_mapa.TENSAO
               and a["a"] in roda_mapa.GLIFO_PONTO and a["b"] in roda_mapa.GLIFO_PONTO]
    linhas_internas = [f for f in roda_mapa.formas(mapa) if f[0] == "linha" and f[8] == .75]
    assert maiores and len(linhas_internas) == len(maiores)
    outro = _mapa({**PESSOA, "data": "1980-01-02", "hora": "06:10"})
    assert roda_mapa.svg(mapa) != roda_mapa.svg(outro)


def test_roda_tem_signos_casas_ac_mc_e_planetas():
    svg = roda_mapa.svg(_mapa(), "Ana")
    for g in "♈♉♊♋♌♍♎♏♐♑♒♓☉☽☿♀♂♃♄":
        assert g in svg, g
    assert ">AC<" in svg and ">MC<" in svg and ">12<" in svg
    assert 'aria-label="Roda do mapa natal de Ana: Sol em' in svg


def test_sem_hora_a_roda_nao_tem_casas():
    mapa = mo.calcular_mapa_ocidental(None, PESSOA["lat"], PESSOA["lon"], data=datetime(1994, 5, 14).date())
    svg = roda_mapa.svg(mapa)
    assert ">AC<" not in svg and ">MC<" not in svg


def test_completo_traz_dimensoes_inteiras_e_a_roda(ocidental):
    c = _completo()
    assert c["roda"].startswith('<svg class="roda-svg"')
    dims = {d["chave"]: d for d in c["dimensoes"]}
    mapa = _mapa()
    sol = dims["essencia"]
    assert sol["texto"] == mt.texto_signo("sol", mapa["pontos"]["sol"]["signo"])
    for a in sol["aspectos"]:
        assert a["texto"]
    # o resto do mapa não repete o que as dimensões mostram
    assert all("Sol em" not in titulo for titulo in c["resto"])


def test_texto_pago_nao_vai_na_amostra(ocidental):
    r = cliente.post("/api/ocidental/mapa", json={**PESSOA, "nivel": "amostra"})
    assert r.status_code == 200
    assert "roda" not in r.json() and "resto" not in r.json()
    mapa = _mapa()
    inteiro = mt.texto_signo("venus", mapa["pontos"]["venus"]["signo"])
    assert inteiro[-80:] not in r.text


def test_pagina_do_mapa_tem_a_tela_da_leitura(ocidental):
    html = cliente.get("/mapa").text
    for trecho in ("leitura-grade", "roda-lateral", "secaoDimensao"):
        assert trecho in html, trecho


# ------------------------------------------------------------------ PDF
def test_pdf_tem_capa_roda_e_fontes_novas(ocidental):
    token = acesso.emitir_token("mapa", acesso.chave_mapa(PESSOA["data"], PESSOA["hora"], PESSOA["lat"], PESSOA["lon"]), "ocidental")
    r = cliente.post("/api/ocidental/pdf", json={**PESSOA, "nivel": "completo", "token": token})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    for fonte in (b"Fraunces", b"Figtree", b"NotoSansSymbols-", b"NotoSansSymbols2-"):
        assert fonte in r.content, fonte
    assert b"/DCTDecode" in r.content  # a capa ilustrada (JPEG)
    assert len(r.content) < 1_500_000


def test_fontes_de_glifos_cobrem_a_roda():
    from fontTools.ttLib import TTFont
    sym = TTFont(RAIZ / "fontes" / "NotoSansSymbols-astro.ttf").getBestCmap()
    sym2 = TTFont(RAIZ / "fontes" / "NotoSansSymbols2-astro.ttf").getBestCmap()
    glifos = set("".join(roda_mapa.GLIFO_SIGNO.values()) + "".join(roda_mapa.GLIFO_PONTO.values()))
    for g in glifos:
        fonte = sym2 if g in roda_mapa.SO_NA_SYMBOLS_2 else sym
        assert ord(g) in fonte, g


# ------------------------------------------------------------------ e-mails
def test_email_de_entrega_com_a_marca_nova():
    html = entrega.email_completo_html("mapa", "https://padmini.com.br/mapa?token=oc-x", "Ana", sistema="ocidental")
    assert "Valderez Astrologia" in html and "Fraunces" in html and "/privacidade" in html
    assert "Padmini" not in html


def test_email_da_amostra_sem_venda_nao_oferece_compra():
    assert not catalogo.vendas_abertas()
    html = marketing.email_amostra_html("mapa", {"sol": "touro"}, dict(PESSOA), "ana@teste.com", "Ana", "ocidental")
    assert _sem_preco(html) and "Valderez Astrologia" in html


def test_vedica_continua_com_o_email_antigo():
    html = entrega.email_completo_html("mapa", "https://padmini.com.br/mapa?token=x", "Ana", sistema="vedica")
    assert "versao:ocidental" not in html and "Valderez" not in html


# ------------------------------------------------------------------ minhas leituras e textos legais
def test_minhas_leituras_no_visual_2(ocidental):
    html = cliente.get("/minhas-leituras").text
    assert '<body class="vz">' in html and 'id="cartao-pronto" hidden' in html and "noindex" in html
    assert "a resposta é sempre a mesma" in html


@pytest.mark.parametrize("rota", ("/privacidade", "/termos"))
def test_legais_com_indice_e_texto_de_antes(ocidental, rota):
    html = cliente.get(rota).text
    assert '<body class="vz">' in html and 'class="legal-indice"' in html and 'aria-current="page"' in html
    # quem responde pelos dados e a operadora do pagamento não mudam
    assert "Pedro Sperb Monteiro LTDA" in html and "55.428.936/0001-00" in html and "Cakto" in html
    for ident in re.findall(r'<a href="#([a-z0-9]+)">', html[html.index("legal-indice"):]):
        assert f'id="{ident}"' in html, ident


def test_privacidade_tem_o_resumo_e_o_whatsapp(ocidental):
    html = cliente.get("/privacidade").text
    assert "Em resumo" in html and "WhatsApp" in html and "o seu nome" in html and 'id="cookies"' in html

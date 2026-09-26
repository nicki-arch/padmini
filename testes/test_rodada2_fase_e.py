"""
Fase E da rodada 2: marca e acabamento da versão ocidental (home com os 4
produtos, termos e privacidade próprios, og:image por página, venda cruzada
entre os 4 produtos, sitemap). A védica continua exatamente igual.
"""
import json
import re

import pytest

from test_app import RAIZ, app_mod, cliente

import entrega  # noqa: E402
import marketing  # noqa: E402
import ofertas  # noqa: E402
import sistema  # noqa: E402


@pytest.fixture
def versao(monkeypatch):
    def ligar(v):
        monkeypatch.setenv("PADMINI_SISTEMA", v)
        app_mod._paginas_prontas.clear()
    yield ligar
    app_mod._paginas_prontas.clear()


def test_home_ocidental_tem_os_4_produtos_com_preco_do_yaml(versao):
    versao("ocidental")
    html = cliente.get("/").text
    for rota, chave in (("/compatibilidade", "compat"), ("/mapa", "mapa"),
                        ("/numerologia", "numerologia"), ("/tarot", "tarot")):
        assert f'href="{rota}"' in html
        assert f"R${ofertas.preco(chave, 'ocidental')}" in html
    assert f"R${ofertas.preco('bump_mapas_casal', 'ocidental')}" in html  # o combo


@pytest.mark.parametrize("rota", ["/termos", "/privacidade"])
def test_termos_e_privacidade(versao, rota):
    versao("vedica")
    assert cliente.get(rota).content == (RAIZ / "static" / rota.strip("/")).with_suffix(".html").read_bytes()
    versao("ocidental")
    html = cliente.get(rota).text
    assert "numerologia" in html.lower() and "tarot" in html.lower()
    assert "védic" not in html.lower() and "Jyotish" not in html
    # os dados da empresa e o contato continuam
    for trecho in ("Pedro Sperb Monteiro LTDA", "55.428.936/0001-00", "contato@pedrosperbmonteiro.com.br"):
        assert trecho in html


def test_privacidade_ocidental_mantem_as_bases_legais_e_fala_da_pergunta(versao):
    versao("ocidental")
    html = cliente.get("/privacidade").text
    for base in ("art. 7º, V", "art. 7º, I", "art. 7º, II", "art. 7º, IX", "art. 33", "art. 18"):
        assert base in html
    assert "140 caracteres" in html and "não armazenada" in html


def test_cada_pagina_ocidental_tem_a_sua_og_image(versao):
    versao("ocidental")
    vistas = {}
    for rota in sistema.PAGINAS["ocidental"]:
        img = re.search(r'og:image" content="https://padmini\.com\.br/static/([^"]+)"', cliente.get(rota).text)
        assert img, rota
        assert img.group(1).startswith("og-oc-") and (RAIZ / "static" / img.group(1)).exists(), rota
        vistas[rota] = img.group(1)
    produtos = [vistas[r] for r in ("/", "/mapa", "/compatibilidade", "/numerologia", "/tarot")]
    assert len(set(produtos)) == 5  # uma por página de produto


def test_sitemap(versao):
    versao("vedica")
    assert re.findall(r"<loc>[^<]*padmini[^/]*(/[^<]*)</loc>", cliente.get("/sitemap.xml").text) == \
        ["/", "/mapa", "/compatibilidade"]
    versao("ocidental")
    locs = re.findall(r"<loc>[^<]*padmini[^/]*(/[^<]*)</loc>", cliente.get("/sitemap.xml").text)
    assert locs == ["/", "/mapa", "/compatibilidade", "/numerologia", "/tarot"]


# ------------------------------------------------------------------ venda cruzada
@pytest.fixture
def ocidental_com_links(monkeypatch):
    novas = json.loads(json.dumps(ofertas.POR_SISTEMA["ocidental"]))
    for k, o in novas.items():
        o["checkout"] = f"https://pay.cakto.com.br/oc{k}_1"
    monkeypatch.setitem(ofertas.POR_SISTEMA, "ocidental", novas)


@pytest.mark.parametrize("comprado,oferece", [
    ("tarot", ["/numerologia", "/mapa"]),
    ("numerologia", ["/mapa", "/tarot"]),
    ("mapa", ["/compatibilidade", "/numerologia"]),
])
def test_venda_cruzada_entre_os_4_produtos(ocidental_com_links, comprado, oferece):
    bloco = marketing.bloco_venda_cruzada(comprado, {"nome": "Ana"}, "ocidental")
    for rota in oferece:
        assert f"{entrega.SITE_URL}{rota}?" in bloco
    assert f"{entrega.SITE_URL}/{comprado}?" not in bloco  # não oferece o que acabou de comprar
    assert "védic" not in bloco.lower()


def test_venda_cruzada_do_casal_tem_os_mapas_e_a_numerologia(ocidental_com_links):
    dados = {"a": {"nome": "Ana", "data": "1990-01-01", "hora": "", "lat": 1, "lon": 1},
             "b": {"nome": "Rui", "data": "1991-01-01", "hora": "", "lat": 1, "lon": 1}}
    bloco = marketing.bloco_venda_cruzada("compat", dados, "ocidental")
    assert "Mapa natal de Ana" in bloco and "Mapa natal de Rui" in bloco and "/numerologia?" in bloco


def test_sem_links_nao_ha_venda_cruzada_ocidental():
    for produto in ("mapa", "compat", "numerologia", "tarot"):
        assert marketing.bloco_venda_cruzada(produto, {}, "ocidental") == ""

"""
Rodada 6, Fase B: o mapa natal é a porta de entrada da home (ocidental).
Ordem dos produtos em toda parte: mapa natal, sinastria, numerologia, tarot.
"""
import json
import re

import pytest

from test_app import app_mod, cliente

import marketing  # noqa: E402

ORDEM = ["/mapa", "/compatibilidade", "/numerologia", "/tarot"]


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


def test_hero_e_do_mapa_natal(ocidental):
    html = cliente.get("/").text
    hero = html[html.index('<section class="hero'):html.index("</section>")]
    # rodada 9 (tela Site-Home 2.0): a data de nascimento já no topo, e o botão leva ao /mapa
    assert "nasceu" in hero and "Ver meu mapa grátis" in hero
    assert 'action="/mapa"' in hero and 'id="h-data"' in hero
    fim = html[html.rindex('<section class="secao fecho">'):]
    assert 'class="bt bt-1" href="/mapa"' in fim


def test_ordem_dos_cards_e_do_menu(ocidental):
    # rodada 9: "Todas as leituras" segue a ordem do catálogo (mapa natal primeiro)
    html = cliente.get("/leituras").text
    assert re.findall(r'class="bt bt-[12] bt-p" href="(/[a-z]+)', html) == ORDEM
    for rota in ("/", "/mapa", "/tarot"):
        menu = re.search(r'<nav class="nav".*?</nav>', cliente.get(rota).text, re.S).group(0)
        # rodada 9: o menu vem do catálogo e termina em "Todas as leituras"
        assert re.findall(r'href="(/[a-z]+)"', menu) == ORDEM + ["/leituras"], rota


def test_home_com_a_sinastria_em_breve_mostra_o_me_avise(ocidental):
    """Rodada 9: a home do pacote 2.0 é do mapa natal; a sinastria aparece em "Chegando em
    breve" quando está em breve (o conftest a deixa ativa: aqui, o catálogo de verdade)."""
    import catalogo
    catalogo.usar(catalogo.carregar())
    app_mod._paginas_prontas.clear()
    html = cliente.get("/").text
    assert html.index('id="dimensoes"') < html.index('id="em-breve"')
    assert 'href="/compatibilidade#me-avise"' in html


def test_head_e_json_ld_falam_do_mapa(ocidental):
    html = cliente.get("/").text
    assert '<meta property="og:title" content="O seu mapa natal — Valderez Astrologia">' in html
    bloco = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
    org = next(g for g in json.loads(bloco)["@graph"] if g["@type"] == "Organization")
    assert org["description"].startswith("Mapa natal")
    assert "og-oc-home.png" in html  # a imagem da home já é neutra (“O céu de quando você nasceu”)


def test_venda_cruzada_segue_a_escada():
    escada = ["mapa", "compat", "numerologia", "tarot"]
    for comprado, sugeridos in marketing.VENDA_CRUZADA_OCIDENTAL.items():
        assert comprado not in sugeridos
    assert marketing.VENDA_CRUZADA_OCIDENTAL["mapa"][0] == "compat"
    assert marketing.VENDA_CRUZADA_OCIDENTAL["tarot"][0] == "mapa"
    for sugeridos in marketing.VENDA_CRUZADA_OCIDENTAL.values():
        assert list(sugeridos) == sorted(sugeridos, key=escada.index)


def test_precos_da_home_saem_das_ofertas(ocidental):
    import ofertas
    html = cliente.get("/").text
    of = ofertas.do_sistema("ocidental")
    # rodada 9: na home, só o preço do mapa natal (tela Site-Home); os outros em "Todas as leituras"
    assert f"R${ofertas.moeda(of['mapa']['preco'])}" in html
    leituras = cliente.get("/leituras").text
    for p in ("mapa", "compat", "numerologia", "tarot"):
        assert f"R${ofertas.moeda(of[p]['preco'])}" in leituras, p

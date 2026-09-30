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
    assert "nasceu" in hero and "Ver meu mapa natal" in hero
    assert re.search(r'class="button" href="/mapa"', hero)  # rodada visual: botão principal do pacote
    assert 'href="/compatibilidade"' in hero  # a sinastria continua a um clique
    fim = html[html.rindex("<h2>"):]
    assert 'class="button" href="/mapa"' in fim


def test_ordem_dos_cards_e_do_menu(ocidental):
    html = cliente.get("/").text
    cards = html[html.index('class="produtos"'):]
    cards = cards[:cards.index("</section>")]
    assert re.findall(r'<a class="button[^"]*" href="(/[a-z]+)"', cards) == ORDEM
    assert 'prod anchor"' in cards[:cards.index("/compatibilidade")]  # o destaque é do mapa
    for rota in ("/", "/mapa", "/tarot"):
        menu = re.search(r'<nav class="nav-desktop".*?</nav>', cliente.get(rota).text, re.S).group(0)
        menu = re.sub(r'<a class="button"[^>]*>.*?</a>', "", menu)  # o botão do cabeçalho não é item do menu
        assert re.findall(r'href="(/[a-z]+)"', menu) == ORDEM, rota


def test_sinastria_continua_na_home_mais_abaixo(ocidental):
    html = cliente.get("/").text
    assert html.index('class="produtos"') < html.index("As oito dimensões do casal") < html.index('class="galeria"')
    assert html.count('class="rosa"') == 3


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
    for p in ("mapa", "compat", "numerologia", "tarot"):
        assert f"R${ofertas.moeda(of[p]['preco'])}" in html, p

"""
Rodada 9.1: ajustes visuais depois da abertura — ícones de traço por item (a roda
nunca vira ícone), colunas de "Todas as leituras" sem cartão sozinho, o link
"Preferências de cookies" de volta ao rodapé e o topo da home no celular.
"""
import copy
import re
import socket
import threading
import time

import pytest

from test_app import RAIZ, app_mod, cliente  # primeiro: define os segredos de teste
from test_rodada6_cookies import _chromium

import catalogo
import icones
import produtos_ocidental
import textos

pytestmark = pytest.mark.catalogo_real
HTML = {"accept": "text/html"}
CSS = (RAIZ / "static" / "valderez" / "v2.css").read_text(encoding="utf-8")


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    app_mod._paginas_prontas.clear()
    original = catalogo.dados()
    yield
    catalogo.usar(original)
    app_mod._paginas_prontas.clear()


def _ligar_todos(estado="em_breve"):
    d = copy.deepcopy(catalogo.dados())
    for p in d["produtos"]:
        if p["estado"] == "oculto":
            p["estado"] = estado
    catalogo.usar(d)
    app_mod._paginas_prontas.clear()


def _bloco(html, inicio, fim):
    i = html.index(inicio)
    return html[i:html.index(fim, i)]


# ------------------------------------------------------------------ ícones
def test_a_roda_nao_e_um_icone():
    assert "roda" not in icones.NOMES and len(icones.NOMES) >= 10
    with pytest.raises(KeyError):
        icones.svg("roda")
    for nome in icones.NOMES:
        svg = icones.svg(nome)
        assert 'stroke="currentColor"' in svg and 'aria-hidden="true"' in svg and "<img" not in svg, nome
        assert (RAIZ / "static" / "valderez" / "icones" / f"{nome}.svg").stat().st_size < 2_000


def test_item_sem_icone_quebra_na_subida():
    with pytest.raises(KeyError):
        icones.conferir([{"titulo": "Sem ícone"}], "teste")
    with pytest.raises(KeyError):
        icones.conferir([{"titulo": "Roda", "icone": "roda"}], "teste")


@pytest.mark.parametrize("chave", ["compat", "numerologia", "tarot", "comunidade", "astrologia-do-zero", "consulta"])
def test_o_que_voce_recebe_tem_um_icone_por_item_e_nunca_a_roda(ocidental, chave):
    _ligar_todos()
    rota = catalogo.produto(chave)["rota"]
    html = cliente.get(rota, headers=HTML).text
    grade = _bloco(html, '<div class="grade-recebe">', "</section>")
    itens = produtos_ocidental.pagina(chave)["recebe"]
    assert "roda" not in grade and "/static/valderez/roda" not in grade, chave
    assert grade.count('<svg class="icone"') == len(itens), chave
    pedidos = [i["icone"] for i in itens]
    assert len(set(pedidos)) == len(pedidos), (chave, pedidos)  # cada item tem o seu, como no desenho
    for nome in pedidos:
        assert icones.svg(nome) in grade


def test_sinastria_com_os_icones_do_desenho():
    assert [i["icone"] for i in produtos_ocidental.pagina("compat")["recebe"]] == ["venus", "mais", "casa", "estrela"]


def test_lista_do_mapa_com_sol_mercurio_e_cadeado(ocidental):
    html = cliente.get("/mapa", headers=HTML).text
    lista = _bloco(html, '<ul class="itens-dim">', "</ul>")
    assert [i["icone"] for i in textos.da_pagina("mapa", "ocidental")["form"]["itens"]] == ["sol", "mercurio", "cadeado"]
    for nome in ("sol", "mercurio", "cadeado"):
        assert icones.svg(nome) in lista
    assert "roda" not in lista


def test_nenhum_template_usa_a_roda_como_icone_de_lista():
    for f in (RAIZ / "static" / "ocidental").glob("*.html"):
        texto = f.read_text(encoding="utf-8")
        for m in re.finditer(r'class="(ico[^"]*)"[^>]*>\s*\{\{\s*marca\.roda', texto):
            pytest.fail(f"{f.name}: a roda dentro de .{m.group(1)}")


# ------------------------------------------------------------------ colunas de "Todas as leituras"
@pytest.mark.parametrize("n", range(1, 13))
def test_regra_das_colunas_nao_deixa_cartao_sozinho(n):
    c = catalogo.colunas(n)
    assert 1 <= c <= 4
    assert n <= c or n % c != 1, (n, c)


@pytest.mark.parametrize("visiveis", [3, 4, 5])
def test_leituras_sem_cartao_sozinho(ocidental, visiveis):
    d = copy.deepcopy(catalogo.dados())
    for i, p in enumerate(d["produtos"]):
        p["estado"] = "em_breve" if i < visiveis else "oculto"
    d["produtos"][0]["estado"] = "ativo"
    catalogo.usar(d)
    app_mod._paginas_prontas.clear()
    html = cliente.get("/leituras").text
    c = int(re.search(r'class="grade-capas" style="--colunas:(\d+)"', html).group(1))
    cartoes = html.count('<div class="cartao capa">')
    assert cartoes == visiveis
    assert cartoes <= c or cartoes % c != 1, (cartoes, c)
    if visiveis == 4:
        assert c == 4  # a tela Produto-Catalogo: os 4 numa linha


def test_grade_usa_a_variavel_e_no_celular_uma_coluna():
    assert "grid-template-columns: repeat(var(--colunas, 3), minmax(0, 1fr))" in CSS
    assert ".tres-passos, .grade-capas { grid-template-columns: 1fr;" in CSS


# ------------------------------------------------------------------ preferências de cookies
@pytest.mark.parametrize("rota", ["/", "/mapa", "/leituras", "/privacidade", "/compatibilidade"])
def test_link_de_preferencias_sempre_no_rodape(ocidental, monkeypatch, rota):
    for k in ("PADMINI_META_PIXEL", "PADMINI_TIKTOK_PIXEL", "PADMINI_GOOGLE_TAG", "PADMINI_POSTHOG_KEY"):
        monkeypatch.delenv(k, raising=False)
    html = cliente.get(rota, headers=HTML).text
    link = re.search(r'<a [^>]*id="preferencias-cookies"[^>]*>', html).group(0)
    assert "hidden" not in link and 'href="/privacidade#cookies"' in link
    assert "Preferências de cookies</a>" in html


def test_sem_pixel_as_preferencias_dizem_que_so_ha_necessarios():
    js = (RAIZ / "static" / "ocidental" / "consentimento.js").read_text(encoding="utf-8")
    assert "function mostrarSoNecessarios" in js and "só cookies necessários" in js
    corpo = js[js.index("function iniciar"):]
    assert corpo.index("linkNoRodape()") < corpo.index("if (!haOQueConsentir()) return;")


@pytest.fixture
def servidor_sem_pixel(monkeypatch):
    import uvicorn
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    for k in ("PADMINI_META_PIXEL", "PADMINI_TIKTOK_PIXEL", "PADMINI_GOOGLE_TAG", "PADMINI_GOOGLE_ADS_LEAD",
              "PADMINI_POSTHOG_KEY"):
        monkeypatch.delenv(k, raising=False)
    app_mod._paginas_prontas.clear()
    s = socket.socket(); s.bind(("127.0.0.1", 0)); porta = s.getsockname()[1]; s.close()
    srv = uvicorn.Server(uvicorn.Config(app_mod.app, port=porta, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True); t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{porta}"
    srv.should_exit = True; t.join(5)
    app_mod._paginas_prontas.clear()


@pytest.mark.skipif(not _chromium(), reason="sem Chromium (roda localmente, não no CI)")
def test_no_navegador_preferencias_e_topo_da_home_no_celular(servidor_sem_pixel):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=_chromium())
        pg = b.new_page(viewport={"width": 390, "height": 844})
        pg.goto(servidor_sem_pixel + "/", wait_until="networkidle")
        assert not pg.query_selector("#aviso-cookies")  # sem pixel, nenhum aviso sozinho
        # topo da home: imagem, depois o cartão da Dona Valderez, depois o olho e o título
        img = pg.locator(".hero-img-cel").bounding_box()
        quem = pg.locator(".hero .quem-mini").bounding_box()
        olho = pg.locator(".hero .olho").bounding_box()
        titulo = pg.locator(".hero h1").bounding_box()
        assert img["y"] + img["height"] <= quem["y"] + 0.5, (img, quem)
        assert quem["y"] + quem["height"] <= olho["y"] and olho["y"] < titulo["y"]
        # preferências de cookies
        pg.click("#preferencias-cookies")
        pg.wait_for_selector("#aviso-cookies")
        assert "só cookies necessários" in pg.inner_text("#aviso-cookies")
        assert pg.url.endswith("/")  # o JS abriu as preferências em vez de seguir o link
        pg.click("[data-cookies-fechar]")
        assert not pg.query_selector("#aviso-cookies")
        b.close()

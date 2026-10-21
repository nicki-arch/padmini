"""
Rodada 18 (17/out/2026): domínio novo (valderezastrologia.com.br), redes da Dona
Valderez e o "Código-fonte" saindo do rodapé para os Termos.

Fase 1 — um lugar só para o endereço do site (enderecos.py + marca.yaml) e o 301 do
domínio antigo, ligado por PADMINI_DOMINIO_PRINCIPAL (sem ela, nada muda).
"""
import re
from pathlib import Path

import pytest

from test_app import app_mod, cliente  # primeiro: define os segredos de teste
import dados_estruturados
import enderecos
import entrega
import sequencias

RAIZ = Path(__file__).resolve().parents[1]
OCIDENTAL = sorted((RAIZ / "static" / "ocidental").glob("*.html"))
HTML = {"accept": "text/html"}
NOVO = "valderezastrologia.com.br"


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    for v in ("PADMINI_CAPTURA", "PADMINI_VENDAS_TESTE", "PADMINI_PAGAMENTO", "PADMINI_DOMINIO_PRINCIPAL"):
        monkeypatch.delenv(v, raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


# ------------------------------------------------------------------ fonte única
@pytest.mark.parametrize("arquivo", OCIDENTAL, ids=lambda p: p.name)
def test_template_ocidental_sem_dominio_nem_contato_escritos_a_mao(arquivo):
    texto = arquivo.read_text(encoding="utf-8")
    assert "padmini.com.br" not in texto, f"{arquivo.name}: use {{{{ site }}}} / {{{{ site_host }}}}"
    assert "pedrosperbmonteiro" not in texto, f"{arquivo.name}: use {{{{ contato }}}}"


def test_um_endereco_so_para_o_site():
    # nos testes, PADMINI_SITE_URL = https://padmini.teste (test_app): vence o marca.yaml
    assert enderecos.SITE_URL == entrega.SITE_URL == dados_estruturados.SITE == "https://padmini.teste"
    assert enderecos.SITE_HOST == "padmini.teste"
    assert app_mod._jinja.globals["site"] == enderecos.SITE_URL


def test_contato_vem_do_marca_yaml(monkeypatch):
    assert enderecos.CONTATO == "contato@pedrosperbmonteiro.com.br"  # muda só quando a caixa nova existir
    monkeypatch.delenv("PADMINI_EMAIL_RESPOSTA", raising=False)
    assert sequencias.responder_para() == enderecos.CONTATO
    monkeypatch.setenv("PADMINI_EMAIL_RESPOSTA", "outra@exemplo.com")
    assert sequencias.responder_para() == "outra@exemplo.com"


@pytest.mark.parametrize("rota", ["/", "/mapa", "/compatibilidade", "/numerologia", "/tarot"])
def test_canonical_e_og_usam_o_endereco_do_site(ocidental, rota):
    html = cliente.get(rota, headers=HTML).text
    caminho = "/" if rota == "/" else rota
    assert f'<link rel="canonical" href="https://padmini.teste{caminho}">' in html
    assert f'<meta property="og:url" content="https://padmini.teste{caminho}">' in html
    assert '<meta property="og:image" content="https://padmini.teste/static/og-oc-' in html


def test_sitemap_robots_e_json_ld_usam_o_endereco_do_site(ocidental):
    assert "<loc>https://padmini.teste/mapa</loc>" in cliente.get("/sitemap.xml").text
    assert "Sitemap: https://padmini.teste/sitemap.xml" in cliente.get("/robots.txt").text
    assert '"url":"https://padmini.teste/"' in cliente.get("/", headers=HTML).text


def test_contato_e_dominio_nas_paginas(ocidental):
    for rota in ("/", "/minhas-leituras", "/termos", "/privacidade"):
        html = cliente.get(rota, headers=HTML).text
        assert f"mailto:{enderecos.CONTATO}" in html or enderecos.CONTATO in html, rota
    assert "Valderez Astrologia (padmini.teste)" in cliente.get("/termos", headers=HTML).text
    assert 'fillText("padmini.teste"' in cliente.get("/compatibilidade", headers=HTML).text


# ------------------------------------------------------------------ redirecionamento
@pytest.mark.parametrize("host", ["padmini.com.br", "www.padmini.com.br", "www.valderezastrologia.com.br"])
def test_destino_301(monkeypatch, host):
    monkeypatch.setenv("PADMINI_DOMINIO_PRINCIPAL", NOVO)
    assert (enderecos.destino_301("GET", host, "/mapa", "utm_source=tiktok")
            == f"https://{NOVO}/mapa?utm_source=tiktok")
    assert enderecos.destino_301("HEAD", host + ":443", "/", "") == f"https://{NOVO}/"


@pytest.mark.parametrize("metodo,host,caminho", [
    ("GET", NOVO, "/mapa"),                          # já no principal
    ("GET", "padmini.onrender.com", "/mapa"),        # o ping diário chega por aqui
    ("GET", "padmini.com.br", "/webhook/stripe"),    # webhook: nunca
    ("GET", "padmini.com.br", "/api/config"),        # API: nunca
    ("POST", "padmini.com.br", "/mapa"),             # POST não sobrevive a 301
    ("GET", "outro.com.br", "/mapa"),                # host que não conhecemos
])
def test_sem_301(monkeypatch, metodo, host, caminho):
    monkeypatch.setenv("PADMINI_DOMINIO_PRINCIPAL", NOVO)
    assert enderecos.destino_301(metodo, host, caminho, "") is None


def test_sem_a_variavel_nada_redireciona(monkeypatch):
    monkeypatch.delenv("PADMINI_DOMINIO_PRINCIPAL", raising=False)
    assert enderecos.destino_301("GET", "padmini.com.br", "/mapa", "") is None
    monkeypatch.setenv("PADMINI_DOMINIO_PRINCIPAL", "https://valderezastrologia.com.br/")  # digitado com esquema
    assert enderecos.dominio_principal() == NOVO


def test_301_no_app_preserva_caminho_e_query(monkeypatch, ocidental):
    monkeypatch.setenv("PADMINI_DOMINIO_PRINCIPAL", NOVO)
    for caminho in ("/mapa?utm_source=tiktok", "/mapa?token=oc-abc.def&utm_source=email&x=%C3%A9", "/"):
        r = cliente.get(caminho, headers={"host": "padmini.com.br"}, follow_redirects=False)
        assert r.status_code == 301, caminho
        assert r.headers["location"] == f"https://{NOVO}{caminho}"
        assert r.headers["strict-transport-security"].startswith("max-age=")  # o 301 sai com os cabeçalhos


def test_webhook_e_api_no_dominio_antigo_respondem_como_hoje(monkeypatch, ocidental):
    sem = cliente.post("/webhook/stripe", content=b"{}", headers={"host": "padmini.com.br"}).status_code
    monkeypatch.setenv("PADMINI_DOMINIO_PRINCIPAL", NOVO)
    com = cliente.post("/webhook/stripe", content=b"{}", headers={"host": "padmini.com.br"},
                       follow_redirects=False).status_code
    assert com == sem and com not in (301, 302, 307, 308)
    r = cliente.get("/api/config", headers={"host": "padmini.com.br"}, follow_redirects=False)
    assert r.status_code == 200


def test_sem_a_variavel_o_dominio_antigo_abre_normal(ocidental):
    r = cliente.get("/mapa", headers={"host": "padmini.com.br", **HTML}, follow_redirects=False)
    assert r.status_code == 200


# ------------------------------------------------------------------ smoke
def _smoke(monkeypatch, base):
    from test_smoke import smoke
    monkeypatch.setattr(smoke, "BASE", base)
    return smoke


def _checagem(smoke, trecho):
    return next(f for n, f in smoke.CHECAGENS if trecho in n)


def test_smoke_no_dominio_antigo_nao_confere_o_301(monkeypatch):
    smoke = _smoke(monkeypatch, "https://padmini.com.br")
    monkeypatch.setattr(smoke, "_sem_seguir", lambda *a, **k: pytest.fail("não devia chamar"))
    assert _checagem(smoke, "o antigo redireciona")() and _checagem(smoke, "/webhook/* no domínio antigo")()
    assert not _smoke(monkeypatch, "https://padmini.onrender.com")._dominio_novo_no_ar()


def test_smoke_no_dominio_novo_confere_301_com_caminho_e_query(monkeypatch):
    smoke = _smoke(monkeypatch, f"https://{NOVO}")
    vistos = []

    def certo(url, corpo=None, timeout=90):
        vistos.append(url)
        caminho = url.split(".com.br", 1)[1]
        return (401, "") if "/webhook/" in caminho else (301, f"https://{NOVO}{caminho}")
    monkeypatch.setattr(smoke, "_sem_seguir", certo)
    assert _checagem(smoke, "o antigo redireciona")() and _checagem(smoke, "/webhook/* no domínio antigo")()
    assert "https://www.padmini.com.br/mapa?utm_source=tiktok&utm_campaign=smoke" in vistos

    # perdeu a query (ou redirecionou o webhook) = falha
    monkeypatch.setattr(smoke, "_sem_seguir", lambda url, corpo=None, timeout=90: (301, f"https://{NOVO}/"))
    assert not _checagem(smoke, "o antigo redireciona")()
    assert not _checagem(smoke, "/webhook/* no domínio antigo")()


# ================================================================== Fase 2 — redes
TODAS = {"Instagram": "https://www.instagram.com/astrologiavalderez_/",
         "TikTok": "https://www.tiktok.com/@astrologiavalderez",
         "YouTube": "https://www.youtube.com/@astrologiavalderez"}
# rodada 20.1: o Instagram de volta, com o endereço certo (sublinhado no fim)
REDES = dict(TODAS)


def test_redes_no_marca_yaml():
    assert {r["nome"]: r["url"] for r in enderecos.TODAS_AS_REDES} == TODAS
    assert {r["nome"]: r["url"] for r in enderecos.REDES} == REDES
    assert {r["nome"]: r["arroba"] for r in enderecos.TODAS_AS_REDES} == {
        "Instagram": "@astrologiavalderez_", "TikTok": "@astrologiavalderez", "YouTube": "@astrologiavalderez"}


def _rodape(html):
    return html[html.index('<footer class="rod">'):]


@pytest.mark.parametrize("rota", ["/", "/mapa", "/compatibilidade", "/termos", "/minhas-leituras"])
def test_redes_no_rodape(ocidental, rota):
    rod = _rodape(cliente.get(rota, headers=HTML).text)
    for nome, url in REDES.items():
        assert f'<a href="{url}" rel="noopener" aria-label="{nome} da Dona Valderez"><svg class="icone"' in rod, (rota, nome)
    assert 'target="_blank"' not in rod  # mesma aba (no celular, abre o app)


def test_redes_no_quem_revisa_da_home(ocidental):
    html = cliente.get("/", headers=HTML).text
    quem = html[html.index('id="quem-revisa"'):]
    quem = quem[:quem.index("</section>")]
    assert "Acompanhe a Dona Valderez" in quem
    for nome, url in REDES.items():
        assert f'<a href="{url}" rel="noopener">' in quem and f"<span>{nome}</span>" in quem


def test_redes_sem_embed_nem_script_de_terceiros(ocidental):
    html = cliente.get("/", headers=HTML).text
    for dominio in ("instagram.com", "tiktok.com", "youtube.com"):
        for tag in re.findall(r"<(?:script|iframe|img|link|embed|object)\b[^>]*>", html):
            assert dominio not in tag, tag
    csp = cliente.get("/", headers=HTML).headers["content-security-policy"]
    assert "instagram" not in csp and "youtube" not in csp


def test_json_ld_same_as(ocidental):
    import json
    html = cliente.get("/", headers=HTML).text
    bloco = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
    org = next(g for g in json.loads(bloco)["@graph"] if g["@type"] == "Organization")
    assert org["sameAs"] == list(REDES.values())


def test_icones_das_redes_no_traco_do_pacote():
    import icones
    for nome in ("instagram", "tiktok", "youtube"):
        svg = icones.svg(nome)
        assert 'stroke="currentColor"' in svg and 'stroke-width="1.4"' in svg and 'fill="none"' in svg


# ================================================================== Fase 3 — rodapé e Termos
CODIGO = "github.com/nicki-arch/padmini"


@pytest.mark.parametrize("rota", ["/", "/mapa", "/termos", "/privacidade", "/minhas-leituras", "/leituras"])
def test_rodape_sem_codigo_fonte(ocidental, rota):
    rod = _rodape(cliente.get(rota, headers=HTML).text)
    assert CODIGO not in rod and "Código-fonte" not in rod, rota


def test_termos_tem_a_secao_de_software_livre(ocidental):
    html = cliente.get("/termos", headers=HTML).text
    corpo = html[:html.index('<footer class="rod">')]
    assert '<h2 id="s13">13. Software livre</h2>' in corpo and 'href="#s13"' in corpo
    assert ("Os cálculos usam o Swiss Ephemeris, sob a licença AGPL-3.0. O código-fonte deste site está em "
            f'<a href="https://{CODIGO}" rel="noopener">{CODIGO}</a>.') in corpo
    assert "Última atualização: 17 de outubro de 2026." in corpo


def test_termos_com_a_cakto_tambem_tem_software_livre(ocidental, monkeypatch):
    monkeypatch.setenv("PADMINI_PAGAMENTO", "cakto")
    html = cliente.get("/termos", headers=HTML).text
    assert '<h2 id="s13">13. Software livre</h2>' in html and "17 de outubro de 2026" in html


@pytest.mark.parametrize("aberta", [True, False])
def test_lista_de_espera_no_rodape_so_com_a_venda_fechada(ocidental, aberta):
    import catalogo
    dados = dict(catalogo.dados(), vendas_abertas=aberta)
    catalogo.usar(dados)
    app_mod._paginas_prontas.clear()
    rod = _rodape(cliente.get("/mapa", headers=HTML).text)
    assert ('<a href="/lista">Lista de espera</a>' in rod) is (not aberta)


def test_vedica_nao_muda(monkeypatch):
    """As páginas antigas da védica ficam como estão (a foto inteira é o test_sistema)."""
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    app_mod._paginas_prontas.clear()
    html = cliente.get("/", headers=HTML).text
    assert "astrologiavalderez" not in html
    app_mod._paginas_prontas.clear()

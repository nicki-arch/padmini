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

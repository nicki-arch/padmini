"""
Rodada 15, Fase 1: o estado do site no banco (config_site), com o YAML como padrão.

Precedência, chave a chave: o que o painel salvou → catalogo.yaml / PADMINI_CAPTURA → aberto.
Sem nada salvo, o site fica idêntico ao de antes. Cache de 15 s; banco fora do ar = último
estado conhecido + alerta. Páginas escondidas: 404 e fora de menu, rodapé e sitemap.
"""
import os

import pytest

from test_app import app_mod, cliente  # primeiro: define os segredos de teste
import alertas
import catalogo
import db
import estado_site

HTML = {"accept": "text/html"}
TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
precisa_banco = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL não definida")
pytestmark = pytest.mark.catalogo_real  # o catálogo como está no ar (venda aberta, só o mapa ativo)


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    for v in ("PADMINI_CAPTURA", "PADMINI_VENDAS_TESTE", "PADMINI_DOMINIO_PRINCIPAL", "DATABASE_URL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_" + "a" * 20)  # produção
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_live_" + "b" * 20)
    estado_site.esquecer()
    app_mod._paginas_prontas.clear()
    yield
    estado_site.esquecer()
    app_mod._paginas_prontas.clear()


@pytest.fixture
def banco(monkeypatch, ocidental):
    monkeypatch.setenv("DATABASE_URL", TEST_URL)
    assert db.iniciar()
    with db._conectar() as c:
        c.execute("TRUNCATE config_site, config_site_historico")
    estado_site.esquecer()
    yield
    with db._conectar() as c:
        c.execute("TRUNCATE config_site, config_site_historico")
    estado_site.esquecer()


def salvar(**mudancas):
    """Grava como o painel grava (e invalida o cache deste processo)."""
    feitas = db.gravar_config_site(mudancas, "Teste")
    estado_site.invalidar()
    return feitas


def _get(rota, **kw):
    return cliente.get(rota, headers=HTML, follow_redirects=False, **kw)


# ------------------------------------------------------------------ sem nada salvo = como antes
def test_sem_banco_vale_o_yaml(ocidental):
    assert estado_site.salvo() == {}
    assert estado_site.modo() == "aberto"
    assert catalogo.vendas_abertas() is True  # catalogo.yaml: vendas_abertas: true
    assert catalogo.estado("mapa") == "ativo" and catalogo.estado("previsao") == "oculto"
    assert [p["estado"] for p in catalogo.produtos()] == [p["estado"] for p in catalogo.produtos_do_yaml()]
    assert all(estado_site.pagina_visivel(r) for r in ("/blog", "/links", "/leituras", "/", "/termos"))


def test_sem_banco_a_captura_continua_valendo(ocidental, monkeypatch):
    monkeypatch.setenv("PADMINI_CAPTURA", "1")
    assert estado_site.modo() == "lista_espera"
    r = _get("/")
    assert r.status_code == 302 and r.headers["location"] == "/lista"


@precisa_banco
def test_banco_vazio_e_igual_a_sem_banco(banco):
    assert estado_site.salvo() == {}
    assert estado_site.modo() == "aberto" and catalogo.vendas_abertas()
    assert _get("/").status_code == 200 and _get("/seu-ano").status_code == 404


# ------------------------------------------------------------------ precedência
@precisa_banco
def test_o_painel_vence_o_yaml_e_a_variavel(banco, monkeypatch):
    monkeypatch.setenv("PADMINI_CAPTURA", "1")
    salvar(modo="aberto", vendas_abertas=False, **{"produto:compat": "oculto"})
    assert estado_site.modo() == "aberto"  # o painel vence o PADMINI_CAPTURA
    assert catalogo.vendas_abertas() is False  # o painel vence o catalogo.yaml
    assert catalogo.estado("compat") == "oculto" and catalogo.produto("compat")["estado"] == "oculto"
    assert "compat" not in [p["chave"] for p in catalogo.visiveis()]


@precisa_banco
def test_valor_invalido_no_banco_cai_no_padrao(banco):
    salvar(modo="qualquer", vendas_abertas="sim", **{"produto:mapa": "talvez"})
    assert estado_site.modo() == "aberto" and catalogo.vendas_abertas() is True
    assert catalogo.estado("mapa") == "ativo"


# ------------------------------------------------------------------ os critérios de aceite
@precisa_banco
def test_lista_de_espera_e_volta(banco):
    """Critério 2: lista de espera manda a home para /lista; link com token abre; voltar desfaz."""
    salvar(modo="lista_espera")
    r = _get("/")
    assert r.status_code == 302 and r.headers["location"] == "/lista"
    assert _get("/mapa?token=oc-qualquer").status_code == 200
    assert _get("/lista").status_code == 200
    salvar(modo="aberto")
    assert _get("/").status_code == 200


@precisa_banco
def test_o_seu_ano_oculto_ativo_oculto_sem_deploy(banco):
    """Critério 4: oculto → 404; ativo → página e botão na /links; oculto → 404 de novo."""
    assert _get("/seu-ano").status_code == 404
    assert "/seu-ano" not in _get("/links").text
    salvar(**{"produto:previsao": "ativo"})
    assert _get("/seu-ano").status_code == 200
    assert 'href="/seu-ano?' in _get("/links").text
    assert "/seu-ano" in cliente.get("/sitemap.xml").text
    salvar(**{"produto:previsao": "oculto"})
    assert _get("/seu-ano").status_code == 404
    assert "/seu-ano" not in _get("/links").text


@precisa_banco
def test_venda_fechada_pelo_painel_tira_o_preco(banco):
    assert "R$47" in _get("/mapa").text.replace("&nbsp;", "")
    salvar(vendas_abertas=False)
    html = _get("/mapa").text
    assert "R$47" not in html.replace("&nbsp;", "") and "R$97" not in html


# ------------------------------------------------------------------ cache de 15 s
@precisa_banco
def test_mudanca_de_outro_processo_aparece_em_ate_15_segundos(banco, monkeypatch):
    assert estado_site.modo() == "aberto"
    db.gravar_config_site({"modo": "lista_espera"}, "Outro processo")  # sem invalidar aqui
    assert estado_site.modo() == "aberto"  # ainda no cache
    agora = estado_site.time.monotonic()
    monkeypatch.setattr(estado_site.time, "monotonic", lambda: agora + estado_site.CACHE_SEGUNDOS + 0.1)
    assert estado_site.modo() == "lista_espera"


def test_o_banco_e_lido_no_maximo_a_cada_15_segundos(ocidental, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://falso")
    leituras = []
    monkeypatch.setattr(db, "ler_config_site", lambda: leituras.append(1) or {"modo": "aberto"})
    for _ in range(50):
        estado_site.modo()
    assert len(leituras) == 1


# ------------------------------------------------------------------ banco fora do ar
def test_banco_fora_do_ar_mantem_o_ultimo_estado_e_alerta(ocidental, monkeypatch):
    """Critério 9."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://falso")
    monkeypatch.setattr(db, "ler_config_site", lambda: {"modo": "lista_espera", "vendas_abertas": False})
    assert estado_site.modo() == "lista_espera"

    def caiu():
        raise OSError("banco fora do ar")
    monkeypatch.setattr(db, "ler_config_site", caiu)
    alertas_enviados = []
    monkeypatch.setattr(alertas, "alertar", lambda *a, **k: alertas_enviados.append(a[0]))
    estado_site.invalidar()
    assert estado_site.modo() == "lista_espera" and catalogo.vendas_abertas() is False
    assert alertas_enviados == ["Painel: não consegui ler o estado do site"]
    r = _get("/")
    assert r.status_code == 302  # o site segue de pé, com o último estado


def test_banco_fora_do_ar_sem_estado_conhecido_usa_o_yaml(ocidental, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://falso")

    def caiu():
        raise OSError("banco fora do ar")
    monkeypatch.setattr(db, "ler_config_site", caiu)
    monkeypatch.setattr(alertas, "alertar", lambda *a, **k: None)
    assert estado_site.modo() == "aberto" and catalogo.vendas_abertas() is True
    assert _get("/").status_code == 200


# ------------------------------------------------------------------ páginas escondidas
@precisa_banco
@pytest.mark.parametrize("rota", ["/links", "/leituras"])
def test_pagina_escondida_some(banco, rota):
    assert _get(rota).status_code == 200
    salvar(**{f"pagina:{rota}": False})
    assert _get(rota).status_code == 404
    assert f'href="{rota}"' not in _get("/").text
    assert rota not in cliente.get("/sitemap.xml").text
    salvar(**{f"pagina:{rota}": True})
    assert _get(rota).status_code == 200


@precisa_banco
def test_blog_escondido(banco, monkeypatch):
    import blog
    monkeypatch.setattr(blog, "publicados", lambda: [{"slug": "x", "revisado": True, "titulo": "X"}])
    assert "/blog" in cliente.get("/sitemap.xml").text
    salvar(**{"pagina:/blog": False})
    assert _get("/blog").status_code == 404 and _get("/blog/x").status_code == 404
    assert "/blog" not in cliente.get("/sitemap.xml").text
    assert 'href="/blog"' not in _get("/").text


def test_paginas_que_nunca_se_escondem():
    assert set(estado_site.PAGINAS) == {"/blog", "/links", "/leituras"}
    for rota in ("/", "/termos", "/privacidade", "/lista", "/minhas-leituras", "/painel", "/api/saude"):
        assert rota not in estado_site.PAGINAS


# ------------------------------------------------------------------ histórico
@precisa_banco
def test_historico_grava_de_para_e_quem(banco):
    salvar(modo="lista_espera")
    salvar(modo="lista_espera")  # igual: não vira linha
    salvar(modo="aberto")
    h = db.historico_config_site()
    assert [(x["chave"], x["de"], x["para"], x["quem"]) for x in h] == [
        ("modo", "lista_espera", "aberto", "Teste"), ("modo", None, "lista_espera", "Teste")]


# ------------------------------------------------------------------ cache de páginas acompanha o estado
@precisa_banco
def test_cache_de_paginas_se_esvazia_quando_o_estado_muda(banco):
    _get("/leituras")
    assert app_mod._paginas_prontas
    salvar(**{"produto:compat": "oculto"})
    html = _get("/leituras").text
    assert "/compatibilidade" not in html

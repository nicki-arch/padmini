"""
Rodada 15, Fase 2: os quatro modos (aberto, lista de espera, manutenção, tudo liberado).

O que este arquivo protege, acima de tudo: o "tudo liberado" da PRODUÇÃO vale só para o
navegador logado no painel. O público não vê nada a mais, nem pelo cache de páginas, nem
pelo /api/config, nem pelo sitemap; e a leitura completa sem pagar nunca é do público.
"""
import re

import pytest

from test_app import app_mod, cliente  # primeiro: define os segredos de teste
import alertas
import catalogo
import db
import estado_site
import painel

SENHA = "uma-senha-bem-longa-de-teste"
ANA = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30", "lat": -23.5505, "lon": -46.6333, "cidade": "São Paulo"}
pytestmark = pytest.mark.catalogo_real


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    for v in ("PADMINI_CAPTURA", "PADMINI_VENDAS_TESTE", "PADMINI_DOMINIO_PRINCIPAL", "DATABASE_URL",
              "RESEND_API_KEY", "PADMINI_PREVIA_CHAVE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("PADMINI_PAINEL_SENHA", SENHA)
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    monkeypatch.setattr(alertas, "alertar", lambda *a, **k: None)
    monkeypatch.setattr(db, "amostras_enviadas_hoje", lambda e: 0)
    monkeypatch.setattr(db, "registrar_amostra_email", lambda *a, **k: True)
    estado_site.esquecer()
    app_mod._paginas_prontas.clear()
    yield
    estado_site.esquecer()
    app_mod._paginas_prontas.clear()


@pytest.fixture
def producao(base, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_" + "a" * 20)
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_live_" + "b" * 20)
    assert estado_site.ambiente() == "producao"


@pytest.fixture
def previa(base, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_" + "a" * 20)
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_" + "b" * 20)
    assert estado_site.ambiente() == "previa"


def modo(monkeypatch, valor, **outros):
    """O que o painel teria salvo (sem banco: o estado_site lê daqui)."""
    monkeypatch.setattr(estado_site, "salvo", lambda: {"modo": valor, **outros})
    app_mod._paginas_prontas.clear()


def logado(so_para_mim=False):
    valor, _ = painel.emitir_sessao("Nicolas")
    cookie = f"{painel.COOKIE}={valor}"
    if so_para_mim:
        cookie += f"; {painel.COOKIE_SO_PARA_MIM}=1"
    return {"cookie": cookie}


def get(rota, equipe=None, **kw):
    return cliente.get(rota, headers={"accept": "text/html", **(equipe or {})}, follow_redirects=False, **kw)


# ------------------------------------------------------------------ manutenção (critério 3)
@pytest.mark.parametrize("rota", ["/", "/mapa", "/leituras", "/links", "/blog", "/compatibilidade", "/lista"])
def test_manutencao_publico_recebe_503(producao, monkeypatch, rota):
    modo(monkeypatch, "manutencao")
    r = get(rota)
    assert r.status_code == 503 and r.headers["retry-after"] == "300"
    assert "Voltamos" in r.text and "noindex" in r.text


@pytest.mark.parametrize("rota", ["/api/saude", "/termos", "/privacidade", "/live", "/minhas-leituras",
                                  "/robots.txt", "/sitemap.xml", "/mapa?token=oc-qualquer"])
def test_manutencao_deixa_de_pe_o_que_nao_pode_cair(producao, monkeypatch, rota):
    modo(monkeypatch, "manutencao")
    assert get(rota).status_code == 200, rota


def test_manutencao_webhook_e_link_pago_funcionam(producao, monkeypatch):
    modo(monkeypatch, "manutencao")
    r = cliente.post("/webhook/stripe", content=b"{}")
    assert r.status_code != 503  # sem assinatura: recusa como sempre, mas não é a manutenção
    r = cliente.post("/api/ocidental/mapa", json={**ANA, "nivel": "completo", "token": "oc-errado"})
    assert r.status_code == 402  # a API do link pago responde (aqui, token errado)


def test_manutencao_nao_abre_pedido_novo(producao, monkeypatch):
    modo(monkeypatch, "manutencao")
    r = cliente.post("/api/checkout", json={"produto": "mapa"})
    assert r.status_code == 503 and r.json()["detail"].startswith("Estamos em manutenção")


def test_manutencao_logado_ve_o_site(producao, monkeypatch):
    modo(monkeypatch, "manutencao")
    assert get("/", logado()).status_code == 200


def test_manutencao_some_ao_voltar_para_aberto(producao, monkeypatch):
    modo(monkeypatch, "manutencao")
    assert get("/").status_code == 503
    modo(monkeypatch, "aberto")
    assert get("/").status_code == 200


# ------------------------------------------------------------------ lista de espera
def test_lista_de_espera_logado_passa(producao, monkeypatch):
    modo(monkeypatch, "lista_espera")
    assert get("/").status_code == 302
    assert get("/", logado()).status_code == 200


# ------------------------------------------------------------------ tudo liberado na PRODUÇÃO (critério 5)
def test_producao_publico_ve_o_normal(producao, monkeypatch):
    modo(monkeypatch, "tudo_liberado")
    assert estado_site.tudo_liberado_global() is False
    assert get("/seu-ano").status_code == 404
    assert "faixa-teste" not in get("/").text
    assert "/seu-ano" not in cliente.get("/sitemap.xml").text
    assert "X-Robots-Tag" not in get("/").headers
    r = cliente.post("/api/ocidental/mapa", json={**ANA, "nivel": "completo"})
    assert r.status_code == 402


@pytest.mark.parametrize("rota", ["/seu-ano", "/numerologia", "/tarot", "/compatibilidade", "/comunidade"])
def test_producao_logado_ve_tudo_com_a_faixa(producao, monkeypatch, rota):
    modo(monkeypatch, "tudo_liberado")
    r = get(rota, logado())
    assert r.status_code == 200, rota
    assert "Modo teste:</b> só você está vendo assim" in r.text
    assert r.headers["x-robots-tag"] == "noindex, nofollow" and r.headers["cache-control"] == "no-store"


def test_producao_logado_le_o_completo_sem_pagar(producao, monkeypatch):
    modo(monkeypatch, "tudo_liberado")
    r = cliente.post("/api/ocidental/mapa", json={**ANA, "nivel": "completo"}, headers=logado())
    assert r.status_code == 200 and r.json()["dimensoes"]


def test_producao_logado_nao_compra_o_que_o_publico_nao_compra(producao, monkeypatch):
    """O modo teste mostra "O seu ano", mas não abre a venda dele (a venda real não abre por aqui)."""
    modo(monkeypatch, "tudo_liberado")
    html = get("/seu-ano", logado()).text
    assert "R$47" not in html.replace("&nbsp;", "")
    r = cliente.post("/api/checkout", json={"produto": "previsao", "pessoa": ANA, "email": "a@teste.com"},
                     headers=logado())
    assert r.status_code == 404


def test_nada_do_modo_teste_vaza_para_o_cache_nem_para_o_config(producao, monkeypatch):
    modo(monkeypatch, "tudo_liberado")
    for rota in ("/", "/seu-ano", "/numerologia", "/leituras", "/links"):
        get(rota, logado())
    assert not any("faixa-teste" in html for html in app_mod._paginas_prontas.values())
    # e o público, logo depois, recebe o site normal
    assert get("/seu-ano").status_code == 404
    assert "faixa-teste" not in get("/").text and "faixa-teste" not in get("/links").text
    assert "/seu-ano" not in get("/links").text
    cfg_publico = cliente.get("/api/config").json()
    cfg_logado = cliente.get("/api/config", headers=logado()).json()
    assert cfg_publico == cfg_logado


def test_so_para_mim_sem_mudar_o_modo(producao, monkeypatch):
    modo(monkeypatch, "aberto")
    assert get("/seu-ano", logado()).status_code == 404  # logado, mas sem pedir
    r = get("/seu-ano", logado(so_para_mim=True))
    assert r.status_code == 200 and "faixa-teste" in r.text
    assert get("/seu-ano").status_code == 404


def test_cookie_so_para_mim_sem_sessao_nao_libera(producao, monkeypatch):
    modo(monkeypatch, "tudo_liberado")
    assert get("/seu-ano", {"cookie": f"{painel.COOKIE_SO_PARA_MIM}=1"}).status_code == 404
    assert get("/seu-ano", {"cookie": f"{painel.COOKIE}=Nicolas|123.abc"}).status_code == 404


def test_amostra_logado_traz_o_link_do_completo(producao, monkeypatch):
    modo(monkeypatch, "tudo_liberado")
    r = cliente.post("/api/ocidental/mapa", json={**ANA, "nivel": "amostra", "email": "a@teste.com"},
                     headers=logado())
    link = r.json()["link_completo"]
    assert link.startswith("/mapa?") and "token=oc-" in link
    r = cliente.post("/api/ocidental/mapa", json={**ANA, "nivel": "amostra", "email": "a@teste.com"})
    assert "link_completo" not in r.json()


def test_link_do_completo_do_modo_teste_e_um_token_de_verdade(producao, monkeypatch):
    modo(monkeypatch, "tudo_liberado")
    link = cliente.post("/api/ocidental/mapa", json={**ANA, "nivel": "amostra", "email": "a@teste.com"},
                        headers=logado()).json()["link_completo"]
    token = re.search(r"token=([^&]+)", link).group(1)
    modo(monkeypatch, "aberto")
    r = cliente.post("/api/ocidental/mapa", json={**ANA, "nivel": "completo", "token": token})
    assert r.status_code == 200


# ------------------------------------------------------------------ tudo liberado na PRÉVIA (critério 6)
def test_previa_tudo_liberado_para_todo_mundo(previa, monkeypatch):
    modo(monkeypatch, "tudo_liberado")
    assert estado_site.tudo_liberado_global()
    r = get("/seu-ano")
    assert r.status_code == 200 and r.headers["x-robots-tag"] == "noindex, nofollow"
    assert "faixa-teste" not in r.text  # a faixa é do navegador logado
    assert catalogo.vendas_abertas() and catalogo.vende("previsao") and catalogo.vende("tarot")
    assert all(p["estado"] == "ativo" for p in catalogo.produtos())


def test_previa_tudo_liberado_publico_paga_para_ler(previa, monkeypatch):
    """Na prévia o teste é a compra de teste (4242, Pix): o completo continua pedindo token."""
    modo(monkeypatch, "tudo_liberado")
    assert cliente.post("/api/ocidental/mapa", json={**ANA, "nivel": "completo"}).status_code == 402


def test_previa_tudo_liberado_mostra_rascunhos_do_blog(previa, monkeypatch):
    import blog
    if not blog.todos():
        pytest.skip("sem artigos no conteúdo privado")
    artigo = dict(blog.todos()[0], revisado=False)
    monkeypatch.setattr(blog, "artigo", lambda slug: artigo if slug == artigo["slug"] else None)
    modo(monkeypatch, "aberto")
    assert get(f"/blog/{artigo['slug']}").status_code == 404
    modo(monkeypatch, "tudo_liberado")
    r = get(f"/blog/{artigo['slug']}")
    assert r.status_code == 200 and r.headers["x-robots-tag"].startswith("noindex")


def test_previa_em_aberto_e_igual_a_producao(previa, monkeypatch):
    modo(monkeypatch, "aberto")
    assert get("/seu-ano").status_code == 404 and not estado_site.liberado()


# ------------------------------------------------------------------ sem senha, sem painel
def test_sem_senha_o_cookie_nao_vale(producao, monkeypatch):
    modo(monkeypatch, "tudo_liberado")
    cab = logado()
    monkeypatch.delenv("PADMINI_PAINEL_SENHA")
    assert get("/seu-ano", cab).status_code == 404


def test_trocar_a_senha_derruba_as_sessoes(producao, monkeypatch):
    modo(monkeypatch, "tudo_liberado")
    cab = logado()
    monkeypatch.setenv("PADMINI_PAINEL_SENHA", SENHA + "-nova")
    assert get("/seu-ano", cab).status_code == 404

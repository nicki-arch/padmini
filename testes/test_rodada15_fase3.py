"""
Rodada 15, Fase 3: a tela /painel.

Acesso (senha de 16+ caracteres, sem ela 404; sessão de 12 h em cookie HttpOnly, Secure e
SameSite=Strict; CSRF em todo POST; 5 senhas erradas por IP em 15 min bloqueiam) e as ações
(modo, venda com ABRIR e a trava do preço, produtos, páginas, só para mim), cada uma no
histórico e num e-mail curto.
"""
import os
import re
from http.cookies import SimpleCookie

import pytest

from test_app import app_mod, cliente  # primeiro: define os segredos de teste
import alertas
import catalogo
import db
import entrega
import estado_site
import ofertas
import painel

SENHA = "uma-senha-bem-longa-de-teste"
TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
precisa_banco = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL não definida")
pytestmark = pytest.mark.catalogo_real


@pytest.fixture
def ligado(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    for v in ("PADMINI_CAPTURA", "PADMINI_VENDAS_TESTE", "DATABASE_URL", "RESEND_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("PADMINI_PAINEL_SENHA", SENHA)
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_" + "a" * 20)
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_live_" + "b" * 20)
    estado_site.esquecer()
    app_mod._paginas_prontas.clear()
    yield
    estado_site.esquecer()
    app_mod._paginas_prontas.clear()


@pytest.fixture
def banco(monkeypatch, ligado):
    monkeypatch.setenv("DATABASE_URL", TEST_URL)
    assert db.iniciar()
    with db._conectar() as c:
        c.execute("TRUNCATE config_site, config_site_historico")
    estado_site.esquecer()
    yield
    with db._conectar() as c:
        c.execute("TRUNCATE config_site, config_site_historico")
    estado_site.esquecer()


@pytest.fixture
def emails(monkeypatch):
    enviados = []
    monkeypatch.setenv("PADMINI_ALERTA_EMAIL", "equipe@teste.com")
    monkeypatch.setattr(entrega, "enviar_email", lambda para, assunto, html, **k: enviados.append(assunto) or True)
    return enviados


def _cookies(resp) -> dict:
    jar = SimpleCookie()
    for linha in resp.headers.get_list("set-cookie"):
        jar.load(linha)
    return {k: v.value for k, v in jar.items()}


def _csrf(html):
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def entrar(senha=SENHA, quem="Nicolas"):
    """Faz o login como um navegador faria. Devolve (cookie da sessão, csrf) ou a resposta."""
    r = cliente.get("/painel")
    pre = _cookies(r)[app_mod.COOKIE_PAINEL_PRE]
    r = cliente.post("/painel/entrar", data={"csrf": _csrf(r.text), "senha": senha, "quem": quem},
                     headers={"cookie": f"{app_mod.COOKIE_PAINEL_PRE}={pre}"}, follow_redirects=False)
    if r.status_code != 303:
        return r
    sessao = _cookies(r)[painel.COOKIE]
    tela = cliente.get("/painel", headers={"cookie": f"{painel.COOKIE}={sessao}"})
    return sessao, _csrf(tela.text)


def acao(sessao, csrf, **form):
    rota = form.pop("_rota", "/painel/acao")
    return cliente.post(rota, data={"csrf": csrf, **form}, headers={"cookie": f"{painel.COOKIE}={sessao}"},
                        follow_redirects=False)


def tela(sessao, extra=""):
    return cliente.get("/painel" + extra, headers={"cookie": f"{painel.COOKIE}={sessao}"}).text


# ------------------------------------------------------------------ acesso
def test_sem_senha_o_painel_nao_existe(ligado, monkeypatch):
    monkeypatch.delenv("PADMINI_PAINEL_SENHA")
    assert cliente.get("/painel").status_code == 404
    assert cliente.post("/painel/entrar", data={"senha": "x"}).status_code == 404


def test_senha_curta_nao_liga(ligado, monkeypatch):
    monkeypatch.setenv("PADMINI_PAINEL_SENHA", "curta")
    assert cliente.get("/painel").status_code == 404


def test_na_vedica_o_painel_nao_existe(ligado, monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    assert cliente.get("/painel").status_code == 404


def test_sem_login_so_o_formulario(ligado):
    r = cliente.get("/painel")
    assert r.status_code == 200 and 'type="password"' in r.text
    for coisa in ("Modo do site", "Produtos", "Últimas mudanças", "Venda"):
        assert coisa not in r.text
    assert r.headers["cache-control"] == "no-store" and "noindex" in r.headers["x-robots-tag"]
    assert "posthog" not in r.text.lower() and "consentimento.js" not in r.text
    assert "/painel" not in cliente.get("/sitemap.xml").text
    assert "Disallow: /painel" in cliente.get("/robots.txt").text


def test_login_e_o_cookie(ligado):
    r = cliente.get("/painel")
    pre = _cookies(r)[app_mod.COOKIE_PAINEL_PRE]
    r = cliente.post("/painel/entrar", data={"csrf": _csrf(r.text), "senha": SENHA, "quem": "Pedro"},
                     headers={"cookie": f"{app_mod.COOKIE_PAINEL_PRE}={pre}"}, follow_redirects=False)
    assert r.status_code == 303
    linha = next(c for c in r.headers.get_list("set-cookie") if c.startswith(painel.COOKIE + "="))
    for atributo in ("HttpOnly", "Secure", "SameSite=strict", "Max-Age=43200"):
        assert atributo.lower() in linha.lower(), atributo
    sessao = _cookies(r)[painel.COOKIE]
    assert painel.quem_da_sessao(sessao) == "Pedro"
    assert "Sair (Pedro)" in tela(sessao)


def test_login_sem_csrf_e_recusado(ligado):
    assert cliente.post("/painel/entrar", data={"senha": SENHA}).status_code == 403


def test_senha_errada_5_vezes_bloqueia(ligado):
    """Critério 8: a 6ª tentativa (mesmo com a senha certa) espera 15 minutos."""
    for _ in range(5):
        r = entrar("senha-errada-mas-comprida")
        assert r.status_code == 401
    r = entrar(SENHA)
    assert r.status_code == 429 and r.headers["retry-after"] == "900"


def test_post_sem_csrf_e_recusado(ligado):
    sessao, _ = entrar()
    r = cliente.post("/painel/acao", data={"acao": "modo", "valor": "manutencao"},
                     headers={"cookie": f"{painel.COOKIE}={sessao}"})
    assert r.status_code == 403
    r = acao(sessao, "csrf-de-outra-sessao", acao="modo", valor="manutencao")
    assert r.status_code == 403
    assert estado_site.modo() == "aberto"


def test_post_sem_sessao_e_recusado(ligado):
    sessao, csrf = entrar()
    r = cliente.post("/painel/acao", data={"csrf": csrf, "acao": "modo", "valor": "manutencao"})
    assert r.status_code == 401


def test_sessao_vence_em_12_horas(ligado):
    valor, expira = painel.emitir_sessao("Nicolas", agora=1_000_000)
    assert expira == 1_000_000 + 12 * 3600
    assert painel.quem_da_sessao(valor) is None  # venceu há muito tempo


def test_quem_fora_da_lista_nao_entra(ligado):
    valor, _ = painel.emitir_sessao("Nicolas")
    forjado = "Fulano" + valor[len("Nicolas"):]
    assert painel.quem_da_sessao(forjado) is None


# ------------------------------------------------------------------ a tela
@precisa_banco
def test_tela_logado(banco):
    sessao, _ = entrar()
    html = tela(sessao)
    assert "<b>PRODUÇÃO</b> · padmini" in html
    assert "Agora: aberto · venda aberta · 1 produto ativo, 3 em breve, 6 ocultos" in html
    for nome in ("Aberto", "Lista de espera", "Manutenção", "Tudo liberado"):
        assert f"<b>{nome}</b>" in html
    for p in catalogo.produtos_do_yaml():
        assert f'href="{p["rota"]}">{p["nome"]}</a>' in html
    for rota in estado_site.PAGINAS:
        assert f'value="{rota}"' in html
    for proibida in ('value="/termos"', 'value="/"', 'value="/lista"', "/minhas-leituras", "R$", "sk_live"):
        assert proibida not in html, proibida
    assert "Abrir o site como visitante" in html and "janela anônima" in html


def test_previa_mostra_previa(ligado, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_" + "a" * 20)
    sessao, _ = entrar()
    assert "<b>PRÉVIA</b> · teste" in tela(sessao)


# ------------------------------------------------------------------ as ações
@precisa_banco
def test_trocar_o_modo(banco, emails):
    """Critério 2 pelo painel, e o critério 10 (histórico e e-mail)."""
    sessao, csrf = entrar()
    r = acao(sessao, csrf, acao="modo", valor="lista_espera")
    assert r.status_code == 303 and r.headers["location"] == "/painel?feito=1"
    assert "Pronto, já está no ar." in tela(sessao, "?feito=1")
    assert cliente.get("/", headers={"accept": "text/html"}, follow_redirects=False).status_code == 302
    html = tela(sessao)
    assert "<b>Modo do site</b>: padrão → Lista de espera" in html and "Nicolas" in html
    assert len(emails) == 1 and re.fullmatch(r"\[Painel\] Nicolas mudou o site para Lista de espera às \d\d:\d\d",
                                             emails[0])
    acao(sessao, csrf, acao="modo", valor="aberto")
    assert cliente.get("/", headers={"accept": "text/html"}, follow_redirects=False).status_code == 200


@precisa_banco
def test_mudanca_que_nao_muda_nao_vira_historico(banco, emails):
    sessao, csrf = entrar()
    acao(sessao, csrf, acao="modo", valor="manutencao")
    acao(sessao, csrf, acao="modo", valor="manutencao")
    assert len(db.historico_config_site()) == 1 and len(emails) == 1


@precisa_banco
def test_produto_pelo_painel(banco, emails):
    """Critério 4 pelo painel."""
    sessao, csrf = entrar()
    acao(sessao, csrf, acao="produto", chave="previsao", valor="ativo")
    assert cliente.get("/seu-ano").status_code == 200
    assert 'href="/seu-ano?' in cliente.get("/links").text
    acao(sessao, csrf, acao="produto", chave="previsao", valor="oculto")
    assert cliente.get("/seu-ano").status_code == 404
    assert emails[-1].startswith("[Painel] Nicolas mudou O seu ano para Oculto às")


@precisa_banco
def test_fechar_e_abrir_a_venda_na_producao(banco):
    sessao, csrf = entrar()
    acao(sessao, csrf, acao="vendas", valor="fechar")
    assert catalogo.vendas_abertas() is False
    r = acao(sessao, csrf, acao="vendas", valor="abrir")  # sem ABRIR
    assert r.status_code == 409 and "digite ABRIR" in r.text and catalogo.vendas_abertas() is False
    r = acao(sessao, csrf, acao="vendas", valor="abrir", confirmacao="ABRIR")
    assert r.status_code == 303 and catalogo.vendas_abertas() is True


@precisa_banco
def test_venda_nao_abre_com_produto_ativo_sem_preco(banco, monkeypatch):
    """Critério 7: o painel recusa e diz qual produto falta."""
    sessao, csrf = entrar()
    acao(sessao, csrf, acao="vendas", valor="fechar")
    acao(sessao, csrf, acao="produto", chave="tarot", valor="ativo")
    original = ofertas.oferta
    monkeypatch.setattr(ofertas, "oferta", lambda chave, sistema="vedica": {} if chave == "tarot"
                        else original(chave, sistema))
    r = acao(sessao, csrf, acao="vendas", valor="abrir", confirmacao="ABRIR")
    assert r.status_code == 409 and "falta preço no ofertas.yaml para Tarot" in r.text
    assert catalogo.vendas_abertas() is False
    assert "sem preço" in tela(sessao)


@precisa_banco
def test_produto_sem_preco_nao_fica_ativo_com_a_venda_aberta(banco, monkeypatch):
    sessao, csrf = entrar()
    original = ofertas.oferta
    monkeypatch.setattr(ofertas, "oferta", lambda chave, sistema="vedica": {} if chave == "tarot"
                        else original(chave, sistema))
    r = acao(sessao, csrf, acao="produto", chave="tarot", valor="ativo")
    assert r.status_code == 409 and "Tarot não ficou ativo" in r.text
    assert catalogo.estado("tarot") == "em_breve"


def test_na_previa_abrir_nao_pede_a_palavra(ligado, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_" + "a" * 20)
    assert painel.mudancas("vendas", {"valor": "abrir"}) == ({"vendas_abertas": True}, "a venda para aberta")


@precisa_banco
def test_esconder_pagina_pelo_painel(banco):
    sessao, csrf = entrar()
    acao(sessao, csrf, acao="pagina", rota="/leituras", valor="esconder")
    assert cliente.get("/leituras", headers={"accept": "text/html"}).status_code == 404
    acao(sessao, csrf, acao="pagina", rota="/leituras", valor="mostrar")
    assert cliente.get("/leituras").status_code == 200


@pytest.mark.parametrize("rota", ["/", "/termos", "/privacidade", "/lista", "/painel", "/minhas-leituras",
                                  "/api/saude", "/webhook/stripe"])
def test_paginas_que_o_painel_nao_esconde(ligado, rota):
    with pytest.raises(painel.Recusa):
        painel.mudancas("pagina", {"rota": rota, "valor": "esconder"})


def test_acao_desconhecida(ligado):
    for acao_, form in (("apagar", {}), ("modo", {"valor": "festa"}), ("produto", {"chave": "x", "valor": "ativo"})):
        with pytest.raises(painel.Recusa):
            painel.mudancas(acao_, form)


def test_sem_banco_o_painel_avisa_que_nao_salvou(ligado):
    sessao, csrf = entrar()
    r = acao(sessao, csrf, acao="modo", valor="manutencao")
    assert r.status_code == 503 and "não consegue salvar" in r.text
    assert estado_site.modo() == "aberto"


@precisa_banco
def test_banco_caiu_na_hora_de_salvar(banco, monkeypatch):
    sessao, csrf = entrar()

    def caiu(*a, **k):
        raise OSError("fora do ar")
    monkeypatch.setattr(db, "gravar_config_site", caiu)
    r = acao(sessao, csrf, acao="modo", valor="manutencao")
    assert r.status_code == 503 and "Não salvou" in r.text


# ------------------------------------------------------------------ só para mim e sair
def test_so_para_mim_liga_e_desliga(ligado):
    sessao, csrf = entrar()
    r = acao(sessao, csrf, _rota="/painel/so-para-mim", valor="ligar")
    assert r.status_code == 303 and _cookies(r)[painel.COOKIE_SO_PARA_MIM] == "1"
    linha = next(c for c in r.headers.get_list("set-cookie") if c.startswith(painel.COOKIE_SO_PARA_MIM))
    assert "httponly" in linha.lower() and "samesite=strict" in linha.lower()
    cab = {"cookie": f"{painel.COOKIE}={sessao}; {painel.COOKIE_SO_PARA_MIM}=1", "accept": "text/html"}
    assert cliente.get("/seu-ano", headers=cab).status_code == 200
    r = acao(sessao, csrf, _rota="/painel/so-para-mim", valor="desligar")
    assert any(c.startswith(painel.COOKIE_SO_PARA_MIM + '=""') or "Max-Age=0" in c
               for c in r.headers.get_list("set-cookie"))


def test_sair(ligado):
    sessao, csrf = entrar()
    r = acao(sessao, csrf, _rota="/painel/sair")
    assert r.status_code == 303
    assert any(c.startswith(painel.COOKIE + "=") and "Max-Age=0" in c for c in r.headers.get_list("set-cookie"))


# ------------------------------------------------------------------ e-mail
def test_aviso_por_email(ligado, emails):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    painel.avisar("Pedro", "o site para Manutenção", datetime(2026, 10, 18, 14, 3, tzinfo=ZoneInfo("America/Sao_Paulo")))
    assert emails == ["[Painel] Pedro mudou o site para Manutenção às 14:03"]


def test_sem_destinatario_nao_manda(ligado, monkeypatch):
    monkeypatch.delenv("PADMINI_ALERTA_EMAIL", raising=False)
    monkeypatch.setattr(alertas, "destinatarios", lambda: [])
    assert painel.avisar("Pedro", "x") is False

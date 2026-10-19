"""
Rodada 14, Fases 4 e 5: "A sua Lua no ano" no catálogo, no /live e nos cartões.

O produto está oculto e sem preço. A aba do /live e a rota /api/live/ocidental/token/calendario
só existem com o produto ATIVO no estado do site (painel → catalogo.yaml) ou no "tudo
liberado" (prévia: para todos; produção: só no navegador logado no painel). Sem sessão, 401.
Os cartões do mapa e de "O seu ano" só aparecem com o produto ativo E à venda.
"""
import copy

import pytest

from test_app import app_mod, cliente  # primeiro: define os segredos de teste
import acesso
import catalogo
import db
import estado_site
import painel

ANA = {"nome": "Ana", "data": "1994-05-14", "hora": "15:40", "lat": -30.0346, "lon": -51.2177,
       "cidade": "Porto Alegre"}
SENHA_PAINEL = "uma-senha-bem-longa-de-teste"
HTML = {"accept": "text/html"}
pytestmark = pytest.mark.catalogo_real


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    for v in ("PADMINI_CAPTURA", "PADMINI_VENDAS_TESTE", "DATABASE_URL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("PADMINI_PAINEL_SENHA", SENHA_PAINEL)
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_" + "a" * 20)
    registros = []
    monkeypatch.setattr(db, "registrar_live", lambda *a, **k: registros.append(a) or True)
    estado_site.esquecer()
    app_mod._paginas_prontas.clear()
    cliente.cookies.clear()
    yield registros
    estado_site.esquecer()
    app_mod._paginas_prontas.clear()
    cliente.cookies.clear()


def _painel(monkeypatch, **salvo):
    monkeypatch.setattr(estado_site, "salvo", lambda: dict(salvo))


LIVE = {"cookie": f"pad_live={acesso.emitir_sessao('live', 2_000_000_000)}"}


def _logado_no_painel():
    valor, _ = painel.emitir_sessao("Nicolas")
    return f"; {painel.COOKIE}={valor}"


def _token(cab=LIVE, corpo=ANA):
    return cliente.post("/api/live/ocidental/token/calendario", json=corpo, headers=cab)


# ------------------------------------------------------------------ oculto (critério 5)
def test_oculto_404_sem_aba_nem_token(base):
    assert cliente.get("/calendario-lunar", headers=HTML).status_code == 404
    assert 'id="aba-lua"' not in cliente.get("/live").text
    assert _token().status_code == 404


def test_sem_sessao_recusa(base, monkeypatch):
    _painel(monkeypatch, **{"produto:calendario": "ativo"})
    assert cliente.post("/api/live/ocidental/token/calendario", json=ANA).status_code == 401
    assert _token({"cookie": "pad_live=2000000000.assinatura-falsa"}).status_code == 401


# ------------------------------------------------------------------ ligado no painel, sem deploy
def test_ativo_no_painel_liga_pagina_aba_e_token(base, monkeypatch):
    _painel(monkeypatch, **{"produto:calendario": "ativo"})
    assert cliente.get("/calendario-lunar", headers=HTML).status_code == 200
    html = cliente.get("/live").text
    assert 'id="aba-lua"' in html and "/api/live/ocidental/token/calendario" in html
    r = _token()
    assert r.status_code == 200
    t = r.json()
    assert t["token"].startswith("oc-cal-") and len(t["inicio"]) == 7
    assert t["link"] == "/calendario-lunar?token=" + t["token"]
    # o token abre o completo daquele nascimento e daquele ano
    assert acesso.abrir_token_calendario(t["token"])["data"] == ANA["data"]
    d = cliente.post("/api/ocidental/calendario/completo", json={"token": t["token"]}).json()
    assert d["nivel"] == "completo" and d["inicio"][:7] == t["inicio"]
    # e não abre outro produto
    r = cliente.post("/api/ocidental/mapa", json={**ANA, "nivel": "completo", "token": t["token"]})
    assert r.status_code in (402, 422)  # longo demais para o token do mapa, e não é dele
    _painel(monkeypatch, **{"produto:calendario": "oculto"})
    assert 'id="aba-lua"' not in cliente.get("/live").text and _token().status_code == 404


def test_live_nao_registra_dado_de_nascimento(base, monkeypatch):
    _painel(monkeypatch, **{"produto:calendario": "ativo"})
    assert _token().status_code == 200
    (registro,) = base
    assert registro == ("ocidental:calendario", "", "", "")


def test_token_do_live_respeita_o_inicio(base, monkeypatch):
    _painel(monkeypatch, **{"produto:calendario": "ativo"})
    t = _token(corpo={**ANA, "inicio": "2027-01"}).json()
    assert t["inicio"] == "2027-01" and acesso.abrir_token_calendario(t["token"])["inicio"] == "2027-01"


# ------------------------------------------------------------------ tudo liberado (critério 5)
def test_tudo_liberado_na_producao_so_para_o_logado_no_painel(base, monkeypatch):
    _painel(monkeypatch, modo="tudo_liberado")
    assert cliente.get("/calendario-lunar", headers=HTML).status_code == 404
    assert 'id="aba-lua"' not in cliente.get("/live").text and _token().status_code == 404
    cab = {"cookie": LIVE["cookie"] + _logado_no_painel()}
    assert cliente.get("/calendario-lunar", headers={**HTML, "cookie": cab["cookie"]}).status_code == 200
    assert 'id="aba-lua"' in cliente.get("/live", headers=cab).text
    assert _token(cab).status_code == 200
    # o cache de páginas não guardou a versão liberada
    assert cliente.get("/calendario-lunar", headers=HTML).status_code == 404
    assert 'id="aba-lua"' not in cliente.get("/live").text


def test_tudo_liberado_na_previa_para_todos(base, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_" + "a" * 20)
    _painel(monkeypatch, modo="tudo_liberado")
    assert 'id="aba-lua"' in cliente.get("/live").text and _token().status_code == 200


def test_tudo_liberado_nunca_vende_o_calendario(base, monkeypatch):
    """Sem `oferta` no catálogo, nem o "tudo liberado" da prévia abre a venda."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_" + "a" * 20)
    _painel(monkeypatch, modo="tudo_liberado", **{"produto:calendario": "ativo"})
    assert not catalogo.vende("calendario")
    html = cliente.get("/calendario-lunar", headers=HTML).text
    assert 'data-comprar="calendario"' not in html
    r = cliente.post("/api/checkout", json={"produto": "calendario", "pessoa": ANA, "email": "a@b.com"})
    assert r.status_code in (403, 404, 409, 422), r.text


def test_no_live_o_painel_vence_o_yaml(base, monkeypatch):
    dados = copy.deepcopy(catalogo.dados())
    for p in dados["produtos"]:
        if p["chave"] == "calendario":
            p["estado"] = "ativo"
    catalogo.usar(dados)
    _painel(monkeypatch, **{"produto:calendario": "oculto"})
    assert 'id="aba-lua"' not in cliente.get("/live").text and _token().status_code == 404
    _painel(monkeypatch)
    assert 'id="aba-lua"' in cliente.get("/live").text


# ------------------------------------------------------------------ cartões (Fase 4)
def test_cartoes_so_com_o_produto_ativo_e_a_venda(base, monkeypatch):
    _painel(monkeypatch, **{"produto:calendario": "ativo"})
    # ativo, mas sem preço: nada de cartão
    assert 'id="cartao-calendario"' not in cliente.get("/mapa", headers=HTML).text
    monkeypatch.setattr(catalogo, "vende", lambda chave, sistema="ocidental": chave == "calendario")
    app_mod._paginas_prontas.clear()
    assert 'id="cartao-calendario"' in cliente.get("/mapa", headers=HTML).text

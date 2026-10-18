"""
Rodada 15, Fase 4: o /api/config diz o modo do site e o que está ativo PARA O PÚBLICO (nunca
o estado do cookie de quem pede), e o smoke se ajusta ao modo.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from test_app import app_mod, cliente  # primeiro: define os segredos de teste
import estado_site
import painel

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("smoke15", RAIZ / "scripts" / "smoke_producao.py")
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)
pytestmark = pytest.mark.catalogo_real


@pytest.fixture
def producao(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    for v in ("PADMINI_CAPTURA", "PADMINI_VENDAS_TESTE", "DATABASE_URL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("PADMINI_PAINEL_SENHA", "uma-senha-bem-longa-de-teste")
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_" + "a" * 20)
    estado_site.esquecer()
    app_mod._paginas_prontas.clear()
    smoke.AVISOS.clear()
    yield
    estado_site.esquecer()
    smoke.AVISOS.clear()


def _modo(monkeypatch, valor):
    monkeypatch.setattr(estado_site, "salvo", lambda: {"modo": valor})


# ------------------------------------------------------------------ /api/config
def test_config_diz_o_modo_e_os_ativos_do_publico(producao, monkeypatch):
    cfg = cliente.get("/api/config").json()
    assert cfg["modo_site"] == "aberto" and cfg["produtos_ativos"] == ["/mapa"]
    _modo(monkeypatch, "manutencao")
    assert cliente.get("/api/config").json()["modo_site"] == "manutencao"


def test_config_nunca_reflete_o_cookie(producao, monkeypatch):
    _modo(monkeypatch, "tudo_liberado")
    valor, _ = painel.emitir_sessao("Nicolas")
    cab = {"cookie": f"{painel.COOKIE}={valor}; {painel.COOKIE_SO_PARA_MIM}=1"}
    publico, logado = cliente.get("/api/config").json(), cliente.get("/api/config", headers=cab).json()
    assert publico == logado and logado["produtos_ativos"] == ["/mapa"]
    assert "/seu-ano" not in json.dumps(logado)


def test_config_da_vedica_nao_lista_produtos(producao, monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    assert cliente.get("/api/config").json()["produtos_ativos"] == []


def test_config_com_a_captura_antiga(producao, monkeypatch):
    monkeypatch.setenv("PADMINI_CAPTURA", "1")
    assert cliente.get("/api/config").json()["modo_site"] == "lista_espera"


# ------------------------------------------------------------------ o smoke
def _site(monkeypatch, config: dict, paginas: dict | None = None):
    paginas = paginas or {}

    def req(caminho, corpo=None, timeout=90):
        if caminho == "/api/config":
            return 200, json.dumps(config).encode()
        return paginas.get(caminho, (200, b"<html></html>"))
    monkeypatch.setattr(smoke, "req", req)


def test_smoke_le_o_modo(monkeypatch):
    _site(monkeypatch, {"modo_site": "manutencao"})
    assert smoke._modo_site() == "manutencao"
    _site(monkeypatch, {})  # site anterior à rodada 15
    assert smoke._modo_site() == "aberto"


def test_smoke_ativos_vem_do_config(monkeypatch):
    _site(monkeypatch, {"sistema": "ocidental", "produtos_ativos": ["/mapa", "/tarot"]})
    assert smoke._ativo_no_catalogo("/tarot") and not smoke._ativo_no_catalogo("/compatibilidade")


def test_smoke_painel_sem_login(monkeypatch):
    nome, f = next(c for c in smoke.CHECAGENS if c[0].startswith("[painel] /painel sem login"))
    _site(monkeypatch, {}, {"/painel": (404, b"")})
    assert f()
    _site(monkeypatch, {}, {"/painel": (200, b'<input type="password">')})
    assert f()
    _site(monkeypatch, {}, {"/painel": (200, b'<input type="password"> Modo do site')})
    assert not f()


def test_smoke_acao_sem_login(monkeypatch):
    nome, f = next(c for c in smoke.CHECAGENS if c[0].startswith("[painel] ação sem login"))
    _site(monkeypatch, {}, {"/painel/acao": (401, b"")})
    assert f()
    _site(monkeypatch, {}, {"/painel/acao": (303, b"")})
    assert not f()


def test_smoke_publico_sem_modo_teste(monkeypatch):
    nome, f = next(c for c in smoke.CHECAGENS if c[0].startswith("[modo teste]"))
    _site(monkeypatch, {"modo_site": "aberto"})
    assert f()
    _site(monkeypatch, {"modo_site": "aberto"}, {"/": (200, b'<div class="faixa-teste">')})
    assert not f()


def test_smoke_manutencao_tem_as_checagens_do_brief():
    nomes = " ".join(n for n, _ in smoke.CHECAGENS_MANUTENCAO)
    for trecho in ("503", "/api/saude", "token", "webhooks", "402"):
        assert trecho in nomes

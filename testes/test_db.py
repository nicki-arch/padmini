"""
Testes do banco (db.py) e da integração com o webhook e a IA.

Precisam de um Postgres: defina TEST_DATABASE_URL (ex.:
postgresql://postgres@localhost:5432/padmini_teste). Sem ela, são pulados.
No GitHub Actions o workflow sobe um Postgres e define a variável.
"""
import json
import os

import pytest

import test_app as base  # configura o ambiente e o app

TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL não definida")

import app as app_mod  # noqa: E402
import db  # noqa: E402
import entrega  # noqa: E402

# payload no formato da documentação da Cakto (inclui CPF e cartão, que NÃO podem ser gravados)
def evento_cakto(cakto_id="pedido-1", sck=base.SCK_MAPA):
    return {"event": "purchase_approved",
            "data": {"id": cakto_id, "refId": "4852F91", "status": "paid", "offer_type": "main",
                     "amount": 47.0, "fees": 2.49, "paymentMethod": "pix",
                     "customer": {"name": "Ana", "email": "ana@teste.com", "phone": "5551999999999",
                                  "docType": "cpf", "docNumber": "12345678909"},
                     "product": {"id": "p1", "name": "Mapa", "supportEmail": "suporte@padmini.teste"},
                     "offer": {"id": "39dhqty", "price": 47.0},
                     "commissions": [{"user": "produtor@padmini.teste", "type": "producer"}],
                     "card": {"lastDigits": "4242"},
                     "sck": sck, "utm_source": "afiliado", "utm_campaign": "PEDRO"}}


@pytest.fixture(autouse=True)
def banco_limpo(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_URL)
    assert db.iniciar()
    with db._conectar() as c:
        c.execute("TRUNCATE pedidos, textos_ia")
    yield


def _linhas(sql, *args):
    with db._conectar() as c:
        return c.execute(sql, args).fetchall()


def test_webhook_grava_pedido_sem_cpf_nem_cartao():
    r = base._postar_webhook(evento_cakto())
    assert r.status_code == 200, r.text
    rows = _linhas("SELECT cakto_id, produto, email, valor, forma_pagamento, rastreio, "
                   "dados_nascimento, link, row_to_json(pedidos)::text FROM pedidos")
    assert len(rows) == 1
    cakto_id, produto, email, valor, forma, rastreio, nasc, link, tudo = rows[0]
    assert (cakto_id, produto, email, float(valor), forma) == ("pedido-1", "mapa", "ana@teste.com", 47.0, "pix")
    assert rastreio["utm_campaign"] == "PEDRO" and rastreio["sck"].startswith("m~")
    assert nasc["data"] == "1990-05-15"
    assert "token=" in link
    assert "12345678909" not in tudo and "4242" not in tudo


def test_email_do_comprador_e_nao_o_de_suporte():
    r = base._postar_webhook(evento_cakto())
    assert r.json()["email"] == "ana@teste.com"


def test_webhook_repetido_nao_reenvia_email(monkeypatch):
    enviados = []
    monkeypatch.setattr(entrega, "enviar_email", lambda *a, **k: enviados.append(a) or True)
    assert base._postar_webhook(evento_cakto()).status_code == 200
    r2 = base._postar_webhook(evento_cakto())
    assert r2.status_code == 200 and r2.json().get("duplicado") is True
    assert len(enviados) == 1
    assert len(_linhas("SELECT 1 FROM pedidos")) == 1


def test_banco_fora_do_ar_nao_impede_entrega(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://ninguem@127.0.0.1:1/nada")
    r = base._postar_webhook(evento_cakto("pedido-sem-banco"))
    assert r.status_code == 200 and r.json()["link"]


def test_texto_ia_gerado_uma_vez_por_mapa(monkeypatch):
    chamadas = []
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste")
    monkeypatch.setattr(app_mod, "gerar_com_claude", lambda p: chamadas.append(p) or "Texto do mapa.")
    link = base._postar_webhook(evento_cakto()).json()["link"]
    q = base._params(link)
    pedido = {"nome": q["nome"], "data": q["data"], "hora": q["hora"], "lat": float(q["lat"]),
              "lon": float(q["lon"]), "cidade": q["cidade"], "nivel": "completo",
              "token": q["token"], "texto_ia": True}
    for _ in range(3):
        r = base.cliente.post("/api/mapa", json=pedido)
        assert r.status_code == 200 and r.json()["texto_ia"] == "Texto do mapa."
    assert len(chamadas) == 1


def test_sem_database_url_tudo_vira_no_op(monkeypatch):
    monkeypatch.delenv("DATABASE_URL")
    assert db.iniciar() is False
    assert db.texto_ia("x") is None
    assert db.registrar_pedido({}, "mapa", {}, "", "", False) is False
    assert base._postar_webhook(evento_cakto("pedido-2")).status_code == 200


def test_saude_com_banco():
    assert base.cliente.get("/api/saude").json() == {"ok": True, "banco": True}


def test_saude_com_banco_fora(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://ninguem@127.0.0.1:1/nada")
    assert base.cliente.get("/api/saude").json() == {"ok": False, "banco": False}


def test_tabelas_com_rls_ligado():
    """No Supabase, sem RLS a API pública (chave anon) leria os pedidos."""
    rows = _linhas("SELECT relname, relrowsecurity FROM pg_class "
                   "WHERE relname IN ('pedidos', 'textos_ia')")
    assert dict(rows) == {"pedidos": True, "textos_ia": True}

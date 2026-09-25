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
        c.execute("TRUNCATE pedidos, textos_ia, amostras_email, abandonos, email_optout")
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
    assert base.cliente.get("/api/saude").json()["banco"] is True


def test_saude_com_banco_fora(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://ninguem@127.0.0.1:1/nada")
    assert base.cliente.get("/api/saude").json() | {"versao": ""} == {"ok": False, "banco": False, "versao": ""}


def test_tabelas_com_rls_ligado():
    """No Supabase, sem RLS a API pública (chave anon) leria os pedidos."""
    rows = _linhas("SELECT relname, relrowsecurity FROM pg_class "
                   "WHERE relname IN ('pedidos', 'textos_ia')")
    assert dict(rows) == {"pedidos": True, "textos_ia": True}


def test_roles_da_api_publica_sem_acesso():
    """Simula as roles do Supabase: depois do schema, anon/authenticated não leem nada."""
    with db._conectar() as c:
        for role in ("anon", "authenticated"):
            c.execute(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') "
                      f"THEN CREATE ROLE {role} NOLOGIN; END IF; END $$")
            c.execute(f"GRANT ALL ON TABLE pedidos, textos_ia TO {role}")
    assert db.iniciar()
    rows = _linhas("SELECT has_table_privilege('anon','pedidos','SELECT'), "
                   "has_table_privilege('authenticated','textos_ia','INSERT')")
    assert rows[0] == (False, False)


def test_pedido_sem_dados_fica_gravado_para_entrega_manual(monkeypatch):
    import cakto
    monkeypatch.setattr(cakto, "PROD_MAPA", "p1")  # payload traz product.id = "p1"
    r = base._postar_webhook(evento_cakto("pedido-sem-sck", sck=""))
    assert r.status_code == 200 and "pendente" in r.json()
    rows = _linhas("SELECT produto, email, link FROM pedidos WHERE cakto_id = 'pedido-sem-sck'")
    assert rows == [("mapa", "ana@teste.com", None)]


def test_sck_de_outro_produto_fica_gravado_sem_link():
    """Pagou o mapa (oferta 39dhqty) mas o sck traz um casal: não entrega nada
    automaticamente, mas o pedido fica no banco para a equipe entregar o que foi pago."""
    r = base._postar_webhook(evento_cakto("pedido-troca", sck=base.SCK_CASAL))
    assert r.status_code == 200 and "pendente" in r.json()
    rows = _linhas("SELECT produto, link, email_enviado FROM pedidos WHERE cakto_id = 'pedido-troca'")
    assert rows == [("mapa", None, False)]


def test_texto_ia_do_casal_gerado_uma_vez(monkeypatch):
    import acesso
    chamadas = []
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste")
    monkeypatch.setattr(app_mod, "gerar_com_claude", lambda p: chamadas.append(p) or "Texto do casal.")
    a, b = base.PESSOA, base.PESSOA_B
    token = acesso.emitir_token("compat", acesso.chave_compat(
        (a["data"], a["hora"], a["lat"], a["lon"]), (b["data"], b["hora"], b["lat"], b["lon"])))
    pedido = {"a": a, "b": b, "nivel": "completo", "texto_ia": True, "token": token}
    for _ in range(3):
        r = base.cliente.post("/api/compatibilidade", json=pedido)
        assert r.status_code == 200 and r.json()["texto_ia"] == "Texto do casal."
    assert len(chamadas) == 1


def test_lead_gravado_com_consentimentos_e_origem():
    with db._conectar() as c:
        c.execute("TRUNCATE leads")
    r = base.cliente.post("/api/lista", json={
        "nome": "Ana", "email": "Ana@Teste.com", "whatsapp": "(51) 99999-8888",
        "aceita_email": True, "aceita_whatsapp": True, "interesse": "compat",
        "origem": {"ref": "PEDRO", "utm_source": "tiktok", "lixo": "x"}})
    assert r.status_code == 200, r.text
    # mesma pessoa de novo, sem WhatsApp: atualiza em vez de duplicar
    base.cliente.post("/api/lista", json={"email": "ana@teste.com", "aceita_email": True})
    rows = _linhas("SELECT email, whatsapp, aceita_email, aceita_whatsapp, interesse, origem FROM leads")
    assert len(rows) == 1
    email, zap, ae, aw, interesse, origem = rows[0]
    assert (email, zap, ae, interesse) == ("ana@teste.com", "5551999998888", True, "compat")
    assert origem == {"ref": "PEDRO", "utm_source": "tiktok"}


def test_modo_live_registra_cada_leitura(monkeypatch):
    with db._conectar() as c:
        c.execute("TRUNCATE live_geracoes")
    import app as _app
    from fastapi.testclient import TestClient
    monkeypatch.setenv("PADMINI_LIVE_SENHA", "senha-do-pedro-123")
    cl = TestClient(_app.app)
    cl.post("/api/live/entrar", json={"senha": "senha-do-pedro-123"})
    cl.post("/api/live/token/mapa", json=base.PESSOA)
    rows = _linhas("SELECT produto, nome, cidade, nascimento FROM live_geracoes")
    assert rows == [("mapa", "Ana", "São Paulo, SP", "1990-05-15 14:30")]


# ---------------------------------------------------------------- amostra por e-mail / lembrete / abandono
def _amostra(email, horas_atras, aceita=True, produto="mapa"):
    db.registrar_amostra_email(email, produto, base.PESSOA, aceita, {})
    with db._conectar() as c:
        c.execute("UPDATE amostras_email SET criado_em = now() - make_interval(hours => %s) "
                  "WHERE id = (SELECT max(id) FROM amostras_email)", (horas_atras,))


def test_novas_tabelas_com_rls_ligado():
    rows = _linhas("SELECT relname, relrowsecurity FROM pg_class "
                   "WHERE relname IN ('amostras_email', 'abandonos', 'email_optout')")
    assert dict(rows) == {"amostras_email": True, "abandonos": True, "email_optout": True}


def test_lembrete_so_para_quem_autorizou_na_janela_e_nao_comprou():
    _amostra("ok@t.com", 30)                     # entra
    _amostra("cedo@t.com", 2)                    # ainda não fez 24h
    _amostra("velho@t.com", 100)                 # passou de 72h
    _amostra("naoquis@t.com", 30, aceita=False)  # não autorizou
    _amostra("comprou@t.com", 30)
    ev = evento_cakto("pedido-comprou")
    ev["data"]["customer"]["email"] = "comprou@t.com"
    base._postar_webhook(ev)                      # comprou depois da amostra
    _amostra("saiu@t.com", 30)
    db.descadastrar("SAIU@t.com")
    emails = [x["email"] for x in db.lembretes_pendentes()]
    assert emails == ["ok@t.com"]


def test_lembrete_sai_uma_vez_so_por_email():
    _amostra("ok@t.com", 30)
    _amostra("ok@t.com", 40)
    pend = db.lembretes_pendentes()
    assert len(pend) == 1
    db.marcar_lembrete_enviado(pend[0]["id"])
    assert db.lembretes_pendentes() == []


def test_lembretes_ponta_a_ponta(monkeypatch):
    enviados = []
    monkeypatch.setenv("PADMINI_TAREFAS_CHAVE", "k")
    monkeypatch.setattr(entrega, "enviar_email", lambda d, a, h: enviados.append(d) or True)
    _amostra("ok@t.com", 30)
    r = base.cliente.post("/api/tarefas/lembretes", headers={"Authorization": "Bearer k"})
    assert r.json()["enviados"] == 1 and enviados == ["ok@t.com"]
    r = base.cliente.post("/api/tarefas/lembretes", headers={"Authorization": "Bearer k"})
    assert r.json()["enviados"] == 0


def test_limite_de_amostras_por_endereco_conta_24h():
    for _ in range(3):
        _amostra("muito@t.com", 1)
    _amostra("muito@t.com", 30)
    assert db.amostras_enviadas_hoje("MUITO@t.com") == 3


def test_abandono_uma_recuperacao_por_oferta():
    assert db.abandono_ja_tratado("a@t.com", "qo8uskp") is False
    db.registrar_abandono("a@t.com", "Ana", "qo8uskp", "https://pay.cakto.com.br/qo8uskp", True)
    assert db.abandono_ja_tratado("A@t.com", "qo8uskp") is True
    assert db.abandono_ja_tratado("a@t.com", "39dhqty") is False


def test_descadastro_bloqueia_marketing():
    assert db.descadastrado("x@t.com") is False
    assert db.descadastrar("X@t.com")
    assert db.descadastrado("x@T.com") is True

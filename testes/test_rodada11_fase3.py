"""
Rodada 11, Fase 3 — o webhook da Stripe e a entrega (pelo mesmo caminho da Cakto).

Do brief: sem assinatura ou com assinatura errada → 401; evento repetido não entrega duas
vezes; Pix pendente não entrega; async_payment_succeeded entrega; reembolso registra e
alerta; os testes do webhook da Cakto continuam passando (test_app.py, test_db.py).
Os eventos aqui são assinados de verdade (HMAC-SHA256 de "{t}.{corpo}"), como a Stripe faz.
"""
import hashlib
import hmac
import json
import os
import time

import pytest

import test_app as base  # configura o ambiente e o app

import alertas  # noqa: E402
import app as app_mod  # noqa: E402
import db  # noqa: E402
import entrega  # noqa: E402
import pendentes  # noqa: E402
import stripe_api  # noqa: E402

cliente = base.cliente
SEGREDO = "whsec_" + "teste" * 6
TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL não definida")

PESSOA = {"nome": "Ana Clara", "data": "1990-05-15", "hora": "14:30", "lat": -30.0331, "lon": -51.23,
          "cidade": "Porto Alegre, RS"}


def assinar(corpo: bytes, segredo: str = SEGREDO, t: int | None = None) -> str:
    t = int(time.time()) if t is None else t
    v1 = hmac.new(segredo.encode(), f"{t}.".encode() + corpo, hashlib.sha256).hexdigest()
    return f"t={t},v1={v1}"


def postar(evento: dict, assinatura: str | None = "auto", segredo: str = SEGREDO):
    corpo = json.dumps(evento).encode()
    headers = {"content-type": "application/json"}
    if assinatura == "auto":
        assinatura = assinar(corpo, segredo)
    if assinatura is not None:
        headers["stripe-signature"] = assinatura
    return cliente.post("/webhook/stripe", content=corpo, headers=headers)


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_URL)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SEGREDO)
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    assert db.iniciar()
    with db._conectar() as c:
        c.execute("TRUNCATE pedidos_pendentes, eventos_stripe, pedidos, abandonos, email_optout")
    app_mod._paginas_prontas.clear()
    yield


@pytest.fixture
def emails(monkeypatch):
    enviados = []
    monkeypatch.setattr(entrega, "enviar_email", lambda para, assunto, html, *a, **k: enviados.append((para, assunto)) or True)
    return enviados


@pytest.fixture
def avisos(monkeypatch):
    lista = []
    monkeypatch.setattr(alertas, "alertar", lambda titulo, corpo="", *a, **k: lista.append((titulo, corpo)))
    return lista


class StripeFalsa:
    def __init__(self):
        self.sessoes = {}

    def __call__(self, session_id):
        return self.sessoes[session_id]


@pytest.fixture
def stripe_falsa(monkeypatch):
    falsa = StripeFalsa()
    monkeypatch.setattr(stripe_api, "sessao", falsa)
    return falsa


def pedido(stripe_falsa, produto="mapa", pago=True, valor=None, sessao="cs_test_1", **extra) -> dict:
    corpo = {"produto": produto, "pessoa": PESSOA, "email": "ana@teste.com", "origem": {"ref": "PEDRO"}, **extra}
    p = pendentes.montar(pendentes.PedidoCheckout.model_validate(corpo))
    assert db.criar_pendente(p) and db.ligar_sessao(p["id"], sessao, sessao + "_secret")
    stripe_falsa.sessoes[sessao] = {
        "id": sessao, "status": "complete", "payment_status": "paid" if pago else "unpaid",
        "amount_total": p["valor_centavos"] if valor is None else valor, "currency": "brl",
        "payment_intent": "pi_" + sessao, "client_reference_id": p["id"], "metadata": {"pedido": p["id"]}}
    return p


def evento(tipo: str, p: dict | None, sessao="cs_test_1", id_evento="evt_1", **objeto) -> dict:
    obj = {"id": sessao, "object": "checkout.session", "payment_status": "paid",
           "client_reference_id": p["id"] if p else None, "metadata": {"pedido": p["id"]} if p else {}}
    obj.update(objeto)
    return {"id": id_evento, "object": "event", "type": tipo, "data": {"object": obj}}


def _linhas(sql, *args):
    with db._conectar() as c:
        return c.execute(sql, args).fetchall()


# ------------------------------------------------------------------ assinatura (falha fechada)
def test_sem_assinatura_e_401(stripe_falsa, emails, avisos):
    p = pedido(stripe_falsa)
    assert postar(evento("checkout.session.completed", p), assinatura=None).status_code == 401
    assert emails == [] and db.pendente(p["id"])["estado"] == "aberto"
    assert avisos and "recusado" in avisos[0][0]


@pytest.mark.parametrize("assinatura", ["t=1,v1=abc", "lixo", "t=%d,v1=%s" % (time.time(), "0" * 64)])
def test_assinatura_errada_e_401(stripe_falsa, emails, avisos, assinatura):
    p = pedido(stripe_falsa)
    assert postar(evento("checkout.session.completed", p), assinatura=assinatura).status_code == 401
    assert emails == []


def test_assinatura_com_outro_segredo_e_401(stripe_falsa, emails, avisos):
    p = pedido(stripe_falsa)
    assert postar(evento("checkout.session.completed", p), segredo="whsec_outro").status_code == 401
    assert emails == []


def test_assinatura_velha_e_401(stripe_falsa, emails, avisos):
    """Anti-replay: assinatura de mais de 5 minutos atrás."""
    p = pedido(stripe_falsa)
    corpo = json.dumps(evento("checkout.session.completed", p)).encode()
    r = cliente.post("/webhook/stripe", content=corpo,
                     headers={"stripe-signature": assinar(corpo, t=int(time.time()) - 600)})
    assert r.status_code == 401 and emails == []


def test_sem_segredo_configurado_recusa_tudo(stripe_falsa, emails, avisos, monkeypatch):
    p = pedido(stripe_falsa)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET")
    assert postar(evento("checkout.session.completed", p)).status_code == 401
    assert postar(evento("checkout.session.completed", p), segredo="").status_code == 401
    assert emails == []


def test_corpo_adulterado_depois_de_assinado_e_401(stripe_falsa, emails, avisos):
    p = pedido(stripe_falsa)
    corpo = json.dumps(evento("checkout.session.completed", p)).encode()
    assinatura = assinar(corpo)
    adulterado = corpo.replace(b"evt_1", b"evt_2")
    r = cliente.post("/webhook/stripe", content=adulterado, headers={"stripe-signature": assinatura})
    assert r.status_code == 401


# ------------------------------------------------------------------ entrega
def test_cartao_pago_entrega_uma_vez(stripe_falsa, emails, avisos):
    p = pedido(stripe_falsa)
    r = postar(evento("checkout.session.completed", p))
    assert r.status_code == 200, r.text
    assert r.json()["email_enviado"] is True and r.json()["link"] is None
    assert emails == [("ana@teste.com", "Sua leitura da Valderez Astrologia está pronta")]
    assert db.pendente(p["id"])["estado"] == "pago"
    linha = _linhas("SELECT origem_pagamento, stripe_id, stripe_pagamento, produto, email, valor, forma_pagamento, "
                    "oferta_id, rastreio, link, email_enviado, cakto_id FROM pedidos")
    assert len(linha) == 1
    origem, sid, pi, produto, email, valor, forma, oferta, rastreio, link, enviado, cakto_id = linha[0]
    assert (origem, sid, pi, produto, email, float(valor), forma, oferta) == (
        "stripe", "cs_test_1", "pi_cs_test_1", "ocidental:mapa", "ana@teste.com", 37.0, "cartao", "stripe:mapa")
    assert rastreio == {"ref": "PEDRO"} and enviado is True and cakto_id is None
    assert "/mapa?" in link and "token=oc-" in link
    # a página de "obrigado" mostra o mesmo tipo de link
    e = cliente.get(f"/api/checkout/{p['id']}/estado").json()
    assert e["estado"] == "pago" and "token=oc-" in e["link"]


def test_evento_repetido_nao_entrega_duas_vezes(stripe_falsa, emails, avisos):
    p = pedido(stripe_falsa)
    ev = evento("checkout.session.completed", p)
    assert postar(ev).status_code == 200
    r2 = postar(ev)
    assert r2.status_code == 200 and r2.json().get("duplicado") is True
    # a Stripe às vezes gera DOIS eventos para a mesma coisa (ids diferentes)
    r3 = postar(evento("checkout.session.completed", p, id_evento="evt_outro"))
    assert r3.status_code == 200 and r3.json().get("duplicado") is True
    assert len(emails) == 1
    assert len(_linhas("SELECT 1 FROM pedidos")) == 1


def test_pix_pendente_nao_entrega(stripe_falsa, emails, avisos):
    p = pedido(stripe_falsa, pago=False)
    r = postar(evento("checkout.session.completed", p, payment_status="unpaid"))
    assert r.status_code == 200 and r.json()["aguardando"] == "unpaid"
    assert emails == [] and db.pendente(p["id"])["estado"] == "aberto"
    assert _linhas("SELECT 1 FROM pedidos") == []


def test_pix_pago_entrega(stripe_falsa, emails, avisos):
    p = pedido(stripe_falsa, pago=False)
    postar(evento("checkout.session.completed", p, payment_status="unpaid"))
    stripe_falsa.sessoes["cs_test_1"]["payment_status"] = "paid"  # o Pix caiu
    r = postar(evento("checkout.session.async_payment_succeeded", p, id_evento="evt_2"))
    assert r.status_code == 200 and r.json()["email_enviado"] is True
    assert len(emails) == 1 and db.pendente(p["id"])["estado"] == "pago"
    assert _linhas("SELECT forma_pagamento FROM pedidos") == [("pix",)]


def test_foto_velha_do_evento_nao_basta(stripe_falsa, emails, avisos):
    """O evento diz `paid`, mas a sessão na Stripe (buscada de novo) não está paga: não entrega."""
    p = pedido(stripe_falsa, pago=False)
    r = postar(evento("checkout.session.completed", p, payment_status="paid"))
    assert r.status_code == 200 and emails == []


def test_pix_que_falhou(stripe_falsa, emails, avisos):
    p = pedido(stripe_falsa, pago=False)
    assert postar(evento("checkout.session.async_payment_failed", p)).status_code == 200
    assert db.pendente(p["id"])["estado"] == "falhou" and emails == []


def test_valor_diferente_nao_entrega_e_avisa(stripe_falsa, emails, avisos):
    p = pedido(stripe_falsa, valor=100)
    r = postar(evento("checkout.session.completed", p))
    assert r.status_code == 200 and "pendente" in r.json()
    assert emails == [] and db.pendente(p["id"])["estado"] == "aberto"
    assert any("valor diferente" in t for t, _ in avisos)


def test_pagamento_sem_pedido_nosso_avisa(stripe_falsa, emails, avisos):
    r = postar(evento("checkout.session.completed", None, sessao="cs_test_x"))
    assert r.status_code == 200 and r.json()["ignorado"] == "pedido desconhecido"
    assert emails == [] and any("SEM pedido nosso" in t for t, _ in avisos)


def test_sessao_trocada_nao_entrega(stripe_falsa, emails, avisos):
    """Um evento de OUTRA sessão apontando para o nosso pedido (metadata copiada) não entrega."""
    p = pedido(stripe_falsa)
    r = postar(evento("checkout.session.completed", p, sessao="cs_test_outra"))
    assert r.status_code == 200 and emails == []


def test_entrega_que_quebra_e_refeita_no_reenvio(stripe_falsa, emails, avisos, monkeypatch):
    p = pedido(stripe_falsa)
    original = entrega.link_completo

    def quebra(*a, **k):
        raise RuntimeError("falha no meio da entrega")
    monkeypatch.setattr(entrega, "link_completo", quebra)
    with pytest.raises(RuntimeError):
        postar(evento("checkout.session.completed", p))
    assert db.pendente(p["id"])["estado"] == "aberto" and _linhas("SELECT 1 FROM eventos_stripe") == []
    monkeypatch.setattr(entrega, "link_completo", original)
    r = postar(evento("checkout.session.completed", p))  # o reenvio da Stripe
    assert r.status_code == 200 and r.json()["email_enviado"] is True and len(emails) == 1


def test_email_que_nao_sai_avisa_a_equipe(stripe_falsa, avisos, monkeypatch):
    monkeypatch.setattr(entrega, "enviar_email", lambda *a, **k: False)
    p = pedido(stripe_falsa)
    r = postar(evento("checkout.session.completed", p))
    assert r.json()["email_enviado"] is False and "token=oc-" in r.json()["link"]
    assert any("NÃO saiu" in t for t, _ in avisos)


def test_sem_banco_a_stripe_reenvia(stripe_falsa, emails, avisos, monkeypatch):
    p = pedido(stripe_falsa)
    monkeypatch.setenv("DATABASE_URL", "postgresql://ninguem@127.0.0.1:1/nada")
    assert postar(evento("checkout.session.completed", p)).status_code == 503
    assert emails == []


def test_evento_que_nao_tratamos_e_ignorado(stripe_falsa, emails, avisos):
    r = postar({"id": "evt_x", "type": "customer.created", "data": {"object": {}}})
    assert r.status_code == 200 and r.json()["ignorado"] == "customer.created"


# ------------------------------------------------------------------ expirado = abandono
def test_sessao_expirada_marca_e_manda_um_email_de_abandono(stripe_falsa, emails, avisos):
    p = pedido(stripe_falsa, pago=False)
    r = postar(evento("checkout.session.expired", p, payment_status="unpaid"))
    assert r.status_code == 200 and r.json()["email_enviado"] is True
    assert db.pendente(p["id"])["estado"] == "expirado"
    assert len(emails) == 1 and emails[0][0] == "ana@teste.com"
    # outro pedido do mesmo produto que também expira: não manda de novo (7 dias)
    p2 = pedido(stripe_falsa, pago=False, sessao="cs_test_2")
    r2 = postar(evento("checkout.session.expired", p2, sessao="cs_test_2", id_evento="evt_2"))
    assert r2.status_code == 200 and len(emails) == 1


def test_abandono_nao_vai_para_quem_comprou_depois(stripe_falsa, emails, avisos):
    abandonado = pedido(stripe_falsa, pago=False, sessao="cs_test_a")
    comprado = pedido(stripe_falsa, sessao="cs_test_b")
    postar(evento("checkout.session.completed", comprado, sessao="cs_test_b", id_evento="evt_b"))
    assert len(emails) == 1  # a entrega
    postar(evento("checkout.session.expired", abandonado, sessao="cs_test_a", id_evento="evt_a"))
    assert len(emails) == 1


def test_abandono_nao_vai_para_descadastrado(stripe_falsa, emails, avisos):
    db.descadastrar("ana@teste.com")
    p = pedido(stripe_falsa, pago=False)
    postar(evento("checkout.session.expired", p))
    assert emails == [] and db.pendente(p["id"])["estado"] == "expirado"


def test_expirado_depois_de_pago_nao_desfaz_a_compra(stripe_falsa, emails, avisos):
    p = pedido(stripe_falsa)
    postar(evento("checkout.session.completed", p))
    postar(evento("checkout.session.expired", p, id_evento="evt_2"))
    assert db.pendente(p["id"])["estado"] == "pago"


# ------------------------------------------------------------------ reembolso e contestação
def test_reembolso_registra_e_avisa(stripe_falsa, emails, avisos):
    p = pedido(stripe_falsa)
    postar(evento("checkout.session.completed", p))
    r = postar({"id": "evt_r", "type": "charge.refunded", "data": {"object": {
        "id": "ch_1", "object": "charge", "payment_intent": "pi_cs_test_1", "refunded": True, "amount_refunded": 3700}}})
    assert r.status_code == 200 and r.json() == {"ok": True, "pagamento": "pi_cs_test_1", "status": "reembolsado",
                                                 "pedido_encontrado": True}
    assert _linhas("SELECT status FROM pedidos") == [("reembolsado",)]
    assert any("Reembolso" in t for t, _ in avisos)


def test_contestacao_registra_e_avisa(stripe_falsa, emails, avisos):
    p = pedido(stripe_falsa)
    postar(evento("checkout.session.completed", p))
    r = postar({"id": "evt_d", "type": "charge.dispute.created", "data": {"object": {
        "id": "dp_1", "object": "dispute", "payment_intent": "pi_cs_test_1", "amount": 3700, "reason": "fraudulent"}}})
    assert r.status_code == 200 and r.json()["status"] == "contestado"
    assert _linhas("SELECT status FROM pedidos") == [("contestado",)]
    assert any("CONTESTAÇÃO" in t and "fraudulent" in c for t, c in avisos)


def test_reembolso_de_pagamento_desconhecido_so_avisa(stripe_falsa, emails, avisos):
    r = postar({"id": "evt_r", "type": "charge.refunded", "data": {"object": {
        "payment_intent": "pi_nada", "refunded": False, "amount_refunded": 100}}})
    assert r.json()["pedido_encontrado"] is False and r.json()["status"] == "reembolso_parcial"
    assert any("NÃO encontrado" in c for _, c in avisos)


# ------------------------------------------------------------------ a Cakto continua igual
def test_compra_da_cakto_fica_com_origem_cakto(emails, avisos):
    from test_db import evento_cakto
    assert base._postar_webhook(evento_cakto()).status_code == 200
    assert _linhas("SELECT origem_pagamento, stripe_id FROM pedidos") == [("cakto", None)]


def test_nada_pessoal_no_log(stripe_falsa, emails, avisos, caplog):
    import logging
    caplog.set_level(logging.INFO)
    p = pedido(stripe_falsa)
    postar(evento("checkout.session.completed", p))
    texto = caplog.text
    for dado in ("ana@teste.com", "Ana Clara", "1990-05-15", "Porto Alegre"):
        assert dado not in texto, dado

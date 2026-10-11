"""
Padmini — a conversa com a API da Stripe (rodada 11). Tudo que sai daqui para a Stripe
passa por este módulo, para dar para conferir (e testar) o que vai junto.

Lido antes de escrever (regra 5 do CLAUDE.md):
  docs.stripe.com/checkout/embedded/quickstart   (ui_mode=embedded_page, client_secret, return_url)
  docs.stripe.com/checkout/fulfillment           (eventos e entrega, na Fase 3)
  docs.stripe.com/payments/pix/accept-a-payment  (Pix: só BRL, pagamento assíncrono)
  docs.stripe.com/security/guide#content-security-policy  (seguranca.CSP_STRIPE)

O que a Stripe recebe de um pedido, e só isto:
  - o NOME do produto e o PREÇO, em `line_items[].price_data` (do nosso catálogo, nada
    criado no painel da Stripe; nunca o preço vindo do navegador: ver pendentes.py);
  - o id opaco do pedido pendente, em `client_reference_id` e `metadata.pedido`;
  - o e-mail, em `customer_email` (o recibo e o Pix precisam dele).
Nada de data, hora, cidade ou nome de quem é a leitura. Os meios de pagamento (cartão,
Pix, Apple Pay, Google Pay) vêm do painel: `payment_method_types` não é fixado aqui.
"""

import json
import time

import pagamento

# Mesma versão da API que o Stripe.js carregado em /checkout (js.stripe.com/endive).
VERSAO_API = "2026-09-30.endive"
STRIPE_JS = "https://js.stripe.com/endive/stripe.js"


class StripeIndisponivel(RuntimeError):
    """Sem chave, ou a Stripe recusou / não respondeu."""


def _cliente():
    import stripe
    chave = pagamento.chave_secreta()
    if not chave:
        raise StripeIndisponivel("STRIPE_SECRET_KEY não configurada.")
    return stripe.StripeClient(chave, stripe_version=VERSAO_API, max_network_retries=2)


def parametros_da_sessao(pendente: dict, site: str) -> dict:
    """Os parâmetros da Checkout Session de um pedido pendente. Função à parte para os
    testes conferirem que nenhum dado de nascimento vai para a Stripe."""
    import ofertas
    itens = []
    for item in pendente["itens"]:
        nome = ofertas.oferta(item["chave"], pendente.get("sistema") or "ocidental").get("nome") or item["chave"]
        itens.append({"quantity": 1, "price_data": {
            "currency": pendente.get("moeda") or "brl",
            "unit_amount": int(item["valor_centavos"]),
            "product_data": {"name": nome},
        }})
    return {
        "ui_mode": "embedded_page",
        "mode": "payment",
        "line_items": itens,
        "customer_email": pendente["email"],
        "client_reference_id": pendente["id"],
        "metadata": {"pedido": pendente["id"]},
        "payment_intent_data": {"metadata": {"pedido": pendente["id"]}},
        "return_url": f"{site.rstrip('/')}/obrigado/{pendente['id']}",
        "locale": "pt-BR",
    }


def criar_sessao(pendente: dict, site: str) -> dict:
    """Cria a Checkout Session e devolve {id, client_secret}. A chave de idempotência é o
    id do pendente: um clique duplo não cria duas sessões."""
    try:
        s = _cliente().v1.checkout.sessions.create(
            params=parametros_da_sessao(pendente, site),
            options={"idempotency_key": f"pedido-{pendente['id']}"})
    except StripeIndisponivel:
        raise
    except Exception as erro:  # noqa: BLE001  (stripe.StripeError e falhas de rede)
        raise StripeIndisponivel(f"a Stripe recusou a sessão: {type(erro).__name__}") from erro
    return {"id": s.id, "client_secret": s.client_secret}


_cache_estado: dict[str, tuple[float, dict]] = {}
CACHE_ESTADO = 5.0  # segundos: a página de "obrigado" pergunta a cada poucos segundos


def estado_da_sessao(session_id: str) -> dict:
    """{status, payment_status} da sessão (open/complete/expired; paid/unpaid/no_payment_required).
    Pix: status `complete` com `unpaid` = a pessoa gerou o Pix e ainda não pagou."""
    agora = time.monotonic()
    guardado = _cache_estado.get(session_id)
    if guardado and agora - guardado[0] < CACHE_ESTADO:
        return guardado[1]
    try:
        s = _cliente().v1.checkout.sessions.retrieve(session_id)
    except StripeIndisponivel:
        raise
    except Exception as erro:  # noqa: BLE001
        raise StripeIndisponivel(f"não deu para ler a sessão: {type(erro).__name__}") from erro
    estado = {"status": s.status, "payment_status": s.payment_status}
    if len(_cache_estado) > 5000:
        _cache_estado.clear()
    _cache_estado[session_id] = (agora, estado)
    return estado


def sessao(session_id: str) -> dict:
    """A Checkout Session como está AGORA na Stripe (o evento do webhook é uma foto e pode
    estar velho: docs.stripe.com/checkout/fulfillment manda buscar antes de entregar).
    Só os campos que a entrega usa."""
    try:
        # o PaymentIntent e a cobrança expandidos: é deles que sai o meio de pagamento real
        s = _cliente().v1.checkout.sessions.retrieve(
            session_id, params={"expand": ["payment_intent.latest_charge"]})
    except StripeIndisponivel:
        raise
    except Exception as erro:  # noqa: BLE001
        raise StripeIndisponivel(f"não deu para ler a sessão: {type(erro).__name__}") from erro
    d = s.to_dict()  # na biblioteca 16, StripeObject não é dict
    pi = d.get("payment_intent")
    return {"id": d.get("id"), "status": d.get("status"), "payment_status": d.get("payment_status"),
            "amount_total": d.get("amount_total"), "currency": d.get("currency"),
            "payment_intent": pi.get("id") if isinstance(pi, dict) else pi,
            "meio_pagamento": meio_de_pagamento(pi),
            "client_reference_id": d.get("client_reference_id"),
            "metadata": dict(d.get("metadata") or {})}


def meio_de_pagamento(pi) -> str | None:
    """O meio usado de fato ('pix', 'card', …): o `payment_method_details.type` da cobrança
    (latest_charge) e, sem ela, o `payment_method_types` do PaymentIntent quando só há um.
    None se não der para saber (PaymentIntent não expandido)."""
    if not isinstance(pi, dict):
        return None
    cobranca = pi.get("latest_charge")
    if isinstance(cobranca, dict):
        tipo = (cobranca.get("payment_method_details") or {}).get("type")
        if tipo:
            return str(tipo)
    tipos = pi.get("payment_method_types") or []
    return str(tipos[0]) if len(tipos) == 1 else None


class AssinaturaInvalida(ValueError):
    pass


TOLERANCIA_ASSINATURA = 300  # segundos, o padrão das bibliotecas da Stripe (anti-replay)


def verificar_evento(corpo: bytes, assinatura: str, segredo: str) -> dict:
    """O evento, se o cabeçalho Stripe-Signature confere com o segredo do endpoint
    (STRIPE_WEBHOOK_SECRET). Sem segredo, sem cabeçalho ou assinatura errada:
    AssinaturaInvalida. Verificação da biblioteca oficial (docs.stripe.com/webhooks)."""
    if not segredo:
        raise AssinaturaInvalida("STRIPE_WEBHOOK_SECRET não configurado")
    if not assinatura:
        raise AssinaturaInvalida("sem Stripe-Signature")
    import stripe
    try:
        stripe.WebhookSignature.verify_header(corpo.decode("utf-8"), assinatura, segredo, TOLERANCIA_ASSINATURA)
    except Exception as erro:  # noqa: BLE001  (SignatureVerificationError, cabeçalho malformado)
        raise AssinaturaInvalida(type(erro).__name__) from erro
    try:
        evento = json.loads(corpo.decode("utf-8"))
    except ValueError as erro:
        raise AssinaturaInvalida("corpo não é JSON") from erro
    if not isinstance(evento, dict) or not evento.get("id") or not evento.get("type"):
        raise AssinaturaInvalida("evento sem id ou tipo")
    return evento

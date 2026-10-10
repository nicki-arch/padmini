"""
Padmini — o checkout próprio (rodada 11, Stripe Embedded Checkout). Só com
PADMINI_PAGAMENTO=stripe e só para a versão ocidental; com a Cakto, tudo aqui responde 404.

    POST /api/checkout               o botão de compra: valida, grava o pedido pendente,
                                     cria a Checkout Session e devolve {"url": "/checkout/{id}"}
    GET  /api/checkout/{id}          o client_secret para montar o checkout (só pedido aberto)
    GET  /api/checkout/{id}/estado   o que a página de "obrigado" mostra: pago (com o link
                                     da leitura), aguardando o Pix, expirado...

As páginas /checkout/{id} e /obrigado/{id} ficam no app.py (templates).

O id do pedido é a "chave" de tudo aqui: aleatório, opaco, só quem fez o pedido o tem
(ele aparece na URL do checkout e no return_url da Stripe). Nenhum dado pessoal na URL.
"""

import logging
import re

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import ValidationError

import alertas
import catalogo
import db
import entrega
import limites
import pagamento
import pendentes
import stripe_api

log = logging.getLogger("padmini.checkout")
rotas = APIRouter()
ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def ligado() -> bool:
    return pagamento.stripe()


def exigir_ligado() -> None:
    if not ligado():
        raise HTTPException(404, "Não encontrado.")


def pedido_ou_404(id_pedido: str) -> dict:
    exigir_ligado()
    p = db.pendente(id_pedido) if ID_RE.match(id_pedido or "") else None
    if not p:
        raise HTTPException(404, "Pedido não encontrado.")
    return p


@rotas.post("/api/checkout")
def criar_checkout(request: Request, corpo: dict = Body(...)):
    exigir_ligado()
    limites.exigir(limites.CHECKOUT, request)
    try:
        pedido = pendentes.PedidoCheckout.model_validate(corpo)
    except ValidationError:
        raise HTTPException(422, "Confira os dados da leitura e o e-mail.")
    # em breve / oculto / venda fechada (sem PADMINI_VENDAS_TESTE): não vende
    if not catalogo.vende(pedido.produto, pendentes.SISTEMA):
        raise HTTPException(404, "Este produto não está à venda.")
    try:
        novo = pendentes.montar(pedido)
    except pendentes.PedidoInvalido as erro:
        raise HTTPException(422, str(erro))
    if not (pagamento.chave_secreta() and pagamento.chave_publica()):
        log.error("checkout: Stripe sem STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY")
        raise HTTPException(503, "O pagamento está indisponível agora. Tente de novo em instantes.")
    # Sem banco não há checkout (falha fechada): os dados da leitura têm de estar
    # aqui quando a Stripe confirmar o pagamento.
    if not db.criar_pendente(novo):
        log.error("checkout: pedido pendente não foi gravado (banco ausente ou fora do ar)")
        alertas.alertar("Checkout fora do ar: o banco não gravou o pedido",
                        "POST /api/checkout não conseguiu gravar em pedidos_pendentes. Conferir DATABASE_URL.",
                        chave="checkout_banco", intervalo=60 * 60)
        raise HTTPException(503, "O pagamento está indisponível agora. Tente de novo em instantes.")
    try:
        sessao = stripe_api.criar_sessao(novo, entrega.SITE_URL)
    except stripe_api.StripeIndisponivel as erro:
        log.error("checkout: pedido %s sem sessão na Stripe (%s)", novo["id"], erro)
        db.marcar_pendente(novo["id"], "falhou")
        alertas.alertar("Checkout: a Stripe não criou a sessão",
                        f"pedido {novo['id']}: {erro}", chave="checkout_stripe", intervalo=60 * 60)
        raise HTTPException(503, "O pagamento está indisponível agora. Tente de novo em instantes.")
    db.ligar_sessao(novo["id"], sessao["id"], sessao["client_secret"])
    log.info("checkout: pedido %s aberto (%s)", novo["id"], novo["itens"][0]["chave"])
    return {"url": f"/checkout/{novo['id']}"}


@rotas.get("/api/checkout/{id_pedido}")
def segredo_do_checkout(id_pedido: str, request: Request):
    """O que o Stripe.js precisa para montar o checkout: só para pedido aberto."""
    limites.exigir(limites.CHECKOUT_ESTADO, request)
    p = pedido_ou_404(id_pedido)
    if p["estado"] != "aberto" or not p.get("stripe_client_secret"):
        raise HTTPException(409, p["estado"])
    return {"client_secret": p["stripe_client_secret"], "chave_publica": pagamento.chave_publica()}


def link_da_leitura(p: dict) -> str:
    """O link do completo do (único) item do pedido, como o e-mail de entrega manda."""
    item = p["itens"][0]
    return entrega.link_completo(item["chave"], item["dados"], p.get("sistema") or pendentes.SISTEMA)


@rotas.get("/api/checkout/{id_pedido}/estado")
def estado_do_checkout(id_pedido: str, request: Request):
    """Para a página de "obrigado" (que pergunta a cada poucos segundos). O pagamento só
    conta como confirmado quando o WEBHOOK marca o pedido como pago; a sessão da Stripe
    serve só para saber se é um Pix esperando pagamento."""
    limites.exigir(limites.CHECKOUT_ESTADO, request)
    p = pedido_ou_404(id_pedido)
    resposta = {"estado": p["estado"], "aguardando_pix": False, "link": None}
    if p["estado"] == "pago":
        resposta["link"] = link_da_leitura(p)
    elif p["estado"] == "aberto" and p.get("stripe_session_id"):
        try:
            s = stripe_api.estado_da_sessao(p["stripe_session_id"])
        except stripe_api.StripeIndisponivel:
            s = {}
        resposta["aguardando_pix"] = s.get("status") == "complete" and s.get("payment_status") == "unpaid"
        resposta["sessao"] = s.get("status") or ""
    return resposta

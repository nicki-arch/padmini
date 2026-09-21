"""
Padmini — glue com a Cakto (parsing do webhook).

Conforme a documentação oficial (docs.cakto.com.br/conceitos/webhooks):
  - Assinatura: header `X-Cakto-Signature` no formato `v1=<hmac-sha256>`, com o
    digest calculado sobre `{timestamp}.{corpo bruto}` usando o webhook secret
    como chave. O timestamp vem em `X-Cakto-Timestamp` (Unix, em segundos).
    Alternativa documentada: um campo `secret` no próprio corpo do evento.
    As duas formas são aceitas aqui (ver `verificar`).
  - Evento de pagamento aprovado: `purchase_approved` (ver APROVADOS).
  - Dados do comprador: objeto `customer` com `name`, `email`, `phone`, etc.

⚠️ AINDA A CONFIRMAR na prática (a doc não cobre):
  - COMO OS DADOS DE NASCIMENTO VOLTAM: nós os mandamos como parâmetros `pd_*`
    no link do checkout (ver afiliado.js → linkCheckout). A documentação só
    menciona o repasse de UTMs e identificadores do Meta (fbc/fbp), então o
    repasse de parâmetros customizados precisa ser verificado com um pagamento
    de teste. Este módulo varre o payload inteiro atrás de chaves `pd_*`, então
    funciona esteja onde estiver — desde que a Cakto os repasse. Se ela não
    repassar, será preciso outra ponte (ex.: guardar o pedido por um id, ou
    usar os campos de UTM, que comprovadamente voltam).

Como identificamos o produto: pelo `pd_produto` (mapa|compat) que mandamos, ou
pelo id do produto da Cakto mapeado em PADMINI_CAKTO_PROD_MAPA/_COMPAT.
"""

import hashlib
import hmac
import os

APROVADOS = ("paid", "approved", "aprovad", "complete", "concluid", "success")

PROD_MAPA = os.environ.get("PADMINI_CAKTO_PROD_MAPA", "")
PROD_COMPAT = os.environ.get("PADMINI_CAKTO_PROD_COMPAT", "")

# Só libera webhook sem segredo configurado em staging (mesmo flag do gate).
MODO_ABERTO = os.environ.get("PADMINI_MODO_ABERTO") == "1"


def assinatura_esperada(timestamp: str, corpo: bytes, secret: str) -> str:
    """HMAC-SHA256 de '{timestamp}.{corpo}' com o webhook secret, em hex."""
    if isinstance(corpo, str):
        corpo = corpo.encode("utf-8")
    base = f"{timestamp}.".encode("utf-8") + corpo
    return hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()


def verificar(assinatura: str, timestamp: str, corpo: bytes, secret: str,
              secret_do_corpo: str = "") -> bool:
    """
    True se a origem confere. Aceita as duas formas documentadas pela Cakto:
      1) header `X-Cakto-Signature: v1=<hmac>` sobre '{timestamp}.{corpo}';
      2) campo `secret` dentro do corpo do evento.

    Sem segredo configurado, REJEITA em produção (fail-closed) — um webhook
    aberto permitiria forjar uma aprovação e sacar um token do relatório pago.
    Só libera quando PADMINI_MODO_ABERTO=1 (staging).
    """
    if not secret:
        return MODO_ABERTO

    # 2) segredo no corpo
    if secret_do_corpo and hmac.compare_digest(str(secret_do_corpo), secret):
        return True

    # 1) assinatura HMAC no header
    if not assinatura:
        return False
    recebida = assinatura.strip()
    if recebida.startswith("v1="):
        recebida = recebida[3:]
    return hmac.compare_digest(recebida, assinatura_esperada(timestamp or "", corpo, secret))


def _iter_valores(obj):
    """Percorre recursivamente dict/list rendendo (chave, valor) de folhas."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                yield from _iter_valores(v)
            else:
                yield str(k), v
    elif isinstance(obj, list):
        for it in obj:
            yield from _iter_valores(it)


def is_aprovado(evento: dict) -> bool:
    for k, v in _iter_valores(evento):
        if k.lower() in ("status", "event", "type", "situacao", "payment_status") and isinstance(v, str):
            if any(s in v.lower() for s in APROVADOS):
                return True
    return False


def coletar_pd(evento: dict) -> dict:
    """Junta todos os parâmetros pd_* que voltaram no payload."""
    pd = {}
    for k, v in _iter_valores(evento):
        if k.lower().startswith("pd_"):
            pd[k.lower()] = v
    return pd


def email_do_evento(evento: dict) -> str:
    for k, v in _iter_valores(evento):
        if "email" in k.lower() and isinstance(v, str) and "@" in v:
            return v.strip()
    return ""


def produto_do_evento(evento: dict, pd: dict) -> str:
    p = str(pd.get("pd_produto", "")).lower()
    if p in ("mapa", "compat"):
        return p
    # fallback: id do produto da Cakto
    for k, v in _iter_valores(evento):
        if k.lower() in ("product_id", "offer_id", "produto_id", "product", "offer", "sku"):
            sv = str(v)
            if PROD_MAPA and sv == PROD_MAPA:
                return "mapa"
            if PROD_COMPAT and sv == PROD_COMPAT:
                return "compat"
    return ""


def dados_nascimento(pd: dict, produto: str):
    """Monta os dados de nascimento a partir dos pd_*. Retorna dict ou None se faltar o essencial."""
    def campo(nome):
        return pd.get("pd_" + nome, "")

    if produto == "mapa":
        d = {"nome": campo("nome"), "data": campo("data"), "hora": campo("hora"),
             "lat": campo("lat"), "lon": campo("lon"), "cidade": campo("cidade")}
        if not (d["data"] and d["hora"] and d["lat"] and d["lon"]):
            return None
        return d
    if produto == "compat":
        def pessoa(px):
            return {"nome": pd.get(f"pd_{px}_nome", ""), "data": pd.get(f"pd_{px}_data", ""),
                    "hora": pd.get(f"pd_{px}_hora", ""), "lat": pd.get(f"pd_{px}_lat", ""),
                    "lon": pd.get(f"pd_{px}_lon", ""), "cidade": pd.get(f"pd_{px}_cidade", "")}
        a, b = pessoa("a"), pessoa("b")
        if not (a["data"] and a["hora"] and a["lat"] and a["lon"] and b["data"] and b["hora"] and b["lat"] and b["lon"]):
            return None
        return {"a": a, "b": b, "nome": a["nome"]}
    return None

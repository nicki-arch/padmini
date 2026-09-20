"""
Padmini — glue com a Cakto (parsing do webhook).

⚠️ ADAPTAR À CAKTO antes de ligar em produção — três coisas a confirmar na
documentação/painel da Cakto:
  1) COMO A CAKTO ASSINA O WEBHOOK: nome do header e esquema. Aqui conferimos
     um segredo simples (header 'x-cakto-signature' ou ?secret=) contra
     PADMINI_CAKTO_WEBHOOK_SECRET. Se a Cakto usar HMAC do corpo, trocar
     `verificar()`.
  2) NOMES DE STATUS de pagamento aprovado (ver APROVADOS).
  3) COMO OS DADOS DE NASCIMENTO VOLTAM: nós os mandamos como parâmetros
     `pd_*` no link do checkout (ver afiliado.js → linkCheckout). A Cakto
     precisa repassá-los ao webhook (como custom params/metadata). Este módulo
     varre o payload inteiro atrás de chaves `pd_*`, então funciona esteja
     onde estiver — desde que a Cakto os repasse. Se ela não repassar, será
     preciso outra ponte (ex.: guardar o pedido por um id).

Como identificamos o produto: pelo `pd_produto` (mapa|compat) que mandamos, ou
pelo id do produto da Cakto mapeado em PADMINI_CAKTO_PROD_MAPA/_COMPAT.
"""

import hmac
import os

APROVADOS = ("paid", "approved", "aprovad", "complete", "concluid", "success")

PROD_MAPA = os.environ.get("PADMINI_CAKTO_PROD_MAPA", "")
PROD_COMPAT = os.environ.get("PADMINI_CAKTO_PROD_COMPAT", "")


def verificar(assinatura: str, secret: str) -> bool:
    """True se a origem confere. Sem secret configurado, aceita (dev) — em
    produção, SEMPRE configurar PADMINI_CAKTO_WEBHOOK_SECRET."""
    if not secret:
        return True
    return hmac.compare_digest(assinatura or "", secret)


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

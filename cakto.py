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

  - Campos de rastreamento repassados: `utm_source`, `utm_medium`,
    `utm_campaign`, `utm_term`, `utm_content` e `sck`. NÃO existe campo livre
    de metadata: qualquer parâmetro customizado na URL do checkout é
    descartado.

COMO OS DADOS DE NASCIMENTO VOLTAM: empacotados no `sck` (ver afiliado.js →
padEmpacotar), já que era o único campo livre disponível. Uma tentativa
anterior usava parâmetros `pd_*` soltos, que a Cakto descartaria — o
`coletar_pd` abaixo desempacota o `sck` e ainda aceita `pd_*` como rede de
segurança.

⚠️ A CONFIRMAR com um pagamento de teste: que o `sck` informado na URL do
checkout realmente chega ao webhook preenchido (a doc lista o campo no payload,
mas não documenta explicitamente como defini-lo na URL).

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


CAMPOS_PESSOA = ("data", "hora", "lat", "lon", "nome", "cidade")


def coletar_pd(evento: dict) -> dict:
    """
    Recupera os dados de nascimento que mandamos no checkout.

    A Cakto só repassa ao webhook os campos utm_* e `sck` — parâmetros
    customizados na URL são descartados. Então os dados viajam empacotados no
    `sck`, no formato montado por afiliado.js → padEmpacotar:
        mapa:  m~data~hora~lat~lon~nome~cidade
        casal: c~<pessoa A>~<pessoa B>
    Devolve um dicionário no mesmo formato `pd_*` que o resto do módulo já usa,
    para não espalhar a mudança. Mantém também os `pd_*` soltos, se um dia
    chegarem (não custa nada e serve de rede de segurança).
    """
    pd = {}
    for k, v in _iter_valores(evento):
        if k.lower().startswith("pd_"):
            pd[k.lower()] = v

    sck = ""
    for k, v in _iter_valores(evento):
        if k.lower() == "sck" and isinstance(v, str) and v:
            sck = v
            break
    if not sck:
        return pd

    partes = sck.split("~")
    tipo = partes[0].strip().lower()
    resto = partes[1:]
    n = len(CAMPOS_PESSOA)

    if tipo == "m" and len(resto) >= 4:
        pd.setdefault("pd_produto", "mapa")
        for i, campo in enumerate(CAMPOS_PESSOA):
            if i < len(resto) and resto[i]:
                pd.setdefault("pd_" + campo, resto[i])
    elif tipo == "c" and len(resto) >= n + 4:
        pd.setdefault("pd_produto", "compat")
        for prefixo, bloco in (("a", resto[:n]), ("b", resto[n:n * 2])):
            for i, campo in enumerate(CAMPOS_PESSOA):
                if i < len(bloco) and bloco[i]:
                    pd.setdefault(f"pd_{prefixo}_{campo}", bloco[i])
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

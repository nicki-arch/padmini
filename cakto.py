"""
Padmini — glue com a Cakto (parsing do webhook).

Conforme a documentação oficial (docs.cakto.com.br/conceitos/webhooks):
  - Assinatura: header `X-Cakto-Signature` no formato `v1=<hmac-sha256>`, com o
    digest calculado sobre `{timestamp}.{corpo bruto}` usando o webhook secret
    como chave. O timestamp vem em `X-Cakto-Timestamp` (Unix, em segundos).
    Alternativa documentada: um campo `secret` no próprio corpo do evento.
    As duas formas são aceitas aqui (ver `verificar`).
  - Evento de pagamento aprovado: `purchase_approved` (ver is_aprovado).
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

Como identificamos o produto: pelo que a Cakto diz que foi pago — código da
oferta (offer.id / checkoutUrl, vindo de conteudo/<versão>/ofertas.yaml; as
ofertas das duas versões do site são reconhecidas, e a oferta diz também de
qual versão entregar) ou id do produto
mapeado em PADMINI_CAKTO_PROD_MAPA/_COMPAT. O `sck` NÃO decide o produto (o
comprador pode editá-lo); se ele disser outra coisa, o pedido vira entrega manual.
"""

import hashlib
import hmac
import os
import time

import ofertas

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


# Tolerância do X-Cakto-Timestamp, a mesma do exemplo oficial da Cakto. Cada
# (re)envio é assinado com o horário do envio, então retentativas passam.
TOLERANCIA_TIMESTAMP = 5 * 60


def timestamp_recente(timestamp: str, agora: float | None = None) -> bool:
    try:
        ts = int(str(timestamp).strip())
    except (TypeError, ValueError):
        return False
    agora = time.time() if agora is None else agora
    return abs(agora - ts) <= TOLERANCIA_TIMESTAMP


def _iguais(a: str, b: str) -> bool:
    # compare_digest com str exige ASCII: texto estranho no header viraria 500
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def exigir_assinatura() -> bool:
    """PADMINI_CAKTO_EXIGIR_ASSINATURA=1 desliga a validação pelo `secret` do corpo.
    Ligar depois de ver no log da Render que as entregas reais chegam com
    "webhook: origem provada por assinatura" (ver docs/seguranca.md)."""
    return os.environ.get("PADMINI_CAKTO_EXIGIR_ASSINATURA") == "1"


def metodo_de_verificacao(assinatura: str, timestamp: str, corpo: bytes, secret: str,
                          secret_do_corpo: str = "", agora: float | None = None) -> str:
    """
    Como a origem foi provada: "assinatura", "corpo", "aberto" ou "" (rejeitado).

    Aceita as duas formas documentadas pela Cakto:
      1) header `X-Cakto-Signature: v1=<hmac>` sobre '{timestamp}.{corpo}', com
         `X-Cakto-Timestamp` de no máximo 5 min de diferença (anti-replay, como no
         exemplo oficial);
      2) campo `secret` dentro do corpo — a Cakto manda nas duas formas em toda
         entrega. Esta não tem proteção contra replay (quem captura um corpo leva
         junto o segredo), por isso pode ser desligada com
         PADMINI_CAKTO_EXIGIR_ASSINATURA=1 quando a 1 estiver confirmada em produção.

    Sem segredo configurado, REJEITA em produção (fail-closed) — um webhook
    aberto permitiria forjar uma aprovação e sacar um token do relatório pago.
    Só libera quando PADMINI_MODO_ABERTO=1 (staging).
    """
    if not secret:
        return "aberto" if MODO_ABERTO else ""

    recebida = (assinatura or "").strip()
    if recebida and timestamp_recente(timestamp, agora):
        # "v1=abc" ou, numa transição futura de versão, "v1=abc,v2=def"
        v1 = [p.strip()[3:] for p in recebida.split(",") if p.strip().startswith("v1=")]
        esperada = assinatura_esperada(str(timestamp).strip(), corpo, secret)
        if any(_iguais(a, esperada) for a in v1):
            return "assinatura"

    if (not exigir_assinatura() and secret_do_corpo
            and _iguais(str(secret_do_corpo), secret)):
        return "corpo"
    return ""


def verificar(assinatura: str, timestamp: str, corpo: bytes, secret: str,
              secret_do_corpo: str = "", agora: float | None = None) -> bool:
    """True se a origem confere (ver `metodo_de_verificacao`)."""
    return bool(metodo_de_verificacao(assinatura, timestamp, corpo, secret, secret_do_corpo, agora))


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


def pedidos_do_evento(evento) -> list:
    """
    Normaliza a entrega em uma lista de eventos de um pedido cada.
    Webhook V1: `data` é um objeto (um pedido). Webhook V2 (só criável pelo
    painel): `data` é uma lista com todos os pedidos da mesma cobrança —
    principal, order bump, upsell. docs.cakto.com.br/conceitos/webhooks
    """
    if not isinstance(evento, dict):
        return []
    dados = evento.get("data")
    if isinstance(dados, list):
        return [{**evento, "data": item} for item in dados if isinstance(item, dict)]
    return [evento]


EVENTOS_APROVADOS = ("purchase_approved",)
STATUS_APROVADOS = ("paid", "approved")


def is_aprovado(evento: dict) -> bool:
    """
    Pagamento aprovado = `event` purchase_approved (quando vier) e `data.status`
    paid. Olha só esses dois campos oficiais (docs.cakto.com.br/conceitos/webhooks).

    Antes procurava "paid"/"approved"/... em QUALQUER campo status/type do
    payload, inclusive dentro do bloco do meio de pagamento, cujo conteúdo vem
    cru da adquirente — um `refund` com `pix.status = "approved"` lá dentro
    passaria como pagamento aprovado.
    """
    if not isinstance(evento, dict):
        return False
    nome = str(evento.get("event") or "").strip().lower()
    if nome and nome not in EVENTOS_APROVADOS:
        return False
    d = evento.get("data")
    status = str(d.get("status") or "").strip().lower() if isinstance(d, dict) else ""
    return status in STATUS_APROVADOS


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
    # 1º o campo oficial (data.customer.email). A busca genérica abaixo é só
    # fallback: o payload também traz `product.supportEmail` e e-mails em
    # `commissions`, que não são do comprador.
    dados = evento.get("data") if isinstance(evento, dict) else None
    cliente = dados.get("customer") if isinstance(dados, dict) else None
    if isinstance(cliente, dict) and isinstance(cliente.get("email"), str) and "@" in cliente["email"]:
        return cliente["email"].strip()
    for k, v in _iter_valores(evento):
        if k.lower() in ("supportemail", "user"):
            continue
        if "email" in k.lower() and isinstance(v, str) and "@" in v:
            return v.strip()
    return ""


# Oferta de cada produto — é o código no link do checkout
# (pay.cakto.com.br/39dhqty_1125341 → "39dhqty"). Serve de rede de segurança
# para identificar o produto quando o `sck` não vier. Confirmado na 1ª compra real.
# Vem de `conteudo/vedica/ofertas.yaml` (mesmo link que o site usa no botão de compra),
# para não existir um código aqui e outro lá.
OFERTA_MAPA = os.environ.get("PADMINI_CAKTO_OFERTA_MAPA") or ofertas.codigo("mapa")
OFERTA_COMPAT = os.environ.get("PADMINI_CAKTO_OFERTA_COMPAT") or ofertas.codigo("compat")


def _codigos_das_ofertas() -> dict:
    """{código da oferta: (versão, produto)} das DUAS versões do site.

    O webhook reconhece as ofertas de todas as versões, qualquer que seja a
    que está no ar: uma compra feita minutos antes da troca de PADMINI_SISTEMA
    precisa ser entregue (e na versão que foi comprada). As variáveis
    PADMINI_CAKTO_OFERTA_MAPA/_COMPAT continuam valendo para a védica."""
    tabela = {}
    for sistema, chave, oferta in ofertas.todas_as_ofertas():
        if chave in ("mapa", "compat") and oferta.get("codigo"):
            tabela[oferta["codigo"]] = (sistema, chave)
    if OFERTA_MAPA:
        tabela[OFERTA_MAPA] = ("vedica", "mapa")
    if OFERTA_COMPAT:
        tabela[OFERTA_COMPAT] = ("vedica", "compat")
    return tabela


def oferta_paga(evento: dict) -> tuple[str, str]:
    """
    (versão, produto) que a Cakto diz que foi PAGO — ex.: ('vedica', 'mapa').
    ('', '') se não reconhecer.

    Só olha campos que a Cakto preenche (product.id/short_id, offer.id,
    checkoutUrl) — nunca o `sck`, que é montado no navegador do comprador e
    pode ser editado na URL do checkout.
    """
    d = evento.get("data") if isinstance(evento, dict) else None
    if not isinstance(d, dict):
        return "", ""
    prod = d.get("product") if isinstance(d.get("product"), dict) else {}
    oferta = d.get("offer") if isinstance(d.get("offer"), dict) else {}
    ids_produto = {str(prod.get("id") or ""), str(prod.get("short_id") or "")} - {""}
    if PROD_MAPA and PROD_MAPA in ids_produto:
        return "vedica", "mapa"
    if PROD_COMPAT and PROD_COMPAT in ids_produto:
        return "vedica", "compat"
    codigos = {str(oferta.get("id") or "")}
    url = str(d.get("checkoutUrl") or "")
    if url:
        # ex.: https://pay.cakto.com.br/39dhqty_1125341?callback=... → "39dhqty"
        codigos.add(url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1])
    codigos = {c.split("_")[0] for c in codigos if c}
    tabela = _codigos_das_ofertas()
    # ordem fixa (a do código da oferta, depois o do link) para o resultado não
    # depender da ordem de um set
    for codigo in sorted(codigos, key=lambda c: c != str(oferta.get("id") or "").split("_")[0]):
        if codigo in tabela:
            return tabela[codigo]
    return "", ""


def produto_pago(evento: dict) -> str:
    """Produto que a Cakto diz que foi PAGO ('mapa' | 'compat' | ''), de qualquer versão."""
    return oferta_paga(evento)[1]


def sistema_pago(evento: dict) -> str:
    """Versão do site da oferta paga ('vedica' | 'ocidental' | '')."""
    return oferta_paga(evento)[0]


def produto_do_evento(evento: dict, pd: dict) -> str:
    """
    Produto a entregar. Quem manda é o que foi pago (`produto_pago`); o `sck`
    só diz em que formato vieram os dados de nascimento.

    Antes o `sck` tinha prioridade: bastava pagar o mapa (R$47) com um
    `sck=c~...` na URL para receber a compatibilidade (R$97). Agora:
      - pago identificado e `sck` do mesmo tipo (ou sem `sck`) → o produto pago;
      - pago identificado e `sck` de outro tipo → "" (vira entrega manual);
      - pago NÃO identificado → "" (falha fechada: não entrega no escuro).
    """
    pago = produto_pago(evento)
    declarado = str(pd.get("pd_produto", "")).lower()
    if not pago:
        return ""
    if declarado in ("mapa", "compat") and declarado != pago:
        return ""
    return pago


# Oferta do order bump "mapas individuais do casal" (código da oferta na Cakto).
# Vazio = o bump não é reconhecido (falha fechada). Antes, vazio fazia QUALQUER
# order bump com `sck` de casal virar os 2 mapas — um bump barato criado no
# futuro, somado a um `sck=c~...` editado na URL, entregaria dois mapas.
OFERTA_BUMP_MAPAS = (os.environ.get("PADMINI_CAKTO_OFERTA_BUMP_MAPAS")
                     or ofertas.codigo("bump_mapas_casal"))


def e_bump_mapas_do_casal(evento: dict) -> bool:
    d = evento.get("data") if isinstance(evento, dict) else None
    if not isinstance(d, dict) or not OFERTA_BUMP_MAPAS:
        return False
    if coletar_pd(evento).get("pd_produto") != "compat":
        return False  # o bump só existe no checkout do casal (sck "c~...")
    oferta = d.get("offer") if isinstance(d.get("offer"), dict) else {}
    url = str(d.get("checkoutUrl") or "").split("?", 1)[0]
    codigos = {str(oferta.get("id") or ""), url.rstrip("/").rsplit("/", 1)[-1]}
    return OFERTA_BUMP_MAPAS in {c.split("_")[0] for c in codigos if c}


def dados_nascimento(pd: dict, produto: str, exige_hora: bool = True):
    """Monta os dados de nascimento a partir dos pd_*. Retorna dict ou None se faltar o essencial.
    `exige_hora=False` (versão ocidental, só no mapa): hora vazia = "não sei a hora"."""
    def campo(nome):
        return pd.get("pd_" + nome, "")

    if produto == "mapa":
        d = {"nome": campo("nome"), "data": campo("data"), "hora": campo("hora"),
             "lat": campo("lat"), "lon": campo("lon"), "cidade": campo("cidade")}
        if not (d["data"] and (d["hora"] or not exige_hora) and d["lat"] and d["lon"]):
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

"""
Padmini — o PEDIDO PENDENTE do checkout próprio (rodada 11, Stripe).

Na Cakto, os dados de nascimento viajavam no `sck` da URL do checkout e voltavam no
webhook. No checkout próprio eles ficam com a gente: ao clicar em comprar, o navegador
manda o produto, os dados da leitura e o contato; o servidor valida, grava um pedido
pendente no banco (`pedidos_pendentes`) e a Stripe recebe só o `id` opaco dele (em
`metadata` e `client_reference_id`) e o e-mail (em `customer_email`). Quando a Stripe
confirma o pagamento, o webhook acha o pendente pelo id e entrega pelo mesmo caminho
da Cakto.

O que este módulo garante (e os testes conferem):
  - o PREÇO nunca vem do navegador: o modelo `PedidoCheckout` não tem campo de preço
    (o que vier a mais é descartado) e o valor de cada item sai do `ofertas.yaml`,
    com o cupom aplicado aqui (`cupom_codigos` + `cupom_percentual`), nunca na Stripe;
  - os dados de cada leitura são só os campos que a entrega usa, no mesmo formato de
    `cakto.dados_nascimento` (mapa, sinastria, numerologia, tarot);
  - o id é aleatório e opaco (não diz nada da pessoa nem do produto).

Um produto por compra nesta rodada; o formato (`itens` é uma lista) já aceita vários.
"""

import secrets
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field

import ofertas
from rotas_ocidental import EMAIL_RE, ORIGEM_ACEITA, PessoaOcidental

SISTEMA = "ocidental"  # a Stripe vale só para a versão com catálogo (ver pagamento.py)
PRODUTOS = ("mapa", "compat", "numerologia", "tarot")
MOEDA = "brl"


class PedidoCheckout(BaseModel):
    """O que o navegador manda ao clicar em comprar. Sem preço, de propósito: campo
    a mais (preco, valor, amount…) é ignorado."""
    model_config = ConfigDict(extra="ignore")

    produto: str = Field(..., pattern=r"^(mapa|compat|numerologia|tarot)$")
    pessoa: PessoaOcidental | None = None             # mapa
    a: PessoaOcidental | None = None                  # sinastria
    b: PessoaOcidental | None = None
    nome: str | None = Field(None, max_length=120)    # numerologia: nome completo de registro
    data: date | None = None                          # numerologia
    tiragem: str | None = Field(None, max_length=40)  # tarot: só o id da tiragem
    email: str = Field(..., max_length=160)
    aceita_sequencia: bool = False                    # a caixa da amostra (rodada 6)
    origem: dict = Field(default_factory=dict)        # ref, cupom, utm_* (afiliado.js)


class PedidoInvalido(ValueError):
    pass


def novo_id() -> str:
    """Id opaco do pendente: 24 caracteres aleatórios (base64 de URL)."""
    return secrets.token_urlsafe(18)


def _pessoa(p: PessoaOcidental) -> dict:
    return {"nome": p.nome.strip()[:80], "data": p.data.isoformat(), "hora": p.hora,
            "lat": p.lat, "lon": p.lon, "cidade": p.cidade.strip()[:200]}


def dados_da_leitura(pedido: PedidoCheckout) -> dict:
    """Os dados de UMA leitura, no formato que a entrega usa (cakto.dados_nascimento).
    PedidoInvalido se faltar o essencial."""
    if pedido.produto == "mapa":
        if not pedido.pessoa:
            raise PedidoInvalido("Faltam os dados de nascimento.")
        return _pessoa(pedido.pessoa)
    if pedido.produto == "compat":
        if not (pedido.a and pedido.b):
            raise PedidoInvalido("Faltam os dados de nascimento das duas pessoas.")
        a, b = _pessoa(pedido.a), _pessoa(pedido.b)
        return {"a": a, "b": b, "nome": a["nome"]}
    if pedido.produto == "numerologia":
        nome = (pedido.nome or "").strip()
        if not (nome and pedido.data):
            raise PedidoInvalido("Faltam o nome completo e a data de nascimento.")
        return {"nome": nome, "data": pedido.data.isoformat()}
    tiragem = (pedido.tiragem or "").strip()
    if not tiragem:
        raise PedidoInvalido("Falta a tiragem.")
    return {"tiragem": tiragem}


def rastreio(origem: dict) -> dict:
    """ref, cupom e utm_* (só esses, curtos): a origem da venda, como o `rastreio` de
    `pedidos`. Fica no nosso banco; não vai para a Stripe."""
    return {k: str(v).strip()[:80] for k, v in (origem or {}).items()
            if k in ORIGEM_ACEITA and v not in (None, "") and str(v).strip()}


def cupom_valido(produto: str, origem: dict) -> str:
    """O código do cupom, em minúsculas, se ele vale para este produto; senão ''."""
    codigo = str((origem or {}).get("cupom") or "").strip().lower()
    oferta = ofertas.oferta(produto, SISTEMA)
    if codigo and oferta.get("cupom_percentual") and codigo in oferta.get("cupom_codigos", []):
        return codigo
    return ""


def centavos(valor) -> int:
    return int((Decimal(str(valor)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def valor_centavos(produto: str, cupom: str = "") -> int:
    """O preço do produto, do ofertas.yaml (com o cupom, se valer). Nada do navegador.
    Sem a taxa da plataforma da Cakto: na Stripe a pessoa paga só o preço."""
    oferta = ofertas.oferta(produto, SISTEMA)
    if not oferta.get("preco"):
        raise PedidoInvalido(f"Produto sem preço no ofertas.yaml: {produto}")
    preco = oferta["preco_cupom"] if cupom and oferta.get("preco_cupom") else oferta["preco"]
    return centavos(preco)


def nome_da_leitura(produto: str, dados: dict) -> str:
    """O nome de quem é a leitura (para o resumo do pedido e o "Olá" do e-mail)."""
    if produto == "compat":
        return " e ".join(n for n in ((dados.get("a") or {}).get("nome"), (dados.get("b") or {}).get("nome")) if n)
    return str(dados.get("nome") or "")


def montar(pedido: PedidoCheckout) -> dict:
    """O pedido pendente pronto para `db.criar_pendente`. PedidoInvalido se não der."""
    email = (pedido.email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise PedidoInvalido("Confira o e-mail: é para ele que a leitura vai.")
    if pedido.produto not in PRODUTOS:
        raise PedidoInvalido("Produto desconhecido.")
    dados = dados_da_leitura(pedido)
    origem = rastreio(pedido.origem)
    cupom = cupom_valido(pedido.produto, origem)
    valor = valor_centavos(pedido.produto, cupom)
    return {
        "id": novo_id(),
        "sistema": SISTEMA,
        "itens": [{"chave": pedido.produto, "dados": dados, "valor_centavos": valor}],
        "email": email,
        "nome": nome_da_leitura(pedido.produto, dados)[:160],
        "consentimentos": {"aceita_sequencia": bool(pedido.aceita_sequencia)},
        "rastreio": origem,
        "cupom": cupom or None,
        "valor_centavos": valor,
        "moeda": MOEDA,
    }

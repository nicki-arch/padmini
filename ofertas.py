"""
Padmini — preços e links de checkout, lidos de `conteudo/<versão>/ofertas.yaml`
(um arquivo por versão do site: `vedica` e `ocidental`, ver sistema.py).

Existe porque os mesmos números viviam em três lugares: o preço escrito na home,
o link do checkout no JavaScript de cada página e o código da oferta no
`cakto.py` (que é como o webhook descobre qual produto foi comprado). Mudar o
preço na Cakto e esquecer um dos três é como o site passa a anunciar um valor e
cobrar outro — ou o webhook deixa de reconhecer a compra.

As páginas são templates (Jinja) e leem estes valores como `ofertas.compat.preco`.
O código da oferta não é configurado: sai do próprio link do checkout
(`https://pay.cakto.com.br/<codigo>_<numero>`), que é o mesmo identificador que
a Cakto manda no webhook.

As ofertas das DUAS versões ficam carregadas o tempo todo, qualquer que seja a
versão no ar: o webhook precisa reconhecer uma compra feita minutos antes da
troca. As funções abaixo recebem `sistema`; sem ele, valem para a védica (o
comportamento de antes da Fase 0.5).
"""

from pathlib import Path

import yaml

import sistema as _sistema

PASTA = Path(__file__).parent / "conteudo"


def _codigo_da_oferta(checkout: str) -> str:
    """https://pay.cakto.com.br/qo8uskp_1125345 → 'qo8uskp'."""
    ultimo = str(checkout or "").rstrip("/").rsplit("/", 1)[-1]
    return ultimo.split("_")[0]


def arquivo(sistema: str) -> Path:
    return PASTA / sistema / "ofertas.yaml"


def _carregar(sistema: str) -> dict:
    dados = yaml.safe_load(arquivo(sistema).read_text(encoding="utf-8")) or {}
    for chave, oferta in dados.items():
        oferta["checkout"] = str(oferta.get("checkout") or "")
        oferta["codigo"] = _codigo_da_oferta(oferta["checkout"])
        # sempre definido (None = sem desconto): os templates usam StrictUndefined,
        # e `{% if ofertas.compat.preco_de %}` com a chave ausente seria erro.
        oferta.setdefault("preco_de", None)
        oferta.setdefault("preco_cupom", None)  # preço com cupom de afiliado (só a ocidental usa)
        de, por = oferta.get("preco_de"), oferta.get("preco")
        if de and por and de > por:
            oferta["economia"] = de - por
            oferta["desconto"] = round((de - por) / de * 100)
    return dados


POR_SISTEMA = {s: _carregar(s) for s in _sistema.SISTEMAS}

# Nome antigo, mantido: as ofertas da védica (os testes trocam este dicionário).
OFERTAS = POR_SISTEMA["vedica"]


def do_sistema(sistema: str = "vedica") -> dict:
    if sistema == "vedica":
        return OFERTAS  # lido na hora: respeita quem troca OFERTAS (testes)
    return POR_SISTEMA[sistema]


def oferta(chave: str, sistema: str = "vedica") -> dict:
    return do_sistema(sistema).get(chave, {})


def preco(chave: str, sistema: str = "vedica") -> str:
    """Só o número, do jeito que vai para a tela: 97 → '97'."""
    return str(oferta(chave, sistema).get("preco", ""))


def codigo(chave: str, sistema: str = "vedica") -> str:
    return oferta(chave, sistema).get("codigo", "")


def checkout(chave: str, sistema: str = "vedica") -> str:
    return oferta(chave, sistema).get("checkout", "")


def todas_as_ofertas() -> list[tuple[str, str, dict]]:
    """(versão, chave, oferta) de todas as versões — para o webhook e o smoke."""
    return [(s, chave, o) for s in _sistema.SISTEMAS for chave, o in do_sistema(s).items()]

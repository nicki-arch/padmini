"""
Padmini — preços e links de checkout, lidos de `conteudo/ofertas.yaml`.

Existe porque os mesmos números viviam em três lugares: o preço escrito na home,
o link do checkout no JavaScript de cada página e o código da oferta no
`cakto.py` (que é como o webhook descobre qual produto foi comprado). Mudar o
preço na Cakto e esquecer um dos três é como o site passa a anunciar um valor e
cobrar outro — ou o webhook deixa de reconhecer a compra.

O código da oferta não é configurado: sai do próprio link do checkout
(`https://pay.cakto.com.br/<codigo>_<numero>`), que é o mesmo identificador que
a Cakto manda no webhook.
"""

from pathlib import Path

import yaml

ARQUIVO = Path(__file__).parent / "conteudo" / "ofertas.yaml"


def _codigo_da_oferta(checkout: str) -> str:
    """https://pay.cakto.com.br/qo8uskp_1125345 → 'qo8uskp'."""
    ultimo = str(checkout or "").rstrip("/").rsplit("/", 1)[-1]
    return ultimo.split("_")[0]


def _carregar() -> dict:
    dados = yaml.safe_load(ARQUIVO.read_text(encoding="utf-8")) or {}
    for chave, oferta in dados.items():
        oferta["checkout"] = str(oferta.get("checkout") or "")
        oferta["codigo"] = _codigo_da_oferta(oferta["checkout"])
        de, por = oferta.get("preco_de"), oferta.get("preco")
        if de and por and de > por:
            oferta["economia"] = de - por
            oferta["desconto"] = round((de - por) / de * 100)
    return dados


OFERTAS = _carregar()


def oferta(chave: str) -> dict:
    return OFERTAS.get(chave, {})


def preco(chave: str) -> str:
    """Só o número, do jeito que vai para a tela: 97 → '97'."""
    return str(oferta(chave).get("preco", ""))


def codigo(chave: str) -> str:
    return oferta(chave).get("codigo", "")


def checkout(chave: str) -> str:
    return oferta(chave).get("checkout", "")


def substituicoes() -> dict[str, str]:
    """Marcadores que o app troca no HTML antes de servir a página.

    Feito no servidor, e não por JavaScript, para o preço já sair no HTML: com
    fetch, a pessoa veria o bloco de preço vazio até a resposta chegar.
    """
    c, m = oferta("compat"), oferta("mapa")
    return {
        "__CHECKOUT_MAPA__": m.get("checkout", ""),
        "__CHECKOUT_COMPAT__": c.get("checkout", ""),
        "__PRECO_MAPA__": str(m.get("preco", "")),
        "__PRECO_COMPAT__": str(c.get("preco", "")),
        "__PRECO_COMPAT_DE__": str(c.get("preco_de", "")),
        "__DESCONTO_COMPAT__": str(c.get("desconto", "")),
        "__ECONOMIA_COMPAT__": str(c.get("economia", "")),
    }

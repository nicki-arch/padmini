"""
Valderez Astrologia (versão ocidental) — os ÍCONES de traço (rodada 9.1).

Um SVG por ícone em `static/valderez/icones/<nome>.svg` (traço em `currentColor`,
24×24, tirados das telas do pacote valderez-design-2.0). O YAML pede o ícone pelo
nome (`icone: sol`) e o template chama `icone("sol")`, que põe o desenho inline
(herda a cor do texto, sem pedido a mais ao servidor).

A roda é o símbolo da marca e NUNCA vira ícone de lista: não existe "roda" aqui,
e nome que não existe quebra na hora (no teste), não na página no ar.
"""
from functools import lru_cache
from pathlib import Path

PASTA = Path(__file__).parent / "static" / "valderez" / "icones"
NOMES = tuple(sorted(p.stem for p in PASTA.glob("*.svg")))


@lru_cache(maxsize=None)
def _arquivo(nome: str) -> str:
    if nome not in NOMES:
        raise KeyError(f"ícone {nome!r} não existe em static/valderez/icones/ (há: {', '.join(NOMES)})")
    return (PASTA / f"{nome}.svg").read_text(encoding="utf-8").strip()


def svg(nome: str, tamanho: int = 22) -> str:
    """O ícone inline, decorativo (o texto ao lado diz o que ele é)."""
    return _arquivo(nome).replace(
        "<svg ", f'<svg class="icone" width="{tamanho}" height="{tamanho}" aria-hidden="true" focusable="false" ', 1)


def conferir(itens, onde: str) -> None:
    """Erro claro na subida se um item do YAML pedir ícone que não existe (ou nenhum)."""
    for item in itens or []:
        if item.get("icone") not in NOMES:
            raise KeyError(f"{onde}: item {item.get('titulo')!r} sem `icone` válido "
                           f"(use um de: {', '.join(NOMES)})")

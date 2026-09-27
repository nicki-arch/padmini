"""
Padmini (versão ocidental) — DEPOIMENTOS (round 5).

Só depoimento de verdade, de cliente de verdade, com autorização por escrito.
Nada de texto inventado nem número de "casais atendidos" que não saia do banco.
Enquanto conteudo/ocidental/depoimentos.yaml estiver vazio, a seção da home
simplesmente não aparece.

Cada item precisa de: texto, nome (como a pessoa autorizou, ex.: "Marina S."),
produto (sinastria | mapa | numerologia | tarot) e autorizado_em (AAAA-MM-DD,
a data da autorização — guarde a mensagem em que ela foi dada). Item sem algum
desses campos não aparece.
"""
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

ARQUIVO = Path(__file__).resolve().parent / "conteudo" / "ocidental" / "depoimentos.yaml"
PRODUTOS = {"sinastria": "Sinastria", "mapa": "Mapa natal", "numerologia": "Numerologia", "tarot": "Tarot"}


def valido(d: dict) -> bool:
    return (isinstance(d, dict) and str(d.get("texto") or "").strip() and str(d.get("nome") or "").strip()
            and d.get("produto") in PRODUTOS and isinstance(d.get("autorizado_em"), date))


@lru_cache(maxsize=None)
def todos() -> tuple:
    dados = yaml.safe_load(ARQUIVO.read_text(encoding="utf-8")) or {}
    return tuple(dados.get("depoimentos") or ())


def publicaveis() -> list[dict]:
    return [{**d, "produto_nome": PRODUTOS[d["produto"]]} for d in todos() if valido(d)]

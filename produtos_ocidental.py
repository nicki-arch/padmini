"""
Valderez Astrologia (versão ocidental) — o texto das páginas de produto
(conteudo/ocidental/produtos.yaml, rodada 9) e o "trecho real" de cada uma:
calculado na hora com a base de textos, nunca escrito para a página.
"""
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

import textos

ARQUIVO = Path(__file__).parent / "conteudo" / "ocidental" / "produtos.yaml"
_dados = textos.com_indice(yaml.safe_load(ARQUIVO.read_text(encoding="utf-8")) or {})
for _p in _dados.values():  # os templates usam StrictUndefined
    for _campo, _vazio in (("rascunho", False), ("selos", []), ("recebe", []), ("passos", []), ("faq", []),
                           ("trecho", {})):
        _p.setdefault(_campo, _vazio)
for _item in (_dados.get("cursos") or {}).get("itens") or []:
    _item.setdefault("catalogo", "")


def pagina(chave: str) -> dict | None:
    return _dados.get(chave)


def cursos() -> dict:
    return _dados.get("cursos") or {}


@lru_cache(maxsize=None)
def trecho_real(chave: str) -> dict:
    """{rotulo, titulo, texto} do bloco "Veja como é por dentro". Para os produtos
    com leitura (sinastria, numerologia, tarot), um texto de verdade da base; para os
    outros, o texto do YAML."""
    import montar_texto_ocidental as mt
    t = (pagina(chave) or {}).get("trecho") or {}
    de = t.get("de")
    if de == "sinastria":
        import exemplos_ocidental as ex
        casal = ex.casais()[0]
        dim = next(d for d in casal["relatorio"]["dimensoes"] if d["chave"] == "emocoes")
        return {"rotulo": f"{dim['titulo']} · trecho real", "titulo": f"{casal['nomes']['a']} e {casal['nomes']['b']}",
                "texto": dim["texto"], "nota": "Exemplo com nascimentos fictícios, calculado pelo mesmo método."}
    if de == "numerologia":
        n = mt._numero(t["numero"], t["valor"])
        return {"rotulo": f"{n['nome']} {n['valor']} · trecho real", "titulo": "Exemplo", "texto": n["texto"], "nota": ""}
    if de == "tarot":
        import tarot
        carta = next(c for c in tarot.CARTAS if c["chave"] == t["carta"])
        leitura = mt._carta({**carta, "posicao": "situacao", "posicao_pt": "Situação"}, "completo")
        return {"rotulo": f"{carta['nome']} na situação · trecho real", "titulo": "Exemplo",
                "texto": leitura["leitura"], "nota": ""}
    return {"rotulo": t.get("rotulo", ""), "titulo": t.get("titulo", ""), "texto": t.get("texto", ""), "nota": ""}


def hoje() -> date:
    return date.today()

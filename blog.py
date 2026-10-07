"""
Padmini (versão ocidental) — BLOG (round 5).

Artigos em conteudo/ocidental/blog/<slug>.yaml. Mesma regra dos textos de
leitura: nada vai ao ar sem a família revisar. Cada artigo tem `revisado`;
só os `revisado: true` aparecem em /blog, no sitemap e no menu. Rascunho abre
só com a chave de prévia (PADMINI_PREVIA_CHAVE), com a faixa "rascunho" e fora
do buscador — para quem revisa ler como vai ficar.

Formato:
    titulo, descricao (buscador e lista), data (AAAA-MM-DD), revisado (bool),
    abertura (parágrafo de entrada), secoes: [{titulo, paragrafos: [...]}],
    chamada: {texto, botao, href} (sempre para uma amostra grátis).
"""
import re
from datetime import date
from functools import lru_cache

import yaml

import conteudo_privado
import textos

PASTA = conteudo_privado.BLOG  # repositório privado (rodada 10): os rascunhos não são públicos
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
OBRIGATORIOS = ("titulo", "descricao", "data", "revisado", "abertura", "secoes", "chamada")


@lru_cache(maxsize=None)
def todos() -> tuple[dict, ...]:
    """Todos os artigos (rascunhos inclusive), do mais novo para o mais velho."""
    artigos = []
    for arq in sorted(PASTA.glob("*.yaml")):
        dados = textos.com_indice(yaml.safe_load(arq.read_text(encoding="utf-8")) or {})
        faltando = [k for k in OBRIGATORIOS if k not in dados]
        if faltando or not SLUG.match(arq.stem):
            raise ValueError(f"blog/{arq.name}: campos faltando {faltando} ou nome de arquivo inválido")
        d = dados["data"] if isinstance(dados["data"], date) else date.fromisoformat(str(dados["data"]))
        artigos.append({**dados, "slug": arq.stem, "data": d, "data_br": d.strftime("%d/%m/%Y")})
    return tuple(sorted(artigos, key=lambda a: (a["data"], a["slug"]), reverse=True))


def publicados() -> list[dict]:
    return [a for a in todos() if a["revisado"] is True]


def artigo(slug: str) -> dict | None:
    return next((a for a in todos() if a["slug"] == slug), None)

"""
Valderez Astrologia (versão ocidental) — o CATÁLOGO: quais produtos estão no ar,
em que estado, em que ordem, e se o site vende. Lido de
`conteudo/ocidental/catalogo.yaml` (ver o cabeçalho de lá).

    ativo     aparece em todo lugar e a página funciona
    em_breve  aparece com "em breve"; a página mostra o "me avise"
    oculto    não aparece em lugar nenhum; a rota responde 404

`vendas_abertas()` é o interruptor de venda: com `false`, nenhuma página nem
e-mail mostra preço, botão de compra ou link da Cakto.

Só a ocidental tem catálogo. A védica não pergunta nada aqui: as funções que
recebem `sistema` respondem como antes para ela (vende, tudo no ar).

O que o catálogo NÃO decide (de propósito): links já entregues (com `token`),
o /live do Pedro, o webhook da Cakto e o /minhas-leituras. Quem comprou antes
continua lendo, qualquer que seja o estado do produto.
"""

from pathlib import Path

import yaml

ARQUIVO = Path(__file__).parent / "conteudo" / "ocidental" / "catalogo.yaml"
ESTADOS = ("ativo", "em_breve", "oculto")


class CatalogoInvalido(ValueError):
    pass


def validar(dados: dict) -> dict:
    """Erro claro na subida (em vez de página pela metade) se o YAML estiver errado."""
    if not isinstance(dados.get("vendas_abertas"), bool):
        raise CatalogoInvalido("catalogo.yaml: `vendas_abertas` precisa ser true ou false.")
    chaves, rotas = set(), set()
    for p in dados.get("produtos") or []:
        for campo in ("chave", "nome", "rota", "estado"):
            if not p.get(campo):
                raise CatalogoInvalido(f"catalogo.yaml: produto sem `{campo}`: {p!r}")
        if p["estado"] not in ESTADOS:
            raise CatalogoInvalido(f"catalogo.yaml: estado {p['estado']!r} de {p['chave']!r} não existe "
                                   f"(use {', '.join(ESTADOS)}).")
        if p["chave"] in chaves or p["rota"] in rotas:
            raise CatalogoInvalido(f"catalogo.yaml: chave ou rota repetida em {p['chave']!r}.")
        if not str(p["rota"]).startswith("/"):
            raise CatalogoInvalido(f"catalogo.yaml: rota de {p['chave']!r} precisa começar com /.")
        for campo in ("oferta", "resumo", "vaga", "botao"):  # templates usam StrictUndefined
            p.setdefault(campo, None if campo == "oferta" else "")
        chaves.add(p["chave"])
        rotas.add(p["rota"])
    for d in dados.get("dimensoes_mapa") or []:
        if d.get("estado") not in ("ativo", "em_breve"):
            raise CatalogoInvalido(f"catalogo.yaml: dimensão {d.get('chave')!r} com estado inválido.")
    return dados


def carregar(arquivo: Path = ARQUIVO) -> dict:
    return validar(yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {})


_dados = carregar()


def usar(dados: dict) -> None:
    """Troca o catálogo em memória (os testes usam; o site lê o YAML na subida)."""
    global _dados
    _dados = validar(dados)


def dados() -> dict:
    return _dados


def vendas_abertas(sistema: str = "ocidental") -> bool:
    """O interruptor de venda. A védica não tem catálogo: vende como sempre."""
    return True if sistema != "ocidental" else bool(_dados["vendas_abertas"])


def produtos() -> list[dict]:
    return list(_dados.get("produtos") or [])


def visiveis() -> list[dict]:
    """O que aparece no menu, na home, no rodapé e em "Todas as leituras"."""
    return [p for p in produtos() if p["estado"] != "oculto"]


def produto(chave: str) -> dict | None:
    return next((p for p in produtos() if p["chave"] == chave), None)


def por_rota(rota: str) -> dict | None:
    return next((p for p in produtos() if p["rota"] == rota), None)


def estado(chave: str) -> str:
    """Estado do produto; chave fora do catálogo conta como oculto."""
    p = produto(chave)
    return p["estado"] if p else "oculto"


def ativo(chave: str) -> bool:
    return estado(chave) == "ativo"


def interesses() -> tuple[str, ...]:
    """Valores aceitos como `interesse` no "me avise" / lista: produtos visíveis."""
    return tuple(p["chave"] for p in visiveis())


def vende(chave: str, sistema: str = "ocidental") -> bool:
    """Mostra preço e botão de compra deste produto? Só com a venda aberta e o produto ativo."""
    if sistema != "ocidental":
        return True
    return vendas_abertas() and ativo(chave)


def dimensoes_mapa() -> list[dict]:
    return list(_dados.get("dimensoes_mapa") or [])


def textos() -> dict:
    """A copy do catálogo (me avise, em breve, todas as leituras)."""
    return {k: _dados.get(k) or {} for k in ("me_avise", "em_breve", "leituras")}

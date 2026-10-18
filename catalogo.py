"""
Valderez Astrologia (versão ocidental) — o CATÁLOGO: quais produtos estão no ar,
em que estado, em que ordem, e se o site vende. Lido de
`conteudo/ocidental/catalogo.yaml` (ver o cabeçalho de lá).

Rodada 15: o YAML é o PADRÃO; quem manda no ar é o /painel. O estado de cada produto
e o interruptor de venda passam por `estado_site.py` (painel → YAML), que também aplica
o "tudo liberado". `produtos()`, `visiveis()`, `estado()` e `ativo()` já devolvem o
estado no ar; o YAML cru fica em `dados()` / `produtos_do_yaml()` (o painel mostra).

    ativo     aparece em todo lugar e a página funciona
    em_breve  aparece com "em breve"; a página mostra o "me avise"
    oculto    não aparece em lugar nenhum; a rota responde 404

`vendas_abertas()` é o interruptor de venda: com `false`, nenhuma página nem
e-mail mostra preço, botão de compra ou link da Cakto. A única exceção é a prévia
com PADMINI_VENDAS_TESTE=1 (rodada 11, `pagamento.vendas_teste`): a venda abre só
naquele serviço, e só em modo de teste da Stripe — o YAML não muda.

Só a ocidental tem catálogo. A védica não pergunta nada aqui: as funções que
recebem `sistema` respondem como antes para ela (vende, tudo no ar).

O que o catálogo NÃO decide (de propósito): links já entregues (com `token`),
o /live do Pedro, o webhook da Cakto e o /minhas-leituras. Quem comprou antes
continua lendo, qualquer que seja o estado do produto.
"""

from pathlib import Path

import yaml

import estado_site
import pagamento

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
        for campo in ("ponto", "rotulo", "descricao", "vaga"):
            d.setdefault(campo, "")
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
    """O interruptor de venda. A védica não tem catálogo: vende como sempre.
    PADMINI_VENDAS_TESTE=1 (só com a Stripe em modo de teste) abre a venda no serviço
    em que estiver, sem mexer no YAML."""
    if sistema != "ocidental":
        return True
    return estado_site.vendas_abertas(bool(_dados["vendas_abertas"])) or pagamento.vendas_teste()


def produtos_do_yaml() -> list[dict]:
    """Os produtos como estão no catalogo.yaml (o padrão, sem o painel)."""
    return list(_dados.get("produtos") or [])


def produtos() -> list[dict]:
    """Os produtos com o estado NO AR (painel → YAML; "tudo liberado" por cima)."""
    return [dict(p, estado=estado_site.estado_produto(p["chave"], p["estado"])) for p in produtos_do_yaml()]


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


def estado_publico(chave: str) -> str:
    """O estado que vale para VENDER: o do público, sem o modo teste do navegador logado
    no painel (que mostra o produto, mas nunca abre uma venda de verdade)."""
    p = next((x for x in produtos_do_yaml() if x["chave"] == chave), None)
    return estado_site.estado_produto(chave, p["estado"], publico=True) if p else "oculto"


def vende(chave: str, sistema: str = "ocidental") -> bool:
    """Mostra preço e botão de compra deste produto? Só com a venda aberta e o produto
    ativo para o público (o checkout pergunta a mesma coisa)."""
    if sistema != "ocidental":
        return True
    return vendas_abertas() and estado_publico(chave) == "ativo"


def colunas(quantos: int, maximo: int = 4) -> int:
    """Colunas da grade de capas no computador (rodada 9.1): o número de colunas
    acompanha o número de cartões, para nenhum ficar sozinho na última linha.
    Até `maximo` cartões, uma linha só; depois, o maior número de colunas que não
    deixa sobrar 1 (5 → 3+2, 7 → 4+3, 9 → 3+3+3). No celular a grade é de uma coluna (CSS)."""
    if quantos <= maximo:
        return max(quantos, 1)
    for c in range(maximo, 1, -1):
        if quantos % c != 1:
            return c
    return 2


def dimensoes_mapa() -> list[dict]:
    return list(_dados.get("dimensoes_mapa") or [])


def textos() -> dict:
    """A copy do catálogo (me avise, em breve, todas as leituras)."""
    return {k: _dados.get(k) or {} for k in ("me_avise", "em_breve", "leituras", "dimensao_em_breve")}

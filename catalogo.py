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
        kit = bool(p.get("inclui"))  # rodada 20: um pacote não tem rota (nem página): tem `entrada`
        for campo in ("chave", "nome", "entrada" if kit else "rota", "estado"):
            if not p.get(campo):
                raise CatalogoInvalido(f"catalogo.yaml: produto sem `{campo}`: {p!r}")
        if p["estado"] not in ESTADOS:
            raise CatalogoInvalido(f"catalogo.yaml: estado {p['estado']!r} de {p['chave']!r} não existe "
                                   f"(use {', '.join(ESTADOS)}).")
        if kit:
            p["rota"] = None
            if not str(p["entrada"]).startswith("/"):
                raise CatalogoInvalido(f"catalogo.yaml: entrada de {p['chave']!r} precisa começar com /.")
            if not p.get("oferta") or not isinstance(p["inclui"], list) or len(set(p["inclui"])) < 2:
                raise CatalogoInvalido(f"catalogo.yaml: o kit {p['chave']!r} precisa de `oferta` e de "
                                       "`inclui` com dois produtos ou mais.")
        if p["chave"] in chaves or (p["rota"] and p["rota"] in rotas):
            raise CatalogoInvalido(f"catalogo.yaml: chave ou rota repetida em {p['chave']!r}.")
        if p["rota"] and not str(p["rota"]).startswith("/"):
            raise CatalogoInvalido(f"catalogo.yaml: rota de {p['chave']!r} precisa começar com /.")
        for campo in ("oferta", "resumo", "vaga", "botao"):  # templates usam StrictUndefined
            p.setdefault(campo, None if campo == "oferta" else "")
        p.setdefault("inclui", [])
        p.setdefault("entrada", p["rota"])
        chaves.add(p["chave"])
        if p["rota"]:
            rotas.add(p["rota"])
    # o que um kit inclui: produtos de verdade, com oferta (que se vendem sozinhos), nunca outro kit
    simples = {p["chave"]: p for p in dados.get("produtos") or [] if not p["inclui"]}
    for p in dados.get("produtos") or []:
        for chave in p["inclui"]:
            if chave not in simples or not simples[chave].get("oferta"):
                raise CatalogoInvalido(f"catalogo.yaml: o kit {p['chave']!r} inclui {chave!r}, que não é "
                                       "um produto com oferta do catálogo.")
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
    """O que aparece no menu, na home, no rodapé e em "Todas as leituras". Kits nunca:
    não têm página (a /links e "Todas as leituras" mostram o kit à parte, com `vende`)."""
    return [p for p in produtos() if p["estado"] != "oculto" and not p["inclui"]]


def produto(chave: str) -> dict | None:
    return next((p for p in produtos() if p["chave"] == chave), None)


def por_rota(rota: str) -> dict | None:
    return next((p for p in produtos() if p["rota"] and p["rota"] == rota), None)


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
    ativo para o público (o checkout pergunta a mesma coisa). Um KIT (rodada 20) também
    exige que TODOS os produtos que ele inclui se vendam, e o checkout próprio (Stripe)."""
    if sistema != "ocidental":
        return True
    # produto sem `oferta` (comunidade, cursos, consulta…) não se vende: nem no "tudo liberado"
    # da prévia, que liga todos (rodada 15; antes a /links quebrava procurando o preço dele)
    p = next((x for x in produtos_do_yaml() if x["chave"] == chave), None)
    if not (p and p.get("oferta") and vendas_abertas() and estado_publico(chave) == "ativo"):
        return False
    if p["inclui"]:
        return pagamento.stripe() and all(vende(c, sistema) for c in p["inclui"])
    return True


# ------------------------------------------------------------------ kits (rodada 20)
def inclui(chave: str) -> list[str]:
    """Os produtos de um kit (vazio para produto comum)."""
    p = next((x for x in produtos_do_yaml() if x["chave"] == chave), None)
    return list(p["inclui"]) if p else []


def kits_a_venda() -> list[dict]:
    """Os kits que se vendem agora (para a /links e "Todas as leituras")."""
    return [p for p in produtos() if p["inclui"] and vende(p["chave"])]


def faltam_para_o_kit(chave: str) -> list[dict]:
    """Os produtos do kit que NÃO estão à venda agora (o aviso do /painel)."""
    return [x for x in produtos_do_yaml() if x["chave"] in inclui(chave) and not vende(x["chave"])]


def quem_inclui(chave: str) -> list[str]:
    """O próprio produto e os kits que o incluem: comprar qualquer um deles é ter `chave`."""
    return [chave] + [p["chave"] for p in produtos_do_yaml() if chave in p["inclui"]]


def que_tem(comprados) -> set[str]:
    """As chaves dos produtos que alguém TEM, a partir do que comprou ("ocidental:kit",
    "mapa"…): quem comprou o kit tem cada produto dele; o combo do casal conta como mapa.
    Para nenhum e-mail oferecer o que a pessoa já tem."""
    tem = {str(c).split(":", 1)[-1] for c in comprados or []}
    for k in list(tem):
        tem.update(inclui(k))
    if "mapas_casal" in tem:
        tem.add("mapa")
    return tem


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
    """A copy do catálogo (me avise, em breve, todas as leituras, o kit)."""
    return {k: _dados.get(k) or {} for k in ("me_avise", "em_breve", "leituras", "dimensao_em_breve", "kit")}

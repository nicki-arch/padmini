"""
Valderez Astrologia — o ESTADO DO SITE (rodada 15): a fonte única do que está no ar.

Quem manda no ar é o /painel; o YAML e as variáveis são só o PADRÃO, usado enquanto
o painel não salvou nada. Precedência, chave a chave:

    1. o valor salvo pelo painel (tabela `config_site`, no banco de cada serviço);
    2. sem nada salvo: `conteudo/ocidental/catalogo.yaml` (venda e estado de cada
       produto) e PADMINI_CAPTURA=1 (modo lista de espera), como antes da rodada 15;
    3. sem nada disso: modo aberto, página visível.

Assim o primeiro deploy não muda nada no ar. Quem pergunta: `catalogo.py` (venda,
estado dos produtos) e o `app.py` (modo, páginas escondidas). Não existe um segundo
lugar decidindo isso.

O banco é lido no máximo a cada CACHE_SEGUNDOS: uma mudança no painel aparece no site
em até 15 s, sem deploy (no processo que salvou, na hora: `invalidar()`). Banco fora do
ar: fica o último estado conhecido (e, sem nenhum, o YAML) e sai o alerta de sempre. O
painel nunca derruba o site.

Os quatro modos:
    aberto         o normal: estados dos produtos e interruptor de venda
    lista_espera   home, mapa e produtos mandam para /lista (o PADMINI_CAPTURA=1 de antes)
    manutencao     "Voltamos já", 503 com Retry-After (o app decide o que continua de pé)
    tudo_liberado  na PRÉVIA (Stripe de teste), para todo mundo: todo produto ativo, venda
                   de teste aberta. Na PRODUÇÃO, o público vê o "aberto"; só o navegador
                   logado no painel vê tudo liberado.

"Tudo liberado só para mim" (cookie do painel) vale nos dois ambientes e não muda o modo
do site. Liberado para a pessoa = produtos ocultos e em breve como ativos e a leitura
completa sem pagar; a VENDA continua a pública (`estado_produto(..., publico=True)`):
o modo teste nunca abre venda de verdade. Esse estado pessoal vive numa ContextVar
marcada pelo app a cada pedido; páginas montadas com ele não entram no cache.
"""
import contextvars
import json
import logging
import os
import threading
import time

import pagamento

log = logging.getLogger("padmini.estado_site")

MODOS = ("aberto", "lista_espera", "manutencao", "tudo_liberado")
NOMES_MODO = {"aberto": "Aberto", "lista_espera": "Lista de espera", "manutencao": "Manutenção",
              "tudo_liberado": "Tudo liberado"}
ESTADOS = ("ativo", "em_breve", "oculto")
# Páginas que o painel pode esconder (404 e fora de menu, rodapé e sitemap). A home, os
# termos, a privacidade, a /lista, os links com token, /minhas-leituras, o checkout, os
# webhooks, a /api e o próprio /painel NUNCA entram aqui. /cursos é produto do catálogo
# (Ativo · Em breve · Oculto), não página.
PAGINAS = {"/blog": "Blog", "/links": "Links (bio)", "/leituras": "Todas as leituras"}
CACHE_SEGUNDOS = 15

_trava = threading.Lock()
_salvo: dict | None = None      # o último estado lido do banco (None = nunca leu)
_lido_em: float | None = None   # time.monotonic() da última tentativa (None = ler já)

# Marcadas pelo app a cada pedido (middleware), a partir do cookie do painel.
_equipe: contextvars.ContextVar[bool] = contextvars.ContextVar("painel_logado", default=False)
_liberado_para_mim: contextvars.ContextVar[bool] = contextvars.ContextVar("painel_liberado", default=False)


# ------------------------------------------------------------------ ambiente
def ambiente() -> str:
    """'previa' só com a Stripe em chave de TESTE; qualquer outra coisa é 'producao'
    (falha fechada: na dúvida, o "tudo liberado" não vale para o público)."""
    return "previa" if pagamento.stripe() and pagamento.chave_de_teste(pagamento.chave_secreta()) else "producao"


# ------------------------------------------------------------------ leitura do banco
def salvo() -> dict:
    """O que o painel salvou ({chave: valor}), com cache de CACHE_SEGUNDOS."""
    global _salvo, _lido_em
    import db
    if not db.ativo():
        return {}
    agora = time.monotonic()
    with _trava:
        if _lido_em is not None and agora - _lido_em < CACHE_SEGUNDOS:
            return dict(_salvo or {})
        _lido_em = agora  # mesmo se falhar: tenta de novo em 15 s, não a cada pedido
    try:
        valores = db.ler_config_site()
    except Exception as erro:  # noqa: BLE001
        log.exception("estado do site: falha ao ler o banco; fica o último estado conhecido")
        import alertas
        alertas.alertar("Painel: não consegui ler o estado do site",
                        "O banco não respondeu ao ler config_site. O site segue com o último estado "
                        f"conhecido{'' if _salvo is not None else ' (nenhum: vale o catalogo.yaml)'}.\n{erro!r}",
                        chave="estado_site_leitura", intervalo=60 * 60)
        return dict(_salvo or {})
    with _trava:
        _salvo = dict(valores)
    return dict(valores)


def invalidar() -> None:
    """A próxima pergunta lê o banco de novo (o painel chama depois de salvar)."""
    global _lido_em
    with _trava:
        _lido_em = None


def esquecer() -> None:
    """Zera o último estado conhecido (os testes usam)."""
    global _salvo, _lido_em
    with _trava:
        _salvo, _lido_em = None, None


# ------------------------------------------------------------------ o que está no ar
def modo() -> str:
    """O modo do site para o PÚBLICO."""
    v = salvo().get("modo")
    if v in MODOS:
        return v
    return "lista_espera" if os.environ.get("PADMINI_CAPTURA") == "1" else "aberto"


def tudo_liberado_global() -> bool:
    """"Tudo liberado" para todo mundo: só na prévia (Stripe de teste)."""
    return modo() == "tudo_liberado" and ambiente() == "previa"


def vendas_abertas(padrao: bool) -> bool:
    """O interruptor de venda: o do painel; sem ele, `padrao` (o catalogo.yaml). Na prévia em
    "tudo liberado", aberta (é Stripe de teste). O modo pessoal nunca abre a venda."""
    v = salvo().get("vendas_abertas")
    return (v if isinstance(v, bool) else bool(padrao)) or tudo_liberado_global()


def estado_salvo(chave: str, padrao: str) -> str:
    """O estado do produto decidido (painel → YAML), sem modo nenhum por cima."""
    v = salvo().get(f"produto:{chave}")
    return v if v in ESTADOS else padrao


def estado_produto(chave: str, padrao: str, publico: bool = False) -> str:
    """Estado do produto no ar. `publico=True`: o que vale para vender (ignora o modo
    pessoal do painel, que mostra mas nunca vende)."""
    if tudo_liberado_global() or (not publico and liberado_para_mim()):
        return "ativo"
    return estado_salvo(chave, padrao)


def pagina_visivel(rota: str) -> bool:
    """As páginas de PAGINAS podem ser escondidas no painel; as outras estão sempre no ar."""
    if rota not in PAGINAS or tudo_liberado_global() or liberado_para_mim():
        return True
    return salvo().get(f"pagina:{rota}") is not False


def assinatura() -> str:
    """Muda sempre que o estado PÚBLICO muda: o app esvazia o cache de páginas quando
    ela muda (as páginas dependem do modo, da venda e dos estados)."""
    return json.dumps([salvo(), modo(), ambiente(), os.environ.get("PADMINI_CAPTURA", "")],
                      sort_keys=True, default=str)


# ------------------------------------------------------------------ o pedido atual (cookie do painel)
def marcar_pedido(equipe: bool, so_para_mim: bool) -> tuple:
    """O app chama no começo de cada pedido. `equipe` = cookie do painel válido.
    Liberado para a pessoa = equipe e (o site em "tudo liberado" ou o "só para mim")."""
    t1 = _equipe.set(bool(equipe))
    t2 = _liberado_para_mim.set(bool(equipe) and (so_para_mim or modo() == "tudo_liberado"))
    return t1, t2


def desmarcar(tokens: tuple) -> None:
    _equipe.reset(tokens[0])
    _liberado_para_mim.reset(tokens[1])


def equipe() -> bool:
    """O navegador deste pedido está logado no painel."""
    return _equipe.get()


def liberado_para_mim() -> bool:
    """Tudo liberado só para este navegador (logado no painel)."""
    return _liberado_para_mim.get()


def liberado() -> bool:
    """Este pedido vê "tudo liberado" (a prévia inteira, ou só este navegador)?"""
    return tudo_liberado_global() or liberado_para_mim()


def leitura_liberada() -> bool:
    """A leitura completa sem pagar: só no navegador logado no painel, em modo teste.
    Nunca para o público, em nenhum modo (nem na prévia: lá a compra de teste é o teste)."""
    return liberado_para_mim()


def pessoal() -> bool:
    """A resposta deste pedido depende do cookie? Então não entra no cache de páginas."""
    return liberado_para_mim()

"""
Padmini — servidor web.

Rodar localmente:
    pip install -r requirements.txt
    uvicorn app:app --reload
e abrir http://127.0.0.1:8000
"""

import contextlib
import hmac
import logging
import os
import time
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import json

import jinja2
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from base_significacoes import NOME_PT, SIGNO_PT
from cidades import BuscaCidades
from compute_chart import calcular_mapa
from detectar_fatos import detectar_todos_os_fatos
from compatibilidade import calcular_compatibilidade, montar_snippets_compatibilidade, nota_br
import acesso
import alertas
import cakto
import db
import entrega
import limites
import marketing
import ofertas
import seguranca
import rotas_ocidental
import sistema
from nascimento import aviso_de_horario, validar_datetime as _validar_datetime
import textos
from gerar_pdf import gerar_pdf
from montar_texto import (
    dasha_atual, gerar_com_claude, montar_prompt, montar_prompt_compat, montar_secoes,
)

RAIZ = Path(__file__).parent

# Carrega variáveis do arquivo .env (ex.: ANTHROPIC_API_KEY), se existir. Nunca versionar o .env.
_env = RAIZ / ".env"
if _env.exists():
    for _linha in _env.read_text(encoding="utf-8-sig").splitlines():
        if "=" in _linha and not _linha.lstrip().startswith("#"):
            _chave, _valor = _linha.split("=", 1)
            os.environ.setdefault(_chave.strip(), _valor.strip())

@contextlib.asynccontextmanager
async def _ciclo_de_vida(_app):
    # sem DATABASE_URL não faz nada; com erro, só registra no log (não derruba o site)
    db.iniciar()
    yield


log = logging.getLogger("padmini.app")

# Qual versão do site está no ar (PADMINI_SISTEMA, ver sistema.py). Lido aqui,
# na subida: valor desconhecido derruba a subida com erro claro, em vez de pôr
# no ar um site meio montado.
SISTEMA_NA_SUBIDA = sistema.ativo()
log.info("Padmini subindo com PADMINI_SISTEMA=%s", SISTEMA_NA_SUBIDA)

app = FastAPI(title="Padmini", lifespan=_ciclo_de_vida)
# Cabeçalhos de segurança (CSP, HSTS, anti-iframe, Referrer-Policy) em toda resposta.
app.middleware("http")(seguranca.cabecalhos_de_seguranca)


@app.middleware("http")
async def _avisar_erro_500(request: Request, call_next):
    """Erro não tratado = e-mail para a equipe (no máximo 1 a cada 15 min)."""
    try:
        return await call_next(request)
    except Exception as erro:
        alertas.alertar("Erro 500 no site", f"{request.method} {request.url.path}\n{erro!r}",
                        chave="erro500", intervalo=15 * 60)
        raise
app.mount("/static", StaticFiles(directory=RAIZ / "static"), name="static")
# Rotas da versão ocidental (/api/ocidental/*): existem sempre, qualquer que seja
# a versão no ar — um link já entregue precisa abrir depois de uma troca.
app.include_router(rotas_ocidental.rotas)
busca = BuscaCidades()


class PedidoMapa(BaseModel):
    nome: str = Field("", max_length=80)
    data: date
    hora: str = Field(pattern=r"^\d{2}:\d{2}$")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    cidade: str = Field("", max_length=200)
    texto_ia: bool = False
    # 'amostra' = isca grátis (Ascendente + Lua/nakshatra + fase atual);
    # 'completo' = mapa inteiro (só após pagamento em produção).
    nivel: str = Field("completo", pattern=r"^(amostra|completo)$")
    token: str | None = Field(None, max_length=64)  # libera o completo (ver acesso.py)


class PessoaCompat(BaseModel):
    """Uma das duas pessoas do pedido de compatibilidade."""
    nome: str = Field("", max_length=80)
    data: date
    hora: str = Field(pattern=r"^\d{2}:\d{2}$")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    cidade: str = Field("", max_length=200)


class PedidoCompatibilidade(BaseModel):
    a: PessoaCompat
    b: PessoaCompat
    # 'amostra' = isca grátis; 'completo' = relatório pago. Em produção, o
    # 'completo' só deve ser liberado após confirmação de pagamento (webhook
    # da Cakto) — ver checklist §5. Aqui o parâmetro existe para o pipeline.
    nivel: str = Field("amostra", pattern=r"^(amostra|completo)$")
    texto_ia: bool = False
    token: str | None = Field(None, max_length=64)  # libera o completo (ver acesso.py)


# aviso_de_horario e _validar_datetime moraram aqui até a Fase 1 da versão
# ocidental; foram para nascimento.py para as rotas das duas versões usarem.


# ---------------------------------------------------------------------------
# Pré-lançamento: com PADMINI_CAPTURA=1 o site fica "trancado" — home, mapa e
# compatibilidade mandam para a lista de espera (/lista). Continuam abrindo:
#   - links de entrega (têm `token`), para quem já comprou;
#   - quem tem a chave de prévia (PADMINI_PREVIA_CHAVE): abrir qualquer página
#     com ?previa=CHAVE grava um cookie e libera o site nesse navegador.
# Desligar = apagar a variável (ou pôr 0) na Render; não precisa de deploy.
# ---------------------------------------------------------------------------
def _captura_ligada() -> bool:
    return os.environ.get("PADMINI_CAPTURA") == "1"


_paginas_prontas: dict[tuple[str, str], str] = {}

# As páginas são templates: o texto vem de `conteudo/<pagina>.yaml` e o preço de
# `conteudo/<versão>/ofertas.yaml`. Montado no servidor, e não por JavaScript, para o
# conteúdo já sair no HTML (com fetch, o bloco de preço apareceria vazio até a
# resposta chegar) e para o buscador ver a página inteira.
# autoescape desligado: o texto é escrito por nós e pode ter <em>/<strong>
# de propósito. Nada aqui vem de quem visita o site.
_jinja = jinja2.Environment(
    loader=jinja2.FileSystemLoader(RAIZ / "static"),
    autoescape=False,
    undefined=jinja2.StrictUndefined,  # nome errado no template vira erro, não buraco na página
    keep_trailing_newline=True,
)


def _pagina_montada(arquivo: str, versao: str, pagina: str) -> Response:
    """Serve uma página montada de uma versão do site. O resultado fica em
    memória: os arquivos só mudam em deploy, que reinicia o processo."""
    if (versao, arquivo) not in _paginas_prontas:
        _paginas_prontas[(versao, arquivo)] = _jinja.get_template(arquivo).render(
            t=textos.da_pagina(pagina, versao),
            ofertas=ofertas.do_sistema(versao),
        )
    return Response(_paginas_prontas[(versao, arquivo)], media_type="text/html; charset=utf-8")


def _pagina(rota: str, versao: str | None = None) -> Response:
    """A página de `rota` ("/", "/mapa"...) na versão pedida (padrão: a do ar)."""
    versao = versao or sistema.ativo()
    arquivo, pagina = sistema.pagina(rota, versao)
    return _pagina_montada(arquivo, versao, pagina)


def _versao_do_pedido(request: Request) -> str:
    """Link de entrega (com `token`) abre na versão do token, qualquer que seja a
    versão no ar: quem comprou a védica continua lendo a védica, e vice-versa."""
    if "token" in request.query_params:
        return acesso.sistema_do_token(request.query_params.get("token"))
    return sistema.ativo()


def _pagina_ou_lista(request: Request, rota: str):
    chave = os.environ.get("PADMINI_PREVIA_CHAVE", "")
    previa_url = request.query_params.get("previa", "")
    liberado = (not _captura_ligada()
                or "token" in request.query_params
                or (chave and (request.cookies.get("pad_previa") == chave or previa_url == chave)))
    if not liberado:
        destino = "/lista"
        if request.url.query:
            destino += "?" + request.url.query  # mantém ref/utm do afiliado
        return RedirectResponse(destino, status_code=302)
    resp = _pagina(rota, _versao_do_pedido(request))
    if chave and previa_url == chave:
        resp.set_cookie("pad_previa", chave, max_age=60 * 60 * 24 * 60, httponly=True,
                        secure=request.url.scheme == "https", samesite="lax")
    return resp


@app.api_route("/", methods=["GET", "HEAD"])
def pagina_home(request: Request):
    return _pagina_ou_lista(request, "/")


@app.api_route("/mapa", methods=["GET", "HEAD"])
def pagina_mapa(request: Request):
    return _pagina_ou_lista(request, "/mapa")


@app.api_route("/compatibilidade", methods=["GET", "HEAD"])
def pagina_compatibilidade(request: Request):
    return _pagina_ou_lista(request, "/compatibilidade")


@app.api_route("/lista", methods=["GET", "HEAD"])
def pagina_lista():
    return _pagina("/lista")


class Inscricao(BaseModel):
    nome: str = Field("", max_length=80)
    email: str = Field(..., max_length=160)
    whatsapp: str = Field("", max_length=30)
    aceita_email: bool = False
    aceita_whatsapp: bool = False
    interesse: str = Field("", max_length=20)
    origem: dict = Field(default_factory=dict)
    site: str = Field("", max_length=200)  # honeypot: humanos não veem este campo


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.post("/api/lista")
def inscrever_na_lista(ins: Inscricao, request: Request):
    limites.exigir(limites.LISTA, request)
    if ins.site:
        return {"ok": True}  # robô preencheu o campo escondido: finge sucesso e descarta
    email = ins.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(422, "Confira o e-mail.")
    if not ins.aceita_email:
        raise HTTPException(422, "Marque a autorização para receber o aviso por e-mail.")
    zap = re.sub(r"\D", "", ins.whatsapp)
    if zap and not (10 <= len(zap) <= 13):
        raise HTTPException(422, "Confira o WhatsApp (com DDD).")
    if zap and len(zap) in (10, 11):
        zap = "55" + zap
    origem = {k: str(v)[:80] for k, v in (ins.origem or {}).items()
              if k in ("ref", "cupom", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")}
    interesse = ins.interesse if ins.interesse in ("mapa", "compat", "ambos") else ""
    if not db.registrar_lead(ins.nome.strip()[:80], email, zap, True,
                             bool(zap) and ins.aceita_whatsapp, interesse, origem):
        raise HTTPException(503, "Não conseguimos salvar agora. Tente de novo em instantes.")
    return {"ok": True}


# ---------------------------------------------------------------------------
# MODO LIVE (só o Pedro) — /live gera o relatório completo sem pagamento, para
# ler mapas ao vivo. Entra com senha (PADMINI_LIVE_SENHA) e fica um cookie
# assinado de 12h; nada de token na URL, que apareceria na tela da transmissão.
# Cada geração fica registrada no banco (live_geracoes).
# ---------------------------------------------------------------------------
HORAS_SESSAO_LIVE = 12


def _senha_live() -> str:
    return os.environ.get("PADMINI_LIVE_SENHA", "")


def _live_liberado(request: Request) -> bool:
    return acesso.sessao_valida("live", request.cookies.get("pad_live"))


def _exigir_live(request: Request) -> None:
    if not _live_liberado(request):
        raise HTTPException(401, "Sessão do modo live expirada. Entre de novo.")


class SenhaLive(BaseModel):
    senha: str = Field("", max_length=200)


@app.get("/live")
def pagina_live():
    versao = sistema.ativo()
    if versao == "vedica":
        return FileResponse(RAIZ / "static" / sistema.LIVE[versao])
    return _pagina_montada(sistema.LIVE[versao], versao, "live")


@app.get("/api/live/sessao")
def live_sessao(request: Request):
    return {"ativa": _live_liberado(request), "configurado": bool(_senha_live())}


@app.post("/api/live/entrar")
def live_entrar(dados: SenhaLive, request: Request):
    senha = _senha_live()
    if not senha:
        raise HTTPException(503, "Modo live não está configurado neste servidor.")
    # Força bruta: só as tentativas ERRADAS contam, por IP e no total.
    ip = limites.ip_do_cliente(request)
    if (limites.LIVE_FALHAS_IP.estourado(ip)
            or limites.LIVE_FALHAS_GLOBAL.estourado("todos")):
        raise HTTPException(429, "Muitas tentativas erradas. Espere e tente de novo mais tarde.",
                            headers={"Retry-After": "900"})
    # bytes: compare_digest com str não-ASCII levantaria erro (500) em vez de 401
    if not hmac.compare_digest(dados.senha.encode("utf-8"), senha.encode("utf-8")):
        limites.LIVE_FALHAS_IP.registrar(ip)
        limites.LIVE_FALHAS_GLOBAL.registrar("todos")
        log.warning("live: senha incorreta (ip %s)", ip)
        raise HTTPException(401, "Senha incorreta.")
    expira = int(time.time()) + HORAS_SESSAO_LIVE * 3600
    resp = JSONResponse({"ok": True, "expira_em": expira})
    resp.set_cookie("pad_live", acesso.emitir_sessao("live", expira),
                    max_age=HORAS_SESSAO_LIVE * 3600, httponly=True,
                    secure=request.url.scheme == "https", samesite="lax")
    return resp


@app.post("/api/live/sair")
def live_sair():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("pad_live")
    return resp


@app.post("/api/live/token/mapa")
def live_token_mapa(pedido: PedidoMapa, request: Request):
    """Devolve o token do completo daquele nascimento (sem pagamento) e registra a leitura."""
    _exigir_live(request)
    _validar_datetime(pedido.data, pedido.hora)
    chave = acesso.chave_mapa(pedido.data.isoformat(), pedido.hora, pedido.lat, pedido.lon)
    db.registrar_live("mapa", pedido.nome.strip(), pedido.cidade,
                      f"{pedido.data.isoformat()} {pedido.hora}")
    return {"token": acesso.emitir_token("mapa", chave)}


@app.post("/api/live/token/compat")
def live_token_compat(pedido: PedidoCompatibilidade, request: Request):
    _exigir_live(request)
    _validar_datetime(pedido.a.data, pedido.a.hora)
    _validar_datetime(pedido.b.data, pedido.b.hora)
    chave = acesso.chave_compat(
        (pedido.a.data.isoformat(), pedido.a.hora, pedido.a.lat, pedido.a.lon),
        (pedido.b.data.isoformat(), pedido.b.hora, pedido.b.lat, pedido.b.lon))
    db.registrar_live("compat", f"{pedido.a.nome.strip()} & {pedido.b.nome.strip()}".strip(" &"),
                      pedido.a.cidade, f"{pedido.a.data.isoformat()} / {pedido.b.data.isoformat()}")
    return {"token": acesso.emitir_token("compat", chave)}


def _rotulo_produto(produto: str, versao: str) -> str:
    """Como o produto vai para o banco: 'mapa' na védica (como sempre foi),
    'ocidental:mapa' na ocidental."""
    return produto if versao == "vedica" else f"{versao}:{produto}"


@app.api_route("/robots.txt", methods=["GET", "HEAD"])
def robots():
    # /live é a página do Pedro (senha), /api não é conteúdo, e os links de entrega
    # carregam token na URL — nada disso deve entrar em buscador.
    corpo = ("User-agent: *\n"
             "Disallow: /live\n"
             "Disallow: /api/\n"
             "Disallow: /*?token=\n"
             # /static serve os mesmos HTMLs crus, ainda com os marcadores de preço.
             "Disallow: /static/*.html\n"
             f"\nSitemap: {entrega.SITE_URL}/sitemap.xml\n")
    return Response(corpo, media_type="text/plain; charset=utf-8")


@app.api_route("/sitemap.xml", methods=["GET", "HEAD"])
def sitemap():
    # Com a captura ligada, home/mapa/compatibilidade redirecionam para /lista;
    # anunciar as três no sitemap faria o buscador indexar redirecionamento.
    caminhos = ["/lista"] if _captura_ligada() else ["/", "/mapa", "/compatibilidade"]
    urls = "".join(f"  <url><loc>{entrega.SITE_URL}{c}</loc></url>\n" for c in caminhos)
    corpo = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
             f"{urls}</urlset>\n")
    return Response(corpo, media_type="application/xml")


@app.api_route("/privacidade", methods=["GET", "HEAD"])
def pagina_privacidade():
    return FileResponse(RAIZ / "static" / "privacidade.html")


@app.api_route("/termos", methods=["GET", "HEAD"])
def pagina_termos():
    return FileResponse(RAIZ / "static" / "termos.html")


@app.get("/api/cidades")
def cidades(request: Request, q: str = Query("", max_length=80)):
    limites.exigir(limites.CIDADES, request)
    return busca.buscar(q)


@app.api_route("/api/saude", methods=["GET", "HEAD"])
def saude():
    """Usado pelo keep-alive diário (GitHub Actions) e por monitores de uptime
    (que costumam usar HEAD): acorda o site e faz uma consulta no banco —
    o Supabase grátis pausa após uma semana sem uso."""
    banco = db.saude()
    # versao = commit no ar (a Render define RENDER_GIT_COMMIT): o workflow
    # pos-deploy espera esta versão aparecer antes de rodar o smoke.
    return {"ok": banco is not False, "banco": banco,
            "versao": os.environ.get("RENDER_GIT_COMMIT", "")[:7]}


@app.get("/api/config")
def config():
    return {
        "sistema": sistema.ativo(),
        "texto_ia_disponivel": bool(os.environ.get("ANTHROPIC_API_KEY")),
        # Métricas de funil (PostHog). Em branco = desligado (nada é carregado).
        "posthog_key": os.environ.get("PADMINI_POSTHOG_KEY", ""),
        "posthog_host": os.environ.get("PADMINI_POSTHOG_HOST", "https://us.i.posthog.com"),
        # pré-lançamento (página /lista)
        "data_abertura": os.environ.get("PADMINI_DATA_ABERTURA", ""),
        # "receber a amostra por e-mail" só aparece se o envio estiver configurado
        "amostra_email": bool(os.environ.get("RESEND_API_KEY")),
    }


def calcular_pedido(pedido: PedidoMapa):
    """Valida o pedido e devolve (data/hora local, mapa, fatos, seções do relatório)."""
    dt = _validar_datetime(pedido.data, pedido.hora)
    resultado = calcular_mapa(dt_local_naive=dt, lat=pedido.lat, lon=pedido.lon)
    fatos = detectar_todos_os_fatos(resultado)
    secoes, _ = montar_secoes(resultado, fatos)
    return dt, resultado, fatos, secoes


@app.post("/api/mapa")
def mapa(pedido: PedidoMapa, request: Request):
    limites.exigir(limites.CALCULO, request)
    dt, resultado, fatos, secoes = calcular_pedido(pedido)

    # Amostra grátis: só o gancho (Ascendente + Lua/nakshatra + fase atual).
    # Não devolve a tabela de planetas, o mapa, as casas nem os dashas completos.
    if pedido.nivel == "amostra":
        atual = dasha_atual(resultado)
        lua = resultado["grahas"]["Chandra"]
        return {
            "nivel": "amostra",
            "nome": pedido.nome.strip(),
            "cidade": pedido.cidade,
            "fuso": resultado["fuso_resolvido"],
            "aviso_horario": aviso_de_horario(dt, resultado["fuso_resolvido"]["nome_iana"]),
            "lagna": {**resultado["lagna"], "signo_pt": SIGNO_PT[resultado["lagna"]["signo"]]},
            "lua": {"signo_pt": SIGNO_PT[lua["signo"]], "nakshatra": resultado["nakshatra_lua"]},
            "lua_texto": secoes.get("Lua e nakshatra", ""),
            "fase_atual": ({"nome": NOME_PT[atual["regente"]], "inicio": atual["inicio"], "fim": atual["fim"]}
                           if atual else None),
        }

    # completo requer pagamento (token assinado) — a amostra acima é sempre grátis
    chave = acesso.chave_mapa(pedido.data.isoformat(), pedido.hora, pedido.lat, pedido.lon)
    if not acesso.completo_liberado("mapa", chave, pedido.token):
        raise HTTPException(402, "O mapa completo requer pagamento.")

    texto_ia = None
    if pedido.texto_ia:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(503, "Texto por IA não está configurado neste servidor.")
        # um texto por mapa: guardado no banco para não pagar a IA a cada clique
        texto_ia = db.texto_ia(chave)
        if texto_ia is None:
            limites.exigir(limites.TEXTO_IA, request)
            texto_ia = gerar_com_claude(montar_prompt(secoes))
            db.guardar_texto_ia(chave, "mapa", texto_ia,
                                os.environ.get("PADMINI_MODELO", "claude-sonnet-5"))

    atual = dasha_atual(resultado)
    return {
        "nivel": "completo",
        "nome": pedido.nome.strip(),
        "cidade": pedido.cidade,
        "fuso": resultado["fuso_resolvido"],
        "aviso_horario": aviso_de_horario(dt, resultado["fuso_resolvido"]["nome_iana"]),
        "lagna": {**resultado["lagna"], "signo_pt": SIGNO_PT[resultado["lagna"]["signo"]]},
        "grahas": [
            {"id": k, "nome": NOME_PT[k], "signo": v["signo"], "signo_pt": SIGNO_PT[v["signo"]],
             "grau": v["grau_no_signo"], "casa": v["casa_whole_sign"],
             "retrogrado": v["retrogrado"] and k not in ("Rahu", "Ketu")}
            for k, v in resultado["grahas"].items()
        ],
        "nakshatra_lua": resultado["nakshatra_lua"],
        "dashas": [{**d, "nome": NOME_PT[d["regente"]], "atual": d == atual}
                   for d in resultado["vimshottari_dasha"]],
        "secoes": secoes,
        "texto_ia": texto_ia,
    }


@app.post("/api/compatibilidade")
def compatibilidade(pedido: PedidoCompatibilidade, request: Request):
    """
    Compatibilidade de casal (Guna Milan). Corte do paywall:
      - nivel='amostra': só a nota, a categoria, o ponto forte e o de atenção
        (o suficiente para o card compartilhável). NÃO devolve as 8 kootas.
      - nivel='completo': as 8 kootas, doshas e Mangal. Em produção, liberar só
        após pagamento confirmado.
    """
    limites.exigir(limites.CALCULO, request)
    dt_a = _validar_datetime(pedido.a.data, pedido.a.hora)
    dt_b = _validar_datetime(pedido.b.data, pedido.b.hora)
    # Texto por IA custa dinheiro a cada chamada: só no completo (pago). Antes a
    # amostra grátis aceitava texto_ia=true e qualquer script gerava custo em loop.
    if pedido.texto_ia and pedido.nivel != "completo":
        raise HTTPException(402, "O texto por IA faz parte do relatório completo.")
    mapa_a = calcular_mapa(dt_local_naive=dt_a, lat=pedido.a.lat, lon=pedido.a.lon)
    mapa_b = calcular_mapa(dt_local_naive=dt_b, lat=pedido.b.lat, lon=pedido.b.lon)

    resultado = calcular_compatibilidade(mapa_a, mapa_b)

    chave = None
    if pedido.nivel == "completo":
        chave = acesso.chave_compat(
            (pedido.a.data.isoformat(), pedido.a.hora, pedido.a.lat, pedido.a.lon),
            (pedido.b.data.isoformat(), pedido.b.hora, pedido.b.lat, pedido.b.lon))
        if not acesso.completo_liberado("compat", chave, pedido.token):
            raise HTTPException(402, "O relatório completo requer pagamento.")

    nome_a = pedido.a.nome.strip() or "Pessoa A"
    nome_b = pedido.b.nome.strip() or "Pessoa B"
    snippets = montar_snippets_compatibilidade(resultado, pedido.nivel, nome_a, nome_b)

    texto_ia = None
    if pedido.texto_ia:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(503, "Texto por IA não está configurado neste servidor.")
        # um texto por casal, guardado no banco (como no mapa): não paga a IA a cada clique
        texto_ia = db.texto_ia(chave)
        if texto_ia is None:
            limites.exigir(limites.TEXTO_IA, request)
            texto_ia = gerar_com_claude(montar_prompt_compat(snippets))
            db.guardar_texto_ia(chave, "compat", texto_ia,
                                os.environ.get("PADMINI_MODELO", "claude-sonnet-5"))

    resposta = {
        "nivel": pedido.nivel,
        "nomes": {"a": nome_a, "b": nome_b},
        "total": resultado["total"],
        "maximo": 36,
        "categoria": resultado["categoria"],
        "snippets": snippets,
        "avisos_horario": {
            "a": aviso_de_horario(dt_a, mapa_a["fuso_resolvido"]["nome_iana"]),
            "b": aviso_de_horario(dt_b, mapa_b["fuso_resolvido"]["nome_iana"]),
        },
        "texto_ia": texto_ia,
    }
    # o detalhamento numérico das 8 kootas + doshas só sai no completo (paywall)
    if pedido.nivel == "completo":
        resposta["kootas"] = resultado["kootas"]
        resposta["doshas"] = resultado["doshas"]
    return resposta


@app.post("/api/pdf")
def pdf(pedido: PedidoMapa, request: Request):
    """Relatório completo em PDF. Não usa IA (sem custo por download). Requer pagamento."""
    limites.exigir(limites.PDF, request)
    chave = acesso.chave_mapa(pedido.data.isoformat(), pedido.hora, pedido.lat, pedido.lon)
    if not acesso.completo_liberado("mapa", chave, pedido.token):
        raise HTTPException(402, "O PDF completo requer pagamento.")
    dt, resultado, fatos, secoes = calcular_pedido(pedido)
    conteudo = gerar_pdf(resultado=resultado, fatos=fatos, secoes=secoes, nome=pedido.nome,
                         cidade=pedido.cidade, nascimento=dt)
    sem_acento = unicodedata.normalize("NFKD", pedido.nome).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")[:40]
    arquivo = f"mapa-vedico-{slug}.pdf" if slug else "mapa-vedico.pdf"
    return Response(conteudo, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{arquivo}"'})


@app.post("/webhook/cakto")
async def webhook_cakto(request: Request):
    """
    Recebe a confirmação de pagamento da Cakto → emite o token → manda o e-mail
    com o link do completo. Ver cakto.py para os pontos a confirmar na Cakto.
    Responde 200 rápido (retorna o link quando o e-mail não está configurado,
    para envio manual no soft launch).
    """
    corpo = await request.body()
    try:
        evento = json.loads(corpo.decode("utf-8"))
    except Exception:
        raise HTTPException(400, "payload inválido")

    # Assinatura: header `X-Cakto-Signature: v1=<hmac>` sobre '{timestamp}.{corpo}',
    # ou o campo `secret` no corpo do evento (as duas formas são documentadas).
    assinatura = request.headers.get("x-cakto-signature") or ""
    timestamp = request.headers.get("x-cakto-timestamp") or ""
    secret_do_corpo = evento.get("secret", "") if isinstance(evento, dict) else ""
    metodo = cakto.metodo_de_verificacao(assinatura, timestamp, corpo,
                                         os.environ.get("PADMINI_CAKTO_WEBHOOK_SECRET", ""),
                                         secret_do_corpo)
    if not metodo:
        log.warning("webhook: origem NÃO provada (assinatura %s, timestamp %r) — recusado",
                    "presente" if assinatura else "ausente", timestamp[:20])
        alertas.alertar("Webhook da Cakto recusado (assinatura inválida)",
                        "Se foi uma venda real, o segredo do webhook na Render pode estar errado "
                        "(PADMINI_CAKTO_WEBHOOK_SECRET). Se não, é alguém testando o endereço.",
                        chave="webhook401", intervalo=60 * 60)
        raise HTTPException(401, "assinatura inválida")
    # Serve para decidir quando ligar PADMINI_CAKTO_EXIGIR_ASSINATURA=1 (docs/seguranca.md).
    log.info("webhook: origem provada por %s", metodo)

    if isinstance(evento, dict) and str(evento.get("event") or "").lower() == "checkout_abandonment":
        return _tratar_abandono(evento)

    # Webhook V1 manda um pedido por entrega (`data` = objeto); o V2 manda todos
    # os pedidos da mesma cobrança numa lista. Tratamos os dois formatos.
    pedidos = cakto.pedidos_do_evento(evento)
    resultados = [_processar_pedido(p) for p in pedidos]
    if len(resultados) == 1:
        return resultados[0]
    return {"ok": True, "pedidos": resultados}


def _processar_pedido(evento: dict) -> dict:
    if not cakto.is_aprovado(evento):
        return {"ok": True, "ignorado": "pagamento não aprovado"}

    # Combo "casal completo": order bump no checkout do casal que entrega o mapa
    # individual de cada um. Chega como pedido próprio (offer_type=orderbump) com o
    # mesmo `sck` do casal. Outros bumps/upsells ainda não existem: ignorar evita
    # entregar o produto principal duas vezes.
    tipo = str((evento.get("data") or {}).get("offer_type") or "main").lower()
    versao_bump = cakto.versao_do_bump_mapas(evento) if tipo == "orderbump" else ""
    if versao_bump:
        return _entregar_mapas_do_casal(evento, versao_bump)
    if tipo != "main":
        return {"ok": True, "ignorado": f"oferta {tipo} ainda não tratada"}

    pd = cakto.coletar_pd(evento)
    produto = cakto.produto_do_evento(evento, pd)
    # versão do site da oferta paga (não a que está no ar): uma compra feita
    # antes da troca de PADMINI_SISTEMA é entregue na versão comprada
    versao = cakto.sistema_pago(evento) or "vedica"
    email = cakto.email_do_evento(evento)
    if produto not in ("mapa", "compat"):
        # Pagou, mas não dá para entregar com segurança: a oferta paga não foi
        # reconhecida, ou o `sck` pede outro produto (ex.: pagou o mapa e o sck
        # traz um casal — tentativa de levar o produto mais caro). Não emite
        # token; grava para a equipe olhar e entregar à mão o que foi pago.
        pago = cakto.produto_pago(evento) or "desconhecido"
        log.warning("webhook: pedido %s sem entrega automática (pago=%s, sck=%s)",
                    (evento.get("data") or {}).get("id"), pago, pd.get("pd_produto"))
        db.registrar_pedido(evento, pago, {}, email, None, False)
        _alertar_pendente(evento, pago, email, "produto pago não confere com o sck (ou oferta desconhecida)", pd)
        return {"ok": True, "produto": pago, "email": email or None,
                "pendente": "produto pago não confere com os dados enviados — conferir e entregar manualmente"}

    # a versão ocidental aceita nascimento sem hora (sem Ascendente e casas)
    dados = cakto.dados_nascimento(pd, produto, exige_hora=versao == "vedica")
    if not dados:
        # Pagou, mas o `sck` não trouxe os dados de nascimento: não dá para gerar.
        # Grava o pedido sem link (aparece no banco para entrega manual) e responde
        # 200 — a Cakto não reenvia respostas de erro, então 422 não ajudaria.
        db.registrar_pedido(evento, _rotulo_produto(produto, versao), {}, email, None, False)
        _alertar_pendente(evento, _rotulo_produto(produto, versao), email,
                          "sck sem os dados de nascimento", pd)
        return {"ok": True, "produto": produto, "email": email or None,
                "pendente": "dados de nascimento ausentes — entregar manualmente"}

    # a Cakto reenvia o webhook se não receber resposta a tempo: não mandar o e-mail duas vezes
    cakto_id = str((evento.get("data") or {}).get("id") or "")
    if db.pedido_entregue(cakto_id):
        return {"ok": True, "produto": produto, "duplicado": True}

    link = entrega.link_completo(produto, dados, versao)
    try:
        extra = marketing.bloco_venda_cruzada(produto, dados, versao)
    except Exception:  # noqa: BLE001  (a oferta extra nunca pode travar a entrega)
        log.exception("venda cruzada: falha ao montar o bloco")
        extra = ""
    enviado = entrega.enviar_email(
        email, "Seu relatório Padmini está pronto",
        entrega.email_completo_html(produto, link, dados.get("nome", ""), extra, versao))
    db.registrar_pedido(evento, _rotulo_produto(produto, versao), dados, email, link, enviado)
    if not enviado:
        alertas.alertar("E-mail de entrega NÃO saiu — mandar o link à mão",
                        f"pedido {cakto_id} · {_rotulo_produto(produto, versao)} · "
                        f"{email or '(sem e-mail)'}\nlink: {link}")
    # se não enviou (Resend não configurado), devolve o link para envio manual
    return {"ok": True, "produto": produto, "email": email or None,
            "email_enviado": enviado, "link": None if enviado else link}


def _entregar_mapas_do_casal(evento: dict, versao: str = "vedica") -> dict:
    """Order bump do casal: um link de mapa individual para cada pessoa, na
    versão do site da oferta paga (na ocidental, mapa natal; aceita sem hora)."""
    produto = _rotulo_produto("mapas_casal", versao)
    email = cakto.email_do_evento(evento)
    dados = cakto.dados_nascimento(cakto.coletar_pd(evento), "compat", exige_hora=versao == "vedica")
    if not dados:
        db.registrar_pedido(evento, produto, {}, email, None, False)
        _alertar_pendente(evento, produto, email, "sck sem os dados de nascimento (bump)", {})
        return {"ok": True, "produto": produto, "email": email or None,
                "pendente": "dados de nascimento ausentes — entregar manualmente"}
    cakto_id = str((evento.get("data") or {}).get("id") or "")
    if db.pedido_entregue(cakto_id):
        return {"ok": True, "produto": produto, "duplicado": True}
    links = [(p.get("nome") or rotulo, entrega.link_completo("mapa", p, versao))
             for rotulo, p in (("Pessoa A", dados["a"]), ("Pessoa B", dados["b"]))]
    enviado = entrega.enviar_email(
        email, "Os mapas individuais de vocês estão prontos",
        entrega.email_mapas_do_casal_html(links, dados["a"].get("nome", ""), versao))
    db.registrar_pedido(evento, produto, dados, email, "\n".join(l for _, l in links), enviado)
    if not enviado:
        alertas.alertar("E-mail dos mapas do casal NÃO saiu — mandar à mão",
                        f"pedido {cakto_id} · {email or '(sem e-mail)'}\n" + "\n".join(l for _, l in links))
    return {"ok": True, "produto": produto, "email": email or None, "email_enviado": enviado,
            "links": None if enviado else [l for _, l in links]}


def _alertar_pendente(evento: dict, produto: str, email: str, motivo: str, pd: dict) -> None:
    d = evento.get("data") if isinstance(evento.get("data"), dict) else {}
    alertas.alertar(
        "Pedido PAGO sem entrega automática — entregar à mão",
        f"motivo: {motivo}\npedido: {d.get('id')} (ref {d.get('refId')})\nproduto pago: {produto}\n"
        f"e-mail: {email or '(sem e-mail)'}\nsck: {d.get('sck')!r}\n\n"
        "Veja docs/seguranca.md → Pedidos pendentes.")


# ---------------------------------------------------------------------------
# Carrinho abandonado (evento checkout_abandonment da Cakto)
# ---------------------------------------------------------------------------
def _tratar_abandono(evento: dict) -> dict:
    """
    A pessoa chegou ao checkout, deixou o e-mail e não pagou. Um e-mail de
    recuperação por pessoa e oferta (7 dias), nunca para quem se descadastrou ou
    já comprou. Sempre responde 200: a Cakto não reenvia erro e não há o que refazer.
    `data` aqui tem outra forma (customerEmail, customerName, offer, checkoutUrl);
    no webhook V2 vem numa lista de um elemento.
    """
    d = evento.get("data")
    if isinstance(d, list):
        d = d[0] if d and isinstance(d[0], dict) else {}
    if not isinstance(d, dict):
        return {"ok": True, "ignorado": "abandono sem dados"}
    email = str(d.get("customerEmail") or "").strip()
    if not _EMAIL_RE.match(email.lower()):
        return {"ok": True, "ignorado": "abandono sem e-mail"}
    produto = cakto.produto_pago({"data": d})
    if produto not in ("mapa", "compat"):
        return {"ok": True, "ignorado": "abandono de oferta desconhecida"}
    oferta_id = str((d.get("offer") or {}).get("id") or "") if isinstance(d.get("offer"), dict) else ""
    if db.descadastrado(email) or db.abandono_ja_tratado(email, oferta_id):
        return {"ok": True, "ignorado": "já tratado, comprou ou descadastrado"}
    # O link do próprio checkout só serve se ainda carregar os dados de
    # nascimento (sck); sem eles a compra viraria entrega manual. Aí manda
    # para a página do produto, que refaz a amostra e monta o link certo.
    checkout = str(d.get("checkoutUrl") or "")
    if checkout.startswith("https://pay.cakto.com.br/") and "sck=" in checkout:
        link = checkout
    else:
        link = marketing.link_site(produto, "abandono")
    nome = str(d.get("customerName") or "").split(" ")[0]
    enviado = entrega.enviar_email(email, "Seu pedido na Padmini ficou pela metade",
                                   marketing.email_abandono_html(produto, nome, link, email))
    db.registrar_abandono(email, nome, oferta_id, checkout, enviado)
    return {"ok": True, "abandono": produto, "email_enviado": enviado}


# ---------------------------------------------------------------------------
# Amostra por e-mail + lembrete
# ---------------------------------------------------------------------------
class PedidoAmostraEmail(BaseModel):
    email: str = Field(..., max_length=160)
    produto: str = Field(..., pattern=r"^(mapa|compat)$")
    pessoa: PessoaCompat | None = None          # produto = mapa
    a: PessoaCompat | None = None               # produto = compat
    b: PessoaCompat | None = None
    aceita_lembrete: bool = False
    origem: dict = Field(default_factory=dict)


def _dados_pessoa(p: PessoaCompat) -> dict:
    return {"nome": p.nome.strip()[:80], "data": p.data.isoformat(), "hora": p.hora,
            "lat": p.lat, "lon": p.lon, "cidade": p.cidade[:200]}


def _amostra_mapa(p: PessoaCompat) -> dict:
    """O mesmo conteúdo da amostra grátis do site, no formato do e-mail."""
    pedido = PedidoMapa(nome=p.nome, data=p.data, hora=p.hora, lat=p.lat, lon=p.lon,
                        cidade=p.cidade, nivel="amostra")
    _, resultado, _, secoes = calcular_pedido(pedido)
    lua = resultado["grahas"]["Chandra"]
    atual = dasha_atual(resultado)
    return {
        "ascendente": SIGNO_PT[resultado["lagna"]["signo"]],
        "lua": f'{SIGNO_PT[lua["signo"]]} · {resultado["nakshatra_lua"]["nome"]}',
        "fase": (f'{NOME_PT[atual["regente"]]} ({atual["inicio"][:4]}–{atual["fim"][:4]})'
                 if atual else ""),
        "lua_texto": secoes.get("Lua e nakshatra", ""),
    }


def _amostra_compat(a: PessoaCompat, b: PessoaCompat) -> dict:
    dt_a = _validar_datetime(a.data, a.hora)
    dt_b = _validar_datetime(b.data, b.hora)
    resultado = calcular_compatibilidade(calcular_mapa(dt_local_naive=dt_a, lat=a.lat, lon=a.lon),
                                         calcular_mapa(dt_local_naive=dt_b, lat=b.lat, lon=b.lon))
    nome_a, nome_b = a.nome.strip() or "Pessoa A", b.nome.strip() or "Pessoa B"
    s = montar_snippets_compatibilidade(resultado, "amostra", nome_a, nome_b)
    return {"nomes": {"a": nome_a, "b": nome_b}, "nota": nota_br(resultado["total"]),
            "categoria": resultado["categoria"], "moldura": s.get("moldura", ""),
            "ponto_forte": s.get("ponto_forte"), "ponto_atencao": s.get("ponto_atencao")}


def _montar_amostra(produto: str, dados: dict) -> dict:
    if produto == "compat":
        return _amostra_compat(PessoaCompat(**dados["a"]), PessoaCompat(**dados["b"]))
    return _amostra_mapa(PessoaCompat(**dados))


MAX_AMOSTRAS_POR_EMAIL_DIA = 3


@app.post("/api/amostra/email")
def amostra_por_email(pedido: PedidoAmostraEmail, request: Request):
    limites.exigir(limites.AMOSTRA_EMAIL, request)
    if not os.environ.get("RESEND_API_KEY"):
        raise HTTPException(503, "O envio por e-mail não está disponível agora.")
    email = pedido.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(422, "Confira o e-mail.")
    if pedido.produto == "mapa":
        if not pedido.pessoa:
            raise HTTPException(422, "Faltam os dados de nascimento.")
        _validar_datetime(pedido.pessoa.data, pedido.pessoa.hora)
        dados = _dados_pessoa(pedido.pessoa)
        nome = dados["nome"]
    else:
        if not (pedido.a and pedido.b):
            raise HTTPException(422, "Faltam os dados de nascimento do casal.")
        dados = {"a": _dados_pessoa(pedido.a), "b": _dados_pessoa(pedido.b)}
        nome = dados["a"]["nome"]
    # Anti-spam: o formulário não pode virar um jeito de mandar e-mail em massa
    # com a nossa marca para endereços de terceiros.
    if db.amostras_enviadas_hoje(email) >= MAX_AMOSTRAS_POR_EMAIL_DIA:
        raise HTTPException(429, "Este e-mail já recebeu várias amostras hoje. Tente amanhã.")
    amostra = _montar_amostra(pedido.produto, dados)
    enviado = entrega.enviar_email(
        email, "Sua amostra da Padmini" if pedido.produto == "mapa" else "A amostra de vocês na Padmini",
        marketing.email_amostra_html(pedido.produto, amostra, dados, email, nome))
    if not enviado:
        raise HTTPException(503, "Não conseguimos enviar agora. Tente de novo em instantes.")
    origem = {k: str(v)[:80] for k, v in (pedido.origem or {}).items()
              if k in ("ref", "cupom", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")}
    db.registrar_amostra_email(email, pedido.produto, dados, pedido.aceita_lembrete, origem)
    return {"ok": True}


def _chave_tarefas_ok(request: Request) -> None:
    """Rotas de tarefa agendada: só com PADMINI_TAREFAS_CHAVE (falha fechada)."""
    chave = os.environ.get("PADMINI_TAREFAS_CHAVE", "")
    if not chave:
        raise HTTPException(503, "Tarefas agendadas não configuradas.")
    recebida = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(recebida.encode("utf-8"), chave.encode("utf-8")):
        raise HTTPException(401, "Chave inválida.")


@app.post("/api/tarefas/lembretes")
def enviar_lembretes(request: Request):
    """Chamado 1x por dia pelo GitHub Actions (.github/workflows/tarefas.yml)."""
    _chave_tarefas_ok(request)
    enviados, falhas = 0, 0
    for item in db.lembretes_pendentes():
        try:
            amostra = _montar_amostra(item["produto"], item["dados"])
            ok = entrega.enviar_email(
                item["email"], "Faltou uma parte do seu mapa" if item["produto"] == "mapa"
                else "O resto da compatibilidade de vocês",
                marketing.email_lembrete_html(item["produto"], amostra, item["dados"], item["email"]))
        except Exception:  # noqa: BLE001
            log.exception("lembrete: falha na amostra %s", item["id"])
            ok = False
        if ok:
            db.marcar_lembrete_enviado(item["id"])
            enviados += 1
        else:
            falhas += 1
    if falhas:
        alertas.alertar("Lembretes com falha", f"{falhas} lembrete(s) não saíram; {enviados} saíram.",
                        chave="lembretes", intervalo=6 * 3600)
    return {"ok": True, "enviados": enviados, "falhas": falhas}


# ---------------------------------------------------------------------------
# Descadastro (link em todo e-mail de marketing)
# ---------------------------------------------------------------------------
def _pagina_simples(titulo: str, corpo: str) -> Response:
    import html as _html
    pagina = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>Padmini — {_html.escape(titulo)}</title><link rel="stylesheet" href="/static/base.css"></head>
<body><main style="max-width:520px;margin:12vh auto;padding:0 16px"><h1>{_html.escape(titulo)}</h1>{corpo}
<p><a href="/">Voltar para a Padmini</a></p></main></body></html>"""
    return Response(pagina, media_type="text/html; charset=utf-8")


@app.get("/descadastrar")
def descadastrar_confirmar(e: str = Query("", max_length=160), t: str = Query("", max_length=64)):
    # GET só mostra o botão: leitores de e-mail abrem links sozinhos (antivírus,
    # pré-visualização) e não podem descadastrar ninguém por engano.
    import html as _html
    if not marketing.descadastro_valido(e, t):
        return _pagina_simples("Link inválido", "<p>Este link de descadastro não é válido.</p>")
    corpo = (f'<p>Parar de receber e-mails da Padmini em <b>{_html.escape(e)}</b>?</p>'
             f'<form method="post" action="/descadastrar">'
             f'<input type="hidden" name="e" value="{_html.escape(e, quote=True)}">'
             f'<input type="hidden" name="t" value="{_html.escape(t, quote=True)}">'
             f'<button type="submit" class="btn btn-primary">Sim, descadastrar</button></form>'
             f'<p style="font-size:13px">E-mails de compras que você fizer (o link do relatório) continuam chegando.</p>')
    return _pagina_simples("Descadastrar", corpo)


@app.post("/descadastrar")
async def descadastrar(request: Request):
    from urllib.parse import parse_qs
    campos = parse_qs((await request.body()).decode("utf-8", "replace")[:1000])
    e, t = (campos.get("e") or [""])[0], (campos.get("t") or [""])[0]
    if not marketing.descadastro_valido(e, t):
        return _pagina_simples("Link inválido", "<p>Este link de descadastro não é válido.</p>")
    if not db.descadastrar(e):
        return _pagina_simples("Tente de novo", "<p>Não conseguimos registrar agora. Tente em instantes.</p>")
    return _pagina_simples("Pronto", "<p>Você não vai mais receber e-mails de novidades da Padmini.</p>")

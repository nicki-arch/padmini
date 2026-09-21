"""
Padmini — servidor web.

Rodar localmente:
    pip install -r requirements.txt
    uvicorn app:app --reload
e abrir http://127.0.0.1:8000
"""

import contextlib
import os
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import json

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from base_significacoes import NOME_PT, SIGNO_PT
from cidades import BuscaCidades
from compute_chart import calcular_mapa
from detectar_fatos import detectar_todos_os_fatos
from compatibilidade import calcular_compatibilidade, montar_snippets_compatibilidade
import acesso
import cakto
import db
import entrega
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


app = FastAPI(title="Padmini", lifespan=_ciclo_de_vida)
app.mount("/static", StaticFiles(directory=RAIZ / "static"), name="static")
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


def aviso_de_horario(dt: datetime, nome_fuso: str) -> str | None:
    """Detecta horários que não existem ou são ambíguos por causa do horário de verão."""
    if "hora média local" in nome_fuso:
        return ("Nascimento antes da adoção da hora padrão nesse local: usamos a hora média local, "
                "calculada pela longitude da cidade.")
    z = ZoneInfo(nome_fuso)
    ida_volta = dt.replace(tzinfo=z).astimezone(timezone.utc).astimezone(z).replace(tzinfo=None)
    if ida_volta != dt:
        return ("Esse horário não existiu nesse local: o relógio foi adiantado para o horário de verão "
                "nesse dia. Confira a hora na certidão de nascimento.")
    if dt.replace(tzinfo=z, fold=0).utcoffset() != dt.replace(tzinfo=z, fold=1).utcoffset():
        return ("Esse horário aconteceu duas vezes nesse dia (fim do horário de verão). "
                "Usamos a primeira ocorrência; se a pessoa nasceu na segunda, o Ascendente pode mudar.")
    return None


def _validar_datetime(d: date, hora: str) -> datetime:
    """Valida hora e faixa de data; devolve o datetime local ingênuo."""
    h, m = map(int, hora.split(":"))
    if not (0 <= h < 24 and 0 <= m < 60):
        raise HTTPException(422, "Hora inválida.")
    dt = datetime(d.year, d.month, d.day, h, m)
    if not (datetime(1800, 1, 1) <= dt <= datetime.now()):
        raise HTTPException(422, "A data de nascimento precisa estar entre 1800 e hoje.")
    return dt


@app.get("/")
def pagina_home():
    return FileResponse(RAIZ / "static" / "home.html")


@app.get("/mapa")
def pagina_mapa():
    return FileResponse(RAIZ / "static" / "index.html")


@app.get("/compatibilidade")
def pagina_compatibilidade():
    return FileResponse(RAIZ / "static" / "compatibilidade.html")


@app.get("/privacidade")
def pagina_privacidade():
    return FileResponse(RAIZ / "static" / "privacidade.html")


@app.get("/termos")
def pagina_termos():
    return FileResponse(RAIZ / "static" / "termos.html")


@app.get("/api/cidades")
def cidades(q: str = Query("", max_length=80)):
    return busca.buscar(q)


@app.get("/api/saude")
def saude():
    """Usado pelo keep-alive diário (GitHub Actions): acorda o site e faz uma
    consulta no banco — o Supabase grátis pausa após uma semana sem uso."""
    banco = db.saude()
    return {"ok": banco is not False, "banco": banco}


@app.get("/api/config")
def config():
    return {
        "texto_ia_disponivel": bool(os.environ.get("ANTHROPIC_API_KEY")),
        # Métricas de funil (PostHog). Em branco = desligado (nada é carregado).
        "posthog_key": os.environ.get("PADMINI_POSTHOG_KEY", ""),
        "posthog_host": os.environ.get("PADMINI_POSTHOG_HOST", "https://us.i.posthog.com"),
    }


def calcular_pedido(pedido: PedidoMapa):
    """Valida o pedido e devolve (data/hora local, mapa, fatos, seções do relatório)."""
    dt = _validar_datetime(pedido.data, pedido.hora)
    resultado = calcular_mapa(dt_local_naive=dt, lat=pedido.lat, lon=pedido.lon)
    fatos = detectar_todos_os_fatos(resultado)
    secoes, _ = montar_secoes(resultado, fatos)
    return dt, resultado, fatos, secoes


@app.post("/api/mapa")
def mapa(pedido: PedidoMapa):
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
def compatibilidade(pedido: PedidoCompatibilidade):
    """
    Compatibilidade de casal (Guna Milan). Corte do paywall:
      - nivel='amostra': só a nota, a categoria, o ponto forte e o de atenção
        (o suficiente para o card compartilhável). NÃO devolve as 8 kootas.
      - nivel='completo': as 8 kootas, doshas e Mangal. Em produção, liberar só
        após pagamento confirmado.
    """
    dt_a = _validar_datetime(pedido.a.data, pedido.a.hora)
    dt_b = _validar_datetime(pedido.b.data, pedido.b.hora)
    mapa_a = calcular_mapa(dt_local_naive=dt_a, lat=pedido.a.lat, lon=pedido.a.lon)
    mapa_b = calcular_mapa(dt_local_naive=dt_b, lat=pedido.b.lat, lon=pedido.b.lon)

    resultado = calcular_compatibilidade(mapa_a, mapa_b)

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
        texto_ia = gerar_com_claude(montar_prompt_compat(snippets))

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
def pdf(pedido: PedidoMapa):
    """Relatório completo em PDF. Não usa IA (sem custo por download). Requer pagamento."""
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
    if not cakto.verificar(assinatura, timestamp, corpo,
                           os.environ.get("PADMINI_CAKTO_WEBHOOK_SECRET", ""),
                           secret_do_corpo):
        raise HTTPException(401, "assinatura inválida")

    if not cakto.is_aprovado(evento):
        return {"ok": True, "ignorado": "pagamento não aprovado"}

    pd = cakto.coletar_pd(evento)
    produto = cakto.produto_do_evento(evento, pd)
    if produto not in ("mapa", "compat"):
        return {"ok": True, "ignorado": "produto desconhecido"}

    dados = cakto.dados_nascimento(pd, produto)
    if not dados:
        # sem os dados de nascimento não dá para gerar; sinaliza para tratamento manual
        raise HTTPException(422, "dados de nascimento ausentes no payload (ver cakto.py)")

    # a Cakto reenvia o webhook se não receber 200 a tempo: não mandar o e-mail duas vezes
    cakto_id = str((evento.get("data") or {}).get("id") or "") if isinstance(evento, dict) else ""
    if db.pedido_entregue(cakto_id):
        return {"ok": True, "produto": produto, "duplicado": True}

    link = entrega.link_completo(produto, dados)
    email = cakto.email_do_evento(evento)
    enviado = entrega.enviar_email(
        email, "Seu relatório Padmini está pronto",
        entrega.email_completo_html(produto, link, dados.get("nome", "")))
    db.registrar_pedido(evento, produto, dados, email, link, enviado)
    # se não enviou (Resend não configurado), devolve o link para envio manual
    return {"ok": True, "produto": produto, "email": email or None,
            "email_enviado": enviado, "link": None if enviado else link}

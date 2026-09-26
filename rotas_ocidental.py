"""
Padmini (versão ocidental) — rotas da API.

    POST /api/ocidental/mapa   amostra (grátis) ou completo (token "oc-…")
    POST /api/ocidental/pdf    PDF do completo (token)

As páginas (/mapa etc.) continuam servidas pelo app.py, que escolhe a versão
pelo PADMINI_SISTEMA ou pelo token do link. Aqui as rotas têm o nome da versão
de propósito: a resposta depende da página que pediu, nunca da versão no ar —
uma aba aberta antes da troca de PADMINI_SISTEMA continua funcionando.

Mesmas regras da védica: completo só com token (402 sem), IA só no completo e
em cache no banco, limite de requisições por IP.
"""

import os
import re
import unicodedata
from datetime import date

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

import acesso
import db
import limites
import mapa_ocidental as mo
import montar_texto_ocidental as mt
from gerar_pdf_ocidental import gerar_pdf_ocidental
from nascimento import aviso_de_horario, validar_data, validar_datetime

VERSAO = "ocidental"
rotas = APIRouter()


class PedidoMapaOcidental(BaseModel):
    nome: str = Field("", max_length=80)
    data: date
    # hora vazia = "não sei a hora": sem Ascendente, Meio do Céu e casas
    hora: str = Field("", pattern=r"^(\d{2}:\d{2})?$")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    cidade: str = Field("", max_length=200)
    texto_ia: bool = False
    nivel: str = Field("amostra", pattern=r"^(amostra|completo)$")
    token: str | None = Field(None, max_length=64)


def chave_do_pedido(p: PedidoMapaOcidental) -> str:
    """A mesma chave canônica da védica; sem hora, a hora entra vazia."""
    return acesso.chave_mapa(p.data.isoformat(), p.hora, p.lat, p.lon)


def calcular(p: PedidoMapaOcidental):
    """Valida e calcula. Devolve (mapa, aviso de horário de verão ou None)."""
    if p.hora:
        dt = validar_datetime(p.data, p.hora)
        mapa = mo.calcular_mapa_ocidental(dt, p.lat, p.lon)
        return mapa, aviso_de_horario(dt, mapa["fuso_resolvido"]["nome_iana"])
    validar_data(p.data)
    return mo.calcular_mapa_ocidental(None, p.lat, p.lon, data=p.data), None


def _cabecalho(p: PedidoMapaOcidental, mapa: dict, aviso: str | None, nivel: str) -> dict:
    return {"nivel": nivel, "sistema": VERSAO, "nome": p.nome.strip(), "cidade": p.cidade,
            "tem_hora": mapa["tem_hora"], "fuso": mapa["fuso_resolvido"], "aviso_horario": aviso}


def _pontos(mapa: dict) -> list[dict]:
    lista = []
    for k in list(mo.PLANETAS) + ["nodo_norte", "ascendente", "meio_do_ceu"]:
        if k not in mapa["pontos"]:
            continue
        p = mapa["pontos"][k]
        lista.append({"id": k, "nome": mo.PONTO_PT[k], "signo": p["signo"], "signo_pt": p["signo_pt"],
                      "longitude": p["longitude"], "grau": p["grau_texto"], "casa": p.get("casa"),
                      "retrogrado": bool(p.get("retrogrado")) and k in mo.PLANETAS,
                      "signo_incerto": bool(p.get("signo_incerto")),
                      "signos_possiveis_pt": [mo.SIGNO_PT[s] for s in p.get("signos_possiveis", [])]})
    return lista


def _texto_ia(p: PedidoMapaOcidental, chave: str, secoes: dict, request: Request) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "Texto por IA não está configurado neste servidor.")
    from montar_texto import gerar_com_claude  # o mesmo cliente da védica
    chave_cache = f"{VERSAO}|{chave}"  # não se mistura com o cache da védica
    texto = db.texto_ia(chave_cache)
    if texto is None:
        limites.exigir(limites.TEXTO_IA, request)
        texto = gerar_com_claude(mt.montar_prompt(secoes))
        db.guardar_texto_ia(chave_cache, f"{VERSAO}:mapa", texto,
                            os.environ.get("PADMINI_MODELO", "claude-sonnet-5"))
    return texto


@rotas.post("/api/ocidental/mapa")
def mapa_ocidental(p: PedidoMapaOcidental, request: Request):
    limites.exigir(limites.CALCULO, request)
    if p.texto_ia and p.nivel != "completo":
        raise HTTPException(402, "O texto por IA faz parte do mapa completo.")
    mapa, aviso = calcular(p)

    if p.nivel == "amostra":
        # Amostra grátis: a tríade (Sol, Lua, Ascendente) e o aspecto mais exato.
        return {**_cabecalho(p, mapa, aviso, "amostra"), "amostra": mt.montar_amostra(mapa)}

    chave = chave_do_pedido(p)
    if not acesso.completo_liberado("mapa", chave, p.token, VERSAO):
        raise HTTPException(402, "O mapa completo requer pagamento.")
    secoes = mt.montar_secoes(mapa)
    return {
        **_cabecalho(p, mapa, aviso, "completo"),
        "pontos": _pontos(mapa),
        "casas": ({"sistema": mapa["casas"]["sistema"], "aviso": mapa["casas"]["aviso"],
                   "cuspides": mapa["casas"]["cuspides"]} if mapa["casas"] else None),
        "aspectos": [{**a, "titulo": mt.titulo_aspecto(a)} for a in mapa["aspectos"]],
        "elementos": {k: [mo.PONTO_PT[x] for x in v] for k, v in mapa["elementos"].items()},
        "modalidades": {k: [mo.PONTO_PT[x] for x in v] for k, v in mapa["modalidades"].items()},
        "regente_ascendente": mapa["regente_ascendente"],
        "amostra": mt.montar_amostra(mapa),
        "secoes": secoes,
        "texto_ia": _texto_ia(p, chave, secoes, request) if p.texto_ia else None,
    }


@rotas.post("/api/ocidental/pdf")
def pdf_ocidental(p: PedidoMapaOcidental, request: Request):
    """Mapa natal completo em PDF. Sem IA (sem custo por download). Requer pagamento."""
    limites.exigir(limites.PDF, request)
    if not acesso.completo_liberado("mapa", chave_do_pedido(p), p.token, VERSAO):
        raise HTTPException(402, "O PDF completo requer pagamento.")
    mapa, _ = calcular(p)
    conteudo = gerar_pdf_ocidental(mapa=mapa, secoes=mt.montar_secoes(mapa), nome=p.nome, cidade=p.cidade,
                                   data_nascimento=p.data, hora=p.hora)
    sem_acento = unicodedata.normalize("NFKD", p.nome).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")[:40]
    arquivo = f"mapa-natal-{slug}.pdf" if slug else "mapa-natal.pdf"
    return Response(conteudo, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{arquivo}"'})


# --------------------------------------------------------------------------
# Modo live (Pedro): token do completo sem pagamento, com a sessão do /live
# (mesmo cookie assinado da védica, ver app.py) e registro em live_geracoes.
# --------------------------------------------------------------------------
@rotas.post("/api/live/ocidental/token/mapa")
def live_token_mapa_ocidental(p: PedidoMapaOcidental, request: Request):
    if not acesso.sessao_valida("live", request.cookies.get("pad_live")):
        raise HTTPException(401, "Sessão do modo live expirada. Entre de novo.")
    if p.hora:
        validar_datetime(p.data, p.hora)
    else:
        validar_data(p.data)
    db.registrar_live(f"{VERSAO}:mapa", p.nome.strip(), p.cidade, f"{p.data.isoformat()} {p.hora}".strip())
    return {"token": acesso.emitir_token("mapa", chave_do_pedido(p), VERSAO)}


# --------------------------------------------------------------------------
# SINASTRIA (o casal) — /compatibilidade na versão ocidental
# --------------------------------------------------------------------------
class PessoaOcidental(BaseModel):
    nome: str = Field("", max_length=80)
    data: date
    hora: str = Field("", pattern=r"^(\d{2}:\d{2})?$")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    cidade: str = Field("", max_length=200)


class PedidoSinastria(BaseModel):
    a: PessoaOcidental
    b: PessoaOcidental
    nivel: str = Field("amostra", pattern=r"^(amostra|completo)$")
    texto_ia: bool = False
    token: str | None = Field(None, max_length=64)


def chave_do_casal(p: PedidoSinastria) -> str:
    return acesso.chave_compat((p.a.data.isoformat(), p.a.hora, p.a.lat, p.a.lon),
                               (p.b.data.isoformat(), p.b.hora, p.b.lat, p.b.lon))


def _calcular_pessoa(x: PessoaOcidental):
    return calcular(PedidoMapaOcidental(**x.model_dump()))


@rotas.post("/api/ocidental/sinastria")
def sinastria_ocidental(p: PedidoSinastria, request: Request):
    """Amostra: Índice Padmini + ponto forte e de atenção (o card). Completo:
    as 8 dimensões, aspectos cruzados e casas — com token."""
    import sinastria as si
    limites.exigir(limites.CALCULO, request)
    if p.texto_ia and p.nivel != "completo":
        raise HTTPException(402, "O texto por IA faz parte do relatório completo.")
    (ma, aviso_a), (mb, aviso_b) = _calcular_pessoa(p.a), _calcular_pessoa(p.b)
    chave = None
    if p.nivel == "completo":
        chave = chave_do_casal(p)
        if not acesso.completo_liberado("compat", chave, p.token, VERSAO):
            raise HTTPException(402, "O relatório completo requer pagamento.")
    nome_a, nome_b = p.a.nome.strip() or "Pessoa A", p.b.nome.strip() or "Pessoa B"
    rel = mt.montar_sinastria(si.calcular_sinastria(ma, mb), ma, mb, nome_a, nome_b, p.nivel)

    texto_ia = None
    if p.texto_ia:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(503, "Texto por IA não está configurado neste servidor.")
        from montar_texto import gerar_com_claude
        chave_cache = f"{VERSAO}|{chave}"
        texto_ia = db.texto_ia(chave_cache)
        if texto_ia is None:
            limites.exigir(limites.TEXTO_IA, request)
            texto_ia = gerar_com_claude(mt.montar_prompt_sinastria(rel, nome_a, nome_b))
            db.guardar_texto_ia(chave_cache, f"{VERSAO}:compat", texto_ia,
                                os.environ.get("PADMINI_MODELO", "claude-sonnet-5"))
    return {"nivel": p.nivel, "sistema": VERSAO, "nomes": {"a": nome_a, "b": nome_b},
            "maximo": 100, **rel, "avisos_horario": {"a": aviso_a, "b": aviso_b}, "texto_ia": texto_ia}


@rotas.post("/api/live/ocidental/token/sinastria")
def live_token_sinastria_ocidental(p: PedidoSinastria, request: Request):
    if not acesso.sessao_valida("live", request.cookies.get("pad_live")):
        raise HTTPException(401, "Sessão do modo live expirada. Entre de novo.")
    for x in (p.a, p.b):
        validar_datetime(x.data, x.hora) if x.hora else validar_data(x.data)
    db.registrar_live(f"{VERSAO}:compat", f"{p.a.nome.strip()} & {p.b.nome.strip()}".strip(" &"),
                      p.a.cidade, f"{p.a.data.isoformat()} / {p.b.data.isoformat()}")
    return {"token": acesso.emitir_token("compat", chave_do_casal(p), VERSAO)}


# --------------------------------------------------------------------------
# NUMEROLOGIA (/numerologia) — nome completo de registro + data
# --------------------------------------------------------------------------
class PedidoNumerologia(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120)  # nome completo de REGISTRO
    data: date
    nivel: str = Field("amostra", pattern=r"^(amostra|completo)$")
    texto_ia: bool = False
    token: str | None = Field(None, max_length=64)


def _calcular_numerologia(p: PedidoNumerologia) -> dict:
    import numerologia as nu
    validar_data(p.data)
    try:
        return nu.calcular_numerologia(p.nome, p.data)
    except ValueError as e:
        raise HTTPException(422, str(e))


def chave_da_numerologia(p: PedidoNumerologia) -> str:
    import numerologia as nu
    return acesso.chave_numerologia(nu.normalizar_nome(p.nome), p.data.isoformat())


@rotas.post("/api/ocidental/numerologia")
def numerologia_ocidental(p: PedidoNumerologia, request: Request):
    limites.exigir(limites.CALCULO, request)
    if p.texto_ia and p.nivel != "completo":
        raise HTTPException(402, "O texto por IA faz parte da numerologia completa.")
    res = _calcular_numerologia(p)
    base_resp = {"nivel": p.nivel, "sistema": VERSAO, "nome": p.nome.strip(), "data": p.data.isoformat()}
    if p.nivel == "amostra":
        return {**base_resp, **mt.montar_numerologia(res, "amostra")}
    chave = chave_da_numerologia(p)
    if not acesso.completo_liberado("numerologia", chave, p.token, VERSAO):
        raise HTTPException(402, "A numerologia completa requer pagamento.")
    rel = mt.montar_numerologia(res, "completo")
    texto_ia = None
    if p.texto_ia:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(503, "Texto por IA não está configurado neste servidor.")
        from montar_texto import gerar_com_claude
        chave_cache = f"{VERSAO}|{chave}|{res['ano_corrente']}"  # o Ano Pessoal muda todo ano
        texto_ia = db.texto_ia(chave_cache)
        if texto_ia is None:
            limites.exigir(limites.TEXTO_IA, request)
            texto_ia = gerar_com_claude(mt.montar_prompt_numerologia(rel))
            db.guardar_texto_ia(chave_cache, f"{VERSAO}:numerologia", texto_ia,
                                os.environ.get("PADMINI_MODELO", "claude-sonnet-5"))
    return {**base_resp, **rel, "texto_ia": texto_ia}


@rotas.post("/api/ocidental/numerologia/pdf")
def numerologia_pdf(p: PedidoNumerologia, request: Request):
    limites.exigir(limites.PDF, request)
    if not acesso.completo_liberado("numerologia", chave_da_numerologia(p), p.token, VERSAO):
        raise HTTPException(402, "O PDF completo requer pagamento.")
    from gerar_pdf_ocidental import gerar_pdf_numerologia
    rel = mt.montar_numerologia(_calcular_numerologia(p), "completo")
    conteudo = gerar_pdf_numerologia(rel=rel, nome=p.nome.strip(), data_nascimento=p.data)
    return Response(conteudo, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{_arquivo("numerologia", p.nome)}"'})


def _arquivo(prefixo: str, nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")[:40]
    return f"{prefixo}-{slug}.pdf" if slug else f"{prefixo}.pdf"


@rotas.post("/api/live/ocidental/token/numerologia")
def live_token_numerologia(p: PedidoNumerologia, request: Request):
    if not acesso.sessao_valida("live", request.cookies.get("pad_live")):
        raise HTTPException(401, "Sessão do modo live expirada. Entre de novo.")
    _calcular_numerologia(p)
    db.registrar_live(f"{VERSAO}:numerologia", p.nome.strip()[:80], "", p.data.isoformat())
    return {"token": acesso.emitir_token("numerologia", chave_da_numerologia(p), VERSAO)}


# --------------------------------------------------------------------------
# TAROT (/tarot) — tiragem de 3 cartas. O ID da tiragem (tarot.py) carrega as
# cartas com selo do servidor; o link pago assina esse ID, então o completo
# mostra exatamente as cartas da amostra.
#
# A PERGUNTA (opcional, até 140 caracteres) só entra no prompt da IA do
# completo: não vai para o banco, nem para o log, nem para o cache — texto
# com pergunta é gerado na hora e não é guardado.
# --------------------------------------------------------------------------
class PedidoTarot(BaseModel):
    tiragem: str = Field(..., min_length=10, max_length=40)
    nivel: str = Field("amostra", pattern=r"^(amostra|completo)$")
    texto_ia: bool = False
    pergunta: str = Field("", max_length=140)
    token: str | None = Field(None, max_length=64)


def _cartas(p: PedidoTarot) -> list[dict]:
    import tarot
    try:
        return tarot.cartas_da_tiragem(p.tiragem)
    except ValueError as e:
        raise HTTPException(422, str(e))


@rotas.post("/api/ocidental/tarot/tirar")
def tarot_tirar(request: Request):
    """Sorteia no servidor (gerador criptográfico) e devolve o ID + a amostra."""
    import tarot
    limites.exigir(limites.CALCULO, request)
    tiragem = tarot.tirar()
    return {"nivel": "amostra", "sistema": VERSAO, "tiragem": tiragem,
            **mt.montar_tarot(tarot.cartas_da_tiragem(tiragem), "amostra")}


@rotas.post("/api/ocidental/tarot")
def tarot_ocidental(p: PedidoTarot, request: Request):
    limites.exigir(limites.CALCULO, request)
    if p.texto_ia and p.nivel != "completo":
        raise HTTPException(402, "O texto por IA faz parte da leitura completa.")
    cartas = _cartas(p)
    base_resp = {"nivel": p.nivel, "sistema": VERSAO, "tiragem": p.tiragem}
    if p.nivel == "amostra":
        return {**base_resp, **mt.montar_tarot(cartas, "amostra")}
    chave = acesso.chave_tarot(p.tiragem)
    if not acesso.completo_liberado("tarot", chave, p.token, VERSAO):
        raise HTTPException(402, "A leitura completa requer pagamento.")
    rel = mt.montar_tarot(cartas, "completo")
    texto_ia = None
    if p.texto_ia:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(503, "Texto por IA não está configurado neste servidor.")
        from montar_texto import gerar_com_claude
        pergunta = " ".join(p.pergunta.split())
        if pergunta:  # não vai para o cache: a pergunta não é guardada
            limites.exigir(limites.TEXTO_IA, request)
            texto_ia = gerar_com_claude(mt.montar_prompt_tarot(rel, pergunta))
        else:
            chave_cache = f"{VERSAO}|{chave}"
            texto_ia = db.texto_ia(chave_cache)
            if texto_ia is None:
                limites.exigir(limites.TEXTO_IA, request)
                texto_ia = gerar_com_claude(mt.montar_prompt_tarot(rel))
                db.guardar_texto_ia(chave_cache, f"{VERSAO}:tarot", texto_ia,
                                    os.environ.get("PADMINI_MODELO", "claude-sonnet-5"))
    return {**base_resp, **rel, "texto_ia": texto_ia}


@rotas.post("/api/ocidental/tarot/pdf")
def tarot_pdf(p: PedidoTarot, request: Request):
    limites.exigir(limites.PDF, request)
    if not acesso.completo_liberado("tarot", acesso.chave_tarot(p.tiragem), p.token, VERSAO):
        raise HTTPException(402, "O PDF completo requer pagamento.")
    from gerar_pdf_ocidental import gerar_pdf_tarot
    conteudo = gerar_pdf_tarot(rel=mt.montar_tarot(_cartas(p), "completo"))
    return Response(conteudo, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="tarot-padmini.pdf"'})


@rotas.post("/api/live/ocidental/token/tarot")
def live_token_tarot(p: PedidoTarot, request: Request):
    if not acesso.sessao_valida("live", request.cookies.get("pad_live")):
        raise HTTPException(401, "Sessão do modo live expirada. Entre de novo.")
    cartas = _cartas(p)
    db.registrar_live(f"{VERSAO}:tarot", " · ".join(c["nome"] for c in cartas)[:80], "", "")
    return {"token": acesso.emitir_token("tarot", acesso.chave_tarot(p.tiragem), VERSAO)}

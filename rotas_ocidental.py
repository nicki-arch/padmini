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

import logging
import os
import re
import unicodedata
from datetime import date

from fastapi import APIRouter, Body, HTTPException, Request, Response
from pydantic import ValidationError
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
log = logging.getLogger("padmini.ocidental")


# --------------------------------------------------------------------------
# E-MAIL ANTES DA AMOSTRA (rodada 6). Na ocidental, toda amostra grátis pede o
# e-mail: uma parte aparece na tela e o resto chega por e-mail — é isso que
# garante que o endereço é de verdade. A resposta da API leva SÓ a parte da
# tela (senão bastaria abrir as ferramentas do navegador). Se o e-mail não sai
# (Resend fora do ar, sem chave), a tela mostra tudo: a falha é nossa, não da
# pessoa. O completo com token e o /live do Pedro não pedem e-mail.
# --------------------------------------------------------------------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_AMOSTRAS_POR_EMAIL_DIA = 3  # o mesmo limite da amostra por e-mail da rodada 4
ORIGEM_ACEITA = ("ref", "cupom", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")


class ComEmail(BaseModel):
    """Campos da amostra: o e-mail (obrigatório no nível amostra) e a caixa
    desmarcada "pode me mandar mais sobre a minha leitura" (até 3 e-mails)."""
    email: str = Field("", max_length=160)
    aceita_sequencia: bool = False
    origem: dict = Field(default_factory=dict)


def exigir_email(p: ComEmail) -> str:
    """422 sem e-mail válido; 429 se o endereço já recebeu amostras demais hoje.
    Vem ANTES do cálculo: sem e-mail, nada é calculado."""
    email = (p.email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "Deixe um e-mail válido: o resto da sua leitura chega nele.")
    if db.amostras_enviadas_hoje(email) >= MAX_AMOSTRAS_POR_EMAIL_DIA:
        raise HTTPException(429, "Este e-mail já recebeu várias amostras hoje. Tente amanhã.")
    return email


def entregar_amostra(request: Request, p: ComEmail, email: str, produto: str, dados: dict, nome: str,
                     tela: dict, inteira: dict) -> dict:
    """Manda a amostra inteira por e-mail, registra (com a caixa) e devolve só
    a parte da tela. E-mail que não saiu = a tela mostra tudo, e a equipe é avisada."""
    import alertas
    import entrega
    import marketing
    limites.exigir(limites.AMOSTRA_EMAIL, request)
    enviado = False
    if os.environ.get("RESEND_API_KEY"):
        try:
            html = marketing.email_amostra_html(produto, montar_amostra_email(produto, dados), dados, email,
                                                nome, VERSAO)
            enviado = entrega.enviar_email(email, marketing.assunto("amostra", produto, VERSAO), html)
        except Exception:  # noqa: BLE001
            log.exception("amostra %s: falha ao montar/enviar o e-mail", produto)
    if not enviado:
        alertas.alertar("Amostra não saiu por e-mail",
                        f"Uma amostra de {produto} não saiu por e-mail; a tela mostrou a leitura inteira.",
                        chave="amostra_email_falhou", intervalo=3600)
    origem = {k: str(v)[:80] for k, v in (p.origem or {}).items() if k in ORIGEM_ACEITA}
    # aceita_lembrete acompanha a caixa: até a sequência nova existir, quem marcou
    # recebe o lembrete de sempre (1 e-mail, dentro do "até 3" que autorizou).
    db.registrar_amostra_email(email, produto, dados, p.aceita_sequencia, origem, VERSAO,
                               aceita_sequencia=p.aceita_sequencia)
    if enviado:
        return {**tela, "parcial": True, "email": {"enviado": True, "para": email}}
    return {**inteira, "email": {"enviado": False, "para": email}}


def _pessoa_para_dados(x) -> dict:
    return {"nome": x.nome.strip()[:80], "data": x.data.isoformat(), "hora": x.hora,
            "lat": x.lat, "lon": x.lon, "cidade": x.cidade[:200]}


# O que fica SÓ no e-mail, produto a produto (a tela tem valor sozinha e o card
# compartilhável da sinastria continua na tela).
def tela_mapa(amostra: dict) -> dict:
    """Tela: o Sol inteiro (signo, grau e texto) e os NOMES da Lua e do Ascendente.
    E-mail: os textos da Lua e do Ascendente e o aspecto mais exato."""
    triade = [i if i["ponto"] == "sol" else {k: v for k, v in i.items() if k != "texto"}
              for i in amostra["triade"]]
    return {"triade": triade, "aspecto": None, "avisos": amostra["avisos"], "parcial": True}


def tela_sinastria(rel: dict) -> dict:
    """Tela: o Índice (com a frase dele), o card e o TÍTULO do ponto mais forte.
    E-mail: o texto do ponto forte e o ponto de atenção."""
    forte = {k: rel["ponto_forte"][k] for k in ("chave", "titulo", "nota")}
    return {**{k: v for k, v in rel.items() if k not in ("ponto_forte", "ponto_atencao")},
            "ponto_forte": forte, "ponto_atencao": None, "parcial": True}


def tela_numerologia(rel: dict) -> dict:
    """Tela: o número do Caminho de Vida (e o que é esse número). E-mail: o texto dele."""
    cv = {k: v for k, v in rel["caminho_de_vida"].items() if k != "texto"}
    return {**rel, "caminho_de_vida": cv, "parcial": True}


def tela_tarot(rel: dict) -> dict:
    """Tela: as 3 cartas (nome e posição). E-mail: a frase de cada carta."""
    return {**rel, "cartas": [{k: v for k, v in c.items() if k != "frase"} for c in rel["cartas"]],
            "parcial": True}


class PedidoMapaOcidental(ComEmail):
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
    if p.nivel == "amostra" and len(p.nome.strip()) < 2:
        # rodada 9: nome sempre obrigatório no formulário do mapa (o completo com
        # token e o /live continuam aceitando sem nome: links já entregues)
        raise HTTPException(422, "Preencha o seu nome.")
    email = exigir_email(p) if p.nivel == "amostra" else None
    mapa, aviso = calcular(p)

    if p.nivel == "amostra":
        # Amostra grátis: a tríade (Sol, Lua, Ascendente) e o aspecto mais exato —
        # parte na tela, o resto por e-mail.
        amostra = mt.montar_amostra(mapa)
        cab = _cabecalho(p, mapa, aviso, "amostra")
        dados = {"nome": p.nome.strip()[:80], "data": p.data.isoformat(), "hora": p.hora,
                 "lat": p.lat, "lon": p.lon, "cidade": p.cidade[:200]}
        return entregar_amostra(request, p, email, "mapa", dados, dados["nome"],
                                {**cab, "amostra": tela_mapa(amostra)}, {**cab, "amostra": amostra})

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


class PedidoSinastria(ComEmail):
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
    """Amostra: o índice (textos.NOME_INDICE) + ponto forte e de atenção (o card). Completo:
    as 8 dimensões, aspectos cruzados e casas — com token."""
    import sinastria as si
    limites.exigir(limites.CALCULO, request)
    if p.texto_ia and p.nivel != "completo":
        raise HTTPException(402, "O texto por IA faz parte do relatório completo.")
    email = exigir_email(p) if p.nivel == "amostra" else None
    (ma, aviso_a), (mb, aviso_b) = _calcular_pessoa(p.a), _calcular_pessoa(p.b)
    chave = None
    if p.nivel == "completo":
        chave = chave_do_casal(p)
        if not acesso.completo_liberado("compat", chave, p.token, VERSAO):
            raise HTTPException(402, "O relatório completo requer pagamento.")
    nome_a, nome_b = p.a.nome.strip() or "Pessoa A", p.b.nome.strip() or "Pessoa B"
    rel = mt.montar_sinastria(si.calcular_sinastria(ma, mb), ma, mb, nome_a, nome_b, p.nivel)
    if p.nivel == "amostra":
        cab = {"nivel": "amostra", "sistema": VERSAO, "nomes": {"a": nome_a, "b": nome_b}, "maximo": 100,
               "avisos_horario": {"a": aviso_a, "b": aviso_b}, "texto_ia": None}
        dados = {"a": _pessoa_para_dados(p.a), "b": _pessoa_para_dados(p.b)}
        return entregar_amostra(request, p, email, "compat", dados, dados["a"]["nome"],
                                {**cab, **tela_sinastria(rel)}, {**cab, **rel})

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
    if p.nivel == "completo":
        # a rosa das oito dimensões, desenhada no servidor (o mesmo SVG da home)
        import exemplos_ocidental as ex
        rel["rosa"] = ex.rosa_svg({d["chave"]: d["nota"] for d in rel["dimensoes"]}, rel["ponto_forte"]["chave"])
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
class PedidoNumerologia(ComEmail):
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
    email = exigir_email(p) if p.nivel == "amostra" else None
    res = _calcular_numerologia(p)
    base_resp = {"nivel": p.nivel, "sistema": VERSAO, "nome": p.nome.strip(), "data": p.data.isoformat()}
    if p.nivel == "amostra":
        rel = mt.montar_numerologia(res, "amostra")
        nome = p.nome.strip()
        return entregar_amostra(request, p, email, "numerologia", {"nome": nome, "data": p.data.isoformat()},
                                nome.split(" ")[0], {**base_resp, **tela_numerologia(rel)}, {**base_resp, **rel})
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
class PedidoTarot(ComEmail):
    tiragem: str = Field(..., min_length=10, max_length=40)
    nivel: str = Field("amostra", pattern=r"^(amostra|completo)$")
    texto_ia: bool = False
    pergunta: str = Field("", max_length=140)
    token: str | None = Field(None, max_length=64)


def _cartas(p: PedidoTarot) -> list[dict]:
    import tarot
    try:
        return tarot.cartas_da_tiragem(p.tiragem)
    except tarot.SemSegredo:
        raise HTTPException(503, "O tarot está indisponível no momento.")
    except ValueError as e:
        raise HTTPException(422, str(e))


@rotas.post("/api/ocidental/tarot/tirar")
def tarot_tirar(request: Request, corpo: dict = Body(default={})):
    """Sorteia no servidor (gerador criptográfico) e devolve o ID + a amostra.
    Pede o e-mail como as outras amostras; no /live do Pedro (sessão válida),
    não — lá o sorteio vira direto o token do completo."""
    import tarot
    limites.exigir(limites.CALCULO, request)
    live = acesso.sessao_valida("live", request.cookies.get("pad_live"))
    try:
        p = ComEmail(**{k: v for k, v in (corpo or {}).items() if k in ComEmail.model_fields})
    except ValidationError:
        raise HTTPException(422, "Confira o e-mail.")
    email = None if live else exigir_email(p)
    try:
        tiragem = tarot.tirar()
    except tarot.SemSegredo:  # falha fechada: sem segredo não há sorteio
        raise HTTPException(503, "O tarot está indisponível no momento.")
    rel = mt.montar_tarot(tarot.cartas_da_tiragem(tiragem), "amostra")
    base_resp = {"nivel": "amostra", "sistema": VERSAO, "tiragem": tiragem}
    if live:
        return {**base_resp, **rel}
    # só o número da tiragem vai para o banco e para o e-mail — a pergunta nem chega aqui
    return entregar_amostra(request, p, email, "tarot", {"tiragem": tiragem}, "",
                            {**base_resp, **tela_tarot(rel)}, {**base_resp, **rel})


@rotas.post("/api/ocidental/tarot")
def tarot_ocidental(p: PedidoTarot, request: Request):
    limites.exigir(limites.CALCULO, request)
    if p.texto_ia and p.nivel != "completo":
        raise HTTPException(402, "O texto por IA faz parte da leitura completa.")
    email = exigir_email(p) if p.nivel == "amostra" else None
    cartas = _cartas(p)
    base_resp = {"nivel": p.nivel, "sistema": VERSAO, "tiragem": p.tiragem}
    if p.nivel == "amostra":
        rel = mt.montar_tarot(cartas, "amostra")
        return entregar_amostra(request, p, email, "tarot", {"tiragem": p.tiragem}, "",
                                {**base_resp, **tela_tarot(rel)}, {**base_resp, **rel})
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


# --------------------------------------------------------------------------
# AMOSTRA POR E-MAIL (versão ocidental). A rota é a mesma da védica,
# /api/amostra/email, e quem decide a versão é o SERVIDOR (sistema.ativo(), no
# app.py): o navegador não escolhe. Aqui ficam só a validação dos dados de cada
# produto e a montagem da amostra — com as MESMAS funções das páginas.
# --------------------------------------------------------------------------
class PedidoAmostraEmailOcidental(BaseModel):
    email: str = Field(..., max_length=160)
    produto: str = Field(..., pattern=r"^(mapa|compat|numerologia|tarot)$")
    pessoa: PessoaOcidental | None = None          # mapa
    a: PessoaOcidental | None = None               # sinastria
    b: PessoaOcidental | None = None
    nome: str | None = Field(None, max_length=120)  # numerologia: nome completo de registro
    data: date | None = None                        # numerologia
    tiragem: str | None = Field(None, max_length=40)  # tarot: SÓ o número da tiragem (nunca a pergunta)
    aceita_lembrete: bool = False
    origem: dict = Field(default_factory=dict)


def _dados_pessoa(p: PessoaOcidental) -> dict:
    if p.hora:
        validar_datetime(p.data, p.hora)
    else:
        validar_data(p.data)
    return {"nome": p.nome.strip()[:80], "data": p.data.isoformat(), "hora": p.hora,
            "lat": p.lat, "lon": p.lon, "cidade": p.cidade[:200]}


def dados_da_amostra_email(p: PedidoAmostraEmailOcidental) -> tuple[dict, str]:
    """(dados que vão para o banco e para o `sck`, nome para o "Olá"). Só os
    campos de cada produto — um campo a mais no pedido (ex.: a pergunta do
    tarot) nunca chega aqui."""
    import numerologia as nu
    import tarot
    if p.produto == "mapa":
        if not p.pessoa:
            raise HTTPException(422, "Faltam os dados de nascimento.")
        dados = _dados_pessoa(p.pessoa)
        return dados, dados["nome"]
    if p.produto == "compat":
        if not (p.a and p.b):
            raise HTTPException(422, "Faltam os dados de nascimento do casal.")
        dados = {"a": _dados_pessoa(p.a), "b": _dados_pessoa(p.b)}
        return dados, dados["a"]["nome"]
    if p.produto == "numerologia":
        if not (p.nome and p.data):
            raise HTTPException(422, "Faltam o nome e a data de nascimento.")
        validar_data(p.data)
        if not nu.normalizar_nome(p.nome):
            raise HTTPException(422, "O nome precisa ter letras.")
        nome = p.nome.strip()
        return {"nome": nome, "data": p.data.isoformat()}, nome.split(" ")[0]
    if not p.tiragem:
        raise HTTPException(422, "Falta a tiragem.")
    try:
        tarot.cartas_da_tiragem(p.tiragem)
    except tarot.SemSegredo:
        raise HTTPException(503, "O tarot está indisponível no momento.")
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"tiragem": p.tiragem}, ""


def montar_amostra_email(produto: str, dados: dict) -> dict:
    """A amostra do e-mail = a da tela (mesmas funções dos endpoints acima)."""
    import numerologia as nu
    import sinastria as si
    import tarot
    if produto == "mapa":
        mapa, _ = calcular(PedidoMapaOcidental(**dados))
        return mt.montar_amostra(mapa)
    if produto == "compat":
        ma, _ = calcular(PedidoMapaOcidental(**dados["a"]))
        mb, _ = calcular(PedidoMapaOcidental(**dados["b"]))
        nome_a, nome_b = dados["a"]["nome"] or "Pessoa A", dados["b"]["nome"] or "Pessoa B"
        rel = mt.montar_sinastria(si.calcular_sinastria(ma, mb), ma, mb, nome_a, nome_b, "amostra")
        return {"nomes": {"a": nome_a, "b": nome_b}, **rel}
    if produto == "numerologia":
        res = nu.calcular_numerologia(dados["nome"], date.fromisoformat(dados["data"]))
        return mt.montar_numerologia(res, "amostra")
    return mt.montar_tarot(tarot.cartas_da_tiragem(dados["tiragem"]), "amostra")

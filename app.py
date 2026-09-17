"""
Padmini — servidor web.

Rodar localmente:
    pip install -r requirements.txt
    uvicorn app:app --reload
e abrir http://127.0.0.1:8000
"""

import os
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from base_significacoes import NOME_PT, SIGNO_PT
from cidades import BuscaCidades
from compute_chart import calcular_mapa
from detectar_fatos import detectar_todos_os_fatos
from gerar_pdf import gerar_pdf
from montar_texto import dasha_atual, gerar_com_claude, montar_prompt, montar_secoes

RAIZ = Path(__file__).parent

# Carrega variáveis do arquivo .env (ex.: ANTHROPIC_API_KEY), se existir. Nunca versionar o .env.
_env = RAIZ / ".env"
if _env.exists():
    for _linha in _env.read_text(encoding="utf-8-sig").splitlines():
        if "=" in _linha and not _linha.lstrip().startswith("#"):
            _chave, _valor = _linha.split("=", 1)
            os.environ.setdefault(_chave.strip(), _valor.strip())

app = FastAPI(title="Padmini")
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


@app.get("/")
def pagina():
    return FileResponse(RAIZ / "static" / "index.html")


@app.get("/api/cidades")
def cidades(q: str = Query("", max_length=80)):
    return busca.buscar(q)


@app.get("/api/config")
def config():
    return {"texto_ia_disponivel": bool(os.environ.get("ANTHROPIC_API_KEY"))}


def calcular_pedido(pedido: PedidoMapa):
    """Valida o pedido e devolve (data/hora local, mapa, fatos, seções do relatório)."""
    hora, minuto = map(int, pedido.hora.split(":"))
    if not (0 <= hora < 24 and 0 <= minuto < 60):
        raise HTTPException(422, "Hora inválida.")
    dt = datetime(pedido.data.year, pedido.data.month, pedido.data.day, hora, minuto)
    if not (datetime(1800, 1, 1) <= dt <= datetime.now()):
        raise HTTPException(422, "A data de nascimento precisa estar entre 1800 e hoje.")
    resultado = calcular_mapa(dt_local_naive=dt, lat=pedido.lat, lon=pedido.lon)
    fatos = detectar_todos_os_fatos(resultado)
    secoes, _ = montar_secoes(resultado, fatos)
    return dt, resultado, fatos, secoes


@app.post("/api/mapa")
def mapa(pedido: PedidoMapa):
    dt, resultado, fatos, secoes = calcular_pedido(pedido)

    texto_ia = None
    if pedido.texto_ia:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(503, "Texto por IA não está configurado neste servidor.")
        texto_ia = gerar_com_claude(montar_prompt(secoes))

    atual = dasha_atual(resultado)
    return {
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


@app.post("/api/pdf")
def pdf(pedido: PedidoMapa):
    """Relatório completo em PDF. Não usa IA (sem custo por download)."""
    dt, resultado, fatos, secoes = calcular_pedido(pedido)
    conteudo = gerar_pdf(resultado=resultado, fatos=fatos, secoes=secoes, nome=pedido.nome,
                         cidade=pedido.cidade, nascimento=dt)
    sem_acento = unicodedata.normalize("NFKD", pedido.nome).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")[:40]
    arquivo = f"mapa-vedico-{slug}.pdf" if slug else "mapa-vedico.pdf"
    return Response(conteudo, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{arquivo}"'})

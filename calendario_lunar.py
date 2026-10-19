"""
Padmini — motor do CALENDÁRIO LUNAR PERSONALIZADO, "A sua Lua no ano" (rodada 14,
versão ocidental).

Os próximos 12 meses (do dia 1º do mês da compra, como "O seu ano") lidos no mapa
natal da pessoa. Este módulo só calcula QUANDO e ONDE; o texto (anti-fatalista,
revisável) vem do banco do repositório privado, nunca de IA.

Sobre o mesmo Swiss Ephemeris do mapa e da previsão (tropical, Moshier, geocêntrico
aparente), reaproveitando o motor da rodada 13 (`previsao.py`):

  1. LUNAÇÕES: luas novas (Lua e Sol na mesma longitude) e cheias (a 180°), com dia e
     hora, signo e grau (da Lua). Bisseção na elongação Lua − Sol a partir de uma
     amostra diária: erro numérico abaixo de 1 segundo.
  2. ECLIPSES: a mesma busca da previsão (`previsao.eclipses_entre`), agora com a hora
     do máximo. O eclipse fica junto da lunação que ele acompanha.
  3. MERCÚRIO RETRÓGRADO: as estações (velocidade de Mercúrio passando por zero), com o
     signo do começo e do fim. Entra o período que toca os 12 meses, mesmo que tenha
     começado antes ou termine depois.
  4. REVOLUÇÃO LUNAR: a Lua voltando à longitude da Lua natal, ~13 vezes no período
     (`swe.mooncross_ut`).

Personalização:
  - com hora: a casa natal de cada lunação, de cada eclipse e de cada Mercúrio
    retrógrado (a casa do grau onde ele estaciona retrógrado), e a lunação sobre um
    ponto natal (conjunção até ORBE_PONTO, 3°, com Sol, Lua, Mercúrio, Vênus, Marte,
    Júpiter, Saturno, Ascendente e Meio do Céu);
  - sem hora: sem casas, sem Ascendente e Meio do Céu e sem a Lua natal (calculada ao
    meio-dia, pode estar ~7° fora do lugar). Ficam o signo e os contatos com os outros
    planetas. Sem a Lua natal também não há Revolução Lunar: com até 7° de erro, a data
    poderia sair até ~13 horas errada (decisão da rodada 14, docs/calendario.md).

Fuso: o horário de Brasília por padrão; a pessoa pode escolher outro fuso brasileiro
(FUSOS). O fuso muda a hora e, perto da meia-noite, o dia; o período (os 12 meses) é
sempre o mesmo. O fuso não entra no token: o mesmo link abre em qualquer fuso.

Validação (testes/test_calendario_lunar.py, docs/calendario.md): lunações de 2026 e
2027 e os 8 eclipses do período contra o timeanddate.com, diferença máxima de 2 min.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import swisseph as swe

import mapa_ocidental as mo
import previsao as pv

# --------------------------------------------------------------------------
# Parâmetros — um lugar só (e docs/calendario.md)
# --------------------------------------------------------------------------
ORBE_PONTO = 3.0           # graus: lunação "sobre" um ponto natal (conjunção)
PONTOS_NATAIS = pv.PONTOS_NATAIS
FUSO_PADRAO = "America/Sao_Paulo"
# Os fusos do Brasil (sem horário de verão desde 2019). Rótulo = como a pessoa reconhece.
FUSOS = {
    "America/Sao_Paulo": "Horário de Brasília",
    "America/Manaus": "Amazonas, Mato Grosso, Rondônia e Roraima (−1 h de Brasília)",
    "America/Rio_Branco": "Acre e oeste do Amazonas (−2 h de Brasília)",
    "America/Noronha": "Fernando de Noronha (+1 h de Brasília)",
}

_F = swe.FLG_MOSEPH | swe.FLG_SPEED


def fuso_valido(nome: str | None) -> str:
    return nome if nome in FUSOS else FUSO_PADRAO


def instante(jd: float, fuso: str) -> datetime:
    """JD (UT) → data e hora no fuso (com o deslocamento). CORTA no minuto, como o
    timeanddate e o astro-seek (04:11:47 é 04:11), para a hora bater com a das referências."""
    y, m, d, h = swe.revjul(jd)
    utc = datetime(y, m, d, tzinfo=timezone.utc) + timedelta(hours=h)
    utc = utc.replace(second=0, microsecond=0)
    return utc.astimezone(ZoneInfo(fuso))


def _quando(jd: float, fuso: str) -> dict:
    t = instante(jd, fuso)
    return {"jd": jd, "data": t.date(), "hora": t.strftime("%H:%M"), "instante": t.isoformat()}


def _onde(natal: dict, lon: float) -> dict:
    signo, grau = mo.signo_de(lon)
    return {"longitude": round(lon % 360, 4), "signo": signo, "grau_texto": mo.grau_minuto(grau),
            "casa": mo.casa_de(lon, natal["casas"]["cuspides"]) if natal["tem_hora"] else None}


def _limites(ini: date, fim: date) -> tuple[float, float]:
    """Busca com 1 dia de folga dos dois lados: o filtro final é pelo dia no fuso."""
    return pv.jd_de(ini) - 1, pv.jd_de(fim + timedelta(days=1)) + 1


def _no_periodo(ev: dict, ini: date, fim: date) -> bool:
    return ini <= ev["data"] <= fim


# --------------------------------------------------------------------------
# 1. Lunações
# --------------------------------------------------------------------------
def _elongacao(jd: float) -> float:
    return (pv._lon(jd, "lua") - pv._lon(jd, "sol")) % 360


def lunacoes_entre(jd_ini: float, jd_fim: float) -> list[dict]:
    """Luas novas e cheias em [jd_ini, jd_fim): fase, instante (JD UT) e a longitude da
    Lua nele. Amostra diária (a elongação cresce ~12°/dia) e bisseção."""
    out = []
    jd, e = jd_ini, _elongacao(jd_ini)
    while jd < jd_fim:
        jd2 = jd + 1
        e2 = _elongacao(jd2)
        for fase, alvo in (("nova", 0.0), ("cheia", 180.0)):
            a, b = pv._desvio(e, alvo), pv._desvio(e2, alvo)
            if a < 0 <= b and b - a < 90:
                t = pv._bissecao(lambda j: pv._desvio(_elongacao(j), alvo), jd, jd2, iter_=30)
                if jd_ini <= t < jd_fim:
                    out.append({"fase": fase, "jd": t, "longitude": pv._lon(t, "lua")})
        jd, e = jd2, e2
    return out


# --------------------------------------------------------------------------
# 3. Mercúrio retrógrado
# --------------------------------------------------------------------------
def _vel_mercurio(jd: float) -> float:
    return swe.calc_ut(jd, swe.MERCURY, _F)[0][3]


def estacoes_mercurio(jd_ini: float, jd_fim: float) -> list[dict]:
    """As estações de Mercúrio em [jd_ini, jd_fim): "retrograda" (a velocidade fica
    negativa) ou "direta" (volta a ser positiva), com o instante e a longitude."""
    out = []
    jd, v = jd_ini, _vel_mercurio(jd_ini)
    while jd < jd_fim:
        jd2 = jd + 1
        v2 = _vel_mercurio(jd2)
        if (v < 0) != (v2 < 0):
            t = pv._bissecao(_vel_mercurio, jd, jd2, iter_=30)
            out.append({"estacao": "retrograda" if v2 < 0 else "direta", "jd": t,
                        "longitude": pv._lon(t, "mercurio")})
        jd, v = jd2, v2
    return out


def mercurio_retrogrado(natal: dict, ini: date, fim: date, fuso: str) -> list[dict]:
    """Os períodos de Mercúrio retrógrado que tocam [ini, fim] (busca com 30 dias de
    folga, porque um período dura ~3 semanas e pode ter começado antes)."""
    j0, j1 = _limites(ini, fim)
    est = estacoes_mercurio(j0 - 30, j1 + 30)
    out = []
    for i, e in enumerate(est):
        if e["estacao"] != "retrograda" or i + 1 >= len(est):
            continue
        d = est[i + 1]
        comeco, fim_ = _quando(e["jd"], fuso), _quando(d["jd"], fuso)
        if fim_["data"] < ini or comeco["data"] > fim:
            continue
        onde = _onde(natal, e["longitude"])
        out.append({"inicio": comeco, "fim": fim_, **onde,
                    "signo_fim": mo.signo_de(d["longitude"])[0],
                    "grau_fim_texto": mo.grau_minuto(mo.signo_de(d["longitude"])[1])})
    return out


# --------------------------------------------------------------------------
# 4. Revolução Lunar
# --------------------------------------------------------------------------
def retornos_da_lua(lua_natal: float, jd_ini: float, jd_fim: float) -> list[float]:
    """Os instantes (JD UT) em que a Lua volta à longitude natal em [jd_ini, jd_fim)."""
    out, jd = [], jd_ini
    while True:
        t = swe.mooncross_ut(lua_natal, jd, swe.FLG_MOSEPH)
        if t >= jd_fim:
            return out
        out.append(t)
        jd = t + 20  # o mês sideral tem ~27,3 dias


def revolucoes_lunares(natal: dict, ini: date, fim: date, fuso: str) -> list[dict]:
    if not natal["tem_hora"]:
        return []
    lua = natal["pontos"]["lua"]
    j0, j1 = _limites(ini, fim)
    out = []
    for t in retornos_da_lua(lua["longitude"], j0, j1):
        ev = {**_quando(t, fuso), "signo": lua["signo"]}
        if _no_periodo(ev, ini, fim):
            out.append(ev)
    return out


# --------------------------------------------------------------------------
# Tudo junto
# --------------------------------------------------------------------------
def lunacoes(natal: dict, ini: date, fim: date, fuso: str) -> list[dict]:
    """As lunações do período, cada uma com a casa, os pontos natais que ela toca e, se
    houver, o eclipse que a acompanha (o máximo cai a minutos ou poucas horas da lunação)."""
    j0, j1 = _limites(ini, fim)
    ecl = pv.eclipses_entre(j0 - 1, j1 + 1)
    out = []
    for b in lunacoes_entre(j0, j1):
        ev = {"fase": b["fase"], **_quando(b["jd"], fuso), **_onde(natal, b["longitude"]),
              "toca": pv.toques(natal, b["longitude"], ORBE_PONTO), "eclipse": None}
        if not _no_periodo(ev, ini, fim):
            continue
        tipo = "solar" if b["fase"] == "nova" else "lunar"
        for e in ecl:
            if e["tipo"] == tipo and abs(e["jd"] - b["jd"]) < 1:
                ev["eclipse"] = {"tipo": tipo, "subtipo": e["subtipo"], **_quando(e["jd"], fuso),
                                 **_onde(natal, e["longitude"])}
        out.append(ev)
    return out


def calcular_calendario(natal: dict, compra: date, fuso: str = FUSO_PADRAO) -> dict:
    fuso = fuso_valido(fuso)
    ini, fim = pv.periodo(compra)
    lun = lunacoes(natal, ini, fim, fuso)
    return {
        "inicio": ini, "fim": fim, "fuso": fuso, "fuso_nome": FUSOS[fuso],
        "tem_hora": natal["tem_hora"],
        "lunacoes": lun,
        "eclipses": [x["eclipse"] for x in lun if x["eclipse"]],
        "mercurio": mercurio_retrogrado(natal, ini, fim, fuso),
        "revolucoes": revolucoes_lunares(natal, ini, fim, fuso),
    }

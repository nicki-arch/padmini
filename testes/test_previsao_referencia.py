"""
Rodada 13: a previsão contra o astro-seek (testes/dados/referencias_previsao.json — valores
copiados da fonte em 15/out/2026, com a URL de cada consulta). Critérios do brief: datas exatas
com diferença de no máximo 1 dia; eclipses e Revolução Solar iguais.
"""
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import mapa_ocidental as mo
import previsao as pv

DADOS = Path(__file__).parent / "dados"
REF = json.loads((DADOS / "referencias_previsao.json").read_text())
NATAIS = {m["id"]: m for m in json.loads((DADOS / "referencias_ocidental.json").read_text())["mapas"]}
EN = {"Aries": "aries", "Taurus": "touro", "Gemini": "gemeos", "Cancer": "cancer", "Leo": "leao",
      "Virgo": "virgem", "Libra": "libra", "Scorpio": "escorpiao", "Sagittarius": "sagitario",
      "Capricorn": "capricornio", "Aquarius": "aquario", "Pisces": "peixes"}


def _grau(texto: str) -> float:
    """"24°37'01''" ou "17°39’" → graus decimais dentro do signo."""
    n = [int(x) for x in re.findall(r"\d+", texto)] + [0, 0]
    return n[0] + n[1] / 60 + n[2] / 3600


def _longitude(signo_en: str, grau: str) -> float:
    return mo.SIGNOS.index(EN[signo_en]) * 30 + _grau(grau)


def _coord(g):
    return (g[0] + g[1] / 60) * (-1 if g[2] in "SW" else 1)


_cache = {}


def _previsao(mid):
    if mid not in _cache:
        m = NATAIS[mid]
        lat, lon = _coord(m["lat_gm"]), _coord(m["lon_gm"])
        dt = datetime.fromisoformat(m["data"] + "T" + m["hora"])
        natal = mo.calcular_mapa_ocidental(dt, lat, lon)
        _cache[mid] = natal, pv.calcular_previsao(natal, dt.date(), lat, lon, date.fromisoformat(REF["compra"]))
    return _cache[mid]


@pytest.mark.parametrize("ref", REF["transitos"], ids=lambda r: f"{r['mapa']}-{r['planeta']}-{r['aspecto']}-{r['ponto']}")
def test_data_exata_bate_com_o_astro_seek(ref):
    natal, p = _previsao(ref["mapa"])
    # 1. o motor lista essa data exata nesse trânsito
    t = [t for t in p["transitos"] if (t["planeta"], t["aspecto"], t["ponto"]) == (ref["planeta"], ref["aspecto"], ref["ponto"])]
    assert t and any(x.isoformat() == ref["data_motor"] for tr in t for x in tr["exatas"]), ref
    # 2. no instante exato do motor, o planeta do astro-seek está no grau-alvo (bem menos que
    #    um dia de movimento): a data exata deles difere no máximo 1 dia da nossa
    lon_astroseek = _longitude(ref["fonte_mostra"]["signo"], ref["fonte_mostra"]["grau"])
    instante = datetime.fromisoformat(ref["instante_ut"])
    jd = pv.swe.julday(instante.year, instante.month, instante.day, instante.hour + instante.minute / 60)
    alvos = pv._alvos(natal["pontos"][ref["ponto"]]["longitude"], ref["aspecto"])
    vel = abs(pv.swe.calc_ut(jd, mo.PLANETAS[ref["planeta"]], pv._F)[0][3])
    desvio = min(abs(pv._desvio(lon_astroseek, a)) for a in alvos)
    assert desvio < vel, (ref, desvio, vel)
    assert desvio < 2 / 60  # na prática, segundos de arco (arredondamento da página)


@pytest.mark.parametrize("ref", REF["eclipses"], ids=lambda r: r["data"])
def test_eclipses_iguais(ref):
    _, p = _previsao("sp-1990")
    e = [e for e in p["eclipses"] if e["data"].isoformat() == ref["data"]]
    assert len(e) == 1, ref
    e = e[0]
    assert (e["tipo"], e["subtipo"]) == (ref["tipo"], ref["subtipo"])
    assert e["signo"] == EN[ref["signo"]]
    # lunares: a Lua dos dois, igual no minuto; solares: o astro-seek dá a Lua no máximo e
    # nós o Sol (o grau da lua nova) — até ~2' de diferença (docs/previsao.md)
    tolerancia = 1.5 / 60 if e["tipo"] == "lunar" else 3 / 60
    assert abs(pv._desvio(e["longitude"], _longitude(ref["signo"], ref["grau"]))) <= tolerancia, (e, ref)


def test_nenhum_eclipse_a_mais_ou_a_menos():
    _, p = _previsao("sp-1990")
    assert sorted(e["data"].isoformat() for e in p["eclipses"]) == sorted(r["data"] for r in REF["eclipses"])


@pytest.mark.parametrize("ref", REF["revolucao"], ids=lambda r: r["mapa"])
def test_revolucao_solar_igual(ref):
    _, p = _previsao(ref["mapa"])
    rs = p["revolucao"]
    ut = re.search(r"UT (\d+) (\w+) (\d{4}) - (\d{2}):(\d{2})", ref["instante"])
    dia, mes, ano, h, m = ut.groups()
    meses = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    esperado = datetime(int(ano), meses.index(mes[:3]) + 1, int(dia), int(h), int(m))
    y, mo_, d, hora = pv.swe.revjul(rs["jd"])
    nosso = datetime(y, mo_, d) + timedelta(hours=hora)
    assert abs((nosso - esperado).total_seconds()) <= 5 * 60, (nosso, esperado)
    assert rs["ascendente"] == EN[ref["ascendente_signo"]]
    assert rs["casa_do_sol"] == ref["casa_do_sol"]

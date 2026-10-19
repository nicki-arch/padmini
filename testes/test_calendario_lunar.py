"""
Rodada 14, Fase 1: o motor do calendário lunar ("A sua Lua no ano").

Validação contra referências públicas (testes/dados/referencias_calendario.json, valores
copiados das fontes em 19/out/2026): lunações de 2026 e 2027 e os eclipses contra o
timeanddate.com, Revolução Lunar contra o astro-seek em 2 mapas. Critério do brief:
diferença de no máximo 2 minutos.
"""
import json
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import swisseph as swe

import calendario_lunar as cl
import mapa_ocidental as mo
import previsao as pv

DADOS = Path(__file__).parent / "dados"
REF = json.loads((DADOS / "referencias_calendario.json").read_text())
NATAIS = {m["id"]: m for m in json.loads((DADOS / "referencias_ocidental.json").read_text())["mapas"]}
TOLERANCIA_MIN = 2.0
SP = ZoneInfo("America/Sao_Paulo")


def _jd(t: datetime) -> float:
    t = t.astimezone(timezone.utc)
    return swe.julday(t.year, t.month, t.day, t.hour + t.minute / 60 + t.second / 3600)


def _utc(texto: str) -> datetime:
    return datetime.fromisoformat(texto).replace(tzinfo=timezone.utc)


def _coord(g):
    return (g[0] + g[1] / 60) * (-1 if g[2] in "SW" else 1)


def _natal(mid, com_hora=True):
    m = NATAIS[mid]
    lat, lon = _coord(m["lat_gm"]), _coord(m["lon_gm"])
    if com_hora:
        return mo.calcular_mapa_ocidental(datetime.fromisoformat(m["data"] + "T" + m["hora"]), lat, lon)
    return mo.calcular_mapa_ocidental(None, lat, lon, data=date.fromisoformat(m["data"]))


LUNACOES = cl.lunacoes_entre(_jd(_utc("2026-01-01T00:00")), _jd(_utc("2028-01-01T00:00")))


# ------------------------------------------------------------------ validação (critério 1)
@pytest.mark.parametrize("fase", ["nova", "cheia"])
def test_lunacoes_de_2026_e_2027_batem_com_o_timeanddate(fase):
    nossas = [x["jd"] for x in LUNACOES if x["fase"] == fase]
    ref = REF["lunacoes_utc"][fase]
    assert len(nossas) == len(ref) == 25
    for jd, r in zip(nossas, ref):
        # o timeanddate corta os segundos: a referência é o começo do minuto
        dif = abs(jd - _jd(_utc(r))) * 24 * 60
        assert dif <= TOLERANCIA_MIN, (fase, r, dif)


def test_eclipses_batem_com_o_timeanddate():
    achados = pv.eclipses_entre(_jd(_utc("2026-01-01T00:00")), _jd(_utc("2028-01-01T00:00")))
    # 18/07/2027: penumbral de magnitude 0,001 ("quase eclipse" no timeanddate, listado pela
    # NASA e pelos calendários astrológicos) fica no motor, como em "O seu ano"
    achados = [e for e in achados if pv.data_de(e["jd"]) != date(2027, 7, 18)]
    assert len(achados) == len(REF["eclipses_utc"])
    for e, r in zip(achados, REF["eclipses_utc"]):
        assert (e["tipo"], e["subtipo"]) == (r["tipo"], r["subtipo"])
        assert abs(e["jd"] - _jd(_utc(r["maximo"]))) * 24 * 60 <= TOLERANCIA_MIN, r


@pytest.mark.parametrize("mid", ["sp-1990", "rio-1995"])
def test_revolucao_lunar_bate_com_o_astro_seek(mid):
    natal = _natal(mid)
    ref = REF["revolucao_lunar"][mid]["local"]
    nossas = cl.revolucoes_lunares(natal, date(2027, 1, 1), date(2027, 12, 31), "America/Sao_Paulo")
    assert len(nossas) == len(ref)
    for r, n in zip(ref, nossas):
        alvo = datetime.fromisoformat(r).replace(tzinfo=SP)
        assert abs(n["jd"] - _jd(alvo)) * 24 * 60 <= TOLERANCIA_MIN, (mid, r, n["hora"])
        # e a Lua está mesmo de volta ao grau natal (menos de 1")
        assert mo.distancia(pv._lon(n["jd"], "lua"), natal["pontos"]["lua"]["longitude"]) < 1 / 3600


# ------------------------------------------------------------------ o período e o fuso
def test_periodo_de_12_meses_e_ordem():
    cal = cl.calcular_calendario(_natal("sp-1990"), date(2026, 10, 19))
    assert (cal["inicio"], cal["fim"]) == (date(2026, 10, 1), date(2027, 9, 30))
    datas = [x["data"] for x in cal["lunacoes"]]
    assert datas == sorted(datas) and all(cal["inicio"] <= d <= cal["fim"] for d in datas)
    assert 24 <= len(datas) <= 26
    assert len(cal["revolucoes"]) in (13, 14)
    assert cal["fuso"] == "America/Sao_Paulo"


def test_hora_no_fuso_escolhido():
    """A lua cheia de 26/10/2026 04:11 UTC: 01:11 em Brasília, 00:11 em Manaus e 23:11 do
    DIA ANTERIOR no Acre. O período é o mesmo em todos os fusos."""
    natal = _natal("sp-1990")
    def cheia(fuso):
        cal = cl.calcular_calendario(natal, date(2026, 10, 19), fuso)
        return next(x for x in cal["lunacoes"] if x["fase"] == "cheia" and x["data"].month == 10
                    and x["data"].day >= 25)
    assert (cheia("America/Sao_Paulo")["data"], cheia("America/Sao_Paulo")["hora"]) == (date(2026, 10, 26), "01:11")
    assert cheia("America/Manaus")["hora"] == "00:11"
    acre = cheia("America/Rio_Branco")
    assert (acre["data"], acre["hora"]) == (date(2026, 10, 25), "23:11")
    assert cheia("America/Noronha")["hora"] == "02:11"
    assert acre["instante"].endswith("-05:00")


def test_fuso_desconhecido_vira_brasilia():
    cal = cl.calcular_calendario(_natal("sp-1990"), date(2026, 10, 19), "Europe/Lisbon")
    assert cal["fuso"] == "America/Sao_Paulo"


def test_lua_nova_no_signo_do_sol_e_cheia_no_oposto():
    for x in LUNACOES:
        lua, sol = pv._lon(x["jd"], "lua"), pv._lon(x["jd"], "sol")
        assert mo.distancia(lua, sol) == pytest.approx(0 if x["fase"] == "nova" else 180, abs=1e-3)


# ------------------------------------------------------------------ eclipses junto da lunação
def test_eclipse_vem_junto_da_lunacao():
    cal = cl.calcular_calendario(_natal("sp-1990"), date(2026, 10, 19))
    com = [x for x in cal["lunacoes"] if x["eclipse"]]
    assert [(x["data"].isoformat(), x["eclipse"]["tipo"]) for x in com] == [
        ("2027-02-06", "solar"), ("2027-02-20", "lunar"), ("2027-07-18", "lunar"),
        ("2027-08-02", "solar"), ("2027-08-17", "lunar")]
    for x in com:
        assert (x["fase"] == "nova") == (x["eclipse"]["tipo"] == "solar")
        assert x["eclipse"]["hora"] and x["eclipse"]["casa"] in range(1, 13)
    # as datas dos eclipses são as mesmas de "O seu ano"
    prev = pv.eclipses(_natal("sp-1990"), cal["inicio"], cal["fim"])
    assert [e["data"] for e in prev] == [e["data"] for e in cal["eclipses"]]


# ------------------------------------------------------------------ Mercúrio retrógrado
def test_mercurio_retrogrado():
    natal = _natal("sp-1990")
    cal = cl.calcular_calendario(natal, date(2026, 10, 19))
    m = cal["mercurio"]
    assert 3 <= len(m) <= 4
    for p in m:
        assert p["inicio"]["data"] < p["fim"]["data"]
        assert 18 <= (p["fim"]["data"] - p["inicio"]["data"]).days <= 26
        meio = (p["inicio"]["jd"] + p["fim"]["jd"]) / 2
        assert swe.calc_ut(meio, swe.MERCURY, swe.FLG_MOSEPH | swe.FLG_SPEED)[0][3] < 0
        assert p["casa"] in range(1, 13) and p["signo"] in mo.SIGNOS
        assert p["fim"]["data"] >= cal["inicio"] and p["inicio"]["data"] <= cal["fim"]
    # 24/10 a 13/11/2026 em Escorpião; 09/02 a 03/03/2027 de Peixes de volta a Aquário
    assert [(p["inicio"]["data"].isoformat(), p["signo"], p["signo_fim"]) for p in m[:2]] == [
        ("2026-10-24", "escorpiao", "escorpiao"), ("2027-02-09", "peixes", "aquario")]


def test_mercurio_que_comecou_antes_do_periodo_entra():
    """Período que começa no meio de um Mercúrio retrógrado: o período entra inteiro."""
    natal = _natal("sp-1990")
    est = cl.estacoes_mercurio(pv.jd_de(date(2026, 10, 1)), pv.jd_de(date(2027, 1, 1)))
    r = next(e for e in est if e["estacao"] == "retrograda")
    meio = pv.data_de(r["jd"] + 5)
    cal = cl.calcular_calendario(natal, meio)  # compra no mês em que ele está retrógrado
    assert any(p["inicio"]["data"] <= meio <= p["fim"]["data"] for p in cal["mercurio"])


# ------------------------------------------------------------------ personalização (critério 2)
def test_com_hora_tem_casa_e_pontos_tocados():
    natal = _natal("sp-1990")
    cal = cl.calcular_calendario(natal, date(2026, 10, 19))
    assert cal["tem_hora"]
    for x in cal["lunacoes"]:
        assert x["casa"] == mo.casa_de(x["longitude"], natal["casas"]["cuspides"])
        for t in x["toca"]:
            assert t["orbe"] <= cl.ORBE_PONTO
            assert mo.distancia(x["longitude"], natal["pontos"][t["ponto"]]["longitude"]) <= cl.ORBE_PONTO
    # nenhuma lunação a 3° de um ponto ficou de fora
    for x in cal["lunacoes"]:
        perto = {p for p in cl.PONTOS_NATAIS
                 if mo.distancia(x["longitude"], natal["pontos"][p]["longitude"]) <= cl.ORBE_PONTO}
        assert perto == {t["ponto"] for t in x["toca"]}
    assert any(x["toca"] for x in cal["lunacoes"])


def test_sem_hora_so_signos_e_planetas():
    natal = _natal("sp-1990", com_hora=False)
    cal = cl.calcular_calendario(natal, date(2026, 10, 19))
    assert not cal["tem_hora"]
    assert all(x["casa"] is None for x in cal["lunacoes"])
    assert all(p["casa"] is None for p in cal["mercurio"])
    assert all(x["eclipse"]["casa"] is None for x in cal["lunacoes"] if x["eclipse"])
    assert all(t["ponto"] not in ("lua", "ascendente", "meio_do_ceu")
               for x in cal["lunacoes"] for t in x["toca"])
    # sem a Lua natal confiável, sem Revolução Lunar
    assert cal["revolucoes"] == []
    # as lunações (o céu) são as mesmas com e sem hora
    com = cl.calcular_calendario(_natal("sp-1990"), date(2026, 10, 19))
    assert [(x["data"], x["hora"], x["signo"]) for x in com["lunacoes"]] == \
           [(x["data"], x["hora"], x["signo"]) for x in cal["lunacoes"]]

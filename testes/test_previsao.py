"""
Rodada 13: o motor da previsão dos próximos 12 meses (`previsao.py`). Método em
docs/previsao.md; a validação contra o astro-seek está em test_previsao_referencia.py.
"""
import json
from datetime import date, datetime
from pathlib import Path

import pytest

import mapa_ocidental as mo
import previsao as pv

REF = {m["id"]: m for m in json.loads(
    (Path(__file__).parent / "dados" / "referencias_ocidental.json").read_text())["mapas"]}
COMPRA = date(2026, 10, 15)


def _coord(g):
    return (g[0] + g[1] / 60) * (-1 if g[2] in "SW" else 1)


def _calcular(mid, sem_hora=False):
    m = REF[mid]
    lat, lon = _coord(m["lat_gm"]), _coord(m["lon_gm"])
    dt = datetime.fromisoformat(m["data"] + "T" + m["hora"])
    natal = (mo.calcular_mapa_ocidental(None, lat, lon, data=dt.date()) if sem_hora
             else mo.calcular_mapa_ocidental(dt, lat, lon))
    return natal, pv.calcular_previsao(natal, dt.date(), lat, lon, COMPRA)


@pytest.fixture(scope="module")
def tres():
    return {mid: _calcular(mid) for mid in ("sp-1990", "rio-1995", "lisboa-1985")}


def test_periodo_do_dia_1_do_mes_ate_12_meses():
    assert pv.periodo(date(2026, 10, 15)) == (date(2026, 10, 1), date(2027, 9, 30))
    assert pv.periodo(date(2026, 1, 31)) == (date(2026, 1, 1), date(2026, 12, 31))
    assert pv.periodo(date(2027, 12, 1)) == (date(2027, 12, 1), date(2028, 11, 30))


def test_trânsitos_coerentes(tres):
    for mid, (natal, p) in tres.items():
        assert p["transitos"], mid
        for t in p["transitos"]:
            assert t["planeta"] in pv.LENTOS and t["ponto"] in pv.PONTOS_NATAIS
            assert t["grupo"] == pv.GRUPO_DO_ASPECTO[t["aspecto"]]
            # toca o período
            assert t["entra"] <= p["fim"] and t["sai"] >= p["inicio"], (mid, t)
            # as exatas estão dentro da passagem, em ordem
            assert t["exatas"] == sorted(t["exatas"])
            assert all(t["entra"] <= x <= t["sai"] for x in t["exatas"]), (mid, t)
            assert t["exatas"] or t["mais_perto"], (mid, t)


def test_nas_datas_exatas_o_planeta_esta_no_grau(tres):
    """No dia exato, o desvio ao alvo cabe no movimento de um dia (≤ 0,3°); na
    entrada e na saída, o planeta está na borda da órbita."""
    natal, p = tres["sp-1990"]
    for t in p["transitos"]:
        alvos = pv._alvos(natal["pontos"][t["ponto"]]["longitude"], t["aspecto"])
        for x in t["exatas"]:
            meio_dia = pv.jd_de(x) + 0.5
            assert min(abs(pv._desvio(pv._lon(meio_dia, t["planeta"]), a)) for a in alvos) < 0.3, t
        for borda in (t["entra"], t["sai"]):
            meio_dia = pv.jd_de(borda) + 0.5
            d = min(abs(pv._desvio(pv._lon(meio_dia, t["planeta"]), a)) for a in alvos)
            assert abs(d - pv.ORBE_TRANSITO) < 0.3, (t, borda, d)


def test_retrogradacao_vira_um_periodo_so(tres):
    """Júpiter em quadratura ao Sol de sp-1990: entra, fica exato 3 vezes com a
    retrogradação e sai — um item só, com as 3 datas."""
    _, p = tres["sp-1990"]
    jq = [t for t in p["transitos"] if (t["planeta"], t["aspecto"], t["ponto"]) == ("jupiter", "quadratura", "sol")]
    assert len(jq) == 1
    assert [str(x) for x in jq[0]["exatas"]] == ["2026-11-03", "2027-01-21", "2027-06-28"]
    assert jq[0]["passagens"] == 3
    # nenhum par planeta × aspecto × ponto aparece duas vezes com períodos sobrepostos
    for mid, (_, p) in tres.items():
        vistos = {}
        for t in p["transitos"]:
            k = (t["planeta"], t["aspecto"], t["ponto"])
            for e, s in vistos.get(k, []):
                assert t["entra"] > s or t["sai"] < e, (mid, k)
            vistos.setdefault(k, []).append((t["entra"], t["sai"]))


def test_temas_sao_os_3_de_maior_peso_um_por_par(tres):
    for mid, (_, p) in tres.items():
        temas = p["temas"]
        assert len(temas) == 3, mid
        pares = [(t["planeta"], t["ponto"]) for t in temas]
        assert len(set(pares)) == 3
        assert [t["peso"] for t in temas] == sorted([t["peso"] for t in temas], reverse=True)
        # nenhum trânsito de par fora dos temas pesa mais que o 3º tema
        resto = [t for t in p["transitos"] if (t["planeta"], t["ponto"]) not in pares]
        assert all(t["peso"] <= temas[-1]["peso"] for t in resto), mid


def test_pesos_seguem_a_regra():
    base = {"planeta": "jupiter", "ponto": "venus", "aspecto": "trigono", "dias_no_periodo": 30,
            "exata_no_periodo": True}
    w = pv.peso
    assert w({**base, "planeta": "plutao"}) > w({**base, "planeta": "saturno"}) > w(base)
    assert w({**base, "ponto": "sol"}) > w(base) and w({**base, "ponto": "meio_do_ceu"}) > w(base)
    assert w({**base, "aspecto": "conjuncao"}) > w({**base, "aspecto": "quadratura"}) > w(base)
    assert w({**base, "aspecto": "oposicao"}) == w({**base, "aspecto": "conjuncao"})
    assert w({**base, "dias_no_periodo": 200}) > w(base)
    assert w({**base, "exata_no_periodo": False}) < w(base)


def test_ingressos_com_retrogradacao_juntam_as_datas(tres):
    """Rio 1995: Júpiter entra na casa 1, volta para a 12 e entra de novo."""
    natal, p = tres["rio-1995"]
    ing = {(i["planeta"], i["casa"]): i["datas"] for i in p["ingressos"]}
    assert ("jupiter", 1) in ing and len(ing[("jupiter", 1)]) == 2
    for (planeta, casa), datas in ing.items():
        for d in datas:
            assert p["inicio"] <= d <= p["fim"]
            dia_seguinte = pv.jd_de(d) + 1
            assert mo.casa_de(pv._lon(dia_seguinte, planeta), natal["casas"]["cuspides"]) == casa


def test_eclipses_do_periodo(tres):
    _, p = tres["sp-1990"]
    e = p["eclipses"]
    assert [(x["data"].isoformat(), x["tipo"], x["subtipo"]) for x in e] == [
        ("2027-02-06", "solar", "anular"), ("2027-02-20", "lunar", "penumbral"),
        ("2027-07-18", "lunar", "penumbral"), ("2027-08-02", "solar", "total"),
        ("2027-08-17", "lunar", "penumbral")]
    assert all(x["casa"] in range(1, 13) for x in e)
    # o eclipse lunar de 18/07/2027 cai em cima do Saturno natal (0,7°)
    assert e[2]["toca"] == [{"ponto": "saturno", "orbe": 0.72}]


def test_revolucao_solar_no_local_de_nascimento(tres):
    natal, p = tres["sp-1990"]
    rs = p["revolucao"]
    assert rs["aniversario"] == date(2027, 5, 15) and rs["data"] == date(2027, 5, 15)
    assert abs(pv._desvio(pv._lon(rs["jd"], "sol"), natal["pontos"]["sol"]["longitude"])) < 1e-4
    assert rs["ascendente"] in mo.SIGNOS and rs["casa_do_sol"] in range(1, 13)


def test_revolucao_fora_do_periodo_ou_29_de_fevereiro():
    natal = mo.calcular_mapa_ocidental(datetime(1992, 2, 29, 10, 0), -23.55, -46.63)
    rs = pv.revolucao_solar(natal, date(1992, 2, 29), -23.55, -46.63, date(2026, 10, 1), date(2027, 9, 30))
    assert rs["aniversario"] == date(2027, 3, 1)
    assert rs["data"] in (date(2027, 2, 28), date(2027, 3, 1))


def test_sem_hora(tres):
    natal, p = _calcular("sp-1990", sem_hora=True)
    assert not p["tem_hora"]
    pontos = {t["ponto"] for t in p["transitos"]}
    assert not pontos & {"ascendente", "meio_do_ceu", "lua"}
    assert p["ingressos"] == []
    assert all(e["casa"] is None for e in p["eclipses"])
    assert all(x["ponto"] != "lua" for e in p["eclipses"] for x in e["toca"])
    assert p["revolucao"]["data"] == date(2027, 5, 15)
    assert "ascendente" not in p["revolucao"] and "casa_do_sol" not in p["revolucao"]
    # o que não depende da hora é igual ao do mapa com hora
    # (as datas podem andar um dia: sem hora, o grau natal é o do meio-dia)
    com = {(t["planeta"], t["aspecto"], t["ponto"]) for t in tres["sp-1990"][1]["transitos"]
           if t["ponto"] not in ("ascendente", "meio_do_ceu", "lua")}
    sem = {(t["planeta"], t["aspecto"], t["ponto"]) for t in p["transitos"]}
    assert com == sem


def test_perto_do_polo_nao_quebra():
    natal = mo.calcular_mapa_ocidental(datetime(1980, 6, 1, 12, 0), 69.65, 18.96)  # Tromsø
    p = pv.calcular_previsao(natal, date(1980, 6, 1), 69.65, 18.96, COMPRA)
    assert natal["casas"]["sistema"] == "porfirio"
    assert p["revolucao"]["casa_do_sol"] in range(1, 13)

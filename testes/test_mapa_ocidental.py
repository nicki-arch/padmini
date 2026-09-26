"""
Motor do mapa natal ocidental (mapa_ocidental.py), Fase 1.

A validação principal é contra 11 mapas de referência copiados do astro-seek
(testes/dados/referencias_ocidental.json — fonte e URL de cada um anotadas lá),
incluindo 4 nascimentos no Brasil em horário de verão e 2 fora do Brasil.
Tolerância: 1 minuto de arco, que é como os sites mostram as posições.
"""
import json
import re
from datetime import date, datetime

import pytest

from test_app import RAIZ

import mapa_ocidental as mo  # noqa: E402

REF = json.loads((RAIZ / "testes" / "dados" / "referencias_ocidental.json").read_text(encoding="utf-8"))
SIGNOS_EN = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
             "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
PLANETA_EN = {"Sun": "sol", "Moon": "lua", "Mercury": "mercurio", "Venus": "venus", "Mars": "marte",
              "Jupiter": "jupiter", "Saturn": "saturno", "Uranus": "urano", "Neptune": "netuno",
              "Pluto": "plutao", "Node": "nodo_norte"}
UM_MINUTO = 1 / 60


def _longitude(signo: str, grau: str) -> float:
    g, m, s = map(int, re.findall(r"\d+", grau))
    return SIGNOS_EN.index(signo) * 30 + g + m / 60 + s / 3600


def _coord(gm) -> float:
    graus, minutos, lado = gm
    return (graus + minutos / 60) * (-1 if lado in ("S", "W") else 1)


def _mapa(caso):
    dt = datetime.fromisoformat(f"{caso['data']}T{caso['hora']}")
    return mo.calcular_mapa_ocidental(dt, _coord(caso["lat_gm"]), _coord(caso["lon_gm"]))


def _diferenca(a, b):
    return abs((a - b + 180) % 360 - 180)


def test_referencias_cobrem_o_que_o_brief_pede():
    mapas = REF["mapas"]
    assert len(mapas) >= 10
    brasil_hv = [m for m in mapas if m["horario_de_verao"] and "Brazil" in m["cidade"]]
    assert len(brasil_hv) >= 3
    assert any("Brazil" not in m["cidade"] for m in mapas)


@pytest.mark.parametrize("caso", REF["mapas"], ids=lambda c: c["id"])
def test_planetas_batem_com_a_referencia(caso):
    mapa = _mapa(caso)
    for en, nosso in PLANETA_EN.items():
        ref = caso["planetas"][en]
        p = mapa["pontos"][nosso]
        assert p["signo"] == mo.SIGNOS[SIGNOS_EN.index(ref["signo"])], (en, ref)
        assert _diferenca(p["longitude"], _longitude(ref["signo"], ref["grau"])) < UM_MINUTO, (en, ref)
        if ref["casa"].isdigit():
            assert p["casa"] == int(ref["casa"]), (en, ref)
        if nosso != "nodo_norte":
            retro = "Retrograde" in ref["movimento"] or ref["movimento"].endswith("R")
            assert p["retrogrado"] == retro, (en, ref)


@pytest.mark.parametrize("caso", REF["mapas"], ids=lambda c: c["id"])
def test_casas_ascendente_e_meio_do_ceu_batem(caso):
    mapa = _mapa(caso)
    assert mapa["casas"]["sistema"] == "placidus"
    for n in range(1, 13):
        ref = caso["casas"][str(n)]
        assert _diferenca(mapa["casas"]["cuspides"][n - 1], _longitude(ref["signo"], ref["grau"])) < UM_MINUTO, n
    asc, mc = caso["casas"]["1"], caso["casas"]["10"]
    assert _diferenca(mapa["pontos"]["ascendente"]["longitude"], _longitude(asc["signo"], asc["grau"])) < UM_MINUTO
    assert _diferenca(mapa["pontos"]["meio_do_ceu"]["longitude"], _longitude(mc["signo"], mc["grau"])) < UM_MINUTO


@pytest.mark.parametrize("caso", [c for c in REF["mapas"] if c["horario_de_verao"]], ids=lambda c: c["id"])
def test_horario_de_verao_igual_ao_da_fonte(caso):
    """A fonte diz o deslocamento em `hora_local` (ex.: "08:15 (-02, DST)")."""
    mapa = _mapa(caso)
    mostra = caso["fonte_mostra"]["hora_local"]
    esperado = {"-02": -2.0, "WEST": 1.0, "BST": 1.0}[re.search(r"\((\S+?),", mostra).group(1)]
    assert mapa["fuso_resolvido"]["offset_horas_na_data"] == esperado


# ------------------------------------------------------------------ casos de borda
def test_latitude_polar_cai_para_porfirio_e_avisa():
    mapa = mo.calcular_mapa_ocidental(datetime(1990, 5, 15, 14, 30), 69.65, 18.96)  # Tromsø
    assert mapa["casas"]["sistema"] == "porfirio"
    assert "Porfírio" in mapa["casas"]["aviso"]
    assert all(1 <= mapa["pontos"][p]["casa"] <= 12 for p in mo.PLANETAS)


def test_sem_hora_nao_tem_ascendente_casas_nem_aspectos_da_lua():
    mapa = mo.calcular_mapa_ocidental(None, -23.55, -46.63, data=date(1990, 5, 15))
    assert not mapa["tem_hora"] and mapa["casas"] is None and mapa["regente_ascendente"] is None
    assert "ascendente" not in mapa["pontos"] and "meio_do_ceu" not in mapa["pontos"]
    assert all("casa" not in p for p in mapa["pontos"].values())
    assert not any("lua" in (a["a"], a["b"]) for a in mapa["aspectos"])
    assert mapa["pontos"]["sol"]["signo"] == "touro"


def test_sem_hora_marca_lua_incerta_quando_ela_troca_de_signo_no_dia():
    # 15/05/1990: a Lua estava a 29°59' de Capricórnio às 14:30 (referência sp-1990)
    mapa = mo.calcular_mapa_ocidental(None, -23.5505, -46.6333, data=date(1990, 5, 15))
    assert mapa["pontos"]["lua"]["signo_incerto"] is True
    assert mapa["pontos"]["lua"]["signos_possiveis"] == ["capricornio", "aquario"]
    assert "lua" not in sum(mapa["elementos"].values(), [])


@pytest.mark.parametrize("tipo,a,b,orbe", [
    ("conjuncao", "venus", "marte", 8), ("conjuncao", "sol", "marte", 10), ("trigono", "lua", "saturno", 10),
    ("sextil", "sol", "lua", 6), ("sextil", "venus", "marte", 6), ("oposicao", "jupiter", "saturno", 8)])
def test_orbes_num_lugar_so(tipo, a, b, orbe):
    assert mo.orbe_maximo(tipo, a, b) == orbe


def test_aspectos_respeitam_orbe_e_vem_do_mais_exato():
    mapa = _mapa(REF["mapas"][0])
    orbes = [x["orbe"] for x in mapa["aspectos"]]
    assert orbes == sorted(orbes)
    for x in mapa["aspectos"]:
        d = mo.distancia(mapa["pontos"][x["a"]]["longitude"], mapa["pontos"][x["b"]]["longitude"])
        assert abs(abs(d - mo.ASPECTOS[x["tipo"]]) - x["orbe"]) < 1e-3
        assert x["orbe"] <= mo.orbe_maximo(x["tipo"], x["a"], x["b"])


def test_aspectos_iguais_aos_principais_da_fonte():
    """sp-1990: a fonte lista Sol trígono Saturno (orbe 0°37') e Júpiter oposição Urano (0°24')."""
    mapa = _mapa(REF["mapas"][0])
    achados = {(x["a"], x["b"], x["tipo"]): x["orbe"] for x in mapa["aspectos"]}
    assert abs(achados[("sol", "saturno", "trigono")] - (37 / 60)) < 2 / 60
    assert abs(achados[("jupiter", "urano", "oposicao")] - (24 / 60)) < 2 / 60


def test_destaque_da_amostra_envolve_ponto_pessoal():
    mapa = _mapa(REF["mapas"][0])
    d = mo.aspecto_de_destaque(mapa)
    assert d["a"] in mo.PESSOAIS + ("ascendente",) or d["b"] in mo.PESSOAIS + ("ascendente",)
    # Júpiter–Urano (0°24') é mais exato, mas é aspecto de geração: não vira amostra
    assert {d["a"], d["b"]} != {"jupiter", "urano"}


def test_regente_moderno_do_ascendente():
    mapa = _mapa(REF["mapas"][0])  # sp-1990: Ascendente em Virgem
    assert mapa["pontos"]["ascendente"]["signo"] == "virgem"
    assert mapa["regente_ascendente"]["planeta"] == "mercurio"
    assert mo.REGENTE["escorpiao"] == "plutao" and mo.REGENTE["aquario"] == "urano"


def test_elementos_e_modalidades_contam_planetas_e_ascendente():
    mapa = _mapa(REF["mapas"][0])
    assert sum(len(v) for v in mapa["elementos"].values()) == 11
    assert sum(len(v) for v in mapa["modalidades"].values()) == 11

"""
Rodada 17, Fase 1: as regras dos temas de "O seu ano" (decisão do Nicolas de 16/out/2026).

  - só vira tema o trânsito com DURACAO_MINIMA_TEMA (45) dias ou mais dentro do período;
  - pelo menos um harmônico (sextil, trígono ou conjunção com Júpiter), se existir um que passe;
  - um planeta no máximo VEZES_POR_PLANETA (2) vezes.

Achado do Cowork (15/out): na amostra da Ana fictícia os 3 temas eram de Saturno tenso e o
3º durava 16 dias (16/mar a 1/abr/2027). As regras só escolhem: datas e pesos não mudam.
"""
import json
from datetime import date, datetime
from pathlib import Path

import pytest

import mapa_ocidental as mo
import previsao as pv

COMPRA = date(2026, 10, 15)
REF = {m["id"]: m for m in json.loads(
    (Path(__file__).parent / "dados" / "referencias_ocidental.json").read_text())["mapas"]}


def _coord(g):
    return (g[0] + g[1] / 60) * (-1 if g[2] in "SW" else 1)


def _previsao(dt, lat, lon):
    natal = mo.calcular_mapa_ocidental(dt, lat, lon)
    return pv.calcular_previsao(natal, dt.date(), lat, lon, COMPRA)


@pytest.fixture(scope="module")
def ana():
    return _previsao(datetime(1994, 5, 14, 15, 40), -30.0346, -51.2177)  # Porto Alegre


@pytest.fixture(scope="module")
def validacao():
    out = {}
    for mid in ("sp-1990", "rio-1995", "lisboa-1985"):
        m = REF[mid]
        out[mid] = _previsao(datetime.fromisoformat(m["data"] + "T" + m["hora"]), _coord(m["lat_gm"]),
                             _coord(m["lon_gm"]))
    return out


def _resumo(temas):
    return [(t["planeta"], t["aspecto"], t["ponto"], t["motivo"]) for t in temas]


# ------------------------------------------------------------------ a Ana (critério de aceite 1)
def test_ana_tem_3_temas_longos_e_um_harmonico(ana):
    temas = ana["temas"]
    assert len(temas) == 3
    assert all(t["dias_no_periodo"] >= 45 for t in temas)
    assert any(pv.harmonico(t) for t in temas)
    assert _resumo(temas) == [("saturno", "quadratura", "meio_do_ceu", "peso"),
                              ("saturno", "quadratura", "lua", "peso"),
                              ("jupiter", "sextil", "venus", "harmonico")]


def test_ana_o_tema_de_16_dias_saiu_do_resumo_mas_nao_do_ano(ana):
    curto = next(t for t in ana["transitos"] if (t["planeta"], t["aspecto"], t["ponto"])
                 == ("saturno", "oposicao", "ascendente"))
    assert curto["dias_no_periodo"] == 16 and (curto["entra"], curto["sai"]) == (date(2027, 3, 16),
                                                                               date(2027, 4, 2))
    assert curto not in ana["temas"]
    # continua no ano: o mês a mês e as áreas usam a lista inteira de trânsitos
    assert curto in ana["transitos"]


def test_ana_saturno_no_maximo_duas_vezes(ana):
    assert sum(t["planeta"] == "saturno" for t in ana["temas"]) == 2


# ------------------------------------------------------------------ os 3 mapas da rodada 13
@pytest.mark.parametrize("mid, esperado", [
    ("sp-1990", [("jupiter", "quadratura", "sol", "peso"), ("saturno", "conjuncao", "venus", "peso"),
                 ("plutao", "quadratura", "mercurio", "peso")]),
    ("rio-1995", [("plutao", "trigono", "meio_do_ceu", "peso"), ("plutao", "conjuncao", "mercurio", "peso"),
                  ("urano", "conjuncao", "meio_do_ceu", "peso")]),
    ("lisboa-1985", [("netuno", "quadratura", "lua", "peso"), ("netuno", "oposicao", "meio_do_ceu", "peso"),
                     ("jupiter", "conjuncao", "sol", "peso")]),
])
def test_mapas_de_validacao(validacao, mid, esperado):
    """Os 3 já cumpriam as regras: os temas são os mesmos da rodada 13, agora com o motivo."""
    temas = validacao[mid]["temas"]
    assert _resumo(temas) == esperado
    assert all(t["dias_no_periodo"] >= 45 for t in temas)
    for planeta in {t["planeta"] for t in temas}:
        assert sum(t["planeta"] == planeta for t in temas) <= 2


def test_sp_1990_sem_harmonico_longo_fica_sem_harmonico(validacao):
    """O motivo de o sp-1990 não ter harmônico: os harmônicos do ano duram 9 e 10 dias."""
    p = validacao["sp-1990"]
    harmonicos = [t for t in p["transitos"] if pv.harmonico(t)]
    assert harmonicos and all(t["dias_no_periodo"] < 45 for t in harmonicos)
    assert not any(pv.harmonico(t) for t in p["temas"])


@pytest.mark.parametrize("quem", ["ana", "sp-1990", "rio-1995", "lisboa-1985"])
def test_as_datas_e_os_pesos_nao_mudaram(ana, validacao, quem):
    p = ana if quem == "ana" else validacao[quem]
    for t in p["temas"]:
        original = next(x for x in p["transitos"] if (x["planeta"], x["aspecto"], x["ponto"], x["entra"])
                        == (t["planeta"], t["aspecto"], t["ponto"], t["entra"]))
        assert {k: v for k, v in t.items() if k != "motivo"} == original


# ------------------------------------------------------------------ as regras, uma a uma
def _t(planeta, ponto, aspecto, dias, peso, entra=date(2026, 11, 1)):
    return {"planeta": planeta, "ponto": ponto, "aspecto": aspecto, "grupo": pv.GRUPO_DO_ASPECTO[aspecto],
            "dias_no_periodo": dias, "peso": peso, "entra": entra}


def test_duracao_minima():
    lista = [_t("saturno", "sol", "quadratura", 44, 10), _t("urano", "lua", "trigono", 45, 5)]
    assert [t["planeta"] for t in pv.temas(lista)] == ["urano"]
    assert pv.DURACAO_MINIMA_TEMA == 45


def test_planeta_no_maximo_duas_vezes():
    lista = [_t("saturno", "sol", "quadratura", 100, 10), _t("saturno", "lua", "oposicao", 100, 9),
             _t("saturno", "venus", "quadratura", 100, 8), _t("urano", "marte", "trigono", 100, 1)]
    assert [(t["planeta"], t["ponto"]) for t in pv.temas(lista)] == [
        ("saturno", "sol"), ("saturno", "lua"), ("urano", "marte")]


def test_harmonico_entra_no_lugar_do_menor_peso():
    lista = [_t("saturno", "sol", "quadratura", 100, 10), _t("plutao", "lua", "oposicao", 100, 9),
             _t("netuno", "venus", "quadratura", 100, 8), _t("jupiter", "marte", "trigono", 100, 2),
             _t("jupiter", "mercurio", "sextil", 100, 3)]
    temas = pv.temas(lista)
    assert [(t["planeta"], t["ponto"], t["motivo"]) for t in temas] == [
        ("saturno", "sol", "peso"), ("plutao", "lua", "peso"), ("jupiter", "mercurio", "harmonico")]


def test_conjuncao_com_jupiter_conta_como_harmonico():
    assert pv.harmonico(_t("jupiter", "sol", "conjuncao", 100, 1))
    assert not pv.harmonico(_t("saturno", "sol", "conjuncao", 100, 1))
    lista = [_t("saturno", "sol", "quadratura", 100, 10), _t("plutao", "lua", "oposicao", 100, 9),
             _t("jupiter", "venus", "conjuncao", 100, 8)]
    assert all(t["motivo"] == "peso" for t in pv.temas(lista))  # já tem harmônico


def test_harmonico_curto_nao_entra():
    lista = [_t("saturno", "sol", "quadratura", 100, 10), _t("plutao", "lua", "oposicao", 100, 9),
             _t("netuno", "venus", "quadratura", 100, 8), _t("jupiter", "marte", "trigono", 20, 7)]
    assert not any(pv.harmonico(t) for t in pv.temas(lista))


def test_ano_sem_transito_longo_tem_menos_temas():
    assert pv.temas([_t("saturno", "sol", "quadratura", 10, 10)]) == []
    assert len(pv.temas([_t("saturno", "sol", "quadratura", 90, 10)])) == 1


def test_boas_vindas_sem_tema_usa_o_mapa_natal(monkeypatch):
    """Com menos de 3 temas agora possível, um ano sem tema nenhum não pode quebrar o e-mail
    (antes: temas[0] → IndexError)."""
    import sequencias
    monkeypatch.setattr(sequencias, "_previsao_da_amostra", lambda dados: {"temas": []})
    dados = {"nome": "Ana", "data": "1994-05-14", "hora": "15:40", "lat": -30.0346, "lon": -51.2177,
             "cidade": "Porto Alegre", "inicio": "2026-10"}
    assunto, titulo, texto = sequencias.trecho_extra("previsao", dados)
    assert "Vênus" in assunto and texto

"""
Mapas de referência: posições conferidas contra a Cosmolica em 15/set/2026.
Rodar com:  python testes/test_referencias.py   (ou pytest)

Tolerância de 2' nos graus. Einstein é caso especial: a Cosmolica usa a hora
média de Berlim para Ulm (13 min de diferença), então a Lua dela anda ~8'.
Nosso Ascendente de Einstein confere com o valor tropical publicado
(11°38' Câncer) quando se usa a hora média local de Ulm.
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compute_chart import calcular_mapa  # noqa: E402

# (signo, grau decimal, retrógrado) — Rahu/Ketu sempre com o mesmo grau
REFERENCIAS = {
    "Obama": dict(
        dt=datetime(1961, 8, 4, 19, 24), lat=21.30694, lon=-157.85833, lagna="Makara", nakshatra="Rohini",
        grahas={"Surya": ("Karka", 19.230), "Chandra": ("Vrishabha", 10.039), "Budha": ("Karka", 9.013),
                "Shukra": ("Mithuna", 8.471), "Mangala": ("Simha", 29.258), "Guru": ("Makara", 7.540),
                "Shani": ("Makara", 2.013), "Rahu": ("Simha", 4.574)},
        retro={"Guru", "Shani"}),
    "Churchill": dict(
        dt=datetime(1874, 11, 30, 1, 30), lat=51.8485, lon=-1.35132, lagna="Kanya", nakshatra="Magha",
        grahas={"Surya": ("Vrishchika", 15.612), "Chandra": ("Simha", 7.516), "Budha": ("Tula", 25.484),
                "Shukra": ("Vrishchika", 29.920), "Mangala": ("Kanya", 24.442), "Guru": ("Tula", 1.459),
                "Shani": ("Makara", 17.486), "Rahu": ("Mesha", 2.259)},
        retro={"Shukra"}),
    "JFK": dict(
        dt=datetime(1917, 5, 29, 15, 0), lat=42.33176, lon=-71.12116, lagna="Kanya", nakshatra="Purva Phalguni",
        grahas={"Surya": ("Vrishabha", 15.136), "Chandra": ("Simha", 24.501), "Budha": ("Mesha", 27.886),
                "Shukra": ("Vrishabha", 24.037), "Mangala": ("Mesha", 25.723), "Guru": ("Vrishabha", 0.339),
                "Shani": ("Karka", 4.453), "Rahu": ("Dhanu", 19.781)},
        retro=set()),
    "Marilyn": dict(
        dt=datetime(1926, 6, 1, 9, 30), lat=34.05223, lon=-118.24368, lagna="Karka", nakshatra="Dhanishta",
        grahas={"Surya": ("Vrishabha", 17.620), "Chandra": ("Makara", 26.274), "Budha": ("Vrishabha", 13.954),
                "Shukra": ("Mesha", 5.926), "Mangala": ("Kumbha", 27.907), "Guru": ("Kumbha", 4.001),
                "Shani": ("Tula", 28.617), "Rahu": ("Mithuna", 25.443)},
        retro={"Shani"}),
    "Einstein": dict(
        dt=datetime(1879, 3, 14, 11, 30), lat=48.39841, lon=9.99155, lagna="Mithuna", nakshatra="Jyeshtha",
        grahas={"Surya": ("Meena", 1.324), "Budha": ("Meena", 10.952), "Shukra": ("Meena", 24.800),
                "Mangala": ("Makara", 4.733), "Guru": ("Kumbha", 5.308), "Shani": ("Meena", 12.015),
                "Rahu": ("Makara", 9.307)},
        retro=set(), lagna_grau=(19.47, 0.05)),
}

TOLERANCIA = 2 / 60  # 2 minutos de arco


def verificar():
    falhas = []
    for nome, ref in REFERENCIAS.items():
        m = calcular_mapa(ref["dt"], ref["lat"], ref["lon"])
        g = m["grahas"]
        if m["lagna"]["signo"] != ref["lagna"]:
            falhas.append(f"{nome}: Ascendente {m['lagna']['signo']} != {ref['lagna']}")
        if "lagna_grau" in ref and abs(m["lagna"]["grau"] - ref["lagna_grau"][0]) > ref["lagna_grau"][1]:
            falhas.append(f"{nome}: grau do Ascendente {m['lagna']['grau']} != {ref['lagna_grau'][0]}")
        if m["nakshatra_lua"]["nome"] != ref["nakshatra"]:
            falhas.append(f"{nome}: nakshatra {m['nakshatra_lua']['nome']} != {ref['nakshatra']}")
        for planeta, (signo, grau) in ref["grahas"].items():
            if g[planeta]["signo"] != signo or abs(g[planeta]["grau_no_signo"] - grau) > TOLERANCIA:
                falhas.append(f"{nome}: {planeta} {g[planeta]['signo']} {g[planeta]['grau_no_signo']} != {signo} {grau}")
        retro = {k for k, v in g.items() if v["retrogrado"] and k not in ("Rahu", "Ketu")}
        if retro != ref["retro"]:
            falhas.append(f"{nome}: retrógrados {retro} != {ref['retro']}")
    return falhas


def test_mapas_de_referencia():
    assert verificar() == []


if __name__ == "__main__":
    falhas = verificar()
    print("\n".join(falhas) if falhas else f"OK: {len(REFERENCIAS)} mapas de referência conferem.")
    sys.exit(1 if falhas else 0)

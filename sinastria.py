"""
Padmini (versão ocidental) — SINASTRIA: o mapa de uma pessoa cruzado com o da outra.

Reaproveita o motor do mapa natal (mapa_ocidental.py). Três camadas:

  1. ASPECTOS CRUZADOS (A × B) entre Sol, Lua, Mercúrio, Vênus, Marte, Júpiter,
     Saturno e Ascendente, com os mesmos orbes do mapa natal.
  2. SOBREPOSIÇÃO DE CASAS: planetas de A nas casas de B e vice-versa. Só
     existe para quem tem hora de nascimento (casas dependem dela).
  3. OITO DIMENSÕES e o ÍNDICE PADMINI (0 a 100).

ÍNDICE PADMINI — MÉTODO PRÓPRIO. A sinastria tradicional não tem uma nota
canônica; esta é nossa, e a página diz isso com todas as letras. Como é feito:

  - Cada aspecto cruzado vale PESO_ASPECTO[tipo] × exatidão, onde exatidão vai
    de 1 (aspecto exato) a 0,5 (no limite do orbe).
  - Alguns pares mudam o peso (AJUSTES): tensão entre Vênus e Marte também é
    química (conta menos negativo); conjunção com Saturno é compromisso
    exigente (conta pouco); tensão com Saturno pesa mais.
  - Na dimensão "Dia a dia" entram também planetas pessoais de um nas casas
    6 e 7 do outro (+0,4 cada).
  - A nota de cada dimensão é 50 + 50 × tanh(soma / 1,5): sem aspecto nenhum
    fica em 50 (neutro); somas grandes se aproximam de 0 ou 100 sem estourar.
  - O índice é a média ponderada das dimensões (PESO_DIMENSAO), só das que
    puderam ser calculadas (ex.: sem hora de ninguém, "Dia a dia" fica de fora).

Propriedades garantidas por teste: determinismo, simetria (A,B = B,A) e casos
extremos construídos à mão.
"""

import math

import mapa_ocidental as mo

PONTOS = ("sol", "lua", "mercurio", "venus", "marte", "jupiter", "saturno", "ascendente")
PESSOAIS = ("sol", "lua", "mercurio", "venus", "marte")

PESO_ASPECTO = {"trigono": 1.0, "sextil": 0.7, "conjuncao": 0.8, "quadratura": -0.7, "oposicao": -0.5}

# Ajustes por par (conjunto de dois pontos, sem ordem) e tipo de aspecto.
AJUSTES = {
    (frozenset({"venus", "marte"}), "quadratura"): -0.2,   # atrito, mas também química
    (frozenset({"venus", "marte"}), "oposicao"): 0.1,      # atração dos opostos
    (frozenset({"venus", "marte"}), "conjuncao"): 1.0,
}
PESO_SATURNO = {"conjuncao": 0.1, "trigono": 0.6, "sextil": 0.5, "quadratura": -0.9, "oposicao": -0.8}

# As oito dimensões: pares de pontos que contam (sem ordem: vale A→B e B→A).
DIMENSOES = {
    "atracao": {"titulo": "Atração", "pares": [("venus", "marte")]},
    "emocoes": {"titulo": "Emoções", "pares": [("lua", "lua"), ("lua", "sol")]},
    "comunicacao": {"titulo": "Comunicação", "pares": [("mercurio", "mercurio"), ("mercurio", "sol"),
                                                      ("mercurio", "lua")]},
    "afeto": {"titulo": "Afeto e valores", "pares": [("venus", "venus"), ("venus", "lua"), ("venus", "sol")]},
    "identidade": {"titulo": "Identidade", "pares": [("sol", "sol"), ("sol", "ascendente")]},
    "crescimento": {"titulo": "Crescimento", "pares": [("jupiter", p) for p in PESSOAIS]},
    "compromisso": {"titulo": "Compromisso", "pares": [("saturno", p) for p in PESSOAIS]},
    "dia_a_dia": {"titulo": "Dia a dia", "pares": [("ascendente", p) for p in PESSOAIS + ("ascendente",)]},
}
PESO_DIMENSAO = {"atracao": 1.0, "emocoes": 1.5, "comunicacao": 1.0, "afeto": 1.5, "identidade": 1.0,
                 "crescimento": 0.75, "compromisso": 1.25, "dia_a_dia": 1.0}
BONUS_CASA_6_7 = 0.4
ESCALA = 1.5


def _ids(mapa: dict) -> list[str]:
    return [p for p in PONTOS if p in mapa["pontos"]]


def aspectos_cruzados(ma: dict, mb: dict) -> list[dict]:
    """Aspectos entre um ponto de A e um de B. `a` é sempre de A, `b` de B."""
    lista = []
    for pa in _ids(ma):
        for pb in _ids(mb):
            if pa == "lua" and ma["pontos"]["lua"].get("signo_incerto"):
                continue
            if pb == "lua" and mb["pontos"]["lua"].get("signo_incerto"):
                continue
            d = mo.distancia(ma["pontos"][pa]["longitude"], mb["pontos"][pb]["longitude"])
            for tipo, angulo in mo.ASPECTOS.items():
                orbe = abs(d - angulo)
                limite = mo.orbe_maximo(tipo, pa, pb)
                if orbe <= limite:
                    lista.append({"a": pa, "b": pb, "tipo": tipo, "orbe": round(orbe, 3),
                                  "exatidao": round(1 - 0.5 * orbe / limite, 4)})
                    break
    lista.sort(key=lambda x: (x["orbe"], x["a"], x["b"]))
    return lista


def peso(pa: str, pb: str, tipo: str) -> float:
    if "saturno" in (pa, pb):
        return PESO_SATURNO[tipo]
    return AJUSTES.get((frozenset({pa, pb}), tipo), PESO_ASPECTO[tipo])


def sobreposicao(ma: dict, mb: dict) -> list[dict]:
    """Planetas (pessoais + Júpiter e Saturno) de A nas casas de B. Vazio se B não tem hora."""
    if not mb["casas"]:
        return []
    return [{"planeta": p, "casa": mo.casa_de(ma["pontos"][p]["longitude"], mb["casas"]["cuspides"])}
            for p in PONTOS if p != "ascendente" and p in ma["pontos"]
            and not (p == "lua" and ma["pontos"]["lua"].get("signo_incerto"))]


def _par_bate(asp: dict, pares) -> bool:
    return any({asp["a"], asp["b"]} == {x, y} if x != y else asp["a"] == asp["b"] == x for x, y in pares)


def _nota(soma: float) -> int:
    return round(50 + 50 * math.tanh(soma / ESCALA))


def _calculavel(ma: dict, mb: dict, pares) -> bool:
    """A dimensão existe se algum par tem um ponto em A e o outro em B."""
    return any((x in ma["pontos"] and y in mb["pontos"]) or (y in ma["pontos"] and x in mb["pontos"])
               for x, y in pares)


def calcular_sinastria(ma: dict, mb: dict) -> dict:
    ab = aspectos_cruzados(ma, mb)
    casas_ab, casas_ba = sobreposicao(ma, mb), sobreposicao(mb, ma)

    dimensoes = {}
    for chave, dim in DIMENSOES.items():
        # Cada aspecto de `ab` é (ponto de A, ponto de B). Pares iguais (Lua×Lua)
        # dão um aspecto só; pares diferentes contam nos dois sentidos (Vênus de
        # A × Marte de B e Marte de A × Vênus de B), ambos já em `ab`.
        do_par = [a for a in ab if _par_bate(a, dim["pares"])]
        # soma em ordem fixa: A,B e B,A dão exatamente o mesmo número
        soma = sum(sorted(peso(a["a"], a["b"], a["tipo"]) * a["exatidao"] for a in do_par))
        calculavel = _calculavel(ma, mb, dim["pares"])
        if chave == "dia_a_dia":
            soma += BONUS_CASA_6_7 * sum(1 for c in casas_ab + casas_ba
                                         if c["casa"] in (6, 7) and c["planeta"] in PESSOAIS)
        dimensoes[chave] = {"titulo": dim["titulo"], "nota": _nota(soma) if calculavel else None,
                            "soma": round(soma, 4), "aspectos": do_par}

    notas = [(PESO_DIMENSAO[k], d["nota"]) for k, d in dimensoes.items() if d["nota"] is not None]
    indice = round(sum(p * n for p, n in notas) / sum(p for p, _ in notas)) if notas else 50
    return {"indice": indice, "dimensoes": dimensoes, "aspectos": ab,
            "casas_a_em_b": casas_ab, "casas_b_em_a": casas_ba}


def ponto_forte_e_de_atencao(sin: dict) -> tuple[str, str]:
    """A dimensão de nota mais alta e a mais baixa (empate: ordem de DIMENSOES)."""
    validas = [(k, d["nota"]) for k, d in sin["dimensoes"].items() if d["nota"] is not None]
    forte = max(validas, key=lambda kv: kv[1])[0]
    atencao = min(validas, key=lambda kv: kv[1])[0]
    return forte, atencao


def faixa(nota: int) -> str:
    return "alta" if nota >= 65 else "media" if nota >= 40 else "baixa"

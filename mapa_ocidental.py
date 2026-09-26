"""
Padmini — motor do MAPA NATAL OCIDENTAL (versão `ocidental`, ver sistema.py).

Não mexe no `compute_chart.py` (a védica continua usando aquele). Daqui:

  - Zodíaco TROPICAL: o mesmo Swiss Ephemeris da védica, sem FLG_SIDEREAL.
    Efemérides Moshier (FLG_MOSEPH), que não precisam de arquivo: precisão bem
    abaixo de 1 minuto de arco para os planetas nas datas do produto.
  - Fuso e horário de verão: `julian_day_utc` da védica (zoneinfo, com o
    histórico brasileiro de horário de verão).
  - Casas PLACIDUS. Dentro dos círculos polares o Placidus não existe (algumas
    cúspides nunca cruzam o horizonte); aí caímos para PORFÍRIO e registramos
    isso no resultado (`casas.sistema` e `casas.aviso`).
  - Pontos: Sol, Lua, Mercúrio, Vênus, Marte, Júpiter, Saturno, Urano, Netuno,
    Plutão, Ascendente, Meio do Céu e Nodo Norte. Sem Quíron (o Moshier não tem).
  - NODO VERDADEIRO (swe.TRUE_NODE). É o padrão do astro.com: a tabela padrão
    do gerador de mapas deles lista "TrueNode" (conferido em 26/set/2026 em
    astro.com/cgi/genchart.cgi). O astro-seek usa o médio por padrão e mostra o
    verdadeiro com a opção "Lunar Nodes (True)"; a diferença é de até ~1,5°.
  - Aspectos maiores com os orbes em ORBES (um lugar só).
  - Sem hora de nascimento: calcula ao meio-dia local, e NÃO há Ascendente,
    Meio do Céu nem casas. A Lua anda ~13° por dia, então: se ela muda de signo
    nesse dia, o signo dela sai marcado como incerto; e aspectos da Lua ficam
    de fora (o orbe seria chute).
"""

from datetime import datetime

import swisseph as swe

from compute_chart import julian_day_utc

# --------------------------------------------------------------------------
# Nomes
# --------------------------------------------------------------------------
SIGNOS = ["aries", "touro", "gemeos", "cancer", "leao", "virgem",
          "libra", "escorpiao", "sagitario", "capricornio", "aquario", "peixes"]
SIGNO_PT = {"aries": "Áries", "touro": "Touro", "gemeos": "Gêmeos", "cancer": "Câncer",
            "leao": "Leão", "virgem": "Virgem", "libra": "Libra", "escorpiao": "Escorpião",
            "sagitario": "Sagitário", "capricornio": "Capricórnio", "aquario": "Aquário",
            "peixes": "Peixes"}
ELEMENTO = {s: ("fogo", "terra", "ar", "agua")[i % 4] for i, s in enumerate(SIGNOS)}
MODALIDADE = {s: ("cardinal", "fixo", "mutavel")[i % 3] for i, s in enumerate(SIGNOS)}
ELEMENTO_PT = {"fogo": "Fogo", "terra": "Terra", "ar": "Ar", "agua": "Água"}
MODALIDADE_PT = {"cardinal": "Cardinal", "fixo": "Fixo", "mutavel": "Mutável"}

PLANETAS = {
    "sol": swe.SUN, "lua": swe.MOON, "mercurio": swe.MERCURY, "venus": swe.VENUS,
    "marte": swe.MARS, "jupiter": swe.JUPITER, "saturno": swe.SATURN,
    "urano": swe.URANUS, "netuno": swe.NEPTUNE, "plutao": swe.PLUTO,
}
PONTO_PT = {"sol": "Sol", "lua": "Lua", "mercurio": "Mercúrio", "venus": "Vênus",
            "marte": "Marte", "jupiter": "Júpiter", "saturno": "Saturno", "urano": "Urano",
            "netuno": "Netuno", "plutao": "Plutão", "nodo_norte": "Nodo Norte",
            "ascendente": "Ascendente", "meio_do_ceu": "Meio do Céu"}
PESSOAIS = ("sol", "lua", "mercurio", "venus", "marte")

# Regentes MODERNOS (Escorpião → Plutão, Aquário → Urano, Peixes → Netuno).
REGENTE = {"aries": "marte", "touro": "venus", "gemeos": "mercurio", "cancer": "lua",
           "leao": "sol", "virgem": "mercurio", "libra": "venus", "escorpiao": "plutao",
           "sagitario": "jupiter", "capricornio": "saturno", "aquario": "urano",
           "peixes": "netuno"}

# --------------------------------------------------------------------------
# Aspectos e orbes — O ÚNICO lugar onde eles são definidos.
# --------------------------------------------------------------------------
ASPECTOS = {"conjuncao": 0, "sextil": 60, "quadratura": 90, "trigono": 120, "oposicao": 180}
ASPECTO_PT = {"conjuncao": "conjunção", "sextil": "sextil", "quadratura": "quadratura",
              "trigono": "trígono", "oposicao": "oposição"}
HARMONICOS = ("sextil", "trigono")
TENSOS = ("quadratura", "oposicao")
LUMINARES = ("sol", "lua")


def orbe_maximo(tipo: str, a: str, b: str) -> float:
    """Orbe de partida: 8°, ou 10° quando o Sol ou a Lua participam; sextil, 6°."""
    if tipo == "sextil":
        return 6.0
    return 10.0 if (a in LUMINARES or b in LUMINARES) else 8.0


# Quem entra no cálculo de aspectos do mapa natal: os 10 planetas, e o
# Ascendente e o Meio do Céu quando há hora. O Nodo fica de fora (é ponto de
# leitura em signo e casa, não de aspecto, no produto).
PONTOS_COM_ASPECTO = tuple(PLANETAS) + ("ascendente", "meio_do_ceu")

FLAGS = swe.FLG_MOSEPH | swe.FLG_SPEED  # tropical: sem FLG_SIDEREAL


# --------------------------------------------------------------------------
def signo_de(longitude: float) -> tuple[str, float]:
    longitude %= 360
    return SIGNOS[int(longitude // 30)], longitude % 30


def distancia(a: float, b: float) -> float:
    """Distância angular em graus (0 a 180)."""
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def grau_minuto(grau_no_signo: float) -> str:
    """12.51 → "12°30'" (arredonda para o minuto)."""
    minutos = round(grau_no_signo * 60)
    return f"{minutos // 60}°{minutos % 60:02d}'"


def _ponto(longitude: float, velocidade: float | None = None) -> dict:
    signo, grau = signo_de(longitude)
    p = {"longitude": round(longitude % 360, 5), "signo": signo, "signo_pt": SIGNO_PT[signo],
         "grau_no_signo": round(grau, 4), "grau_texto": grau_minuto(grau)}
    if velocidade is not None:
        p["retrogrado"] = velocidade < 0
    return p


def _casas(jd: float, lat: float, lon: float) -> dict:
    """Cúspides Placidus; dentro do círculo polar, Porfírio (e avisa)."""
    try:
        cuspides, ascmc = swe.houses_ex(jd, lat, lon, b"P", swe.FLG_MOSEPH)
        sistema, aviso = "placidus", None
    except swe.Error:
        cuspides, ascmc = swe.houses_ex(jd, lat, lon, b"O", swe.FLG_MOSEPH)
        sistema = "porfirio"
        aviso = ("Nesta latitude (perto de um polo) as casas Placidus não existem: "
                 "usamos o sistema de Porfírio.")
    return {"sistema": sistema, "aviso": aviso, "cuspides": [round(c, 5) for c in cuspides[:12]],
            "ascendente": ascmc[0], "meio_do_ceu": ascmc[1]}


def casa_de(longitude: float, cuspides: list[float]) -> int:
    for i in range(12):
        ini, fim = cuspides[i], cuspides[(i + 1) % 12]
        if (longitude - ini) % 360 < (fim - ini) % 360:
            return i + 1
    return 12  # só por segurança numérica


def calcular_aspectos(pontos: dict, ids: list[str]) -> list[dict]:
    """Aspectos maiores entre os pontos dados, do mais exato para o menos."""
    lista = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if {a, b} == {"ascendente", "meio_do_ceu"}:
                continue
            d = distancia(pontos[a]["longitude"], pontos[b]["longitude"])
            for tipo, angulo in ASPECTOS.items():
                orbe = abs(d - angulo)
                if orbe <= orbe_maximo(tipo, a, b):
                    lista.append({"a": a, "b": b, "tipo": tipo, "orbe": round(orbe, 3)})
                    break
    lista.sort(key=lambda x: (x["orbe"], x["a"], x["b"]))
    return lista


def calcular_mapa_ocidental(dt_local_naive: datetime | None, lat: float, lon: float,
                            data=None) -> dict:
    """
    Mapa natal tropical.
      - com hora: `dt_local_naive` é a data e hora locais do nascimento;
      - sem hora: `dt_local_naive=None` e `data` (date) — calcula ao meio-dia.
    """
    tem_hora = dt_local_naive is not None
    if not tem_hora:
        dt_local_naive = datetime(data.year, data.month, data.day, 12, 0)
    jd, nome_fuso, offset = julian_day_utc(dt_local_naive, lat, lon)

    pontos = {}
    for nome, codigo in PLANETAS.items():
        (longitude, _lat, _dist, velocidade, *_), _ = swe.calc_ut(jd, codigo, FLAGS)
        pontos[nome] = _ponto(longitude, velocidade)
    (nodo, *_), _ = swe.calc_ut(jd, swe.TRUE_NODE, FLAGS)
    pontos["nodo_norte"] = _ponto(nodo)

    casas = None
    lua_incerta = False
    if tem_hora:
        casas = _casas(jd, lat, lon)
        pontos["ascendente"] = _ponto(casas["ascendente"])
        pontos["meio_do_ceu"] = _ponto(casas["meio_do_ceu"])
        for nome in list(PLANETAS) + ["nodo_norte"]:
            pontos[nome]["casa"] = casa_de(pontos[nome]["longitude"], casas["cuspides"])
    else:
        # a Lua muda de signo neste dia? (00:00 e 23:59 locais)
        signos = set()
        for h, m in ((0, 0), (23, 59)):
            jd_h, _, _ = julian_day_utc(dt_local_naive.replace(hour=h, minute=m), lat, lon)
            (lng, *_), _ = swe.calc_ut(jd_h, swe.MOON, FLAGS)
            signos.add(signo_de(lng)[0])
        lua_incerta = len(signos) > 1
        pontos["lua"]["signo_incerto"] = lua_incerta
        pontos["lua"]["signos_possiveis"] = sorted(signos, key=SIGNOS.index)

    ids_aspecto = [p for p in PONTOS_COM_ASPECTO if p in pontos and (tem_hora or p != "lua")]
    aspectos = calcular_aspectos(pontos, ids_aspecto)

    contaveis = list(PLANETAS) + (["ascendente"] if tem_hora else [])
    elementos = {e: [] for e in ELEMENTO_PT}
    modalidades = {m: [] for m in MODALIDADE_PT}
    for nome in contaveis:
        if nome == "lua" and lua_incerta:
            continue
        s = pontos[nome]["signo"]
        elementos[ELEMENTO[s]].append(nome)
        modalidades[MODALIDADE[s]].append(nome)

    regente = None
    if tem_hora:
        r = REGENTE[pontos["ascendente"]["signo"]]
        regente = {"planeta": r, "signo": pontos[r]["signo"], "casa": pontos[r].get("casa")}

    return {
        "zodiaco": "tropical",
        "tem_hora": tem_hora,
        "fuso_resolvido": {"nome_iana": nome_fuso, "offset_horas_na_data": offset},
        "pontos": pontos,
        "casas": casas,
        "aspectos": aspectos,
        "elementos": elementos,
        "modalidades": modalidades,
        "regente_ascendente": regente,
    }


def aspecto_de_destaque(mapa: dict) -> dict | None:
    """O aspecto mais exato do mapa que envolve um ponto pessoal (Sol, Lua,
    Mercúrio, Vênus, Marte ou Ascendente). Aspectos só entre planetas lentos
    (ex.: Urano–Netuno) são de geração inteira, não da pessoa — não servem de
    amostra."""
    pessoais = set(PESSOAIS) | {"ascendente"}
    for a in mapa["aspectos"]:
        if a["a"] in pessoais or a["b"] in pessoais:
            return a
    return None

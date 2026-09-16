"""
Padmini — motor de cálculo do Mapa Védico (D1)
Ayanamsa: Lahiri | Casas: Whole Sign | Nodos: média (mean node)

Usa pyswisseph diretamente (Swiss Ephemeris via bindings Python) em modo
Moshier (sem arquivos de efeméride externos) — precisão de segundos de arco,
mais que suficiente pra astrologia. Sem dependência de bibliotecas de
terceiros com empacotamento quebrado (vedicastro/flatlib se mostraram
frágeis na prática — ver nota no final).
"""

import swisseph as swe
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from timezonefinder import TimezoneFinder

_TF = TimezoneFinder()

SIGNOS = [
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrishchika", "Dhanu", "Makara", "Kumbha", "Meena",
]

GRAHAS = {
    "Surya": swe.SUN,
    "Chandra": swe.MOON,
    "Mangala": swe.MARS,
    "Budha": swe.MERCURY,
    "Guru": swe.JUPITER,
    "Shukra": swe.VENUS,
    "Shani": swe.SATURN,
    "Rahu": swe.MEAN_NODE,  # nó médio, convenção já padronizada no projeto
}

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

# Sequência Vimshottari e durações (anos) — regente da nakshatra 0 (Ashwini) é Ketu
VIMSHOTTARI_SEQ = ["Ketu", "Shukra", "Surya", "Chandra", "Mangala", "Rahu", "Guru", "Shani", "Budha"]
VIMSHOTTARI_ANOS = {"Ketu": 7, "Shukra": 20, "Surya": 6, "Chandra": 10, "Mangala": 7,
                     "Rahu": 18, "Guru": 16, "Shani": 19, "Budha": 17}
CICLO_TOTAL = 120


def resolver_fuso(lat: float, lon: float) -> str:
    """Resolve o nome IANA do fuso a partir de lat/lon (ex.: 'America/Sao_Paulo')."""
    nome_fuso = _TF.timezone_at(lat=lat, lng=lon)
    if nome_fuso is None:
        raise ValueError(f"Não foi possível resolver o fuso horário para lat={lat}, lon={lon}")
    return nome_fuso


def julian_day_utc(dt_local_naive: datetime, lat: float, lon: float) -> tuple[float, str, float]:
    """
    Converte um horário local 'ingênuo' (sem fuso) + coordenadas em Julian Day UTC.
    Resolve o fuso automaticamente (incluindo horário de verão histórico correto
    pra a data em questão, via IANA tzdata) — não precisa mais passar offset na mão.
    Retorna (jd_utc, nome_do_fuso, offset_horas_efetivo_naquela_data).
    """
    nome_fuso = resolver_fuso(lat, lon)
    dt_local = dt_local_naive.replace(tzinfo=ZoneInfo(nome_fuso))
    if dt_local.tzname() == "LMT":
        # Antes da hora padrão, a hora legal era a hora média local DO LUGAR.
        # O tzdata usa a hora média da cidade de referência do fuso (ex.: Berlim
        # para toda a Alemanha), o que erra Ulm em ~13 min. Usamos a longitude real.
        dt_local = dt_local_naive.replace(tzinfo=timezone(timedelta(hours=lon / 15)))
        nome_fuso = f"{nome_fuso} (hora média local)"
    dt_utc = dt_local.astimezone(timezone.utc)
    offset_horas = round(dt_local.utcoffset().total_seconds() / 3600, 3)
    jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day,
                     dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600)
    return jd, nome_fuso, offset_horas


def signo_de(longitude_sideral: float) -> tuple[str, float]:
    signo_idx = int(longitude_sideral // 30)
    grau_no_signo = longitude_sideral % 30
    return SIGNOS[signo_idx], grau_no_signo


def nakshatra_de(longitude_lua: float) -> tuple[str, int, float]:
    """Retorna (nome, pada 1-4, fração já percorrida da nakshatra 0-1)."""
    tamanho_nakshatra = 360 / 27  # 13°20'
    idx = int(longitude_lua // tamanho_nakshatra)
    resto = longitude_lua % tamanho_nakshatra
    pada = int(resto // (tamanho_nakshatra / 4)) + 1
    fracao_percorrida = resto / tamanho_nakshatra
    return NAKSHATRAS[idx], pada, fracao_percorrida


def vimshottari_atual(nakshatra_nome: str, fracao_percorrida: float, data_nascimento: datetime):
    idx_nakshatra = NAKSHATRAS.index(nakshatra_nome)
    regente_inicial = VIMSHOTTARI_SEQ[idx_nakshatra % 9]
    anos_regente = VIMSHOTTARI_ANOS[regente_inicial]
    anos_restantes_primeiro = anos_regente * (1 - fracao_percorrida)

    sequencia = []
    cursor = data_nascimento
    # saldo do primeiro mahadasha
    fim = cursor + timedelta(days=anos_restantes_primeiro * 365.2425)
    sequencia.append((regente_inicial, cursor, fim))
    cursor = fim
    # demais mahadashas completos, na ordem, até fechar ~120 anos de vida útil de referência
    pos = VIMSHOTTARI_SEQ.index(regente_inicial)
    for _ in range(8):
        pos = (pos + 1) % 9
        regente = VIMSHOTTARI_SEQ[pos]
        anos = VIMSHOTTARI_ANOS[regente]
        fim = cursor + timedelta(days=anos * 365.2425)
        sequencia.append((regente, cursor, fim))
        cursor = fim
    return sequencia


def calcular_mapa(dt_local_naive: datetime, lat: float, lon: float) -> dict:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    jd, nome_fuso, offset_horas = julian_day_utc(dt_local_naive, lat, lon)
    flags = swe.FLG_SIDEREAL | swe.FLG_MOSEPH  # Moshier: sem arquivo de efeméride externo

    # Ascendente (Lagna) — pega-se o ponto Asc de qualquer sistema de casas;
    # o sistema de casas em si (whole sign) é derivado manualmente depois.
    _, ascmc = swe.houses_ex(jd, lat, lon, hsys=b"P", flags=flags)
    asc_longitude = ascmc[0]
    signo_lagna, grau_lagna = signo_de(asc_longitude)
    idx_lagna = SIGNOS.index(signo_lagna)

    posicoes = {}
    for nome, codigo in GRAHAS.items():
        (longitude, _lat, _dist, velocidade, *_resto), _ret = swe.calc_ut(jd, codigo, flags | swe.FLG_SPEED)
        signo, grau = signo_de(longitude)
        idx_signo = SIGNOS.index(signo)
        casa_whole_sign = ((idx_signo - idx_lagna) % 12) + 1
        posicoes[nome] = {
            "longitude_sideral": round(longitude, 4),
            "signo": signo,
            "grau_no_signo": round(grau, 2),
            "casa_whole_sign": casa_whole_sign,
            "retrogrado": velocidade < 0,
        }

    # Ketu é sempre oposto a Rahu (180°)
    ketu_long = (posicoes["Rahu"]["longitude_sideral"] + 180) % 360
    signo_ketu, grau_ketu = signo_de(ketu_long)
    idx_ketu = SIGNOS.index(signo_ketu)
    posicoes["Ketu"] = {
        "longitude_sideral": round(ketu_long, 4),
        "signo": signo_ketu,
        "grau_no_signo": round(grau_ketu, 2),
        "casa_whole_sign": ((idx_ketu - idx_lagna) % 12) + 1,
        "retrogrado": posicoes["Rahu"]["retrogrado"],
    }

    nakshatra_lua, pada_lua, fracao = nakshatra_de(posicoes["Chandra"]["longitude_sideral"])
    dashas = vimshottari_atual(nakshatra_lua, fracao, dt_local_naive)

    return {
        "fuso_resolvido": {"nome_iana": nome_fuso, "offset_horas_na_data": offset_horas},
        "lagna": {"signo": signo_lagna, "grau": round(grau_lagna, 2)},
        "grahas": posicoes,
        "nakshatra_lua": {"nome": nakshatra_lua, "pada": pada_lua},
        "vimshottari_dasha": [
            {"regente": r, "inicio": ini.date().isoformat(), "fim": fim.date().isoformat()}
            for r, ini, fim in dashas
        ],
    }


if __name__ == "__main__":
    # EXEMPLO — não é um mapa real, só pra validar que o cálculo roda ponta a ponta.
    # Nicolas: troque por uma data de nascimento real (sua ou de um cliente) pra conferir.
    # Repare que não passamos mais fuso horário na mão — é resolvido automaticamente
    # a partir de lat/lon + data, incluindo o horário de verão histórico correto.
    exemplo = calcular_mapa(
        dt_local_naive=datetime(1990, 9, 15, 14, 30),
        lat=-30.0346,
        lon=-51.2177,
    )
    import json
    print(json.dumps(exemplo, indent=2, ensure_ascii=False))

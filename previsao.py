"""
Padmini — motor da PREVISÃO DOS PRÓXIMOS 12 MESES (rodada 13, versão ocidental).

"O seu ano": os temas e as janelas do período a partir do mapa natal. Não é
previsão de acontecimentos: este módulo só calcula ONDE e QUANDO os planetas
lentos tocam o mapa; o texto (anti-fatalista, revisável) vem do banco, nunca de IA.

Tudo sobre o mesmo Swiss Ephemeris do mapa (`mapa_ocidental`, tropical, Moshier):

  1. TRÂNSITOS dos lentos (Júpiter, Saturno, Urano, Netuno, Plutão) em conjunção,
     sextil, quadratura, trígono e oposição com Sol, Lua, Mercúrio, Vênus, Marte,
     Júpiter, Saturno, Ascendente e Meio do Céu. Orbe ORBE_TRANSITO (1°) para entrar
     e sair. Com a retrogradação o mesmo trânsito entra e sai da órbita até três
     vezes: as passagens viram UM período (da primeira entrada à última saída),
     com todas as datas exatas listadas.
  2. INGRESSOS: os lentos mudando de casa natal dentro do período.
  3. ECLIPSES do período: tipo, signo e grau, casa natal e os pontos natais que
     tocam (conjunção até ORBE_ECLIPSE, 3°).
  4. REVOLUÇÃO SOLAR do aniversário que cai no período, calculada para o LOCAL DE
     NASCIMENTO: o Ascendente dela e a casa (da própria Revolução) onde cai o Sol.
  5. PESOS de cada trânsito (planeta, ponto, aspecto, duração): os 3 maiores são
     "os temas do seu ano". Os pesos ficam aqui e em docs/previsao.md.

As datas saem no fuso de Brasília (FUSO_DATAS): o produto é brasileiro e um
trânsito lento não muda de data por causa de 3 horas, mas o eclipse e a Revolução
Solar mudam perto da meia-noite, então o fuso é um só e está documentado.

Sem hora de nascimento: sem Ascendente, Meio do Céu e casas, e sem a Lua (calculada
ao meio-dia, pode estar ~7° fora do lugar); os trânsitos aos outros planetas, os
eclipses (sem casa) e a data da Revolução Solar continuam.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import swisseph as swe

import mapa_ocidental as mo

# --------------------------------------------------------------------------
# Parâmetros — um lugar só (e docs/previsao.md)
# --------------------------------------------------------------------------
ORBE_TRANSITO = 1.0      # graus, para entrar e sair da órbita
ORBE_ECLIPSE = 3.0       # graus, eclipse "tocando" um ponto natal (conjunção)
MESMA_PASSAGEM = 15.0    # graus: entre duas janelas, se o planeta não se afastou
                         # mais do que isso do ponto, é a mesma passagem (retrogradação)
FUSO_DATAS = ZoneInfo("America/Sao_Paulo")
MESES = 12
MARGEM_DIAS = 3 * 365    # busca antes e depois do período (Plutão leva ~2 anos numa passagem)

LENTOS = ("jupiter", "saturno", "urano", "netuno", "plutao")
PONTOS_NATAIS = ("sol", "lua", "mercurio", "venus", "marte", "jupiter", "saturno",
                 "ascendente", "meio_do_ceu")
GRUPO_DO_ASPECTO = {"conjuncao": "conjuncao", "sextil": "harmonico", "trigono": "harmonico",
                    "quadratura": "tenso", "oposicao": "tenso"}

# Pesos do resumo ("os temas do seu ano"). Lento pesa mais que rápido; luminares e
# ângulos mais que os outros pontos; conjunção e oposição mais que quadratura, e
# quadratura mais que trígono e sextil; quanto mais tempo dentro do período, mais.
PESO_PLANETA = {"plutao": 5.0, "netuno": 4.5, "urano": 4.0, "saturno": 3.5, "jupiter": 2.5}
PESO_PONTO = {"sol": 1.5, "lua": 1.5, "ascendente": 1.5, "meio_do_ceu": 1.5}  # demais: 1.0
PESO_ASPECTO = {"conjuncao": 1.5, "oposicao": 1.5, "quadratura": 1.2, "trigono": 1.0, "sextil": 1.0}
FORA_DO_PERIODO = 0.75   # trânsito sem nenhuma data exata dentro do período (só começa
                         # ou só termina nele) pesa menos que um que culmina no ano
N_TEMAS = 3

_F = swe.FLG_MOSEPH | swe.FLG_SPEED


# --------------------------------------------------------------------------
# Datas
# --------------------------------------------------------------------------
def jd_de(d: date) -> float:
    """Meia-noite de Brasília do dia d, em JD (UT)."""
    utc = datetime(d.year, d.month, d.day, tzinfo=FUSO_DATAS).astimezone(timezone.utc)
    return swe.julday(utc.year, utc.month, utc.day, utc.hour + utc.minute / 60)


def data_de(jd: float) -> date:
    """Dia (no fuso de Brasília) de um instante em JD (UT)."""
    y, m, d, h = swe.revjul(jd)
    utc = datetime(y, m, d, tzinfo=timezone.utc) + timedelta(hours=h)
    return utc.astimezone(FUSO_DATAS).date()


def periodo(compra: date) -> tuple[date, date]:
    """Do dia 1º do mês da compra até o último dia do 12º mês (inclusive)."""
    ini = date(compra.year, compra.month, 1)
    m = ini.month - 1 + MESES
    fim_exclusivo = date(ini.year + m // 12, m % 12 + 1, 1)
    return ini, fim_exclusivo - timedelta(days=1)


def _lon(jd: float, planeta: str) -> float:
    return swe.calc_ut(jd, mo.PLANETAS[planeta], _F)[0][0]


def _desvio(lon: float, alvo: float) -> float:
    """lon − alvo em (−180, 180]."""
    return (lon - alvo + 180) % 360 - 180


def _bissecao(f, a: float, b: float, iter_: int = 24) -> float:
    """Raiz de f em [a, b] (f(a) e f(b) com sinais opostos)."""
    fa = f(a)
    for _ in range(iter_):
        m = (a + b) / 2
        fm = f(m)
        if (fa <= 0) == (fm <= 0):
            a, fa = m, fm
        else:
            b = m
    return (a + b) / 2


# --------------------------------------------------------------------------
# 1. Trânsitos
# --------------------------------------------------------------------------
def _alvos(natal: float, aspecto: str) -> list[float]:
    ang = mo.ASPECTOS[aspecto]
    if ang in (0, 180):
        return [(natal + ang) % 360]
    return [(natal + ang) % 360, (natal - ang) % 360]


def _serie(planeta: str, jd0: float, dias: int) -> np.ndarray:
    return np.array([_lon(jd0 + i, planeta) for i in range(dias + 1)])


def _passagens(planeta: str, alvo: float, jd0: float, serie: np.ndarray) -> list[dict]:
    """As passagens do planeta pelo alvo: janelas em órbita (|desvio| ≤ orbe) agrupadas
    quando o planeta não se afastou mais que MESMA_PASSAGEM entre elas."""
    d = (serie - alvo + 180) % 360 - 180
    dentro = np.abs(d) <= ORBE_TRANSITO
    janelas, i, n = [], 0, len(d)
    while i < n:
        if dentro[i]:
            j = i
            while j + 1 < n and dentro[j + 1]:
                j += 1
            janelas.append([i, j])
            i = j + 1
        else:
            i += 1
    grupos: list[list[int]] = []
    for ini, fim in janelas:
        if grupos and np.max(np.abs(d[grupos[-1][1]:ini + 1])) <= MESMA_PASSAGEM:
            grupos[-1][1] = fim
        else:
            grupos.append([ini, fim])

    def desvio(jd):
        return _desvio(_lon(jd, planeta), alvo)

    def borda(jd):
        return abs(desvio(jd)) - ORBE_TRANSITO

    out = []
    for ini, fim in grupos:
        # entrada e saída exatas (a janela começa/termina entre dois dias de amostra)
        entra = jd0 + ini if ini == 0 else _bissecao(borda, jd0 + ini - 1, jd0 + ini)
        sai = jd0 + fim if fim == n - 1 else _bissecao(borda, jd0 + fim, jd0 + fim + 1)
        exatas = []
        for k in range(max(ini - 1, 0), min(fim + 1, n - 1)):
            if d[k] == 0 or (d[k] < 0) != (d[k + 1] < 0) and abs(d[k] - d[k + 1]) < 90:
                exatas.append(_bissecao(desvio, jd0 + k, jd0 + k + 1))
        k_min = ini + int(np.argmin(np.abs(d[ini:fim + 1])))
        out.append({"entra": entra, "sai": sai, "exatas": exatas, "mais_perto": jd0 + k_min,
                    "cortada": ini == 0 or fim == n - 1})
    return out


def _ponto_confiavel(natal: dict, ponto: str) -> bool:
    """Ascendente e Meio do Céu só existem com hora; a Lua sem hora (calculada ao
    meio-dia) pode estar ~7° fora do lugar, e 1° de orbe sobre ela seria chute."""
    if ponto not in natal["pontos"]:
        return False
    return natal["tem_hora"] or ponto != "lua"


def transitos(natal: dict, ini: date, fim: date) -> list[dict]:
    """Os trânsitos dos lentos que tocam o período [ini, fim], já com o peso."""
    pontos = natal["pontos"]
    jd0 = jd_de(ini) - MARGEM_DIAS
    dias = (fim - ini).days + 1 + 2 * MARGEM_DIAS
    jd_ini, jd_fim = jd_de(ini), jd_de(fim + timedelta(days=1))
    lista = []
    for planeta in LENTOS:
        serie = _serie(planeta, jd0, dias)
        for ponto in PONTOS_NATAIS:
            if not _ponto_confiavel(natal, ponto):
                continue
            for aspecto in mo.ASPECTOS:
                for alvo in _alvos(pontos[ponto]["longitude"], aspecto):
                    for p in _passagens(planeta, alvo, jd0, serie):
                        if p["sai"] < jd_ini or p["entra"] >= jd_fim:
                            continue
                        dentro = min(p["sai"], jd_fim) - max(p["entra"], jd_ini)
                        t = {"planeta": planeta, "ponto": ponto, "aspecto": aspecto,
                             "grupo": GRUPO_DO_ASPECTO[aspecto],
                             "entra": data_de(p["entra"]), "sai": data_de(p["sai"]),
                             "exatas": [data_de(x) for x in p["exatas"]],
                             "mais_perto": data_de(p["mais_perto"]),
                             "passagens": max(len(p["exatas"]), 1),
                             "dias_no_periodo": max(int(round(dentro)), 1),
                             "exata_no_periodo": any(jd_ini <= x < jd_fim for x in p["exatas"])}
                        t["peso"] = peso(t)
                        lista.append(t)
    lista.sort(key=lambda t: (t["entra"], -t["peso"]))
    return lista


def peso(t: dict) -> float:
    duracao = 1 + min(t["dias_no_periodo"], 365) / 365
    culmina = 1.0 if t["exata_no_periodo"] else FORA_DO_PERIODO
    return round(PESO_PLANETA[t["planeta"]] * PESO_PONTO.get(t["ponto"], 1.0)
                 * PESO_ASPECTO[t["aspecto"]] * duracao * culmina, 3)


def temas(lista: list[dict], n: int = N_TEMAS) -> list[dict]:
    """Os n trânsitos de maior peso (um por par planeta × ponto: Saturno em quadratura
    e depois em oposição ao Sol é o mesmo assunto no ano)."""
    vistos, out = set(), []
    for t in sorted(lista, key=lambda t: (-t["peso"], t["entra"])):
        par = (t["planeta"], t["ponto"])
        if par in vistos:
            continue
        vistos.add(par)
        out.append(t)
        if len(out) == n:
            break
    return out


# --------------------------------------------------------------------------
# 2. Ingressos nas casas natais
# --------------------------------------------------------------------------
def ingressos(natal: dict, ini: date, fim: date) -> list[dict]:
    """Os lentos entrando numa casa natal dentro do período. Com a retrogradação,
    o planeta pode entrar, voltar e entrar de novo: as datas ficam juntas."""
    if not natal["tem_hora"]:
        return []
    cusp = natal["casas"]["cuspides"]
    jd0, jd1 = jd_de(ini), jd_de(fim + timedelta(days=1))
    out = []
    for planeta in LENTOS:
        def casa(jd):
            return mo.casa_de(_lon(jd, planeta), cusp)
        por_casa: dict[int, list[date]] = {}
        anterior = casa(jd0)
        for k in range(1, int(jd1 - jd0) + 1):
            atual = casa(jd0 + k)
            if atual != anterior:
                a, b = jd0 + k - 1, jd0 + k
                for _ in range(20):
                    m = (a + b) / 2
                    if casa(m) == anterior:
                        a = m
                    else:
                        b = m
                if (atual - anterior) % 12 == 1:  # entrando (direto) na casa seguinte
                    por_casa.setdefault(atual, []).append(data_de(b))
                anterior = atual
        for c, datas in por_casa.items():
            out.append({"planeta": planeta, "casa": c, "datas": datas})
    out.sort(key=lambda x: x["datas"][0])
    return out


# --------------------------------------------------------------------------
# 3. Eclipses
# --------------------------------------------------------------------------
SUBTIPO = ((swe.ECL_TOTAL, "total"), (swe.ECL_ANNULAR_TOTAL, "hibrido"),
           (swe.ECL_ANNULAR, "anular"), (swe.ECL_PARTIAL, "parcial"),
           (swe.ECL_PENUMBRAL, "penumbral"))


def _subtipo(flags: int) -> str:
    for bit, nome in SUBTIPO:
        if flags & bit:
            return nome
    return "parcial"


def eclipses(natal: dict, ini: date, fim: date) -> list[dict]:
    jd_ini, jd_fim = jd_de(ini), jd_de(fim + timedelta(days=1))
    pontos = natal["pontos"]
    out = []
    for tipo, buscar, corpo in (("solar", lambda j: swe.sol_eclipse_when_glob(j, swe.FLG_MOSEPH, 0, False),
                                 swe.SUN),
                                ("lunar", lambda j: swe.lun_eclipse_when(j, swe.FLG_MOSEPH, 0, False),
                                 swe.MOON)):
        jd = jd_ini
        while True:
            flags, tret = buscar(jd)
            maximo = tret[0]
            if maximo >= jd_fim:
                break
            lon = swe.calc_ut(maximo, corpo, _F)[0][0]
            signo, grau = mo.signo_de(lon)
            e = {"tipo": tipo, "subtipo": _subtipo(flags), "data": data_de(maximo),
                 "longitude": round(lon, 4), "signo": signo, "grau_texto": mo.grau_minuto(grau),
                 "casa": mo.casa_de(lon, natal["casas"]["cuspides"]) if natal["tem_hora"] else None,
                 "toca": []}
            for p in PONTOS_NATAIS:
                if _ponto_confiavel(natal, p):
                    orbe = mo.distancia(lon, pontos[p]["longitude"])
                    if orbe <= ORBE_ECLIPSE:
                        e["toca"].append({"ponto": p, "orbe": round(orbe, 2)})
            out.append(e)
            jd = maximo + 1
    out.sort(key=lambda e: e["data"])
    return out


# --------------------------------------------------------------------------
# 4. Revolução Solar
# --------------------------------------------------------------------------
def revolucao_solar(natal: dict, nascimento: date, lat: float, lon: float,
                    ini: date, fim: date) -> dict | None:
    """O retorno do Sol ao grau natal no aniversário que cai no período, com o
    Ascendente e as casas calculados para o local de nascimento."""
    for ano in (ini.year, ini.year + 1):
        try:
            aniv = nascimento.replace(year=ano)
        except ValueError:  # 29 de fevereiro
            aniv = date(ano, 3, 1)
        if ini <= aniv <= fim:
            break
    else:
        return None
    sol_natal = natal["pontos"]["sol"]["longitude"]
    jd = swe.solcross_ut(sol_natal, jd_de(aniv) - 3, swe.FLG_MOSEPH)
    rs = {"data": data_de(jd), "aniversario": aniv, "jd": jd}
    if natal["tem_hora"]:
        casas = mo._casas(jd, lat, lon)  # Placidus; Porfírio perto dos polos, como no natal
        rs["ascendente"] = mo.signo_de(casas["ascendente"])[0]
        rs["casa_do_sol"] = mo.casa_de(sol_natal, casas["cuspides"])
    return rs


# --------------------------------------------------------------------------
# Tudo junto
# --------------------------------------------------------------------------
def calcular_previsao(natal: dict, nascimento: date, lat: float, lon: float, compra: date) -> dict:
    ini, fim = periodo(compra)
    lista = transitos(natal, ini, fim)
    return {
        "inicio": ini, "fim": fim, "tem_hora": natal["tem_hora"],
        "transitos": lista,
        "temas": temas(lista),
        "ingressos": ingressos(natal, ini, fim),
        "eclipses": eclipses(natal, ini, fim),
        "revolucao": revolucao_solar(natal, nascimento, lat, lon, ini, fim),
    }

"""
Padmini — detecção determinística de fatos notáveis a partir do mapa calculado.

Recebe a saída de compute_chart.calcular_mapa() e devolve uma lista de fatos
estruturados (não texto). Nenhuma linha aqui usa LLM — é só regra clássica
aplicada a números. É essa lista que depois vira consulta na base de
significações (significacoes-schema-e-regras.md) pra gerar a prosa final.

Simplificações explícitas desta v1 (documentadas, não escondidas):
- Raj Yoga aqui é só por CONJUNÇÃO (mesmo signo). Aspecto mútuo e permuta de
  signos (a outra metade da definição clássica) ficam pra v2.
- Neecha Bhanga usa só a condição principal (dispositor do signo de
  debilitação em kendra a partir da Lua/Lagna), não todas as variantes dos textos.
- Rahu/Ketu não entram nas regras de dignidade/yoga (sem consenso entre escolas).
"""

from compute_chart import SIGNOS, calcular_mapa

DIGNIDADES = {
    "Surya":   {"exaltacao": ("Mesha", 10),    "debilitacao": ("Tula", 10),    "proprio": ["Simha"]},
    "Chandra": {"exaltacao": ("Vrishabha", 3),  "debilitacao": ("Vrishchika", 3), "proprio": ["Karka"]},
    "Mangala": {"exaltacao": ("Makara", 28),    "debilitacao": ("Karka", 28),   "proprio": ["Mesha", "Vrishchika"]},
    "Budha":   {"exaltacao": ("Kanya", 15),     "debilitacao": ("Meena", 15),   "proprio": ["Mithuna", "Kanya"]},
    "Guru":    {"exaltacao": ("Karka", 5),      "debilitacao": ("Makara", 5),   "proprio": ["Dhanu", "Meena"]},
    "Shukra":  {"exaltacao": ("Meena", 27),     "debilitacao": ("Kanya", 27),   "proprio": ["Vrishabha", "Tula"]},
    "Shani":   {"exaltacao": ("Tula", 20),      "debilitacao": ("Mesha", 20),   "proprio": ["Makara", "Kumbha"]},
}

SIGN_LORDS = {
    "Mesha": "Mangala", "Vrishabha": "Shukra", "Mithuna": "Budha", "Karka": "Chandra",
    "Simha": "Surya", "Kanya": "Budha", "Tula": "Shukra", "Vrishchika": "Mangala",
    "Dhanu": "Guru", "Makara": "Shani", "Kumbha": "Shani", "Meena": "Guru",
}

# distância máxima do Sol pra combustão (graus); cazimi é sempre ~1° independente do planeta
COMBUSTAO_LIMIAR = {
    "Chandra": 12, "Mangala": 17, "Budha": 14, "Guru": 11, "Shukra": 10, "Shani": 15,
}
COMBUSTAO_LIMIAR_RETRO = {"Budha": 12, "Shukra": 8}
CAZIMI_LIMIAR = 1.0

KENDRAS = {1, 4, 7, 10}
TRIKONAS = {1, 5, 9}


def _casa_a_partir_de(signo_referencia: str, signo_alvo: str) -> int:
    idx_ref = SIGNOS.index(signo_referencia)
    idx_alvo = SIGNOS.index(signo_alvo)
    return ((idx_alvo - idx_ref) % 12) + 1


def _distancia_angular(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def detectar_dignidades(grahas: dict) -> list[dict]:
    fatos = []
    for nome, regra in DIGNIDADES.items():
        signo_atual = grahas[nome]["signo"]
        grau_atual = grahas[nome]["grau_no_signo"]
        signo_exalt, grau_exalt = regra["exaltacao"]
        signo_debil, grau_debil = regra["debilitacao"]
        if signo_atual == signo_exalt:
            profundidade = "exaltação profunda" if abs(grau_atual - grau_exalt) <= 1 else "exaltado"
            fatos.append({"tipo": "dignidade", "planeta": nome, "estado": "exaltado", "detalhe": profundidade})
        elif signo_atual == signo_debil:
            fatos.append({"tipo": "dignidade", "planeta": nome, "estado": "debilitado"})
        elif signo_atual in regra["proprio"]:
            fatos.append({"tipo": "dignidade", "planeta": nome, "estado": "proprio"})
    return fatos


def detectar_combustao(grahas: dict) -> list[dict]:
    fatos = []
    long_sol = grahas["Surya"]["longitude_sideral"]
    for nome, limiar in COMBUSTAO_LIMIAR.items():
        if grahas[nome].get("retrogrado"):
            limiar = COMBUSTAO_LIMIAR_RETRO.get(nome, limiar)
        dist = _distancia_angular(grahas[nome]["longitude_sideral"], long_sol)
        if dist <= CAZIMI_LIMIAR:
            fatos.append({"tipo": "cazimi", "planeta": nome, "distancia_graus": round(dist, 3)})
        elif dist <= limiar:
            fatos.append({"tipo": "combustao", "planeta": nome, "distancia_graus": round(dist, 3)})
    return fatos


def detectar_mangal_dosha(grahas: dict, lagna_signo: str) -> dict | None:
    signo_marte = grahas["Mangala"]["signo"]
    referencias = {"lagna": lagna_signo, "lua": grahas["Chandra"]["signo"], "venus": grahas["Shukra"]["signo"]}
    casas_afetadas = {1, 2, 4, 7, 8, 12}
    afetados = {}
    for ref_nome, ref_signo in referencias.items():
        casa = _casa_a_partir_de(ref_signo, signo_marte)
        if casa in casas_afetadas:
            afetados[ref_nome] = casa
    # Contando qualquer uma das três referências, ~90% dos mapas teriam Mangal Dosha
    # (medido em 500 mapas aleatórios) — vira alarme genérico. Só sinalizamos quando
    # vale a partir do Ascendente (~metade dos mapas); Lua e Vênus entram como reforço.
    if "lagna" not in afetados:
        return None
    return {"tipo": "mangal_dosha", "referencias_afetadas": afetados}


def detectar_gaja_kesari(grahas: dict) -> dict | None:
    casa = _casa_a_partir_de(grahas["Chandra"]["signo"], grahas["Guru"]["signo"])
    if casa in KENDRAS:
        return {"tipo": "gaja_kesari", "casa_de_guru_a_partir_da_lua": casa}
    return None


def detectar_pancha_mahapurusha(grahas: dict, lagna_signo: str) -> list[dict]:
    mapa = {"Mangala": "ruchaka", "Budha": "bhadra", "Guru": "hamsa", "Shukra": "malavya", "Shani": "sasa"}
    fatos = []
    for planeta, nome_yoga in mapa.items():
        regra = DIGNIDADES[planeta]
        signo_atual = grahas[planeta]["signo"]
        bem_dignificado = signo_atual == regra["exaltacao"][0] or signo_atual in regra["proprio"]
        casa = _casa_a_partir_de(lagna_signo, signo_atual)
        if bem_dignificado and casa in KENDRAS:
            fatos.append({"tipo": "pancha_mahapurusha", "yoga": nome_yoga, "planeta": planeta, "casa": casa})
    return fatos


def detectar_yogakaraka_e_raj_yoga(grahas: dict, lagna_signo: str) -> list[dict]:
    idx_lagna = SIGNOS.index(lagna_signo)
    regente_por_casa = {}
    for casa in range(1, 13):
        signo_da_casa = SIGNOS[(idx_lagna + casa - 1) % 12]
        regente_por_casa[casa] = SIGN_LORDS[signo_da_casa]

    fatos = []
    regentes_kendra = {c: regente_por_casa[c] for c in KENDRAS}
    regentes_trikona = {c: regente_por_casa[c] for c in TRIKONAS}

    # Yogakaraka: mesmo planeta rege um kendra (4, 7, 10) e um trikona (5, 9).
    # A casa 1 fica de fora: ela é kendra e trikona ao mesmo tempo, e contar o regente
    # do Ascendente por isso inflaria o resultado. Só 6 ascendentes têm yogakaraka.
    for casa_k, regente_k in regentes_kendra.items():
        for casa_t, regente_t in regentes_trikona.items():
            if regente_k == regente_t and casa_k != 1 and casa_t != 1:
                fatos.append({"tipo": "yogakaraka", "planeta": regente_k, "rege_kendra": casa_k, "rege_trikona": casa_t})

    # Raj Yoga por conjunção (simplificação v1 — sem aspecto/permuta)
    vistos = set()
    for casa_k, regente_k in regentes_kendra.items():
        for casa_t, regente_t in regentes_trikona.items():
            if regente_k == regente_t:
                continue
            par = tuple(sorted([regente_k, regente_t]))
            if par in vistos:
                continue
            if grahas[regente_k]["signo"] == grahas[regente_t]["signo"]:
                fatos.append({"tipo": "raj_yoga", "regente_kendra": regente_k, "regente_trikona": regente_t,
                              "signo_conjuncao": grahas[regente_k]["signo"]})
                vistos.add(par)

    return fatos


def detectar_neecha_bhanga(grahas: dict, lagna_signo: str) -> list[dict]:
    fatos = []
    for planeta, regra in DIGNIDADES.items():
        if grahas[planeta]["signo"] != regra["debilitacao"][0]:
            continue
        dispositor = SIGN_LORDS[regra["debilitacao"][0]]
        casa_do_dispositor_lagna = _casa_a_partir_de(lagna_signo, grahas[dispositor]["signo"])
        casa_do_dispositor_lua = _casa_a_partir_de(grahas["Chandra"]["signo"], grahas[dispositor]["signo"])
        if casa_do_dispositor_lagna in KENDRAS or casa_do_dispositor_lua in KENDRAS:
            fatos.append({"tipo": "neecha_bhanga", "planeta": planeta, "dispositor": dispositor})
    return fatos


def detectar_todos_os_fatos(mapa: dict) -> list[dict]:
    grahas = mapa["grahas"]
    lagna_signo = mapa["lagna"]["signo"]
    fatos = []
    fatos += detectar_dignidades(grahas)
    fatos += detectar_combustao(grahas)
    md = detectar_mangal_dosha(grahas, lagna_signo)
    if md:
        fatos.append(md)
    gk = detectar_gaja_kesari(grahas)
    if gk:
        fatos.append(gk)
    fatos += detectar_pancha_mahapurusha(grahas, lagna_signo)
    fatos += detectar_yogakaraka_e_raj_yoga(grahas, lagna_signo)
    fatos += detectar_neecha_bhanga(grahas, lagna_signo)
    return fatos


if __name__ == "__main__":
    import json
    from datetime import datetime

    mapa_exemplo = calcular_mapa(dt_local_naive=datetime(1990, 9, 15, 14, 30), lat=-30.0346, lon=-51.2177)
    fatos = detectar_todos_os_fatos(mapa_exemplo)
    print(json.dumps(fatos, indent=2, ensure_ascii=False))

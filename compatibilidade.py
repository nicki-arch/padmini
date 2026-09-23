"""
Padmini — motor de compatibilidade de casal (Ashtakoot Guna Milan).

Recebe dois mapas já calculados (saída de compute_chart.calcular_mapa) e
devolve o casamento védico dos 36 pontos: 8 kootas, os doshas clássicos com
suas regras de cancelamento, e a leitura de Mangal do casal. Nenhuma linha
aqui usa LLM — é regra clássica aplicada a rashi e nakshatra da Lua, no mesmo
padrão do detectar_fatos.py (o código decide os pontos; a IA só reescreve o
texto a partir da base de significações).

Do mapa de cada pessoa o motor usa apenas:
  - rashi (signo) da Lua        -> mapa["grahas"]["Chandra"]["signo"]
  - nakshatra da Lua + pada     -> mapa["nakshatra_lua"]["nome"], ["pada"]
Para Mangal, usa o mapa completo (Ascendente, Lua e Vênus).

CONVENÇÃO DIRECIONAL (importante):
  O Guna Milan clássico é contado da NOIVA para o NOIVO — Varna, Vashya, Gana e
  Bhakoot têm direção. Como o produto não pressupõe gênero, a "pessoa A" ocupa
  a posição da noiva e a "pessoa B" a do noivo (mesma ordem do Prokerala:
  girl = A, boy = B). Trocar a ordem pode mudar a nota. Documentado e travado.

=============================================================================
VALIDAÇÃO (22/set/2026) — fonte de referência: Prokerala (Guna Milan).
  132 casais comparados koota a koota (todos os pares de Yoni, as 25
  combinações de Vashya, os 9 pares de Gana e os 24 pares 6/8 de Bhakoot).
  A Lua (rashi e nakshatra) bateu em 100% dos casos. As tabelas abaixo foram
  ajustadas para reproduzir o Prokerala; o teste testes/test_compatibilidade.py
  trava os 5 casais de referência koota a koota.
=============================================================================
"""

from compute_chart import SIGNOS, NAKSHATRAS
from detectar_fatos import SIGN_LORDS, detectar_mangal_dosha

# ---------------------------------------------------------------------------
# Amizade planetária natural (permanente). Só os 7 clássicos — regentes de
# rashi nunca são Rahu/Ketu. Mesma tradição das dignidades do detectar_fatos.
# ---------------------------------------------------------------------------
AMIZADE_PLANETARIA = {
    "Surya":   {"amigo": {"Chandra", "Mangala", "Guru"}, "inimigo": {"Shukra", "Shani"},          "neutro": {"Budha"}},
    "Chandra": {"amigo": {"Surya", "Budha"},             "inimigo": set(),                         "neutro": {"Mangala", "Guru", "Shukra", "Shani"}},
    "Mangala": {"amigo": {"Surya", "Chandra", "Guru"},   "inimigo": {"Budha"},                     "neutro": {"Shukra", "Shani"}},
    "Budha":   {"amigo": {"Surya", "Shukra"},            "inimigo": {"Chandra"},                   "neutro": {"Mangala", "Guru", "Shani"}},
    "Guru":    {"amigo": {"Surya", "Chandra", "Mangala"},"inimigo": {"Budha", "Shukra"},           "neutro": {"Shani"}},
    "Shukra":  {"amigo": {"Budha", "Shani"},             "inimigo": {"Surya", "Chandra"},          "neutro": {"Mangala", "Guru"}},
    "Shani":   {"amigo": {"Budha", "Shukra"},            "inimigo": {"Surya", "Chandra", "Mangala"},"neutro": {"Guru"}},
}


def _relacao(de: str, para: str) -> str:
    if de == para:
        return "amigo"
    tabela = AMIZADE_PLANETARIA[de]
    if para in tabela["amigo"]:
        return "amigo"
    if para in tabela["inimigo"]:
        return "inimigo"
    return "neutro"


# índice de rashi (0-11) e nakshatra (0-26)
def _idx_rashi(signo: str) -> int:
    return SIGNOS.index(signo)


def _idx_nak(nome: str) -> int:
    return NAKSHATRAS.index(nome)


# ===========================================================================
# 1. VARNA (1 ponto) — por rashi.  CONFIRMADA
# Brâmane(4) > Kshatriya(3) > Vaishya(2) > Shudra(1).
# 1 ponto se o varna do noivo (B) é igual ou maior que o da noiva (A). [Prokerala]
# ===========================================================================
VARNA_POR_RASHI = {
    "Karka": 4, "Vrishchika": 4, "Meena": 4,      # água = Brâmane
    "Mesha": 3, "Simha": 3, "Dhanu": 3,           # fogo = Kshatriya
    "Vrishabha": 2, "Kanya": 2, "Makara": 2,      # terra = Vaishya
    "Mithuna": 1, "Tula": 1, "Kumbha": 1,         # ar = Shudra
}


def koota_varna(rashi_a: str, rashi_b: str) -> float:
    return 1.0 if VARNA_POR_RASHI[rashi_b] >= VARNA_POR_RASHI[rashi_a] else 0.0


# ===========================================================================
# 2. VASHYA (2 pontos) — por rashi, com meio-signo em Dhanu e Makara.  [Prokerala]
# Classes: chatushpada (quadrúpede), nara (humano), jalachara (aquático),
#          vanachara (selvagem), keeta (inseto).
# ===========================================================================
VASHYA_POR_RASHI = {
    "Mesha": "chatushpada", "Vrishabha": "chatushpada",
    "Mithuna": "nara", "Karka": "jalachara", "Simha": "vanachara",
    "Kanya": "nara", "Tula": "nara", "Vrishchika": "keeta",
    "Dhanu": "nara",          # 1ª metade (0–15°) humana; 2ª metade quadrúpede
    "Makara": "chatushpada",  # 1ª metade quadrúpede; 2ª metade aquática
    "Kumbha": "nara", "Meena": "jalachara",
}
_VASHYA_2A_METADE = {"Dhanu": "chatushpada", "Makara": "jalachara"}


def classe_vashya(rashi: str, grau: float | None = None) -> str:
    if grau is not None and grau >= 15 and rashi in _VASHYA_2A_METADE:
        return _VASHYA_2A_METADE[rashi]
    return VASHYA_POR_RASHI[rashi]


# Matriz (linha = noiva/A, coluna = noivo/B), idêntica ao Prokerala nas 25 combinações.
_VASHYA_PTS = {
    ("chatushpada", "chatushpada"): 2, ("chatushpada", "nara"): 1, ("chatushpada", "jalachara"): 1,
    ("chatushpada", "vanachara"): 0, ("chatushpada", "keeta"): 1,
    ("nara", "chatushpada"): 1, ("nara", "nara"): 2, ("nara", "jalachara"): 0.5,
    ("nara", "vanachara"): 0, ("nara", "keeta"): 1,
    ("jalachara", "chatushpada"): 1, ("jalachara", "nara"): 0.5, ("jalachara", "jalachara"): 2,
    ("jalachara", "vanachara"): 1, ("jalachara", "keeta"): 1,
    ("vanachara", "chatushpada"): 0, ("vanachara", "nara"): 0, ("vanachara", "jalachara"): 1,
    ("vanachara", "vanachara"): 2, ("vanachara", "keeta"): 0,
    ("keeta", "chatushpada"): 1, ("keeta", "nara"): 0, ("keeta", "jalachara"): 1,
    ("keeta", "vanachara"): 0, ("keeta", "keeta"): 2,
}


def koota_vashya(rashi_a: str, rashi_b: str, grau_a: float | None = None,
                 grau_b: float | None = None) -> float:
    return float(_VASHYA_PTS[(classe_vashya(rashi_a, grau_a), classe_vashya(rashi_b, grau_b))])


# ===========================================================================
# 3. TARA / DINA (3 pontos) — por nakshatra.  CONFIRMADA
# Conta de A->B e de B->A (inclusivo), resto por 9. Restos 3,5,7 = ruins
# (Vipat, Pratyak, Vadha). Ambos bons -> 3; um bom -> 1.5; nenhum -> 0.
# ===========================================================================
def _tara_favoravel(de_idx: int, para_idx: int) -> bool:
    contagem = ((para_idx - de_idx) % 27) + 1  # inclusivo
    resto = contagem % 9
    return resto not in (3, 5, 7)  # resto 0 (=9) é favorável


def koota_tara(nak_a: str, nak_b: str) -> float:
    a, b = _idx_nak(nak_a), _idx_nak(nak_b)
    bons = int(_tara_favoravel(a, b)) + int(_tara_favoravel(b, a))
    return {2: 3.0, 1: 1.5, 0: 0.0}[bons]


# ===========================================================================
# 4. YONI (4 pontos) — por nakshatra.  animal CONFIRMADO; meio PRELIMINAR
# ===========================================================================
YONI_POR_NAKSHATRA = {
    "Ashwini": "cavalo", "Bharani": "elefante", "Krittika": "ovelha",
    "Rohini": "cobra", "Mrigashira": "cobra", "Ardra": "cao",
    "Punarvasu": "gato", "Pushya": "ovelha", "Ashlesha": "gato",
    "Magha": "rato", "Purva Phalguni": "rato", "Uttara Phalguni": "vaca",
    "Hasta": "bufalo", "Chitra": "tigre", "Swati": "bufalo",
    "Vishakha": "tigre", "Anuradha": "veado", "Jyeshtha": "veado",
    "Mula": "cao", "Purva Ashadha": "macaco", "Uttara Ashadha": "mangusto",
    "Shravana": "macaco", "Dhanishta": "leao", "Shatabhisha": "cavalo",
    "Purva Bhadrapada": "leao", "Uttara Bhadrapada": "vaca", "Revati": "elefante",
}

# Matriz completa (simétrica), idêntica ao Prokerala nos 91 pares de animais.
# 4 = mesmo animal · 0 = inimigos mortais · 1–3 = graus intermediários.
_ANIMAIS = ["cavalo", "elefante", "ovelha", "cobra", "cao", "gato", "rato",
            "vaca", "bufalo", "tigre", "veado", "macaco", "mangusto", "leao"]
_YONI_MATRIZ = [
    # cav ele ove cob cao gat rat vac buf tig vea mac man leo
    [4, 2, 2, 3, 2, 2, 2, 1, 0, 1, 3, 3, 2, 1],  # cavalo
    [2, 4, 3, 3, 2, 2, 2, 2, 3, 1, 2, 3, 2, 0],  # elefante
    [2, 3, 4, 2, 1, 2, 1, 3, 3, 1, 2, 0, 3, 1],  # ovelha
    [3, 3, 2, 4, 2, 1, 1, 1, 1, 2, 2, 2, 0, 2],  # cobra
    [2, 2, 1, 2, 4, 2, 1, 2, 2, 1, 0, 2, 1, 1],  # cao
    [2, 2, 2, 1, 2, 4, 0, 2, 2, 1, 3, 3, 2, 1],  # gato
    [2, 2, 1, 1, 1, 0, 4, 2, 2, 2, 2, 2, 1, 2],  # rato
    [1, 2, 3, 1, 2, 2, 2, 4, 3, 1, 3, 2, 2, 1],  # vaca
    [0, 3, 3, 1, 2, 2, 2, 3, 4, 1, 2, 2, 2, 1],  # bufalo
    [1, 1, 1, 2, 1, 1, 2, 1, 1, 4, 1, 1, 2, 1],  # tigre
    [3, 2, 2, 2, 0, 3, 2, 3, 2, 1, 4, 2, 2, 1],  # veado
    [3, 3, 0, 2, 2, 3, 2, 2, 2, 1, 2, 4, 3, 2],  # macaco
    [2, 2, 3, 0, 1, 2, 1, 2, 2, 2, 2, 3, 4, 2],  # mangusto
    [1, 0, 1, 2, 1, 1, 2, 1, 1, 1, 1, 2, 2, 4],  # leao
]


def koota_yoni(nak_a: str, nak_b: str) -> float:
    ya, yb = YONI_POR_NAKSHATRA[nak_a], YONI_POR_NAKSHATRA[nak_b]
    return float(_YONI_MATRIZ[_ANIMAIS.index(ya)][_ANIMAIS.index(yb)])


# ===========================================================================
# 5. GRAHA MAITRI (5 pontos) — regentes dos rashis lunares.  CONFIRMADA
# ===========================================================================
_MAITRI_PTS = {
    frozenset({"amigo"}): 5.0,               # amigo+amigo
    frozenset({"amigo", "neutro"}): 4.0,
    frozenset({"neutro"}): 3.0,              # neutro+neutro
    frozenset({"amigo", "inimigo"}): 1.0,
    frozenset({"neutro", "inimigo"}): 0.5,
    frozenset({"inimigo"}): 0.0,             # inimigo+inimigo
}


def koota_graha_maitri(rashi_a: str, rashi_b: str) -> float:
    la, lb = SIGN_LORDS[rashi_a], SIGN_LORDS[rashi_b]
    if la == lb:
        return 5.0
    rel = frozenset({_relacao(la, lb), _relacao(lb, la)})
    return _MAITRI_PTS[rel]


# ===========================================================================
# 6. GANA (6 pontos) — por nakshatra.  classe CONFIRMADA; matriz PRELIMINAR
# ===========================================================================
GANA_POR_NAKSHATRA = {
    "Ashwini": "deva", "Mrigashira": "deva", "Punarvasu": "deva", "Pushya": "deva",
    "Hasta": "deva", "Swati": "deva", "Anuradha": "deva", "Shravana": "deva", "Revati": "deva",
    "Bharani": "manushya", "Rohini": "manushya", "Ardra": "manushya",
    "Purva Phalguni": "manushya", "Uttara Phalguni": "manushya", "Purva Ashadha": "manushya",
    "Uttara Ashadha": "manushya", "Purva Bhadrapada": "manushya", "Uttara Bhadrapada": "manushya",
    "Krittika": "rakshasa", "Ashlesha": "rakshasa", "Magha": "rakshasa", "Chitra": "rakshasa",
    "Vishakha": "rakshasa", "Jyeshtha": "rakshasa", "Mula": "rakshasa",
    "Dhanishta": "rakshasa", "Shatabhisha": "rakshasa",
}

# Matriz direcional (linha = noiva/A, coluna = noivo/B).  [Prokerala]
_GANA_PTS = {
    ("deva", "deva"): 6, ("manushya", "manushya"): 6, ("rakshasa", "rakshasa"): 6,
    ("deva", "manushya"): 5, ("manushya", "deva"): 6,
    ("deva", "rakshasa"): 1, ("rakshasa", "deva"): 0,
    ("manushya", "rakshasa"): 0, ("rakshasa", "manushya"): 0,
}


def koota_gana(nak_a: str, nak_b: str) -> float:
    ga, gb = GANA_POR_NAKSHATRA[nak_a], GANA_POR_NAKSHATRA[nak_b]
    return float(_GANA_PTS[(ga, gb)])


# ===========================================================================
# 7. BHAKOOT (7 pontos) — distância entre rashis.  [Prokerala]
# Dosha (0 ponto) nos pares 2/12, 5/9 e 6/8. Demais -> 7.
# Única exceção observada no Prokerala: noiva em Kumbha e noivo em Karka (6/8)
# recebe 7 — o inverso (Karka -> Kumbha) continua 0. Reproduzida para manter
# a consistência com a fonte.
# ===========================================================================
_BHAKOOT_EXCECOES = {("Kumbha", "Karka")}


def _distancia_rashi(a_idx: int, b_idx: int) -> tuple[int, int]:
    d_ab = ((b_idx - a_idx) % 12) + 1
    d_ba = ((a_idx - b_idx) % 12) + 1
    return d_ab, d_ba


def koota_bhakoot(rashi_a: str, rashi_b: str) -> tuple[float, bool]:
    """Retorna (pontos, dosha_presente)."""
    if (rashi_a, rashi_b) in _BHAKOOT_EXCECOES:
        return 7.0, False
    a, b = _idx_rashi(rashi_a), _idx_rashi(rashi_b)
    d_ab, d_ba = _distancia_rashi(a, b)
    if {d_ab, d_ba} in ({6, 8}, {5, 9}, {2, 12}):
        return 0.0, True
    return 7.0, False


# ===========================================================================
# 8. NADI (8 pontos) — por nakshatra.  CONFIRMADA
# Nadis diferentes -> 8; mesma Nadi -> 0 (Nadi dosha, o mais pesado).
# ===========================================================================
NADI_POR_NAKSHATRA = {
    # Aadi (Vata)
    "Ashwini": "aadi", "Ardra": "aadi", "Punarvasu": "aadi", "Uttara Phalguni": "aadi",
    "Hasta": "aadi", "Jyeshtha": "aadi", "Mula": "aadi", "Shatabhisha": "aadi",
    "Purva Bhadrapada": "aadi",
    # Madhya (Pitta)
    "Bharani": "madhya", "Mrigashira": "madhya", "Pushya": "madhya", "Purva Phalguni": "madhya",
    "Chitra": "madhya", "Anuradha": "madhya", "Purva Ashadha": "madhya", "Dhanishta": "madhya",
    "Uttara Bhadrapada": "madhya",
    # Antya (Kapha)
    "Krittika": "antya", "Rohini": "antya", "Ashlesha": "antya", "Magha": "antya",
    "Swati": "antya", "Vishakha": "antya", "Uttara Ashadha": "antya", "Shravana": "antya",
    "Revati": "antya",
}


def koota_nadi(nak_a: str, nak_b: str) -> tuple[float, bool]:
    """Retorna (pontos, dosha_presente)."""
    if NADI_POR_NAKSHATRA[nak_a] != NADI_POR_NAKSHATRA[nak_b]:
        return 8.0, False
    return 0.0, True


# ===========================================================================
# DOSHAS e CANCELAMENTOS (parihara)
# ===========================================================================
def cancelamento_nadi(rashi_a, nak_a, pada_a, rashi_b, nak_b, pada_b) -> bool:
    """Condições principais de anulação do Nadi dosha (spec §3)."""
    if nak_a == nak_b and pada_a != pada_b:
        return True                       # mesma nakshatra, padas diferentes
    if rashi_a == rashi_b and nak_a != nak_b:
        return True                       # mesmo rashi, nakshatras diferentes
    return False


def cancelamento_bhakoot(rashi_a: str, rashi_b: str) -> bool:
    """Bhakoot dosha anulado se os regentes são amigos ou o mesmo planeta."""
    la, lb = SIGN_LORDS[rashi_a], SIGN_LORDS[rashi_b]
    if la == lb:
        return True
    return _relacao(la, lb) == "amigo" and _relacao(lb, la) == "amigo"


def mangal_do_casal(mapa_a: dict, mapa_b: dict) -> dict:
    """
    Manglik de cada um a partir do Ascendente (reaproveita detectar_fatos).
    Regra de casal: se AMBOS são Manglik, o dosha se anula entre eles.
    """
    md_a = detectar_mangal_dosha(mapa_a["grahas"], mapa_a["lagna"]["signo"])
    md_b = detectar_mangal_dosha(mapa_b["grahas"], mapa_b["lagna"]["signo"])
    a_manglik, b_manglik = md_a is not None, md_b is not None
    if a_manglik and b_manglik:
        situacao = "anulado"          # ambos Manglik -> se cancela
    elif a_manglik or b_manglik:
        situacao = "atencao"          # só um -> sinalizar com cuidado
    else:
        situacao = "ausente"
    return {"a": a_manglik, "b": b_manglik, "situacao": situacao,
            "compativel": situacao in ("anulado", "ausente")}


# ===========================================================================
# FAIXAS DE INTERPRETAÇÃO (spec §4)
# ===========================================================================
def categoria_de(total: float) -> str:
    if total >= 32:
        return "excepcional"
    if total >= 25:
        return "forte"
    if total >= 18:
        return "boa com atencao"
    return "requer trabalho"


_TEMAS = {
    "Varna": "postura diante da vida",
    "Vashya": "atração e influência mútua",
    "Tara": "bem-estar e sorte da relação",
    "Yoni": "encaixe físico e instintivo",
    "Graha Maitri": "sintonia mental e amizade",
    "Gana": "temperamento",
    "Bhakoot": "vínculo emocional e prosperidade",
    "Nadi": "vitalidade e saúde a longo prazo",
}
_MAX = {"Varna": 1, "Vashya": 2, "Tara": 3, "Yoni": 4,
        "Graha Maitri": 5, "Gana": 6, "Bhakoot": 7, "Nadi": 8}


# ===========================================================================
# AGREGADOR
# ===========================================================================
def _dados_lua(mapa: dict) -> dict:
    return {
        "rashi": mapa["grahas"]["Chandra"]["signo"],
        "grau": mapa["grahas"]["Chandra"]["grau_no_signo"],
        "nak": mapa["nakshatra_lua"]["nome"],
        "pada": mapa["nakshatra_lua"]["pada"],
    }


def calcular_compatibilidade(mapa_a: dict, mapa_b: dict) -> dict:
    """Motor completo. Recebe dois mapas de compute_chart.calcular_mapa()."""
    A, B = _dados_lua(mapa_a), _dados_lua(mapa_b)

    varna = koota_varna(A["rashi"], B["rashi"])
    vashya = koota_vashya(A["rashi"], B["rashi"], A["grau"], B["grau"])
    tara = koota_tara(A["nak"], B["nak"])
    yoni = koota_yoni(A["nak"], B["nak"])
    maitri = koota_graha_maitri(A["rashi"], B["rashi"])
    gana = koota_gana(A["nak"], B["nak"])
    bhakoot_pts, bhakoot_dosha = koota_bhakoot(A["rashi"], B["rashi"])
    nadi_pts, nadi_dosha = koota_nadi(A["nak"], B["nak"])

    kootas = [
        ("Varna", varna), ("Vashya", vashya), ("Tara", tara), ("Yoni", yoni),
        ("Graha Maitri", maitri), ("Gana", gana),
        ("Bhakoot", bhakoot_pts), ("Nadi", nadi_pts),
    ]
    total = sum(pts for _, pts in kootas)

    # doshas + cancelamentos
    nadi_cancelado = cancelamento_nadi(A["rashi"], A["nak"], A["pada"],
                                       B["rashi"], B["nak"], B["pada"]) if nadi_dosha else None
    bhakoot_cancelado = cancelamento_bhakoot(A["rashi"], B["rashi"]) if bhakoot_dosha else None
    mangal = mangal_do_casal(mapa_a, mapa_b)

    return {
        "total": round(total, 1),
        "maximo": 36,
        "categoria": categoria_de(total),
        "kootas": [
            {"nome": nome, "obtido": round(pts, 1), "max": _MAX[nome], "tema": _TEMAS[nome]}
            for nome, pts in kootas
        ],
        "doshas": {
            "bhakoot": {"presente": bhakoot_dosha, "cancelado": bhakoot_cancelado},
            "nadi": {"presente": nadi_dosha, "cancelado": nadi_cancelado},
            "mangal": mangal,
        },
        "lua": {"a": A, "b": B},
    }


# ===========================================================================
# CORTE DO PAYWALL (spec §5)
# ===========================================================================
def montar_amostra(resultado: dict, nome_a: str = "Pessoa A", nome_b: str = "Pessoa B") -> dict:
    """
    Amostra grátis (isca): nota total, categoria, 1 ponto forte e 1 de atenção.
    Específica do casal, nunca genérica. É o que alimenta o card compartilhável.
    """
    # ponto mais forte e mais fraco por proporção do máximo (não pelo bruto)
    por_proporcao = sorted(resultado["kootas"], key=lambda k: k["obtido"] / k["max"])
    fraco = por_proporcao[0]
    forte = por_proporcao[-1]
    return {
        "nomes": {"a": nome_a, "b": nome_b},
        "total": resultado["total"],
        "maximo": 36,
        "categoria": resultado["categoria"],
        "ponto_forte": {"koota": forte["nome"], "tema": forte["tema"]},
        "ponto_atencao": {"koota": fraco["nome"], "tema": fraco["tema"]},
    }


def payload_completo(resultado: dict) -> dict:
    """Completo (R$127): tudo. Aqui é o resultado inteiro; a prosa das 8 kootas
    e a síntese prática vêm da base de significações + IA, fora deste motor."""
    return resultado


# ===========================================================================
# RECUPERAÇÃO DE TRECHOS (pipeline significações §4, etapas 2->3)
# O código escolhe a faixa de cada koota e busca o trecho exato na base.
# A IA (fora daqui) só costura os trechos retornados — não inventa.
# ===========================================================================
def banda_koota(obtido: float, maximo: int) -> str:
    """Traduz a pontuação de uma koota em 'forte' | 'medio' | 'fraco'."""
    p = obtido / maximo
    if p >= 0.7:
        return "forte"
    if p >= 0.35:
        return "medio"
    return "fraco"


def _texto_por_banda(entrada: dict, obtido: float, maximo: int) -> str:
    """Pega o texto da banda; se ela não existir (koota binária sem 'medio'),
    cai no vizinho mais próximo pela proporção."""
    banda = banda_koota(obtido, maximo)
    if banda in entrada:
        return entrada[banda]
    # fallback: binária ou faixa ausente
    alternativa = "forte" if (obtido / maximo) >= 0.5 else "fraco"
    return entrada.get(alternativa, entrada.get("fraco", ""))


def montar_snippets_compatibilidade(resultado: dict, nivel: str = "completo",
                                    nome_a: str = "Pessoa A", nome_b: str = "Pessoa B") -> dict:
    """
    Retorna os TRECHOS já selecionados (não a prosa final) para a IA costurar.
    nivel='amostra' -> só a isca grátis; nivel='completo' -> relatório inteiro.
    Importa base_significacoes de forma preguiçosa para manter o motor puro.
    """
    import base_significacoes as B

    moldura = B.COMPAT_FAIXA[resultado["categoria"]].format(total=resultado["total"])
    amostra = montar_amostra(resultado, nome_a, nome_b)

    saida = {
        "nivel": nivel,
        "nomes": {"a": nome_a, "b": nome_b},
        "total": resultado["total"],
        "maximo": 36,
        "categoria": resultado["categoria"],
        "moldura": moldura,
    }

    if nivel == "amostra":
        forte = amostra["ponto_forte"]["koota"]
        fraco = amostra["ponto_atencao"]["koota"]
        pts = {k["nome"]: k for k in resultado["kootas"]}
        saida["ponto_forte"] = {
            "koota": forte, "tema": B.KOOTA[forte]["tema"],
            "texto": _texto_por_banda(B.KOOTA[forte], pts[forte]["obtido"], pts[forte]["max"]),
        }
        saida["ponto_atencao"] = {
            "koota": fraco, "tema": B.KOOTA[fraco]["tema"],
            "texto": _texto_por_banda(B.KOOTA[fraco], pts[fraco]["obtido"], pts[fraco]["max"]),
        }
        return saida

    # completo: as 8 kootas + doshas + mangal
    saida["kootas"] = []
    for k in resultado["kootas"]:
        entrada = B.KOOTA[k["nome"]]
        saida["kootas"].append({
            "nome": k["nome"],
            "tema": entrada["tema"],
            "obtido": k["obtido"],
            "max": k["max"],
            "banda": banda_koota(k["obtido"], k["max"]),
            "descricao": entrada["descricao"],
            "texto": _texto_por_banda(entrada, k["obtido"], k["max"]),
        })

    doshas = []
    d = resultado["doshas"]
    if d["bhakoot"]["presente"]:
        item = {"tipo": "bhakoot", "texto": B.COMPAT_DOSHA["bhakoot"]["texto"]}
        if d["bhakoot"]["cancelado"]:
            item["alivio"] = B.COMPAT_DOSHA["bhakoot"]["texto_cancelamento"]
        doshas.append(item)
    if d["nadi"]["presente"]:
        item = {"tipo": "nadi", "texto": B.COMPAT_DOSHA["nadi"]["texto"]}
        if d["nadi"]["cancelado"]:
            item["alivio"] = B.COMPAT_DOSHA["nadi"]["texto_cancelamento"]
        doshas.append(item)
    doshas.append({"tipo": "mangal", "texto": B.MANGAL_CASAL[d["mangal"]["situacao"]]})
    saida["doshas"] = doshas
    return saida


# ===========================================================================
if __name__ == "__main__":
    import json
    from datetime import datetime
    from compute_chart import calcular_mapa

    # Dois nascimentos de exemplo (não são mapas reais).
    mapa_a = calcular_mapa(datetime(1997, 3, 14, 8, 20), lat=-30.0346, lon=-51.2177)   # Porto Alegre
    mapa_b = calcular_mapa(datetime(1995, 9, 2, 21, 45), lat=-25.4284, lon=-49.2733)   # Curitiba

    resultado = calcular_compatibilidade(mapa_a, mapa_b)
    print("=== RESULTADO (motor) ===")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    print("\n=== TRECHOS DA AMOSTRA GRÁTIS (p/ a IA costurar) ===")
    print(json.dumps(montar_snippets_compatibilidade(resultado, "amostra", "Ana", "Rafael"),
                     indent=2, ensure_ascii=False))
    print("\n=== TRECHOS DO RELATÓRIO COMPLETO ===")
    print(json.dumps(montar_snippets_compatibilidade(resultado, "completo", "Ana", "Rafael"),
                     indent=2, ensure_ascii=False))

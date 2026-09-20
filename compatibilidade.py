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
  O Guna Milan clássico é contado da NOIVA para o NOIVO — Tara, Gana e Bhakoot
  têm direção. Como o produto não pressupõe gênero, fixamos "pessoa A" e
  "pessoa B" e contamos SEMPRE de A para B. Trocar a ordem pode mudar Tara/Gana
  em casos de fronteira. Documentado e travado aqui.

=============================================================================
STATUS DAS TABELAS (honestidade de engenharia)
  CONFIRMADAS (padrão clássico estável, baixa divergência entre fontes):
    Varna, Tara (contagem por 9), Graha Maitri (amizade planetária),
    Gana (Deva/Manushya/Rakshasa), Bhakoot (distância), Nadi (Aadi/Madhya/Antya),
    Yoni (animal de cada nakshatra), inimigos mortais de Yoni.
  PRELIMINARES (as fontes divergem — VALIDAR contra a fonte escolhida antes
  de cobrar, ver spec §7):
    - Vashya: classe por rashi em meio-signo (Dhanu, Makara) e a matriz de
      pontuação parcial.
    - Yoni: os valores intermediários 3 (amigo) e 1 (inimigo) — aqui o meio
      cai em 2 (neutro) por padrão até a validação preencher os pares.
    - Gana: o valor de Deva×Manushya (5 ou 6) e a direção de Deva×Rakshasa.
    - Bhakoot: seguimos a spec (dosha só em 6-8 e 5-9; 2-12 tratado como
      auspicioso). Algumas fontes penalizam 2-12 também.
  Cada ponto PRELIMINAR está marcado com  # VALIDAR  no código.
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
# Brâmane(4) > Kshatriya(3) > Vaishya(2) > Shudra(1). 1 ponto se varna(A) >= varna(B).
# ===========================================================================
VARNA_POR_RASHI = {
    "Karka": 4, "Vrishchika": 4, "Meena": 4,      # água = Brâmane
    "Mesha": 3, "Simha": 3, "Dhanu": 3,           # fogo = Kshatriya
    "Vrishabha": 2, "Kanya": 2, "Makara": 2,      # terra = Vaishya
    "Mithuna": 1, "Tula": 1, "Kumbha": 1,         # ar = Shudra
}


def koota_varna(rashi_a: str, rashi_b: str) -> float:
    return 1.0 if VARNA_POR_RASHI[rashi_a] >= VARNA_POR_RASHI[rashi_b] else 0.0


# ===========================================================================
# 2. VASHYA (2 pontos) — por rashi.  PRELIMINAR (validar meio-signo + matriz)
# Classes: chatushpada (quadrúpede), nara (humano), jalachara (aquático),
#          vanachara (selvagem), keeta (inseto).
# ===========================================================================
VASHYA_POR_RASHI = {
    "Mesha": "chatushpada", "Vrishabha": "chatushpada",
    "Mithuna": "nara", "Karka": "jalachara", "Simha": "vanachara",
    "Kanya": "nara", "Tula": "nara", "Vrishchika": "keeta",
    "Dhanu": "nara",       # VALIDAR: 2ª metade é chatushpada em algumas fontes
    "Makara": "chatushpada",  # VALIDAR: 1ª metade chatushpada, 2ª jalachara
    "Kumbha": "nara", "Meena": "jalachara",
}

# Matriz de pontuação entre classes (linha = A, coluna = B).  # VALIDAR (matriz)
# Convenção comum: mesma classe = 2; combinações domésticas = 1; parciais = 0.5;
# "presa/predador" = 0. Os valores fora da diagonal são preliminares.
_VASHYA_PTS = {
    ("chatushpada", "chatushpada"): 2, ("nara", "nara"): 2,
    ("jalachara", "jalachara"): 2, ("vanachara", "vanachara"): 2,
    ("keeta", "keeta"): 2,
    ("nara", "chatushpada"): 1, ("chatushpada", "nara"): 1,
    ("nara", "jalachara"): 1, ("jalachara", "nara"): 1,
    ("chatushpada", "jalachara"): 1, ("jalachara", "chatushpada"): 1,
    ("nara", "keeta"): 0.5, ("keeta", "nara"): 0.5,
    ("jalachara", "keeta"): 1, ("keeta", "jalachara"): 1,
    # vanachara (selvagem, Simha) domina: não é dominado por nara/quadrúpede
    ("vanachara", "nara"): 1, ("nara", "vanachara"): 0,
    ("vanachara", "chatushpada"): 1, ("chatushpada", "vanachara"): 0,
    ("vanachara", "jalachara"): 1, ("jalachara", "vanachara"): 0.5,
    ("vanachara", "keeta"): 1, ("keeta", "vanachara"): 0,
    ("chatushpada", "keeta"): 0.5, ("keeta", "chatushpada"): 0.5,
}


def koota_vashya(rashi_a: str, rashi_b: str) -> float:
    ca, cb = VASHYA_POR_RASHI[rashi_a], VASHYA_POR_RASHI[rashi_b]
    return float(_VASHYA_PTS.get((ca, cb), 1))


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

# 7 pares de inimigos mortais (cobrem os 14 animais).  CONFIRMADOS -> 0 pontos
_YONI_INIMIGOS_MORTAIS = {
    frozenset({"cavalo", "bufalo"}),
    frozenset({"elefante", "leao"}),
    frozenset({"ovelha", "macaco"}),
    frozenset({"cobra", "mangusto"}),
    frozenset({"cao", "veado"}),
    frozenset({"gato", "rato"}),
    frozenset({"vaca", "tigre"}),
}
# VALIDAR: pares "amigos" (3 pts) e "inimigos não-mortais" (1 pt). Até a
# validação preencher, o meio-termo cai em 2 (neutro).
_YONI_AMIGOS = set()   # ex.: frozenset({"vaca","bufalo"}) — preencher na validação
_YONI_INIMIGOS = set()  # inimigos não-mortais (1 pt) — preencher na validação


def koota_yoni(nak_a: str, nak_b: str) -> float:
    ya, yb = YONI_POR_NAKSHATRA[nak_a], YONI_POR_NAKSHATRA[nak_b]
    if ya == yb:
        return 4.0
    par = frozenset({ya, yb})
    if par in _YONI_INIMIGOS_MORTAIS:
        return 0.0
    if par in _YONI_AMIGOS:
        return 3.0
    if par in _YONI_INIMIGOS:
        return 1.0
    return 2.0  # neutro (preliminar)


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

# Matriz direcional (linha = A, coluna = B).  # VALIDAR (deva×manushya e direção)
_GANA_PTS = {
    ("deva", "deva"): 6, ("manushya", "manushya"): 6, ("rakshasa", "rakshasa"): 6,
    ("deva", "manushya"): 6, ("manushya", "deva"): 5,     # VALIDAR (5 ou 6)
    ("deva", "rakshasa"): 1, ("rakshasa", "deva"): 1,     # VALIDAR (direção)
    ("manushya", "rakshasa"): 0, ("rakshasa", "manushya"): 0,
}


def koota_gana(nak_a: str, nak_b: str) -> float:
    ga, gb = GANA_POR_NAKSHATRA[nak_a], GANA_POR_NAKSHATRA[nak_b]
    return float(_GANA_PTS[(ga, gb)])


# ===========================================================================
# 7. BHAKOOT (7 pontos) — distância entre rashis.  CONFIRMADA (segue a spec)
# Dosha (0) em 6-8 e 5-9. Demais -> 7. (2-12 tratado como auspicioso; VALIDAR.)
# ===========================================================================
def _distancia_rashi(a_idx: int, b_idx: int) -> tuple[int, int]:
    d_ab = ((b_idx - a_idx) % 12) + 1
    d_ba = ((a_idx - b_idx) % 12) + 1
    return d_ab, d_ba


def koota_bhakoot(rashi_a: str, rashi_b: str) -> tuple[float, bool]:
    """Retorna (pontos, dosha_presente)."""
    a, b = _idx_rashi(rashi_a), _idx_rashi(rashi_b)
    d_ab, d_ba = _distancia_rashi(a, b)
    par = {d_ab, d_ba}
    if par in ({6, 8}, {5, 9}):
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
        "nak": mapa["nakshatra_lua"]["nome"],
        "pada": mapa["nakshatra_lua"]["pada"],
    }


def calcular_compatibilidade(mapa_a: dict, mapa_b: dict) -> dict:
    """Motor completo. Recebe dois mapas de compute_chart.calcular_mapa()."""
    A, B = _dados_lua(mapa_a), _dados_lua(mapa_b)

    varna = koota_varna(A["rashi"], B["rashi"])
    vashya = koota_vashya(A["rashi"], B["rashi"])
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

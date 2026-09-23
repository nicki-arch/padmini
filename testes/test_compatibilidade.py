"""
Validação do motor de compatibilidade (Ashtakoot Guna Milan).

Duas camadas:

1) INVARIANTES — rodam e passam agora. Garantem que a estrutura nunca sai do
   trilho (total <= 36, cada koota dentro do seu máximo, dosha <=> koota zerada).

2) REFERÊNCIA (spec §7) — 5 casais conferidos KOOTA A KOOTA contra UMA fonte
   escolhida (Prokerala / AstroSage / Drik Panchang). Enquanto os valores
   esperados estiverem como None, a comparação é PULADA e reportada como
   "pendente de validação". Preencher `ESPERADO` com os pontos da fonte antes
   de cobrar. Conferir koota a koota, não só o total — dois erros podem se
   cancelar na soma.

   ATENÇÃO: as tabelas marcadas como PRELIMINARES no compatibilidade.py
   (Vashya, meio-termo de Yoni, direção de Gana) são justamente as que esta
   validação existe para pinar. Ao achar divergência, ajustar a TABELA no
   motor para bater com a fonte escolhida — e manter a mesma fonte sempre.

Rodar:  python testes/test_compatibilidade.py   (ou pytest)
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compute_chart import calcular_mapa          # noqa: E402
from compatibilidade import calcular_compatibilidade, montar_amostra  # noqa: E402

KOOTAS = ["Varna", "Vashya", "Tara", "Yoni", "Graha Maitri", "Gana", "Bhakoot", "Nadi"]

# ---------------------------------------------------------------------------
# 5 casais de teste. As datas/locais são fixtures — troque por casais reais se
# preferir. O que precisa ser preenchido é ESPERADO, com os pontos da FONTE.
# Formato de cada pessoa: (datetime, lat, lon).
# ---------------------------------------------------------------------------
CASAIS = {
    "casal_1": {
        "a": (datetime(1997, 3, 14, 8, 20), -30.0346, -51.2177),   # Porto Alegre
        "b": (datetime(1995, 9, 2, 21, 45), -25.4284, -49.2733),   # Curitiba
    },
    "casal_2": {
        "a": (datetime(1990, 6, 10, 4, 15), -23.5505, -46.6333),   # São Paulo
        "b": (datetime(1988, 11, 22, 17, 5), -22.9068, -43.1729),  # Rio de Janeiro
    },
    "casal_3": {
        "a": (datetime(1993, 1, 30, 12, 0), -19.9167, -43.9345),   # Belo Horizonte
        "b": (datetime(1994, 7, 18, 6, 40), -12.9777, -38.5016),   # Salvador
    },
    "casal_4": {
        "a": (datetime(1985, 4, 5, 23, 10), -3.1190, -60.0217),    # Manaus
        "b": (datetime(1986, 10, 12, 9, 25), -8.0476, -34.8770),   # Recife
    },
    "casal_5": {
        "a": (datetime(2000, 12, 25, 15, 45), -15.7939, -47.8828), # Brasília
        "b": (datetime(1999, 2, 14, 2, 30), -30.0346, -51.2177),   # Porto Alegre
    },
}

# ---------------------------------------------------------------------------
# Pontos esperados por koota, da FONTE DE REFERÊNCIA (preencher).
# None em qualquer koota => aquela comparação é pulada (pendente).
# 'total' opcional: se preenchido, também é conferido.
# ---------------------------------------------------------------------------
ESPERADO = {  # Prokerala (Guna Milan), 22/set/2026 — A = noiva (girl), B = noivo (boy)
    "casal_1": {"Varna": 1.0, "Vashya": 1.0, "Tara": 1.5, "Yoni": 2.0, "Graha Maitri": 3.0, "Gana": 0.0, "Bhakoot": 7.0, "Nadi": 8.0, "total": 23.5},
    "casal_2": {"Varna": 1.0, "Vashya": 2.0, "Tara": 3.0, "Yoni": 3.0, "Graha Maitri": 5.0, "Gana": 6.0, "Bhakoot": 0.0, "Nadi": 0.0, "total": 20.0},
    "casal_3": {"Varna": 1.0, "Vashya": 1.0, "Tara": 1.5, "Yoni": 1.0, "Graha Maitri": 5.0, "Gana": 1.0, "Bhakoot": 0.0, "Nadi": 8.0, "total": 18.5},
    "casal_4": {"Varna": 1.0, "Vashya": 0.5, "Tara": 3.0, "Yoni": 1.0, "Graha Maitri": 5.0, "Gana": 0.0, "Bhakoot": 7.0, "Nadi": 8.0, "total": 25.5},
    "casal_5": {"Varna": 0.0, "Vashya": 1.0, "Tara": 1.5, "Yoni": 1.0, "Graha Maitri": 3.0, "Gana": 0.0, "Bhakoot": 0.0, "Nadi": 8.0, "total": 14.5},
}


def _resultado(casal_id: str) -> dict:
    dados = CASAIS[casal_id]
    mapa_a = calcular_mapa(*dados["a"])
    mapa_b = calcular_mapa(*dados["b"])
    return calcular_compatibilidade(mapa_a, mapa_b)


# ===========================================================================
# CAMADA 1 — INVARIANTES (passam agora)
# ===========================================================================
def verificar_invariantes() -> list[str]:
    falhas = []
    for casal_id in CASAIS:
        r = _resultado(casal_id)
        if r["total"] > 36 or r["total"] < 0:
            falhas.append(f"{casal_id}: total fora de [0,36]: {r['total']}")
        soma = 0.0
        for k in r["kootas"]:
            soma += k["obtido"]
            if not (0 <= k["obtido"] <= k["max"]):
                falhas.append(f"{casal_id}: {k['nome']} fora de [0,{k['max']}]: {k['obtido']}")
        if abs(soma - r["total"]) > 1e-9:
            falhas.append(f"{casal_id}: soma das kootas ({soma}) != total ({r['total']})")
        # coerência dosha <=> koota zerada
        d = r["doshas"]
        pts = {k["nome"]: k["obtido"] for k in r["kootas"]}
        if d["bhakoot"]["presente"] and pts["Bhakoot"] != 0:
            falhas.append(f"{casal_id}: Bhakoot dosha presente mas pontos != 0")
        if d["nadi"]["presente"] and pts["Nadi"] != 0:
            falhas.append(f"{casal_id}: Nadi dosha presente mas pontos != 0")
        # a amostra grátis tem que ser específica (ponto forte != ponto atenção quando há variação)
        amostra = montar_amostra(r)
        if amostra["total"] != r["total"]:
            falhas.append(f"{casal_id}: total da amostra != total do resultado")
    return falhas


def test_invariantes():
    assert verificar_invariantes() == []


# ===========================================================================
# CAMADA 2 — REFERÊNCIA (pula o que ainda não foi preenchido)
# ===========================================================================
def verificar_referencia() -> tuple[list[str], int, int]:
    """Retorna (falhas, comparacoes_feitas, comparacoes_pendentes)."""
    falhas, feitas, pendentes = [], 0, 0
    for casal_id in CASAIS:
        r = _resultado(casal_id)
        pts = {k["nome"]: k["obtido"] for k in r["kootas"]}
        esp = ESPERADO.get(casal_id, {})
        for koota in KOOTAS:
            alvo = esp.get(koota)
            if alvo is None:
                pendentes += 1
                continue
            feitas += 1
            if abs(pts[koota] - alvo) > 1e-9:
                falhas.append(f"{casal_id}: {koota} = {pts[koota]} != referência {alvo}")
        if esp.get("total") is not None:
            feitas += 1
            if abs(r["total"] - esp["total"]) > 1e-9:
                falhas.append(f"{casal_id}: total = {r['total']} != referência {esp['total']}")
    return falhas, feitas, pendentes


def test_referencia_quando_preenchida():
    """Só falha quando há valor de referência preenchido que não bate.
    Enquanto tudo for None, passa (mas o __main__ avisa que está pendente)."""
    falhas, _, _ = verificar_referencia()
    assert falhas == []


if __name__ == "__main__":
    inv = verificar_invariantes()
    print("INVARIANTES:", "OK" if not inv else "FALHAS:\n  " + "\n  ".join(inv))

    ref_falhas, feitas, pendentes = verificar_referencia()
    if feitas == 0:
        print(f"REFERÊNCIA: PENDENTE — 0 de {pendentes} comparações preenchidas.")
        print("  Preencha ESPERADO com os pontos de Prokerala/AstroSage (spec §7) antes de cobrar.")
    elif ref_falhas:
        print(f"REFERÊNCIA: {len(ref_falhas)} divergência(s) em {feitas} comparações "
              f"({pendentes} ainda pendentes):")
        print("  " + "\n  ".join(ref_falhas))
    else:
        print(f"REFERÊNCIA: OK — {feitas} comparações conferem ({pendentes} ainda pendentes).")

    sys.exit(1 if inv or ref_falhas else 0)


# ===========================================================================
# CAMADA 3 — 129 casais do Prokerala (todos os pares de Yoni, Vashya, Gana,
# Bhakoot). Trava as tabelas: qualquer mudança que desalinhe da fonte falha.
# ===========================================================================
def test_129_casais_do_prokerala():
    import json
    dados = json.loads((Path(__file__).parent / "dados" / "prokerala_guna_milan.json").read_text(encoding="utf-8"))
    divergencias = []
    for c in dados["casais"]:
        ma = calcular_mapa(datetime.fromisoformat(c["noiva"]), -23.5505, -46.6333)
        mb = calcular_mapa(datetime.fromisoformat(c["noivo"]), -23.5505, -46.6333)
        r = calcular_compatibilidade(ma, mb)
        nosso = {k["nome"]: k["obtido"] for k in r["kootas"]}
        for koota, esperado in c["pontos"].items():
            if abs(nosso[koota] - esperado) > 1e-9:
                divergencias.append(f"{c['id']} {koota}: nosso {nosso[koota]} x Prokerala {esperado}")
    assert not divergencias, "\n".join(divergencias[:20])
    assert len(dados["casais"]) >= 120

"""
Padmini — montagem do relatório (Mapa Védico Essencial).

Estrutura do relatório:
  1. Ascendente
  2. Lua e nakshatra natal
  3. Fase atual (Vimshottari Dasha)
  4. Destaques do mapa (fatos notáveis detectados por regra)

Dois modos:
  - rascunho mecânico (padrão): junta os trechos da base, sem LLM.
  - prompt para LLM: monta o material que o Claude recebe para costurar a
    prosa final, com instrução de não acrescentar nada fora dele.
"""

from datetime import date
from base_significacoes import (
    NOME_PT, SIGNO_PT, LAGNA, NAKSHATRA, DASHA, GRAHA_DIGNIDADE,
    COMBUSTAO, CAZIMI, YOGAS, DOSHA,
)

REFERENCIA_PT = {"lagna": "o Ascendente", "lua": "a Lua", "venus": "Vênus"}


def dasha_atual(mapa: dict, hoje: date | None = None) -> dict | None:
    hoje = (hoje or date.today()).isoformat()
    for d in mapa["vimshottari_dasha"]:
        if d["inicio"] <= hoje < d["fim"]:
            return d
    return None


def trecho_do_fato(fato: dict) -> str | None:
    tipo = fato["tipo"]
    if tipo == "dignidade":
        return GRAHA_DIGNIDADE.get(fato["planeta"], {}).get(fato["estado"])
    if tipo == "combustao":
        return COMBUSTAO.get(fato["planeta"])
    if tipo == "cazimi":
        return CAZIMI.format(planeta=NOME_PT[fato["planeta"]])
    if tipo == "gaja_kesari":
        return YOGAS["gaja_kesari"]
    if tipo == "pancha_mahapurusha":
        return YOGAS["pancha_mahapurusha"].get(fato["yoga"])
    if tipo == "yogakaraka":
        return YOGAS["yogakaraka"].format(
            planeta=NOME_PT[fato["planeta"]], rege_kendra=fato["rege_kendra"], rege_trikona=fato["rege_trikona"])
    if tipo == "raj_yoga":
        return YOGAS["raj_yoga"].format(
            regente_kendra=NOME_PT[fato["regente_kendra"]], regente_trikona=NOME_PT[fato["regente_trikona"]],
            signo=SIGNO_PT[fato["signo_conjuncao"]])
    if tipo == "neecha_bhanga":
        return YOGAS["neecha_bhanga"].format(
            planeta=NOME_PT[fato["planeta"]], dispositor=NOME_PT[fato["dispositor"]])
    if tipo == "mangal_dosha":
        refs = [REFERENCIA_PT[r] for r in fato["referencias_afetadas"]]
        texto_refs = refs[0] if len(refs) == 1 else ", ".join(refs[:-1]) + " e " + refs[-1]
        return DOSHA["mangal_dosha"].format(referencias=texto_refs)
    return None


def montar_secoes(mapa: dict, fatos: list[dict], hoje: date | None = None) -> tuple[dict, list[dict]]:
    secoes = {}
    lagna = mapa["lagna"]["signo"]
    secoes["Ascendente"] = LAGNA[lagna]

    nak = mapa["nakshatra_lua"]
    info_nak = NAKSHATRA[nak["nome"]]
    secoes["Lua e nakshatra"] = (
        f"A Lua está em {SIGNO_PT[mapa['grahas']['Chandra']['signo']]}, na nakshatra {nak['nome']} "
        f"(pada {nak['pada']}, regida por {NOME_PT[info_nak['regente']]}, deidade {info_nak['deidade']}). "
        + info_nak["texto"]
    )

    atual = dasha_atual(mapa, hoje)
    if atual:
        secoes["Fase atual"] = (
            f"De {atual['inicio'][:4]} a {atual['fim'][:4]}, a pessoa vive a " + DASHA[atual["regente"]]
        )

    destaques, sem_conteudo = [], []
    for fato in fatos:
        trecho = trecho_do_fato(fato)
        (destaques if trecho else sem_conteudo).append(trecho or fato)
    secoes["Destaques do mapa"] = destaques
    return secoes, sem_conteudo


def rascunho_mecanico(secoes: dict) -> str:
    partes = []
    for titulo, conteudo in secoes.items():
        corpo = "\n\n".join(conteudo) if isinstance(conteudo, list) else conteudo
        partes.append(f"## {titulo}\n\n{corpo}")
    return "\n\n".join(partes)


INSTRUCAO_LLM = """Você escreve o Mapa Védico Essencial da Padmini, em português do Brasil.

Regras:
- Use SOMENTE as informações do material abaixo. Não acrescente nenhum fato astrológico, previsão ou traço de personalidade que não esteja nele.
- Reescreva o material como um texto corrido e acolhedor, mantendo as quatro seções e os títulos.
- Quando dois trechos se reforçam ou se contradizem, diga isso explicitamente em vez de listar um depois do outro.
- Nada de frases que serviriam para qualquer pessoa. Nada de promessas, garantias, previsões de eventos, saúde ou dinheiro.
- Escreva para a pessoa, usando "você". Nunca mencione "o material", "os trechos" ou como o texto foi feito.
- Não confunda signo com casa: um planeta em seu próprio signo está em "signo próprio", nunca em "casa própria".
- Comece direto no título "## Ascendente", sem título geral antes.
- Termine com uma linha: "Este mapa é uma ferramenta de autoconhecimento inspirada na tradição védica (Jyotish), não uma previsão nem substituto de orientação profissional."
"""


def montar_prompt(secoes: dict) -> str:
    return INSTRUCAO_LLM + "\n\nMATERIAL:\n\n" + rascunho_mecanico(secoes)


def gerar_com_claude(prompt: str, modelo: str | None = None) -> str:
    """Chama a Claude API. Precisa de ANTHROPIC_API_KEY no ambiente."""
    import os
    import anthropic
    client = anthropic.Anthropic()
    modelo = modelo or os.environ.get("PADMINI_MODELO", "claude-sonnet-5")
    resposta = client.messages.create(
        model=modelo,
        max_tokens=4000,
        thinking={"type": "disabled"},  # reescrita de texto não precisa de raciocínio longo; fica mais rápido e barato
        messages=[{"role": "user", "content": prompt}],
    )
    texto = "".join(b.text for b in resposta.content if b.type == "text").strip()
    if resposta.stop_reason == "max_tokens" or not texto:
        raise RuntimeError(f"Geração incompleta (stop_reason={resposta.stop_reason}).")
    return texto


if __name__ == "__main__":
    import os
    import sys
    from datetime import datetime
    from compute_chart import calcular_mapa
    from detectar_fatos import detectar_todos_os_fatos

    mapa = calcular_mapa(dt_local_naive=datetime(1990, 9, 15, 14, 30), lat=-30.0346, lon=-51.2177)
    fatos = detectar_todos_os_fatos(mapa)
    secoes, faltando = montar_secoes(mapa, fatos)

    if "--llm" in sys.argv:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("Defina ANTHROPIC_API_KEY para gerar com o Claude (ou rode sem --llm).")
        print(gerar_com_claude(montar_prompt(secoes)))
    elif "--prompt" in sys.argv:
        print(montar_prompt(secoes))
    else:
        print(rascunho_mecanico(secoes))
        if faltando:
            print("\n## Fatos sem conteúdo na base\n")
            for f in faltando:
                print(f"- {f}")

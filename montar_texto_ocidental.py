"""
Padmini (versão ocidental) — do mapa calculado ao texto do relatório.

Mesma regra da védica: os FATOS vêm do cálculo (mapa_ocidental.py), o TEXTO vem
da base escrita por nós (conteudo/ocidental/textos/*.yaml). A IA, quando usada,
só reescreve esse texto-base (nunca calcula nada), só no relatório pago, e o
resultado fica em cache no banco.

Cada texto dos YAMLs tem `revisado: true/false`; `contagem_de_revisao()` diz
quantos faltam — é a lista de trabalho da família do Pedro
(`python scripts/revisao_textos.py`).
"""

from functools import lru_cache
from pathlib import Path

import yaml

import mapa_ocidental as mo

PASTA = Path(__file__).parent / "conteudo" / "ocidental" / "textos"
ARQUIVOS = ("planetas_signos", "planetas_casas", "ascendente", "aspectos_pessoais", "pecas")

# Aspectos só entre planetas lentos são de geração, não da pessoa: ficam fora
# da lista de "aspectos principais" do completo.
LENTOS = ("jupiter", "saturno", "urano", "netuno", "plutao")
MAX_ASPECTOS_COMPLETO = 14


@lru_cache(maxsize=None)
def base(arquivo: str) -> dict:
    return yaml.safe_load((PASTA / f"{arquivo}.yaml").read_text(encoding="utf-8")) or {}


def _t(no) -> str:
    return (no or {}).get("texto", "") if isinstance(no, dict) else ""


def cada_texto():
    """(arquivo, caminho, nó) de todo texto da base — nó tem `texto` e `revisado`."""
    def andar(no, caminho):
        if isinstance(no, dict) and "texto" in no:
            yield caminho, no
        elif isinstance(no, dict):
            for k, v in no.items():
                yield from andar(v, caminho + (str(k),))
    for arquivo in ARQUIVOS:
        for caminho, no in andar(base(arquivo), ()):
            yield arquivo, caminho, no


def contagem_de_revisao() -> dict:
    """{arquivo: (revisados, total)} e o total geral em "_total"."""
    por = {}
    for arquivo, _, no in cada_texto():
        r, t = por.get(arquivo, (0, 0))
        por[arquivo] = (r + bool(no.get("revisado")), t + 1)
    por["_total"] = (sum(r for r, _ in por.values()), sum(t for _, t in por.values()))
    return por


# --------------------------------------------------------------------------
# Textos de cada peça do mapa
# --------------------------------------------------------------------------
def texto_signo(ponto: str, signo: str) -> str:
    if ponto == "ascendente":
        return _t(base("ascendente").get(signo))
    return _t(base("planetas_signos").get(ponto, {}).get(signo))


def texto_casa(ponto: str, casa: int) -> str:
    return _t(base("planetas_casas").get(ponto, {}).get(casa))


def texto_aspecto(a: str, b: str, tipo: str) -> str:
    """Texto próprio para os pares de planetas pessoais; nos outros, montado
    com as peças (tema de cada ponto + dinâmica do aspecto + conselho)."""
    proprios = base("aspectos_pessoais")
    for chave in (f"{a}-{b}", f"{b}-{a}"):
        if chave in proprios and tipo in proprios[chave]:
            return _t(proprios[chave][tipo])
    p = base("pecas")
    tema_a, tema_b = _t(p["temas"].get(a)), _t(p["temas"].get(b))
    return (_t(p["dinamica"][tipo]).format(a=tema_a, b=tema_b) + " " + _t(p["conselho"][tipo])).strip()


def titulo_aspecto(asp: dict) -> str:
    return (f"{mo.PONTO_PT[asp['a']]} em {mo.ASPECTO_PT[asp['tipo']]} com "
            f"{mo.PONTO_PT[asp['b']]} (orbe {mo.grau_minuto(asp['orbe'])})")


def aviso(nome: str) -> str:
    return _t(base("pecas")["avisos"].get(nome))


def _dominante(contagem: dict) -> str | None:
    """A chave com mais pontos, se ela estiver sozinha no topo."""
    ordem = sorted(contagem.items(), key=lambda kv: -len(kv[1]))
    if not ordem or (len(ordem) > 1 and len(ordem[0][1]) == len(ordem[1][1])):
        return None
    return ordem[0][0]


def aspectos_principais(mapa: dict) -> list[dict]:
    """Aspectos do completo: sem os de geração (lento × lento), do mais exato."""
    lista = [a for a in mapa["aspectos"] if not (a["a"] in LENTOS and a["b"] in LENTOS)]
    return lista[:MAX_ASPECTOS_COMPLETO]


# --------------------------------------------------------------------------
# Amostra e completo
# --------------------------------------------------------------------------
def _nome_signo(ponto: dict) -> str:
    if ponto.get("signo_incerto"):
        return " ou ".join(mo.SIGNO_PT[s] for s in ponto["signos_possiveis"])
    return ponto["signo_pt"]


def triade(mapa: dict) -> list[dict]:
    """Sol, Lua e Ascendente: título, signo e texto (a Lua incerta traz os dois)."""
    itens = []
    for ponto in ("sol", "lua", "ascendente"):
        if ponto not in mapa["pontos"]:
            continue
        p = mapa["pontos"][ponto]
        if p.get("signo_incerto"):
            texto = " ".join(texto_signo(ponto, s) for s in p["signos_possiveis"])
        else:
            texto = texto_signo(ponto, p["signo"])
        itens.append({"ponto": ponto, "nome": mo.PONTO_PT[ponto], "signo": _nome_signo(p),
                      "grau": p["grau_texto"], "texto": texto})
    return itens


def montar_amostra(mapa: dict) -> dict:
    destaque = mo.aspecto_de_destaque(mapa)
    avisos = []
    if not mapa["tem_hora"]:
        avisos.append(aviso("sem_hora"))
    if mapa["pontos"]["lua"].get("signo_incerto"):
        avisos.append(aviso("lua_incerta"))
    return {
        "triade": triade(mapa),
        "aspecto": ({"titulo": titulo_aspecto(destaque), **destaque,
                     "texto": texto_aspecto(destaque["a"], destaque["b"], destaque["tipo"])}
                    if destaque else None),
        "avisos": avisos,
    }


def montar_secoes(mapa: dict) -> dict:
    """O relatório completo em seções: {título: [parágrafos]} (mesmo formato da
    védica, que o PDF, o live e o prompt da IA já sabem ler)."""
    s = {}
    avisos = []
    if not mapa["tem_hora"]:
        avisos.append(aviso("sem_hora"))
    if mapa["pontos"]["lua"].get("signo_incerto"):
        avisos.append(aviso("lua_incerta"))
    if mapa["casas"] and mapa["casas"]["sistema"] == "porfirio":
        avisos.append(aviso("casas_porfirio"))
    if avisos:
        s["Antes de começar"] = avisos

    s["Sol, Lua e Ascendente"] = [f"{i['nome']} em {i['signo']}. {i['texto']}" for i in triade(mapa)]

    planetas = []
    for ponto in ("mercurio", "venus", "marte", "jupiter", "saturno", "urano", "netuno", "plutao"):
        p = mapa["pontos"][ponto]
        r = " (retrógrado)" if p.get("retrogrado") else ""
        planetas.append(f"{mo.PONTO_PT[ponto]} em {p['signo_pt']}{r}. {texto_signo(ponto, p['signo'])}")
    planetas.append(aviso("geracao"))
    s["Os planetas nos signos"] = planetas

    if mapa["tem_hora"]:
        s["Os planetas nas casas"] = [
            f"{mo.PONTO_PT[ponto]} na casa {mapa['pontos'][ponto]['casa']}. "
            f"{texto_casa(ponto, mapa['pontos'][ponto]['casa'])}"
            for ponto in mo.PLANETAS]

    s["Os aspectos principais"] = [
        f"{titulo_aspecto(a)}. {texto_aspecto(a['a'], a['b'], a['tipo'])}"
        for a in aspectos_principais(mapa)] or ["Não há aspectos maiores dentro dos orbes usados."]

    pecas = base("pecas")
    equilibrio = []
    el, md = _dominante(mapa["elementos"]), _dominante(mapa["modalidades"])
    if el:
        equilibrio.append(_t(pecas["elemento_dominante"][el]))
    for e, pontos in mapa["elementos"].items():
        if len(pontos) <= 1:
            equilibrio.append(_t(pecas["elemento_ausente"][e]))
    if md:
        equilibrio.append(_t(pecas["modalidade_dominante"][md]))
    if equilibrio:
        s["Elementos e modalidades"] = equilibrio

    if mapa["regente_ascendente"]:
        r = mapa["regente_ascendente"]
        s["O regente do Ascendente"] = [
            f"{_t(pecas['regente_ascendente'][r['planeta']])} No seu mapa, "
            f"{mo.PONTO_PT[r['planeta']]} está em {mo.SIGNO_PT[r['signo']]}, na casa {r['casa']}."]

    s["Para terminar"] = [aviso("rodape")]
    return s


# --------------------------------------------------------------------------
# IA: só reescreve (mesma regra da védica)
# --------------------------------------------------------------------------
INSTRUCAO_LLM = """Você escreve o Mapa Natal da Padmini (astrologia ocidental, zodíaco tropical), em português do Brasil.

Regras:
- Use SOMENTE as informações do material abaixo. Não acrescente nenhum fato astrológico, posição, previsão ou traço de personalidade que não esteja nele.
- Reescreva o material como um texto corrido e acolhedor, mantendo as seções e os títulos.
- Quando dois trechos se reforçam ou se contradizem, diga isso explicitamente em vez de listar um depois do outro.
- Tendências, não sentenças: nada de "você vai", promessas, garantias ou previsões de eventos, saúde, morte ou dinheiro.
- Nada de frases que serviriam para qualquer pessoa.
- Escreva para a pessoa, usando "você". Nunca mencione "o material", "os trechos" ou como o texto foi feito.
- Termine com uma linha: "Este mapa é uma ferramenta de autoconhecimento, não uma previsão nem substituto de orientação profissional."
"""


def rascunho(secoes: dict) -> str:
    partes = []
    for titulo, conteudo in secoes.items():
        corpo = "\n\n".join(conteudo) if isinstance(conteudo, list) else conteudo
        partes.append(f"## {titulo}\n\n{corpo}")
    return "\n\n".join(partes)


def montar_prompt(secoes: dict) -> str:
    return INSTRUCAO_LLM + "\n\nMATERIAL:\n\n" + rascunho(secoes)

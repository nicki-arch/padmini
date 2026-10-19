"""
Padmini (versão ocidental) — do mapa calculado ao texto do relatório.

Mesma regra da védica: os FATOS vêm do cálculo (mapa_ocidental.py), o TEXTO vem
da base escrita por nós (conteudo/ocidental/textos/*.yaml). Sem IA: desde a
rodada 16 (16/out/2026) a ocidental não tem mais versão reescrita por IA.

Cada texto dos YAMLs tem `revisado: true/false`; `contagem_de_revisao()` diz
quantos faltam — é a lista de trabalho da família do Pedro
(`python scripts/revisao_textos.py`).
"""

from functools import lru_cache

import re

import yaml

import conteudo_privado
import textos

import mapa_ocidental as mo

PASTA = conteudo_privado.TEXTOS  # repositório privado (rodada 10); PADMINI_CONTEUDO_DIR troca a pasta
ARQUIVOS = ("planetas_signos", "planetas_casas", "ascendente", "aspectos_pessoais", "pecas", "sinastria", "numerologia",
            "tarot",
            # rodada 12: as dimensões Carreira, Dinheiro, Família e Propósito e os aspectos
            # próprios de Júpiter e Saturno com os planetas pessoais
            "meio_do_ceu", "cuspides", "nodo_norte", "regentes", "aspectos_sociais",
            # rodada 13: "O seu ano", a previsão dos próximos 12 meses (subpasta previsao/)
            "previsao/transitos", "previsao/casas", "previsao/eclipses", "previsao/revolucao",
            "previsao/pecas",
            # rodada 14: "A sua Lua no ano", o calendário lunar (subpasta calendario/)
            "calendario/lunacoes_casas", "calendario/lunacoes_signos", "calendario/lunacoes_pontos",
            "calendario/revolucao_lunar", "calendario/mercurio", "calendario/pecas")

# Aspectos só entre planetas lentos são de geração, não da pessoa: ficam fora
# da lista de "aspectos principais" do completo.
LENTOS = ("jupiter", "saturno", "urano", "netuno", "plutao")
MAX_ASPECTOS_COMPLETO = 14


@lru_cache(maxsize=None)
def base(arquivo: str) -> dict:
    return yaml.safe_load((PASTA / f"{arquivo}.yaml").read_text(encoding="utf-8")) or {}


def _t(no) -> str:
    # {indice} → o nome do índice (conteudo/ocidental/marca.yaml); a base guarda o
    # marcador, que é o que a planilha de revisão mostra
    return textos.com_indice((no or {}).get("texto", "")) if isinstance(no, dict) else ""


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
    """Texto próprio para Júpiter e Saturno com os pessoais (`aspectos_sociais`, rodada 12)
    e para os pares de planetas pessoais (`aspectos_pessoais`); nos outros (Urano, Netuno,
    Plutão, nodo, ângulos), montado com as peças (tema de cada ponto + dinâmica do
    aspecto + conselho)."""
    for arquivo in ("aspectos_sociais", "aspectos_pessoais"):
        proprios = base(arquivo)
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


# --------------------------------------------------------------------------
# Amostra por dimensões (rodada 9). A tela mostra, para cada dimensão ATIVA do
# catálogo (conteudo/ocidental/catalogo.yaml), só o começo do texto real dela
# (1 ou 2 frases). O resto que aparece desfocado na tela é enfeite fixo do
# template: o texto pago nunca vai para o navegador.
# --------------------------------------------------------------------------
_FIM_DE_FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý\"“])")
MAX_TRECHO = 260


def trecho(texto: str) -> str:
    """As primeiras 1–2 frases (a segunda só se couber em MAX_TRECHO caracteres)."""
    frases = _FIM_DE_FRASE.split((texto or "").strip())
    if not frases or not frases[0]:
        return ""
    saida = frases[0]
    if len(frases) > 1 and len(saida) + 1 + len(frases[1]) <= MAX_TRECHO:
        saida += " " + frases[1]
    return saida


def revisado_signo(ponto: str, signo: str) -> bool:
    """O texto daquele ponto naquele signo tem `revisado: true`? (selo da Dona Valderez)"""
    no = (base("ascendente").get(signo) if ponto == "ascendente"
          else base("planetas_signos").get(ponto, {}).get(signo))
    return bool(isinstance(no, dict) and no.get("revisado") is True)


# --------------------------------------------------------------------------
# Rodada 12: as 4 dimensões que se leem pelas casas (Carreira, Dinheiro, Família)
# e pelo Nodo Norte (Propósito). Não têm um ponto só: juntam o signo de uma cúspide
# (ou do Meio do Céu / Nodo), os planetas naquela casa e o regente dela. Sem hora
# de nascimento não há casas: cada uma mostra o que vale para o dia inteiro
# (Saturno, Júpiter, a Lua, o Nodo no signo) e um aviso.
#
# Não repetir texto: um planeta que já tem dimensão própria (Sol, Lua, Mercúrio,
# Vênus, Marte) entra só como referência curta (título + uma frase); o texto inteiro
# de um planeta usado aqui sai do "resto do mapa" (`usados_signo` / `usados_casa`).
# --------------------------------------------------------------------------
COMPOSTAS = ("carreira", "dinheiro", "familia", "proposito")
_CASA_DA_DIMENSAO = {"carreira": 10, "dinheiro": 2, "familia": 4}


def _no(arquivo: str, *chaves):
    no = base(arquivo)
    for c in chaves:
        no = no.get(c) if isinstance(no, dict) else None
    return no


def texto_meio_do_ceu(signo: str) -> str:
    return _t(_no("meio_do_ceu", signo))


def texto_cuspide(casa: int, signo: str) -> str:
    return _t(_no("cuspides", f"casa{casa}", signo))


def texto_nodo(signo: str | None = None, casa: int | None = None) -> str:
    return _t(_no("nodo_norte", "signos", signo)) if signo else _t(_no("nodo_norte", "casas", casa))


def texto_regente(casa: int, casa_do_regente: int) -> str:
    return _t(_no("regentes", f"casa{casa}", casa_do_regente))


def signo_da_cuspide(mapa: dict, casa: int) -> str:
    return mo.signo_de(mapa["casas"]["cuspides"][casa - 1])[0]


def _dimensao_do_ponto() -> dict:
    """{ponto: nome da dimensão} das dimensões de um ponto só que estão ativas."""
    import catalogo
    return {d["ponto"]: d["nome"] for d in catalogo.dimensoes_mapa() if d.get("ponto") and d["estado"] == "ativo"}


def _referencia(titulo: str, texto: str, dimensao: str) -> dict:
    return {"titulo": titulo, "texto": f"{trecho(texto)} Mais em {dimensao}.", "referencia": True}


def _bloco_casa(ponto: str, casa: int, onde: dict, usados_casa: set, dimensao: str) -> dict:
    """O texto do planeta na casa: inteiro na primeira vez; referência curta se ele já
    aparece noutra dimensão (`onde`: {ponto: nome da dimensão que mostra o texto})."""
    titulo, texto = f"{mo.PONTO_PT[ponto]} na casa {casa}", texto_casa(ponto, casa)
    if ponto in onde:
        return _referencia(titulo, texto, onde[ponto])
    onde[ponto] = dimensao
    usados_casa.add(ponto)
    return {"titulo": titulo, "texto": texto}


def _planetas_na_casa(mapa: dict, casa: int, onde: dict, usados_casa: set, dimensao: str) -> list[dict]:
    return [_bloco_casa(p, casa, onde, usados_casa, dimensao) for p in mo.PLANETAS
            if mapa["pontos"][p].get("casa") == casa]


def _regente(mapa: dict, casa: int) -> dict:
    planeta = mo.REGENTE[signo_da_cuspide(mapa, casa)]
    casa_r = mapa["pontos"][planeta]["casa"]
    return {"titulo": f"O regente da casa {casa}: {mo.PONTO_PT[planeta]} na casa {casa_r}",
            "texto": texto_regente(casa, casa_r)}


NOMES_COMPOSTAS = {"carreira": "Carreira", "dinheiro": "Dinheiro", "familia": "Família", "proposito": "Propósito"}


def dimensao_composta(chave: str, mapa: dict, onde: dict | None = None) -> dict:
    """Uma das 4 dimensões compostas: título, texto principal, blocos, aviso (sem hora)
    e os planetas cujo texto inteiro ela usa (para o resto do mapa não repetir).
    `onde`: {planeta: dimensão} dos textos de casa já mostrados (as de um ponto só e as
    compostas anteriores); é atualizado aqui."""
    pontos, hora = mapa["pontos"], mapa["tem_hora"]
    onde = _dimensao_do_ponto() if onde is None else onde
    nome = NOMES_COMPOSTAS[chave]
    d = {"blocos": [], "aviso": "", "usados_signo": set(), "usados_casa": set(), "revisado": False}

    def principal(ponto_pt: str, signo: str, texto: str, no_revisao=None):
        d.update({"ponto_pt": ponto_pt, "signo": signo, "signo_pt": mo.SIGNO_PT[signo],
                  "titulo": f"{ponto_pt} em {mo.SIGNO_PT[signo]}", "texto": texto,
                  "revisado": bool(isinstance(no_revisao, dict) and no_revisao.get("revisado") is True)})

    if chave == "proposito":
        nodo = pontos["nodo_norte"]
        principal("Nodo Norte", nodo["signo"], texto_nodo(signo=nodo["signo"]),
                  _no("nodo_norte", "signos", nodo["signo"]))
        if hora:
            d["blocos"].append({"titulo": f"Nodo Norte na casa {nodo['casa']}", "texto": texto_nodo(casa=nodo["casa"])})
        else:
            d["aviso"] = aviso("sem_hora_proposito")
        return d

    if not hora:
        if chave == "carreira":
            sat = pontos["saturno"]
            principal("Saturno", sat["signo"], texto_signo("saturno", sat["signo"]))
            d["usados_signo"].add("saturno")
        elif chave == "dinheiro":
            jup = pontos["jupiter"]
            principal("Júpiter", jup["signo"], texto_signo("jupiter", jup["signo"]))
            d["usados_signo"].add("jupiter")
        else:  # família: a Lua é da dimensão Emoções; aqui, só a referência (no lugar do texto,
            # para o título não sair duas vezes)
            lua = pontos["lua"]
            ref = _referencia("", texto_signo("lua", lua["signo"]), onde.get("lua", "Emoções"))
            principal("Lua", lua["signo"], ref["texto"])
            d["signo_pt"] = _nome_signo(lua)
            d["titulo"] = f"Lua em {d['signo_pt']}"
        d["aviso"] = aviso(f"sem_hora_{chave}")
        return d

    casa = _CASA_DA_DIMENSAO[chave]
    signo = signo_da_cuspide(mapa, casa)
    if chave == "carreira":
        principal("Meio do Céu", pontos["meio_do_ceu"]["signo"], texto_meio_do_ceu(pontos["meio_do_ceu"]["signo"]),
                  _no("meio_do_ceu", pontos["meio_do_ceu"]["signo"]))
    else:
        principal("Casa 2" if casa == 2 else "Fundo do Céu", signo, texto_cuspide(casa, signo),
                  _no("cuspides", f"casa{casa}", signo))
    d["blocos"] += _planetas_na_casa(mapa, casa, onde, d["usados_casa"], nome)
    d["blocos"].append(_regente(mapa, casa))
    if chave == "dinheiro":
        jup = pontos["jupiter"]
        d["blocos"].append({"titulo": f"Júpiter em {jup['signo_pt']}", "texto": texto_signo("jupiter", jup["signo"])})
        d["usados_signo"].add("jupiter")
        if jup["casa"] != casa:  # na casa 2, já entrou entre os planetas da casa
            d["blocos"].append(_bloco_casa("jupiter", jup["casa"], onde, d["usados_casa"], nome))
    if chave == "familia":
        lua = pontos["lua"]
        d["blocos"].append(_referencia(f"A sua Lua em {lua['signo_pt']}", texto_signo("lua", lua["signo"]),
                                       onde.get("lua", "Emoções")))
    return d


def compostas_ativas(mapa: dict) -> dict:
    """{chave: dimensão composta} das que estão ativas no catálogo, na ordem dele."""
    import catalogo
    onde = _dimensao_do_ponto()
    return {d["chave"]: dimensao_composta(d["chave"], mapa, onde) for d in catalogo.dimensoes_mapa()
            if d["chave"] in COMPOSTAS and d["estado"] == "ativo"}


def dimensoes_amostra(mapa: dict) -> list[dict]:
    """Um item por dimensão do catálogo, na ordem dele. Ativa com o ponto no mapa:
    o signo, o grau, o trecho, se o texto é revisado e a vaga da ilustração do
    signo. Sem o ponto (Ascendente sem hora) ou em breve: só o nome e o estado."""
    import catalogo
    itens = []
    compostas = compostas_ativas(mapa)
    for d in catalogo.dimensoes_mapa():
        item = {"chave": d["chave"], "nome": d["nome"], "rotulo": d["rotulo"], "descricao": d["descricao"],
                "estado": d["estado"], "vaga": d["vaga"]}
        if d["chave"] in compostas:  # rodada 12: a composta mostra o começo do texto principal
            c = compostas[d["chave"]]
            item.update({"ponto": d["chave"], "ponto_pt": c["ponto_pt"], "signo": c["signo"],
                         "signo_pt": c["signo_pt"], "titulo": c["titulo"], "composta": True,
                         "trecho": trecho(c["texto"] or c["aviso"]), "revisado": c["revisado"]})
            if c["revisado"]:
                item["selo"] = textos.SELO
            itens.append(item)
            continue
        p = mapa["pontos"].get(d["ponto"]) if d["estado"] == "ativo" and d["ponto"] else None
        if d["estado"] == "ativo" and p is None:
            item["estado"] = "sem_hora"
        elif p is not None:
            signo = p["signo"]
            item.update({"ponto": d["ponto"], "ponto_pt": mo.PONTO_PT[d["ponto"]], "signo": signo,
                         "signo_pt": _nome_signo(p), "grau": p["grau_texto"],
                         "titulo": f"{mo.PONTO_PT[d['ponto']]} em {_nome_signo(p)}",
                         "trecho": trecho(texto_signo(d["ponto"], signo)),
                         "revisado": revisado_signo(d["ponto"], signo), "vaga": f"signo-{signo}"})
            if item["revisado"]:
                item["selo"] = textos.SELO  # regra de honestidade: o selo vem só com texto revisado
        itens.append(item)
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


def dimensoes_completo(mapa: dict) -> list[dict]:
    """Leitura completa por dimensões (rodada 9, tela Site-Leitura): para cada
    dimensão ativa, o texto inteiro do ponto no signo, o da casa (com hora) e os
    aspectos DO MAPA que tocam aquele ponto, cada um com o seu texto."""
    import ilustracoes
    itens = []
    principais = aspectos_principais(mapa)
    compostas = compostas_ativas(mapa)
    for d in dimensoes_amostra(mapa):
        if d["estado"] != "ativo":
            itens.append(d)
            continue
        if d.get("composta"):
            c = compostas[d["chave"]]
            itens.append({**{k: v for k, v in d.items() if k != "trecho"}, "texto": c["texto"],
                          "blocos": c["blocos"], "aviso": c["aviso"], "casa": None, "texto_casa": "",
                          "aspectos": [], "vaga_planeta": d["vaga"]})
            continue
        ponto, p = d["ponto"], mapa["pontos"][d["ponto"]]
        if p.get("signo_incerto"):
            texto = " ".join(texto_signo(ponto, s) for s in p["signos_possiveis"])
        else:
            texto = texto_signo(ponto, p["signo"])
        casa = p.get("casa") if ponto in mo.PLANETAS and mapa["tem_hora"] else None
        aspectos = [{"titulo": titulo_aspecto(a), "tipo": a["tipo"], "orbe": mo.grau_minuto(a["orbe"]),
                     "com": mo.PONTO_PT[a["b"] if a["a"] == ponto else a["a"]],
                     "texto": texto_aspecto(a["a"], a["b"], a["tipo"])}
                    for a in principais if ponto in (a["a"], a["b"])]
        vaga_planeta = f"planeta-{ponto}" if f"planeta-{ponto}" in ilustracoes.VAGAS else d["vaga"]
        itens.append({**{k: v for k, v in d.items() if k != "trecho"}, "texto": texto, "casa": casa,
                      "texto_casa": texto_casa(ponto, casa) if casa else "", "aspectos": aspectos,
                      "vaga_planeta": vaga_planeta})
    return itens


def secoes_compostas(compostas: dict) -> dict:
    """As dimensões compostas como seções do relatório (PDF): {nome: [parágrafos]}."""
    import catalogo
    nomes = {d["chave"]: d["nome"] for d in catalogo.dimensoes_mapa()}
    s = {}
    for chave, c in compostas.items():
        paragrafos = ([c["aviso"]] if c["aviso"] else []) + ([f"{c['titulo']}. {c['texto']}"] if c["texto"] else [])
        paragrafos += [f"{b['titulo']}. {b['texto']}" for b in c["blocos"]]
        s[nomes[chave]] = paragrafos
    return s


def montar_secoes(mapa: dict, omitir: tuple = (), dimensoes: bool = True) -> dict:
    """O relatório completo em seções: {título: [parágrafos]} (mesmo formato da
    védica, que o PDF e o live já sabem ler).
    `omitir`: pontos que a página já mostra nas dimensões (rodada 9) — saem da
    tríade e das listas de planetas, para o texto não aparecer duas vezes.
    `dimensoes` (rodada 12): inclui as dimensões compostas ativas (Carreira, Dinheiro,
    Família, Propósito) como seções; a página, que já as mostra, passa False. Nos dois
    casos, o texto inteiro de um planeta que elas usam sai das listas de planetas."""
    compostas = compostas_ativas(mapa)
    omitir_signo = set(omitir).union(*(c["usados_signo"] for c in compostas.values()))
    omitir_casa = set(omitir).union(*(c["usados_casa"] for c in compostas.values()))
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

    if not {"sol", "lua", "ascendente"} <= set(omitir):
        s["Sol, Lua e Ascendente"] = [f"{i['nome']} em {i['signo']}. {i['texto']}" for i in triade(mapa)
                                      if i["ponto"] not in omitir]

    planetas = []
    for ponto in ("mercurio", "venus", "marte", "jupiter", "saturno", "urano", "netuno", "plutao"):
        if ponto in omitir_signo:
            continue
        p = mapa["pontos"][ponto]
        r = " (retrógrado)" if p.get("retrogrado") else ""
        planetas.append(f"{mo.PONTO_PT[ponto]} em {p['signo_pt']}{r}. {texto_signo(ponto, p['signo'])}")
    planetas.append(aviso("geracao"))
    s["Os planetas nos signos"] = planetas

    if mapa["tem_hora"]:
        s["Os planetas nas casas"] = [
            f"{mo.PONTO_PT[ponto]} na casa {mapa['pontos'][ponto]['casa']}. "
            f"{texto_casa(ponto, mapa['pontos'][ponto]['casa'])}"
            for ponto in mo.PLANETAS if ponto not in omitir_casa]

    if dimensoes:
        s.update(secoes_compostas(compostas))

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
# Sinastria (o casal) — textos de conteudo/ocidental/textos/sinastria.yaml
# --------------------------------------------------------------------------
def _cap(t: str) -> str:
    return t[:1].upper() + t[1:]


def _nomes(texto: str, a: str, b: str) -> str:
    return texto.replace("{a}", a).replace("{b}", b)


def texto_dimensao(chave: str, nota, a: str, b: str) -> str:
    import sinastria as si
    sb = base("sinastria")
    if nota is None:
        return _t(sb["sem_dados"])
    return _nomes(_t(sb["dimensoes"][chave][si.faixa(nota)]), a, b)


def descricao_dimensao(chave: str) -> str:
    return _t(base("sinastria")["dimensoes"][chave]["descricao"])


def texto_indice(indice: int, a: str, b: str) -> str:
    import sinastria as si
    return _nomes(_t(base("sinastria")["indice"][si.faixa(indice)]), a, b)


def texto_metodo() -> str:
    return _t(base("sinastria")["metodo"])


def texto_aspecto_cruzado(asp: dict, a: str, b: str) -> str:
    """asp["a"] é ponto de `a`, asp["b"] ponto de `b` (nomes das pessoas)."""
    sb = base("sinastria")
    tema_a = _t(sb["temas"][asp["a"]]).replace("{nome}", a)
    tema_b = _t(sb["temas"][asp["b"]]).replace("{nome}", b)
    dinamica = _t(sb["dinamica"][asp["tipo"]]).replace("{a}", tema_a).replace("{b}", tema_b)
    return _cap(dinamica) + " " + _t(sb["conselho"][asp["tipo"]])


def titulo_aspecto_cruzado(asp: dict, a: str, b: str) -> str:
    return (f"{mo.PONTO_PT[asp['a']]} de {a} em {mo.ASPECTO_PT[asp['tipo']]} com "
            f"{mo.PONTO_PT[asp['b']]} de {b} (orbe {mo.grau_minuto(asp['orbe'])})")


def texto_casa_sinastria(casa: int, quem: str, de_quem: str) -> str:
    return _t(base("sinastria")["casas"][casa]).replace("{quem}", quem).replace("{de_quem}", de_quem)


MAX_ASPECTOS_SINASTRIA = 12


def montar_sinastria(sin: dict, ma: dict, mb: dict, a: str, b: str, nivel: str) -> dict:
    """Amostra: índice, faixa e os pontos forte e de atenção. Completo: tudo."""
    import sinastria as si
    forte, atencao = si.ponto_forte_e_de_atencao(sin)
    dims = sin["dimensoes"]

    def dim(k):
        return {"chave": k, "titulo": dims[k]["titulo"], "nota": dims[k]["nota"],
                "descricao": descricao_dimensao(k), "texto": texto_dimensao(k, dims[k]["nota"], a, b)}

    avisos = []
    for nome, m in ((a, ma), (b, mb)):
        if not m["tem_hora"]:
            avisos.append(f"{nome}: sem hora de nascimento — sem Ascendente e sem casas no cruzamento.")
        elif m["casas"]["sistema"] == "porfirio":
            avisos.append(f"{nome}: nascimento perto de um polo — casas pelo sistema de Porfírio.")
    r = {"indice": sin["indice"], "indice_texto": texto_indice(sin["indice"], a, b),
         "metodo": texto_metodo(), "ponto_forte": dim(forte), "ponto_atencao": dim(atencao),
         "avisos": avisos}
    if nivel != "completo":
        return r
    r["dimensoes"] = [dim(k) for k in dims]
    r["aspectos"] = [{**x, "titulo": titulo_aspecto_cruzado(x, a, b), "texto": texto_aspecto_cruzado(x, a, b)}
                     for x in sin["aspectos"][:MAX_ASPECTOS_SINASTRIA]]
    casas = []
    for quem, de_quem, lista in ((a, b, sin["casas_a_em_b"]), (b, a, sin["casas_b_em_a"])):
        por_casa = {}
        for c in lista:
            por_casa.setdefault(c["casa"], []).append(mo.PONTO_PT[c["planeta"]])
        for casa in sorted(por_casa):
            casas.append({"quem": quem, "de_quem": de_quem, "casa": casa, "planetas": por_casa[casa],
                          "titulo": f"{', '.join(por_casa[casa])} de {quem} na casa {casa} de {de_quem}",
                          "texto": texto_casa_sinastria(casa, quem, de_quem)})
    r["casas"] = casas
    return r


# --------------------------------------------------------------------------
# Numerologia — textos de conteudo/ocidental/textos/numerologia.yaml
# --------------------------------------------------------------------------
def _numero(chave: str, valor) -> dict:
    import numerologia as nu
    b = base("numerologia")
    return {"chave": chave, "nome": nu.NOME_PT[chave], "valor": valor,
            "mestre": valor in nu.MESTRES, "descricao": _t(b["descricao"][chave]),
            "texto": _t(b[chave].get(valor)) if valor is not None else
            "Este número precisa de pelo menos uma letra desse tipo no nome."}


def montar_numerologia(res: dict, nivel: str) -> dict:
    """Amostra: o Caminho de Vida. Completo: os seis números, com o Ano Pessoal."""
    n = res["numeros"]
    r = {"caminho_de_vida": _numero("caminho_de_vida", n["caminho_de_vida"])}
    if nivel == "completo":
        r["numeros"] = [_numero(k, n[k]) for k in
                        ("caminho_de_vida", "expressao", "alma", "personalidade", "dia", "ano_pessoal")]
        r["ano_corrente"] = res["ano_corrente"]
    return r


# --------------------------------------------------------------------------
# Tarot — textos de conteudo/ocidental/textos/tarot.yaml
# --------------------------------------------------------------------------
def _carta(c: dict, nivel: str) -> dict:
    b = base("tarot")
    texto = b["cartas"][c["chave"]]
    r = {k: c[k] for k in ("chave", "nome", "rotulo", "arcano", "naipe", "posicao", "posicao_pt")}
    r["frase"] = _t(texto["frase"])
    if nivel == "completo":
        r["moldura"] = _t(b["posicoes"][c["posicao"]])
        r["leitura"] = _t(texto["leitura"])
    return r


def conjunto_tarot(cartas: list[dict]) -> list[str]:
    """Peças da leitura de conjunto: quantos arcanos maiores, o naipe que
    predomina (2 ou 3 menores do mesmo naipe) e o fecho."""
    b = base("tarot")["conjunto"]
    maiores = sum(c["arcano"] == "maior" for c in cartas)
    partes = [_t(b["maiores"][maiores])]
    naipes = [c["naipe"] for c in cartas if c["naipe"]]
    dominante = next((n for n in set(naipes) if naipes.count(n) >= 2), None)
    if dominante:
        partes.append(_t(b["naipe"][dominante]))
    partes.append(_t(b["fecho"]))
    return partes


def montar_tarot(cartas: list[dict], nivel: str) -> dict:
    """Amostra: as 3 cartas com nome e uma frase. Completo: a leitura de cada
    carta na sua posição e a leitura de conjunto."""
    r = {"cartas": [_carta(c, nivel) for c in cartas]}
    if nivel == "completo":
        r["conjunto"] = conjunto_tarot(cartas)
    return r



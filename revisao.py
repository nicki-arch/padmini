"""
Padmini (versão ocidental) — revisão dos textos pela família do Pedro.

A família não usa GitHub nem edita YAML: ela recebe uma PLANILHA.

    python scripts/exportar_revisao.py                     # gera revisao-textos.xlsx
    python scripts/importar_revisao.py revisao-textos.xlsx # mostra o que mudaria
    python scripts/importar_revisao.py revisao-textos.xlsx --gravar

Este módulo é o que os dois scripts (e os testes) compartilham:
  - `itens()`: cada texto da base, com um id estável, onde ele aparece no site
    (em português) e os limites de tamanho;
  - `problemas()`: as regras de tom e tamanho — as MESMAS que os testes cobram;
  - `gravar()`: grava textos e o `revisado: true` nos YAMLs, mexendo só nos
    blocos alterados (comentários e o resto do arquivo ficam intactos) e
    conferindo o resultado antes de substituir o arquivo.

id = "<arquivo>:<caminho>", ex.: "planetas_signos:venus/libra". Não muda
enquanto o texto existir, então a planilha de uma semana ainda vale na outra.
"""

import re
import tempfile
import textwrap
from pathlib import Path

import yaml

import mapa_ocidental as mo
import montar_texto_ocidental as mt

# --------------------------------------------------------------------------
# Regras de tom (as mesmas dos testes)
# --------------------------------------------------------------------------
PROIBIDOS = ["morte", "morrer", "morrerá", "doença", "doente", "saúde", "câncer de", "cirurgia",
             "diagnóstico", "acidente", "enriquec", "ficar rico", "fortuna", "herança", "loteria",
             "você vai ", "você irá", "com certeza", "destino é", "está condenad"]
PERIGOSOS = re.compile(r"<\s*script|javascript:|\bon\w+\s*=", re.I)
MARCADOR = re.compile(r"\{[a-z_]+\}")

PRODUTO = {"planetas_signos": "Mapa natal", "planetas_casas": "Mapa natal", "ascendente": "Mapa natal",
           "aspectos_pessoais": "Mapa natal", "pecas": "Mapa natal", "sinastria": "Sinastria",
           "numerologia": "Numerologia", "tarot": "Tarot"}


def limites(arquivo: str, caminho: tuple) -> tuple[int, int] | None:
    """(mínimo, máximo) de palavras, ou None para peças curtas sem limite."""
    if arquivo in ("planetas_signos", "planetas_casas", "ascendente", "aspectos_pessoais"):
        return 60, 120
    if arquivo == "sinastria":
        if caminho[0] == "dimensoes" and caminho[-1] in ("alta", "media", "baixa"):
            return 60, 120
        if caminho[0] == "casas":
            return 55, 120
        return None
    if arquivo == "numerologia":
        return None if caminho[0] == "descricao" else (60, 120)
    if arquivo == "tarot":
        return (40, 90) if caminho[0] == "cartas" and caminho[-1] == "leitura" else None
    return None


def problemas(texto: str, arquivo: str, caminho: tuple, original: str = "") -> list[str]:
    """O que impede este texto de entrar no site (lista vazia = ok)."""
    erros = []
    t = " ".join(str(texto or "").split())
    if not t:
        return ["texto vazio"]
    faixa = limites(arquivo, caminho)
    if faixa:
        # conta com os marcadores trocados por um nome, como aparece no site
        n = len(MARCADOR.sub("Ana", t).split())
        if not faixa[0] <= n <= faixa[1]:
            erros.append(f"tem {n} palavras; o certo é de {faixa[0]} a {faixa[1]}")
    baixo = t.lower()
    for p in PROIBIDOS:
        if p in baixo:
            erros.append(f'usa "{p.strip()}" (proibido: previsão/sentença)')
    if PERIGOSOS.search(t):
        erros.append("tem código (script) no texto")
    if original and set(MARCADOR.findall(t)) != set(MARCADOR.findall(original)):
        erros.append("os marcadores entre chaves ({a}, {b}, {nome}...) precisam ficar iguais aos do original")
    return erros


# --------------------------------------------------------------------------
# Onde cada texto aparece (em português, para a planilha)
# --------------------------------------------------------------------------
NOME_NUMERO = {"caminho_de_vida": "Caminho de Vida", "expressao": "Expressão", "alma": "Alma",
               "personalidade": "Personalidade", "dia": "Dia de nascimento", "ano_pessoal": "Ano Pessoal"}


def _pt(chave: str) -> str:
    return (mo.PONTO_PT.get(chave) or mo.SIGNO_PT.get(chave) or mo.ASPECTO_PT.get(chave)
            or mo.ELEMENTO_PT.get(chave) or mo.MODALIDADE_PT.get(chave) or NOME_NUMERO.get(chave)
            or chave.replace("_", " "))


def onde_aparece(arquivo: str, c: tuple) -> str:
    if arquivo == "planetas_signos":
        return f"Mapa natal · {_pt(c[0])} em {_pt(c[1])}"
    if arquivo == "planetas_casas":
        return f"Mapa natal · {_pt(c[0])} na casa {c[1]}"
    if arquivo == "ascendente":
        return f"Mapa natal · Ascendente em {_pt(c[0])}"
    if arquivo == "aspectos_pessoais":
        a, b = c[0].split("-")
        return f"Mapa natal · {_pt(a)} em {_pt(c[1])} com {_pt(b)}"
    if arquivo == "pecas":
        grupo = {"temas": "tema usado para montar aspectos", "dinamica": "frase de aspecto montado",
                 "conselho": "conselho de aspecto montado", "elemento_dominante": "elemento que mais aparece",
                 "elemento_ausente": "elemento que quase não aparece",
                 "modalidade_dominante": "modalidade que mais aparece",
                 "regente_ascendente": "regente do Ascendente", "avisos": "aviso"}.get(c[0], c[0])
        return f"Mapa natal · {grupo}: {_pt(c[-1])}"
    if arquivo == "sinastria":
        if c[0] == "dimensoes":
            titulo = next((d["titulo"] for k, d in __import__("sinastria").DIMENSOES.items() if k == c[1]), c[1])
            nivel = {"alta": "nota alta", "media": "nota média", "baixa": "nota baixa",
                     "descricao": "descrição curta"}.get(c[2], c[2])
            return f"Sinastria · {titulo} ({nivel})"
        if c[0] == "casas":
            return f"Sinastria · planetas de um na casa {c[1]} do outro"
        if c[0] == "indice":
            return f"Sinastria · Índice Padmini ({ {'alta': 'alto', 'media': 'médio', 'baixa': 'baixo'}[c[1]] })"
        grupo = {"temas": "tema usado nos aspectos", "dinamica": "frase de aspecto",
                 "conselho": "conselho de aspecto", "metodo": "como o Índice Padmini é calculado",
                 "sem_dados": "aviso de dimensão que precisa da hora de nascimento"
                 }.get(c[0], c[0].replace("_", " "))
        return f"Sinastria · {grupo}{': ' + _pt(c[-1]) if len(c) > 1 else ''}"
    if arquivo == "numerologia":
        return f"Numerologia · {_pt(c[0])} {c[1]}" if len(c) > 1 else f"Numerologia · {_pt(c[0])}"
    if arquivo == "tarot":
        import tarot
        if c[0] == "cartas":
            nome = next((x["nome"] for x in tarot.CARTAS if x["chave"] == c[1]), c[1])
            return f"Tarot · {nome} · " + ("frase da amostra" if c[2] == "frase" else "leitura do completo")
        if c[0] == "posicoes":
            return f"Tarot · abertura da posição {tarot.POSICAO_PT[c[1]]}"
        if c[0] == "conjunto":
            if c[1] == "maiores":
                return f"Tarot · leitura de conjunto: {c[2]} arcano(s) maior(es)"
            if c[1] == "naipe":
                return f"Tarot · leitura de conjunto: predomina {c[2].capitalize()}"
            return "Tarot · leitura de conjunto: fecho"
        return "Tarot · " + " · ".join(c)
    return f"{arquivo} · {'/'.join(c)}"


def itens() -> list[dict]:
    lista = []
    for arquivo, caminho, no in mt.cada_texto():
        lista.append({"id": f"{arquivo}:{'/'.join(caminho)}", "arquivo": arquivo, "caminho": caminho,
                      "produto": PRODUTO.get(arquivo, arquivo), "onde": onde_aparece(arquivo, caminho),
                      "texto": " ".join(str(no["texto"]).split()), "revisado": bool(no.get("revisado")),
                      "limites": limites(arquivo, caminho)})
    return lista


# --------------------------------------------------------------------------
# Gravação nos YAMLs, sem destruir comentários nem o resto do arquivo
# --------------------------------------------------------------------------
def _chave_re(chave: str, nivel: int) -> re.Pattern:
    return re.compile(r"^" + " " * nivel + re.escape(str(chave)) + r":(\s|$)")


def _fim_do_bloco(linhas: list[str], i: int, nivel: int) -> int:
    """Primeira linha depois de i que volta a um recuo <= nivel (e não é vazia/comentário)."""
    j = i + 1
    while j < len(linhas):
        l = linhas[j]
        if l.strip() and not l.lstrip().startswith("#") and len(l) - len(l.lstrip()) <= nivel:
            break
        j += 1
    while j > i + 1 and not linhas[j - 1].strip():  # não engole linhas em branco do fim
        j -= 1
    return j


def _reescrever(linhas: list[str], caminho: tuple, texto: str | None, revisado: bool | None) -> None:
    ini, fim, nivel = 0, len(linhas), 0
    for n, chave in enumerate(caminho):
        pat = _chave_re(chave, nivel)
        i = next(k for k in range(ini, fim) if pat.match(linhas[k]))
        if n == len(caminho) - 1:
            break
        ini, fim, nivel = i + 1, _fim_do_bloco(linhas, i, nivel), nivel + 2
    bloco = yaml.safe_load("\n".join(linhas[i:_fim_do_bloco(linhas, i, nivel)]))
    atual = bloco[_chave_real(bloco, caminho[-1])]
    texto = " ".join((atual["texto"] if texto is None else texto).split())
    revisado = atual.get("revisado", False) if revisado is None else revisado
    corpo = textwrap.wrap(texto, 76 - nivel - 4, break_long_words=False, break_on_hyphens=False)
    novo = ([" " * nivel + f"{caminho[-1]}:", " " * (nivel + 2) + f"revisado: {'true' if revisado else 'false'}",
             " " * (nivel + 2) + "texto: >-"] + [" " * (nivel + 4) + l for l in corpo])
    linhas[i:_fim_do_bloco(linhas, i, nivel)] = novo


def gravar(alteracoes: list[dict]) -> list[str]:
    """alteracoes: [{"arquivo", "caminho", "texto" (ou None), "revisado" (ou None)}].
    Grava cada arquivo só se, relendo, TODO o conteúdo bater: os nós alterados
    com os valores novos e todo o resto idêntico ao de antes. Devolve os
    arquivos gravados."""
    por_arquivo: dict[str, list[dict]] = {}
    for a in alteracoes:
        por_arquivo.setdefault(a["arquivo"], []).append(a)
    gravados = []
    for arquivo, lista in por_arquivo.items():
        caminho_arq = mt.PASTA / f"{arquivo}.yaml"
        original = caminho_arq.read_text(encoding="utf-8")
        esperado = yaml.safe_load(original)
        linhas = original.split("\n")
        for a in lista:
            _reescrever(linhas, a["caminho"], a["texto"], a["revisado"])
            no = esperado
            for chave in a["caminho"]:
                no = no[_chave_real(no, chave)]
            if a["texto"] is not None:
                no["texto"] = " ".join(a["texto"].split())
            if a["revisado"] is not None:
                no["revisado"] = a["revisado"]
        novo = "\n".join(linhas)
        if _normalizar(yaml.safe_load(novo)) != _normalizar(esperado):
            raise RuntimeError(f"{arquivo}.yaml: a regravação não bateu com o esperado; nada foi gravado")
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=caminho_arq.parent, delete=False,
                                         suffix=".tmp") as tmp:
            tmp.write(novo)
        Path(tmp.name).replace(caminho_arq)
        gravados.append(arquivo)
    mt.base.cache_clear()
    return gravados


def _chave_real(no: dict, chave: str):
    """No YAML algumas chaves são números (casas 1..12, números 11/22/33)."""
    if chave in no:
        return chave
    return int(chave) if str(chave).isdigit() and int(chave) in no else chave


def _normalizar(no):
    """Compara textos ignorando quebras de linha/espaços (o YAML dobra as linhas)."""
    if isinstance(no, dict):
        return {k: _normalizar(v) for k, v in no.items()}
    if isinstance(no, list):
        return [_normalizar(v) for v in no]
    if isinstance(no, str):
        return " ".join(no.split())
    return no

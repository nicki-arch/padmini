"""
Padmini (versão ocidental) — NUMEROLOGIA PITAGÓRICA.

Entrada: o nome completo de REGISTRO (o da certidão de nascimento) e a data de
nascimento. Não usa hora nem cidade.

Regras (documentadas também em docs/ocidental.md):

  - Tabela pitagórica: A=1 … I=9, J=1 … R=9, S=1 … Z=9.
  - Nome: acentos removidos (Á→A, Ã→A, Ê→E…), Ç→C; tudo que não é letra
    (espaço, hífen, apóstrofo) é ignorado.
  - Vogais: A, E, I, O, U e **Y**. Consoantes: o resto, inclusive **W**.
    Por quê: em nomes brasileiros o Y quase sempre soa como "i" (Yasmin,
    Thaynara, Kelly) e o W soa como "v" ou "u" consonantal (Wagner,
    Wellington, William). Decisão nossa; a tradição tem variantes.
  - Redução: soma dos algarismos até sobrar 1 algarismo, MENOS os números
    mestres 11, 22 e 33, que não reduzem.
  - Caminho de Vida: reduz o dia, o mês e o ano SEPARADAMENTE (cada um
    respeitando os mestres) e depois soma e reduz de novo. É uma das
    variantes; outra soma todos os algarismos da data de uma vez e dá outro
    resultado em algumas datas (ex.: 04/01/1950 → 11 aqui; 2 na outra).
  - Expressão: soma de TODAS as letras do nome, reduzida.
  - Alma: só as vogais. Personalidade: só as consoantes.
  - Dia de nascimento: o dia reduzido (29 → 11, 22 fica 22).
  - Ano Pessoal: dia + mês de nascimento + ANO CORRENTE, cada um reduzido e
    depois somados e reduzidos (mesma lógica do Caminho de Vida).
"""

import unicodedata
from datetime import date

MESTRES = (11, 22, 33)
VOGAIS = set("AEIOUY")
NUMEROS = ("caminho_de_vida", "expressao", "alma", "personalidade", "dia", "ano_pessoal")
NOME_PT = {"caminho_de_vida": "Caminho de Vida", "expressao": "Expressão", "alma": "Alma",
           "personalidade": "Personalidade", "dia": "Dia de nascimento", "ano_pessoal": "Ano Pessoal"}
VALORES = (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 22, 33)


def normalizar_nome(nome: str) -> str:
    """'João da Conceição' → 'JOAODACONCEICAO' (só letras A–Z)."""
    sem_acento = unicodedata.normalize("NFKD", str(nome or "")).encode("ascii", "ignore").decode()
    return "".join(c for c in sem_acento.upper() if "A" <= c <= "Z")


def valor(letra: str) -> int:
    return (ord(letra) - ord("A")) % 9 + 1


def reduzir(n: int) -> int:
    while n > 9 and n not in MESTRES:
        n = sum(int(d) for d in str(n))
    return n


def caminho_de_vida(d: date) -> int:
    return reduzir(reduzir(d.day) + reduzir(d.month) + reduzir(d.year))


def ano_pessoal(d: date, ano_corrente: int) -> int:
    return reduzir(reduzir(d.day) + reduzir(d.month) + reduzir(ano_corrente))


def calcular_numerologia(nome_completo: str, nascimento: date, ano_corrente: int | None = None) -> dict:
    letras = normalizar_nome(nome_completo)
    if not letras:
        raise ValueError("O nome precisa ter letras.")
    ano_corrente = ano_corrente or date.today().year
    vogais = [valor(c) for c in letras if c in VOGAIS]
    consoantes = [valor(c) for c in letras if c not in VOGAIS]
    return {
        "nome_normalizado": letras,
        "ano_corrente": ano_corrente,
        "numeros": {
            "caminho_de_vida": caminho_de_vida(nascimento),
            "expressao": reduzir(sum(valor(c) for c in letras)),
            "alma": reduzir(sum(vogais)) if vogais else None,
            "personalidade": reduzir(sum(consoantes)) if consoantes else None,
            "dia": reduzir(nascimento.day),
            "ano_pessoal": ano_pessoal(nascimento, ano_corrente),
        },
    }

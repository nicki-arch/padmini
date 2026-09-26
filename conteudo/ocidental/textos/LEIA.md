# Textos da versão ocidental — como editar

Cada texto tem dois campos:

```yaml
aries:
  revisado: false      # troque para true quando a família revisar
  texto: >-
    O texto em si. Pode quebrar a linha à vontade: o ">-" junta tudo num parágrafo.
```

Regras de tom (há teste que confere algumas):
- português do Brasil, falando com a pessoa ("você");
- 60 a 120 palavras por texto (mapa, sinastria e numerologia);
- **tarot: 40 a 90 palavras** na leitura de cada carta — mais curto de propósito,
  porque a leitura completa junta três cartas, a moldura de cada posição e a
  leitura de conjunto (a frase da amostra, as molduras e as peças de conjunto
  não têm limite, mas são curtas);
- concreto: um exemplo de comportamento, do tipo "numa discussão, você…";
- tendência, não sentença: "tende a", "pode", "costuma" — nada de "você vai";
- NADA de previsão de saúde, morte ou dinheiro;
- evite frases que serviriam para qualquer pessoa ("você é especial e sensível").

Quanto falta revisar: `python scripts/revisao_textos.py`.

**A família não precisa editar este YAML.** A revisão é feita numa planilha:

    python scripts/exportar_revisao.py        # gera revisao-textos.xlsx (vai para o Drive)
    python scripts/importar_revisao.py revisao-textos.xlsx           # mostra o que mudaria
    python scripts/importar_revisao.py revisao-textos.xlsx --gravar  # grava aqui

A importação recusa (e lista) texto fora do tamanho, com palavra proibida ou com
os marcadores {a}/{b}/{nome} trocados. As regras ficam em `revisao.py`.

Arquivos:
- `planetas_signos.yaml` — 10 planetas × 12 signos
- `planetas_casas.yaml` — 10 planetas × 12 casas
- `ascendente.yaml` — 12 signos
- `aspectos_pessoais.yaml` — Sol, Lua, Mercúrio, Vênus e Marte entre si, 5 aspectos cada par
- `pecas.yaml` — peças para montar os aspectos dos outros pares, elementos,
  modalidades, regente do Ascendente e avisos
- `sinastria.yaml` — dimensões, casas, Índice Padmini e peças da sinastria
- `numerologia.yaml` — descrição curta de cada número + 12 textos para cada um dos 6 números
- `tarot.yaml` — as 78 cartas (frase da amostra + leitura de 40 a 90 palavras),
  a moldura de cada posição (Situação, Desafio, Conselho) e as peças da leitura
  de conjunto (quantos arcanos maiores saíram, naipe que predomina, fecho).
  O nome da carta vem do código (`tarot.py`), por isso os textos não precisam
  repeti-lo — e cartas como "A Morte" e "A Roda da Fortuna" não têm o nome
  escrito no texto, porque "morte" e "fortuna" são palavras barradas.

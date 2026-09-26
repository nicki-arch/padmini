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
- 60 a 120 palavras por texto;
- concreto: um exemplo de comportamento, do tipo "numa discussão, você…";
- tendência, não sentença: "tende a", "pode", "costuma" — nada de "você vai";
- NADA de previsão de saúde, morte ou dinheiro;
- evite frases que serviriam para qualquer pessoa ("você é especial e sensível").

Quanto falta revisar: `python scripts/revisao_textos.py`.

Arquivos:
- `planetas_signos.yaml` — 10 planetas × 12 signos
- `planetas_casas.yaml` — 10 planetas × 12 casas
- `ascendente.yaml` — 12 signos
- `aspectos_pessoais.yaml` — Sol, Lua, Mercúrio, Vênus e Marte entre si, 5 aspectos cada par
- `pecas.yaml` — peças para montar os aspectos dos outros pares, elementos,
  modalidades, regente do Ascendente e avisos

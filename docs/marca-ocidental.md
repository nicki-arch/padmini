> **Substituída em 29/set/2026** pela marca **Valderez Astrologia** (ver `docs/valderez.md`).
> Tela, e-mails e PDF já usam a marca nova.

# Marca da versão ocidental — "Almanaque" (rodada 3, 26/set/2026)

## Por quê
A marca "Lótus à meia-luz" (fundo ameixa, acento açafrão, lótus em dois tons,
"पद्मिनी" em devanágari) foi desenhada para a astrologia **védica**. Na versão
ocidental ela sinalizava a coisa errada: Índia e Jyotish, para um produto de mapa
natal, tarot e numerologia. O nome Padmini fica (decisão do Nicolas); muda a
roupa, não a casa: mesmas páginas, mesmos componentes, só tokens e marca.

A astrologia ocidental, o tarot e a numerologia chegaram ao Brasil pelos
**almanaques**, pelos atlas celestes europeus e pelo baralho **Rider-Waite**
(1909, litografia de cores chapadas com contorno). A identidade vem dessa gráfica
impressa, não do "cósmico digital": nada de degradê roxo-azul, céu estrelado,
neon, glassmorphism ou dourado metálico.

## Onde mora (fonte única)
- `paleta.py` — cores e fontes de **cada versão**, para tela, e-mail e papel (PDF).
  A védica tem aí os mesmos valores de sempre.
- `static/ocidental/tema.css` — **gerado** de `paleta.py`
  (`python scripts/gerar_tema_css.py`; há teste que confere). Carregado depois do
  `base.css` nas páginas da ocidental; só troca tokens e detalhes de impressão.
- `marca.py` — o lótus em traço (SVG das páginas, favicon, PDF, imagens).
- `scripts/gerar_og_ocidental.py` — imagens de compartilhamento (`static/og-oc-*.png`),
  com as fontes de `fontes/` embutidas (sem rede).
- `/estilo?previa=<PADMINI_PREVIA_CHAVE>` — vitrine para aprovar: paleta com os
  contrastes, tipografia, botões, campos, card do mapa, cartas, card do casal e
  e-mail. Fora do buscador.

## Tela (tokens) e contrastes (WCAG)
Regra do `base.css`: texto de corpo entre **10:1 e 13:1** (acima disso o claro
"sangra" no escuro); nada legível abaixo de **4,5:1**. Contrastes sobre
fundo · superfície · superfície elevada.

| Nome | Token | Valor | Uso | Contraste |
|---|---|---|---|---|
| Tinta (fundo) | `--ground` | `#121a2b` | fundo da página | — |
| Tinta clara | `--ground-2` | `#19223a` | cards e superfícies | — |
| Tinta elevada | `--ground-3` | `#212c45` | campos e superfície elevada | — |
| Papel | `--ink` | `#e6dac3` | texto principal | 12.56:1 · 11.4:1 · 10.05:1 |
| Papel envelhecido | `--muted` | `#c6b99e` | texto secundário | 8.97:1 · 8.14:1 · 7.17:1 |
| Papel apagado | `--faint` | `#a59a82` | notas e placeholder | 6.24:1 · 5.67:1 · 4.99:1 |
| Ouro velho | `--saffron` | `#d4a23a` | botão, destaque, traço da marca | 7.47:1 · 6.78:1 · 5.98:1 |
| Zarcão | `--blush` | `#e2744f` | segundo acento, ênfase | 5.66:1 · 5.14:1 · 4.53:1 |
| Sálvia | `--sage` | `#9aab84` | apoio (ok/positivo) | 7.06:1 · 6.41:1 · 5.65:1 |
| Tinta do botão | `--on-accent` | `#17120a` | texto sobre o ouro | 8.01:1 sobre o ouro |
| Erro | `--erro` | `#f2a493` | mensagens de erro | 8.7:1 · 7.89:1 · 6.95:1 |

Os nomes dos tokens são os do `base.css` (`--saffron` = "acento principal",
`--blush` = "segundo acento"), para os componentes servirem às duas versões.
O zarcão passa de 4,5:1 até na superfície elevada; o ouro nunca é usado em texto
pequeno sobre papel.

## Tipografia
- **Títulos: Young Serif** (Google Fonts, OFL). Serifa de impressão antiga, de
  tipo "cheio" de tinta, que aguenta tamanho pequeno no fundo escuro (o nome das
  cartas sai a 15px). Consideradas e descartadas (sem teste em tela): IM Fell English (mais "almanaque", mas imita o
  defeito da impressão e borra em tela e em corpo pequeno) e Newsreader (ótima,
  mas neutra demais para marcar a mudança). Young Serif só tem o peso 400 e não
  tem itálico: a **ênfase é a segunda tinta** (zarcão), como na impressão a duas
  cores, e `font-synthesis: none` impede negrito/itálico falsos.
- **Corpo: Source Sans 3** (Google Fonts, OFL). Sans humanista, de leitura longa;
  Figtree é mais geométrica.
- Fallback declarado: `Georgia, 'Times New Roman', serif` e
  `'Segoe UI', system-ui, -apple-system, sans-serif`.
- Rótulos em **versaletes** espaçados (`font-variant-caps: all-small-caps`,
  `letter-spacing: .16em`): SITUAÇÃO, DESAFIO, CONSELHO.
- No PDF e nas imagens: os TTF em `fontes/` (com as licenças OFL ao lado).

## Marca
O lótus continua (Padmini = "a do lótus"; não é exclusivo da Índia), redesenhado
em **traço de gravura**: linha única, sem preenchimento de dois tons, com um
pequeno **astro de quatro pontas** no centro, em zarcão. O mesmo desenho a 16px
(favicon, traço mais grosso, sobre a tinta) e grande (imagens). Nenhum devanágari
na versão ocidental.

## Detalhes de impressão
- Numeral romano nas cartas (arcanos maiores) e nos passos da home.
- Filetes finos em vez de caixas com sombra (card do casal, autocomplete; o card
  compartilhável e as imagens têm filete duplo de almanaque).
- Símbolos de naipe em traço, **um peso de linha só** (1,8px em qualquer tamanho,
  `vector-effect: non-scaling-stroke`), ouro com um detalhe em zarcão. A roda do
  mapa usa abreviaturas dos signos (não havia glifos a redesenhar).
- Fundo chapado, sem o brilho do topo.
- No `/live`, a "linha laranja" do Pedro é o zarcão.

## E-mail
`paleta.email("ocidental")`: fundo `#121a2b`, texto `#e6dac3`, botão
`#d4a23a` com texto `#17120a`, secundário `#c6b99e`, cantos de
6px no botão. O e-mail não baixa fonte: onde não houver Young Serif,
cai no Georgia.

## Papel (PDF)
| Papel | Valor | Contraste no fundo |
|---|---|---|
| tinta | `#121a2b` | 16.1:1 |
| tinta_suave | `#4a5468` | 7.05:1 |
| noite | `#121a2b` | — |
| acento | `#a8401f` | 5.69:1 |
| acento_suave | `#f4e2d6` | — |
| superficie | `#efe7d4` | — |
| fundo | `#faf6ec` | — |
| linha | `#ddd2bb` | — |
| lotus | `#9a7314` | 4.02:1 |
| harmonico | `#4f6b45` | 5.53:1 |

(`lotus` = ouro velho, só em desenho; texto nunca.)

## Checkout da Cakto (para configurar no painel, se quiser alinhar)
Fundo `#121a2b` ou claro `#faf6ec`; botão `#d4a23a` com texto
`#17120a`; destaque `#e2744f`.

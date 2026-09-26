# Versão ocidental — decisões de método

Rodada 1 (26/set/2026). Tudo aqui vive atrás de `PADMINI_SISTEMA=ocidental`
(ver `sistema.py`); com `vedica` (padrão) nada disto aparece no site.

## Mapa natal (`mapa_ocidental.py`)

| Tema | Decisão | Por quê |
|---|---|---|
| Zodíaco | Tropical | É o da astrologia ocidental |
| Efemérides | Swiss Ephemeris, modo Moshier (`FLG_MOSEPH`) | Sem arquivo de efemérides; erro medido contra o astro-seek ≤ 8" nos planetas |
| Fuso / horário de verão | `julian_day_utc` da védica (zoneinfo) | Já resolve o histórico brasileiro; 4 casos de horário de verão conferidos |
| Casas | Placidus; Porfírio dentro do círculo polar | Placidus não existe acima de ~66°; o resultado diz qual foi usado |
| Nodo | Verdadeiro | Padrão do astro.com (a tabela padrão deles lista "TrueNode"); o astro-seek usa o médio por padrão |
| Quíron | Fora | O Moshier não tem |
| Aspectos | 0°, 60°, 90°, 120°, 180° | Maiores |
| Orbes | 8°; 10° com Sol ou Lua; sextil 6° | Brief; definidos só em `orbe_maximo` |
| Aspectos no mapa | 10 planetas + Ascendente e MC; Nodo fora | Nodo lido por signo e casa |
| "Aspectos principais" do completo | Sem os de geração (lento × lento), até 14, do mais exato | Urano–Netuno não é da pessoa |
| Destaque da amostra | O aspecto mais exato que envolve Sol, Lua, Mercúrio, Vênus, Marte ou Ascendente | Idem |
| Elementos/modalidades | 10 planetas + Ascendente, peso igual | Simples de explicar |
| Regentes | Modernos | Brief |
| Graus na tela | Truncados no minuto (29°59'58" → 29°59') | Como os sites mostram; arredondar parece o signo seguinte |
| Sem hora | Meio-dia local; sem Ascendente, MC, casas; Lua marcada incerta se muda de signo no dia; aspectos da Lua fora | Nada inventado |

## Validação

`testes/dados/referencias_ocidental.json`: 11 mapas copiados do
horoscopes.astro-seek.com em 26/set/2026 (URL de cada um no arquivo; tropical,
Placidus, "Lunar Nodes (True)", fuso automático). Inclui São Paulo 1987, Rio
1995, Porto Alegre 2005 e Brasília 2010 em horário de verão, Lisboa e Londres.
Resultado: **11 de 11 batem a menos de 1'** — planetas até 8", nodo até 30",
casas e Ascendente/MC até 8"; casa de cada planeta e retrogradação iguais.

## Textos

`conteudo/ocidental/textos/` — ver o `LEIA.md` da pasta. 339 textos, todos com
`revisado: false`. Os testes conferem tamanho (60–120 palavras), ausência de
previsão de saúde/morte/dinheiro e que todo aspecto possível entre pessoais
tem texto.

## Sinastria (`sinastria.py`) — Índice Padmini, método próprio

A sinastria tradicional não tem nota canônica. O índice é **nosso** e a
página diz isso ("Índice Padmini — método próprio", com o método explicado).

| Peça | Regra |
|---|---|
| Pontos cruzados | Sol, Lua, Mercúrio, Vênus, Marte, Júpiter, Saturno e Ascendente (A × B), mesmos orbes do mapa natal |
| Peso por aspecto | trígono +1,0 · sextil +0,7 · conjunção +0,8 · quadratura −0,7 · oposição −0,5 |
| Ajustes | Vênus×Marte: quadratura −0,2, oposição +0,1, conjunção +1,0 (química). Saturno: conjunção +0,1, trígono +0,6, sextil +0,5, quadratura −0,9, oposição −0,8 |
| Exatidão | peso × (1 − 0,5 × orbe/orbe máximo): exato vale inteiro, no limite vale metade |
| Nota da dimensão | 50 + 50 × tanh(soma / 1,5) → 0 a 100, 50 = neutro |
| Dia a dia | + 0,4 por planeta pessoal de um nas casas 6 ou 7 do outro |
| Índice | média ponderada: Emoções e Afeto 1,5 · Compromisso 1,25 · Crescimento 0,75 · demais 1,0; dimensão sem dados (sem hora de ninguém) fica fora |

Dimensões (grade da home e card): Atração (Vênus×Marte cruzados) · Emoções
(Lua×Lua, Lua×Sol) · Comunicação (Mercúrio×Mercúrio/Sol/Lua) · Afeto e
valores (Vênus×Vênus/Lua/Sol) · Identidade (Sol×Sol, Sol×Ascendente) ·
Crescimento (Júpiter × pessoais) · Compromisso (Saturno × pessoais) · Dia a
dia (Ascendente × pessoais e casas 6/7). Ajustes em relação ao brief: Mercúrio
também com Sol e Lua (sozinho quase nunca forma aspecto), e Vênus×Sol em Afeto.

Distribuição em 300 casais sorteados: mínimo 39, mediana 60, máximo 81.

Testes (`testes/test_sinastria.py`): determinismo, simetria A,B = B,A em 300
casais (com e sem hora), extremos construídos à mão (tudo em trígono ≥ 85,
tudo em quadratura ≤ 20, nenhum aspecto = 50).

## Preço do casal

`conteudo/ocidental/ofertas.yaml`: `preco: 127` (mostrado por padrão e cobrado
pela oferta), `preco_cupom: 97` (só para quem chega com `?cupom=` de afiliado).
A Cakto aceita `coupon=CODIGO` na URL do checkout e aplica o cupom
(ajuda.cakto.com.br, artigo 61, "checkout pré-preenchido", conferido em
26/set/2026); a página ocidental repassa o cupom assim e ainda avisa para
digitar o código se ele não aparecer aplicado. O cupom precisa existir na
Cakto com o mesmo código. A védica continua como estava (cupom só em utm_term).

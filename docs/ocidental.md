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

## Preços (decisão do Nicolas, 26/set/2026)

Tarot R$19 · Numerologia R$27 · Mapa natal R$37 · Sinastria R$127 (R$97 com
cupom de afiliado) · combo sinastria + 2 mapas natais R$167 (order bump: a
página anuncia "por mais R$40", a diferença para o preço de TABELA — o cupom
desconta só a sinastria). Tudo em `conteudo/ocidental/ofertas.yaml`.

## Preço do casal

`conteudo/ocidental/ofertas.yaml`: `preco: 127` (mostrado por padrão e cobrado
pela oferta), `preco_cupom: 97` (só para quem chega com `?cupom=` de afiliado).
A Cakto aceita `coupon=CODIGO` na URL do checkout e aplica o cupom
(ajuda.cakto.com.br, artigo 61, "checkout pré-preenchido", conferido em
26/set/2026); a página ocidental repassa o cupom assim e ainda avisa para
digitar o código se ele não aparecer aplicado. O cupom precisa existir na
Cakto com o mesmo código. A védica continua como estava (cupom só em utm_term).

## Numerologia (`numerologia.py`) — rodada 2

Pitagórica. Entrada: nome completo de REGISTRO (o da certidão) + data.

| Tema | Decisão |
|---|---|
| Tabela | A=1…I=9, J=1…R=9, S=1…Z=9; acentos removidos, Ç=C; o que não é letra é ignorado |
| Y e W | **Y é vogal, W é consoante** — em nomes brasileiros o Y soa "i" (Yasmin, Kelly) e o W soa "v"/"u" consonantal (Wagner, Wellington) |
| Mestres | 11, 22 e 33 não reduzem |
| Caminho de Vida | dia, mês e ano reduzidos SEPARADAMENTE, depois somados e reduzidos (04/01/1950 → 11; a variante "todos os algarismos" daria 2) |
| Expressão / Alma / Personalidade | todas as letras / vogais / consoantes, somadas e reduzidas |
| Dia | o dia reduzido (29 → 11) |
| Ano Pessoal | dia + mês de nascimento + ano corrente, cada um reduzido, somados e reduzidos |

Token do completo: assinado sobre o nome NORMALIZADO + a data (acento não
muda nada; uma letra a mais muda). `sck`: `n~data~nome completo`.

## Tarot (`tarot.py`) — rodada 2

Tiragem de 3 cartas: **Situação · Desafio · Conselho**. Baralho de 78 cartas
(tradição Rider-Waite-Smith: 22 arcanos maiores + 56 menores em Paus, Copas,
Espadas e Ouros). Nesta versão, só na posição normal (sem cartas invertidas).

| Tema | Decisão |
|---|---|
| Sorteio | no servidor, `secrets.SystemRandom().sample(range(78), 3)` — 3 cartas diferentes |
| ID da tiragem | as 3 cartas + 5 bytes aleatórios + selo HMAC de 4 bytes (chave do `PADMINI_SEGREDO`), em base64url (16 caracteres). Não precisa de banco; ID inventado ou alterado → 422 |
| Amostra → completo | o link pago assina o ID (`acesso.chave_tarot`), então o completo mostra exatamente as cartas da amostra. O `sck` leva `t~<id>` |
| Pergunta | opcional, até 140 caracteres. Fica só no navegador (localStorage) e só vai ao servidor no pedido do texto por IA do completo. Texto com pergunta **não** vai para o cache nem para o banco; sem pergunta, o texto por IA é guardado em cache como nos outros produtos |
| Cartas na tela | só tipografia + um símbolo simples nosso por naipe (lótus nos arcanos maiores). Nenhuma imagem de terceiros |
| Leitura de conjunto | peças escolhidas pelo código: quantos arcanos maiores (0 a 3), o naipe que predomina (2 ou 3 menores do mesmo naipe) e um fecho |

Textos: `conteudo/ocidental/textos/tarot.yaml` (leitura de cada carta com 40 a
90 palavras — ver o LEIA.md da pasta).

## Marca e acabamento (rodada 2, Fase E)

- **Home** com os quatro produtos (sinastria, mapa natal, numerologia, tarot),
  preços do `ofertas.yaml` e a linha do combo casal + 2 mapas.
- **Termos e privacidade** próprios (`static/ocidental/termos.html` e
  `privacidade.html`): mesmos dados da empresa e mesmas bases legais da LGPD,
  com numerologia e tarot. A pergunta do tarot aparece na privacidade: fica no
  navegador e não é armazenada. Com a védica no ar, `/termos` e `/privacidade`
  servem os arquivos de sempre, byte a byte.
- **Imagens de compartilhamento** `static/og-oc-*.png`, uma por página de
  produto, geradas por `scripts/gerar_og_ocidental.py` (desenho próprio, sem a
  marca em sânscrito).
- **Venda cruzada** no e-mail de entrega entre os quatro produtos (só aparece o
  que já tem link de checkout): casal → mapa natal de cada um + numerologia;
  mapa → sinastria + numerologia; numerologia → mapa + tarot; tarot →
  numerologia + mapa.
- **Sitemap** por versão: a ocidental anuncia também `/numerologia` e `/tarot`.
- **Smoke** (`scripts/smoke_producao.py`): a API ocidental dos quatro produtos é
  conferida sempre (amostra grátis, completo e PDF com 402); as páginas de
  numerologia e tarot têm de dar 200 com a ocidental no ar e 404 com a védica.
- **Pronto para virar?** `python scripts/pronto_para_virar.py`.


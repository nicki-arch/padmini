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

Tarot R$19 · Numerologia R$27 · Mapa natal R$37 · Sinastria R$127 (R$96,52
com o cupom do Pedro, 24%) · combo sinastria + 2 mapas natais R$167 (order
bump de R$40 dentro do checkout da sinastria, desmarcado: a página anuncia
"por mais R$40", a diferença para o preço de TABELA — o cupom não vale para o
bump). O tarot parcela em até 4x (limite da Cakto para R$19); nenhuma página
anuncia parcelas. Tudo em `conteudo/ocidental/ofertas.yaml`, com os links de
checkout colados em 26/set/2026 (rodada 3).

Preço sempre em formato brasileiro, por um filtro só (`ofertas.moeda`, e
`{{ x | moeda }}` nos templates): R$127 (inteiro, sem centavos), R$96,52 —
nunca "R$96.52".

## Cupom do Pedro

A Cakto só aceita desconto em **% inteiro**. O cupom criado é `pedro` (a Cakto
grava em minúsculas; `PEDRO` também funciona, conferido no checkout real),
**24%**, só na sinastria, sem validade, sem valer para o bump.

No `ofertas.yaml`: `cupom_percentual: 24` e `cupom_codigos: [pedro]`. O preço
com cupom **não** é escrito à mão: o `ofertas.py` calcula (127 − 24% = 96,52,
centavos arredondados meio-para-cima). Foi assim que o site anunciou R$97
enquanto a Cakto cobraria R$96,52.

A página da sinastria mostra o preço com cupom só para quem chega com um código
da lista (sem diferença de maiúsculas) e manda `coupon=pedro` (sempre em
minúsculas) para a Cakto, que aplica o desconto no checkout
(ajuda.cakto.com.br, "checkout pré-preenchido").

**Conferência do cupom é à mão.** A página do checkout da Cakto é montada por
JavaScript; o smoke abre com `urllib` (sem navegador, de propósito) e nunca vê o
desconto, então deixa um AVISO pedindo a conferência à mão — não é falha (não
pôr navegador no smoke nem no CI).

Estado em 27/set/2026, com duas observações que não batem:
- o Cowork conferiu num navegador de verdade e **o `?coupon=pedro` não estava
  sendo aplicado** (tratado no painel da Cakto, pelo Cowork);
- no mesmo dia, uma renderização automática com navegador (Firecrawl) do link
  simples `https://pay.cakto.com.br/hrf7qtu_1141270?coupon=pedro` **e** do link
  completo que o site gera (com `sck`, `utm_*` e `coupon=pedro`) mostrou o cupom
  aplicado: "pedro · Remover Cupom · Desconto (24%) · R$ 96,52". Pode depender do
  navegador ou da sessão (ex.: um cupom removido antes e lembrado pelo checkout):
  conferir numa janela anônima. Nessa renderização a Cakto redirecionou para uma
  URL **sem os `utm_*`** (ficaram `sck` e `coupon`); vale confirmar num pedido de
  teste que os `utm_*` continuam chegando ao webhook.

Enquanto isso, quem chega pelo link do Pedro vê R$96,52 no site e, se o cupom não
vier aplicado, a página diz para digitar o código no checkout.

**Link que o Pedro divulga:**

    https://padmini.com.br/compatibilidade?cupom=PEDRO&utm_source=pedro&utm_medium=tiktok

A origem da venda vem do cupom e dos `utm_*` (a Cakto repassa os `utm_*` ao
webhook; o cupom também vai em `utm_term`). Não usamos o programa de afiliados
da Cakto. A védica continua como estava (cupom só em `utm_term`).

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

## E-mails de marketing nas duas versões (rodada 4, 27/set/2026)

Amostra por e-mail, lembrete e carrinho abandonado existem nas duas versões. Cada
e-mail sai na copy, na paleta e nos links da **versão em que a pessoa estava**,
nunca na que está no ar na hora do envio (a mesma regra dos links de entrega):

- **A versão viaja com o registro:** coluna `sistema` em `amostras_email` e em
  `abandonos` (migração `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` no `db.py`;
  linhas antigas ficam `vedica`).
- **Amostra por e-mail:** a caixa aparece depois da amostra nas 4 páginas
  (`static/amostra-email.js`). A rota é a mesma da védica, `/api/amostra/email`,
  e **o servidor decide a versão** (`sistema.ativo()`); um campo `sistema` mandado
  pelo navegador é ignorado. Na ocidental, `produto` aceita mapa, compat,
  numerologia e tarot; na védica, só mapa e compat. A amostra do e-mail é a da tela
  (`rotas_ocidental.montar_amostra_email`, com as mesmas funções dos endpoints).
  O botão de compra leva o `sck` no formato do `afiliado.js` (`m~`, `c~`, `n~`, `t~`).
- **Tarot:** só o número da tiragem vai para o banco e para o e-mail; a pergunta,
  nunca (há teste no banco e no e-mail).
- **Numerologia:** guarda o nome da certidão e a data (o mesmo do `sck` `n~`).
- **Lembrete:** um só, 24–72h, só com a caixa marcada (vem desmarcada), nunca para
  quem comprou depois ou se descadastrou; lê `sistema` da linha.
- **Carrinho abandonado:** versão e produto saem da oferta (`cakto.oferta_paga`).
  O bump do combo sozinho não é abandono. Se a versão da oferta não é a que está no
  ar, **não manda** (só registra, `email_enviado = false`): mandar para uma página
  que vende outra coisa é pior que silêncio.
- Copy e assuntos: `marketing.TEXTOS`; cores: `paleta.email(versão)`. Prévia de
  todos em `/estilo?previa=<chave>`.


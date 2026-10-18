# Previsão dos próximos 12 meses — "O seu ano" (rodada 13)

Decisões de método do `previsao.py`. Como o Índice Padmini da sinastria: os números moram no
código (um lugar só, no topo do módulo) e estão repetidos aqui com o porquê. **Não é previsão de
acontecimentos**: o motor só diz onde e quando os planetas lentos tocam o mapa; o texto vem do
banco revisável (`conteudo/ocidental/textos/previsao/`, repositório privado), nunca de IA.

## Período

Do dia 1º do mês da compra até o último dia do 12º mês (compra em 15/out/2026 → 01/10/2026 a
30/09/2027). `previsao.periodo(compra)`.

## Efemérides, fuso das datas

O mesmo Swiss Ephemeris do mapa natal (`mapa_ocidental`: tropical, Moshier, sem arquivo). As
datas saem no **fuso de Brasília** (`FUSO_DATAS`): o produto é brasileiro; um trânsito lento não
muda de data por 3 horas, mas um eclipse ou a Revolução Solar perto da meia-noite mudam, então o
fuso é um só e fica escrito aqui.

## 1. Trânsitos

| Parâmetro | Valor | Por quê |
|---|---|---|
| Quem transita | Júpiter, Saturno, Urano, Netuno, Plutão | Os lentos marcam temas de meses; Sol a Marte passam em dias |
| Pontos natais | Sol, Lua, Mercúrio, Vênus, Marte, Júpiter, Saturno, Ascendente, Meio do Céu | O brief; Ascendente e Meio do Céu só com hora |
| Aspectos | conjunção, sextil, quadratura, trígono, oposição | Os maiores, como no mapa |
| Orbe (`ORBE_TRANSITO`) | **1°**, para entrar e para sair | Parâmetro único. 1° é o padrão de calendário de trânsitos (astro-seek, astro.com usam 1° a 2°) e mantém Júpiter em ~2 semanas por passagem |
| Mesma passagem (`MESMA_PASSAGEM`) | 15° | Com a retrogradação o planeta entra e sai da órbita até 3 vezes (às vezes 5, com Plutão). Duas janelas viram **um período só** quando, entre elas, o planeta não se afastou mais de 15° do ponto — o laço retrógrado de Júpiter, o maior, tem ~10° |
| Busca | o período ± 3 anos, amostra diária, bordas e datas exatas por bisseção | Para dar a data real de entrada de um trânsito que já está ativo no dia 1º (Plutão leva ~2 anos numa passagem) |

Cada trânsito traz: a data em que **entra** na órbita, as datas **exatas** (todas, mesmo as que
caem fora dos 12 meses), a data em que **sai**, e `mais_perto` (o dia de maior aproximação,
útil quando o planeta estaciona perto do ponto sem cruzar). Quadratura e sextil "de ida" e "de
volta" (ponto + 90° e ponto − 90°) são trânsitos diferentes.

## 2. Ingressos nas casas natais

O dia em que cada lento entra numa casa natal (Placidus do mapa; Porfírio perto dos polos)
dentro do período. Com a retrogradação ele pode entrar, voltar e entrar de novo: as datas de
entrada na mesma casa ficam juntas. Só com hora.

## 3. Eclipses

Os de `swe.sol_eclipse_when_glob` e `swe.lun_eclipse_when` cujo máximo cai no período, inclusive
os lunares penumbrais (o astro-seek e a maioria dos calendários os listam). Posição: o **Sol** no
máximo do eclipse solar (na prática, o grau da lua nova, que é o que a astrologia cita) e a Lua
no máximo do lunar. O astro-seek dá, nos solares, a posição da **Lua** no máximo: até ~2' de
diferença (06/02/2027: nós 17°37', eles 17°39'), sem efeito no orbe de 3°. Casa natal (só com hora). **Toca um ponto
natal** quando está a até 3° (`ORBE_ECLIPSE`) de um dos 9 pontos, só por conjunção (a
oposição deixaria quase todo eclipse "tocando" alguma coisa).

## 4. Revolução Solar

O instante em que o Sol volta à longitude do Sol natal (`swe.solcross_ut`), no aniversário que
cai no período (29/fev em ano não bissexto: 1º/mar). **Local: o de nascimento** (decisão do
brief; há quem use o local onde a pessoa está no aniversário, mas pedir isso complica o
formulário e muda pouco o Sol, que é o que mais pesa). Do mapa da Revolução saem o signo do
**Ascendente** e a **casa da Revolução onde cai o Sol** (o brief dizia "casa natal onde cai o
Sol da Revolução", mas o Sol da Revolução está, por definição, no grau do Sol natal, então na
casa natal ele cai sempre na mesma casa; a técnica clássica lê a casa do Sol no mapa da
própria Revolução, e é o que os textos `sol_casa` descrevem).

Sem hora: só a data (o Ascendente da Revolução muda um signo a cada ~2 horas e o instante
depende do grau exato do Sol natal).

## 5. Peso e "os temas do seu ano"

`peso = planeta × ponto × aspecto × duração × culmina`

| Fator | Valores |
|---|---|
| Planeta (`PESO_PLANETA`) | Plutão 5 · Netuno 4,5 · Urano 4 · Saturno 3,5 · Júpiter 2,5 (mais lento, mais peso) |
| Ponto (`PESO_PONTO`) | Sol, Lua, Ascendente e Meio do Céu 1,5 · demais 1,0 |
| Aspecto (`PESO_ASPECTO`) | conjunção e oposição 1,5 · quadratura 1,2 · trígono e sextil 1,0 |
| Duração | 1 + (dias dentro do período, até 365) / 365 → de 1 a 2 |
| Culmina (`FORA_DO_PERIODO`) | 1,0 se alguma data exata cai no período; **0,75** se não (só começa ou só termina nele). Decisão nossa: sem isso, um Plutão que só fica exato daqui a dois anos virava o tema principal do ano |

Os 3 maiores (`N_TEMAS`) são os temas, **um por par planeta × ponto** (Saturno em quadratura e
depois em oposição ao Sol é um assunto só).

**Regras do resumo (rodada 17, decisão do Nicolas de 16/out/2026),** em `previsao.temas`:

| Regra | Parâmetro | Por quê |
|---|---|---|
| Só vira tema o trânsito com **45 dias ou mais dentro do período** | `DURACAO_MINIMA_TEMA = 45` | Na amostra da Ana fictícia (14/05/1994, 15:40, Porto Alegre) o 3º tema durava 16 dias (16/mar a 1/abr/2027). Os mais curtos continuam no mês a mês e nas áreas |
| **Um planeta no máximo 2 vezes** nos 3 temas | `VEZES_POR_PLANETA = 2` | Na mesma amostra os 3 temas eram de Saturno |
| **Pelo menos um harmônico** (sextil, trígono ou conjunção com Júpiter) | `previsao.harmonico` | Os 3 eram tensos. Se nenhum escolhido pelo peso é harmônico e existe um harmônico que passa nas duas regras acima, ele entra no lugar do tema de menor peso. Se não existe (ex.: `sp-1990`, cujos harmônicos duram 9 e 10 dias), os 3 ficam como estão |

Cada tema leva `motivo`: `peso` (escolhido pelo peso) ou `harmonico` (entrou pela regra do
harmônico). Num ano sem trânsito longo que chegue, pode sair **menos de 3 temas**: a amostra e
os e-mails aceitam isso (a boas-vindas usa o mapa natal no lugar do 2º tema). As regras só
escolhem; não mudam peso nem data de nenhum trânsito.

Antes e depois (compra em 15/out/2026, período de out/2026 a set/2027):

| Mapa | Antes | Depois |
|---|---|---|
| Ana fictícia | Saturno □ MC (133 d) · Saturno □ Lua (118 d) · Saturno ☍ Asc (**16 d**) | Saturno □ MC · Saturno □ Lua · **Júpiter ✶ Vênus (252 d, harmônico)** |
| `sp-1990` | Júpiter □ Sol · Saturno ☌ Vênus · Plutão □ Mercúrio | igual (nenhum harmônico com 45+ dias) |
| `rio-1995` | Plutão △ MC · Plutão ☌ Mercúrio · Urano ☌ MC | igual (já tinha harmônico) |
| `lisboa-1985` | Netuno □ Lua · Netuno ☍ MC · Júpiter ☌ Sol | igual (Júpiter ☌ conta como harmônico) |

## Sem hora de nascimento

Sem Ascendente, Meio do Céu, casas, ingressos, casa dos eclipses e Ascendente/casa da Revolução
Solar; os trânsitos aos planetas, os eclipses e a data da Revolução continuam, com o aviso de
sempre. **A Lua sai também**: sem hora ela é calculada ao meio-dia e pode estar até ~7° do lugar,
e 1° de orbe sobre ela seria chute. Por isso, sem hora, nem trânsito à Lua nem eclipse tocando a
Lua (o mesmo critério dos aspectos da Lua no mapa natal sem hora).

## A página e o PDF (Fase 3)

`/seu-ano` (`static/ocidental/seu-ano.html`, texto em `conteudo/ocidental/seu-ano.yaml`), mesmos
estados do `/mapa`. A API é `/api/ocidental/previsao` (amostra ou completo) e `/previsao/pdf`.

- **Período da amostra:** o mês corrente (dia 1º). **Do completo:** `inicio=AAAA-MM` do link pago,
  que entra na chave do token (`acesso.chave_previsao`): o mesmo link abre sempre o mesmo ano.
- **Amostra:** os títulos e os períodos dos 3 temas e o começo do texto do primeiro na tela; o texto
  inteiro do primeiro por e-mail (rodada 6). Os outros textos nunca saem do servidor.
- **Completo:** os 3 temas; mês a mês (o que começa, o que está no auge e o que termina, com
  eclipses, ingressos e a Revolução Solar); por área (as dimensões do mapa: o ponto natal tocado →
  Sol: Essência, Lua: Emoções, Ascendente: Como você chega, Mercúrio: Mente, Vênus: Amor, Marte:
  Ação, Meio do Céu e Saturno: Carreira, Júpiter: Dinheiro; os ingressos pela casa); eclipses;
  Revolução Solar. Sem hora: o aviso, e nada que dependa de casa.
- **Catálogo:** `previsao`, `oculto` até ligar (404 ao público; a prévia `?previa=` abre só os
  ocultos que já têm página própria). Sem venda: nenhum preço nem botão de compra.

## A venda (Fase 4) — pronta e desligada

- **Catálogo:** `previsao` está `oculto` no `catalogo.yaml` (404, fora do menu, do rodapé e do sitemap).
- **Preço:** o `ofertas.yaml` tem só o nome, sem `preco`, porque o preço não foi decidido
  (sugestão do brief: R$47 de lançamento, R$67 cheio). Sem preço, o checkout recusa
  (`pendentes.valor_centavos` levanta erro), e um teste derruba o CI se alguém ligar o
  produto no catálogo sem pôr o preço.
- **Para ligar:** ponha `preco` (e `preco_cheio`, se for o caso) em `ofertas.yaml` → `previsao`
  e mude o `estado` para `ativo` no `catalogo.yaml`. Nada mais muda.
- **Checkout:** é o da Stripe, igual ao do mapa (`/api/checkout`, produto `previsao`). O
  pedido pendente grava `inicio` = mês da compra (fuso de São Paulo); a entrega
  (`entrega.link_completo`) monta `/seu-ano?…&inicio=AAAA-MM&token=…`, e esse link abre sempre
  o mesmo ano comprado. A Stripe recebe só o nome do produto, o preço, o e-mail e o id opaco.
- **Cartão no mapa completo:** quando o produto está `ativo`, o relatório do mapa
  (`/mapa`) mostra o cartão "O seu ano" (`#cartao-seu-ano`), que leva a `/seu-ano`.
- **E-mail de aniversário** (`sequencias.rodar_aniversarios`, na tarefa diária
  `/api/tarefas/sequencias`):
  - sai 30 dias antes do aniversário, com o assunto "O seu ano astrológico começa em …" e o
    link da amostra (`/seu-ano`);
  - só para quem marcou a caixa da sequência (`aceita_sequencia`), na última amostra
    ocidental (mapa ou previsão) dos últimos 24 meses, sem descadastro; leva o link de
    descadastro;
  - um por pessoa por ano (`envios_sequencia`, passo = ano);
  - quem nasceu em 29/02 recebe junto com quem faz aniversário em 01/03 nos anos que não
    são bissextos;
  - **desligado** enquanto `catalogo.vende("previsao")` for falso: nem consulta o banco.
- A sequência de boas-vindas também não empurra produto que não está à venda.

## Validação (15/out/2026)

3 mapas de `testes/dados/referencias_ocidental.json`, compra em 15/out/2026 (período 01/10/2026 a
30/09/2027). Referência: horoscopes.astro-seek.com e mooncalendar.astro-seek.com, valores
copiados em `testes/dados/referencias_previsao.json` com a URL de cada consulta. Teste:
`testes/test_previsao_referencia.py`.

**Trânsitos.** O calendário de trânsitos do astro-seek carrega por JavaScript e não dá para ler
sem navegador; por isso a conferência é pela posição: no instante exato que o motor calcula,
abre-se o mapa do astro-seek daquele instante e lê-se o planeta. Ele está a menos de um dia de
movimento do grau-alvo, então a data exata deles difere no máximo 1 dia da nossa.

| Mapa | Trânsito | Data exata (motor) | Alvo | astro-seek no instante | Diferença |
|---|---|---|---|---|---|
| São Paulo 1990 | Júpiter quadratura Sol | 03/11/2026 | Leão 24°37' | Leão 24°37'01" | 0" |
| São Paulo 1990 | Saturno conjunção Vênus | 28/02/2027 | Áries 13°04' | Áries 13°04'47" | 0" |
| São Paulo 1990 | Saturno quadratura Saturno | 13/06/2027 | Áries 25°14' | Áries 25°14'43" | 1" |
| São Paulo 1990 | Júpiter sextil Meio do Céu | 21/07/2027 | Leão 29°07' | Leão 29°07'37" | 1" |
| São Paulo 1990 | Júpiter trígono Mercúrio | 01/09/2027 | Virgem 7°59' | Virgem 7°59'12" | 1" |
| Rio 1995 | Urano conjunção Meio do Céu | 22/11/2026 | Gêmeos 3°49' | Gêmeos 3°49'31" | 1" |
| Rio 1995 | Júpiter conjunção Ascendente | 29/01/2027 | Leão 23°36' | Leão 23°36'35" | 1" |
| Rio 1995 | Netuno trígono Vênus | 07/03/2027 | Áries 3°26' | Áries 3°26'07" | 0" |
| Rio 1995 | Plutão conjunção Mercúrio | 08/03/2027 | Aquário 6°22' | Aquário 6°22'07" | 0" |
| Rio 1995 | Saturno quadratura Sol | 28/04/2027 | Áries 20°16' | Áries 20°16'12" | 1" |
| Lisboa 1985 | Netuno oposição Meio do Céu | 21/01/2027 | Áries 2°03' | Áries 2°03'14" | 1" |
| Lisboa 1985 | Júpiter conjunção Sol | 28/02/2027 | Leão 19°50' | Leão 19°50'49" | 0" |
| Lisboa 1985 | Saturno trígono Sol | 24/04/2027 | Áries 19°50' | Áries 19°50'48" | 1" |
| Lisboa 1985 | Júpiter quadratura Saturno | 10/06/2027 | Leão 21°43' | Leão 21°43'26" | 1" |

**Eclipses** (01/10/2026 a 30/09/2027): os 5 do astro-seek, com o mesmo tipo e signo; graus
iguais no minuto nos lunares e no solar de agosto, 2' no solar de fevereiro (convenção acima).

| Data | Tipo | Motor | astro-seek |
|---|---|---|---|
| 06/02/2027 | solar anular | Aquário 17°37' | Aquário 17°39' (Lua no máximo) |
| 20/02/2027 | lunar penumbral | Virgem 1°58' | Virgem 1°58' |
| 18/07/2027 | lunar penumbral | Capricórnio 25°57' | Capricórnio 25°57' |
| 02/08/2027 | solar total | Leão 9°55' | Leão 9°55' |
| 17/08/2027 | lunar penumbral | Aquário 24°04' | Aquário 24°04' |

**Revolução Solar 2027** (local de nascimento): instante igual no minuto, mesmo Ascendente,
mesma casa do Sol.

| Mapa | Instante (UT) | Ascendente | Casa do Sol |
|---|---|---|---|
| São Paulo 1990 | 15/05/2027 16:09 | Virgem | 9 |
| Rio 1995 | 10/01/2027 18:13 | Gêmeos | 8 |
| Lisboa 1985 | 12/08/2027 18:45 | Aquário | 7 |

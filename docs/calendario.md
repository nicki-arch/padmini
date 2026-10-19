# "A sua Lua no ano": o calendário lunar personalizado (rodada 14)

As luas novas e cheias, os eclipses, os períodos de Mercúrio retrógrado e as Revoluções
Lunares dos 12 meses a partir do dia 1º do mês da compra (o mesmo período de "O seu ano"),
lidos no mapa natal. Entrega: página (`/calendario-lunar`), PDF e arquivo de agenda (.ics).

**Estado: OCULTO, com preço (rodada 20).** O produto `calendario` está no `catalogo.yaml`
com `estado: oculto` e `oferta: calendario` (R$47, "de R$97", no `ofertas.yaml`, decisão do
Nicolas de 19/out): a página responde 404 em produção (abre com `?previa=`, com um link pago
ou com o produto ligado no `/painel`). Checkout só pela Stripe, como "O seu ano": pedido
pendente com os dados no servidor, entrega por e-mail com o link (só o token cifrado) e o
`/obrigado` com o link.

**Para ligar a venda:** no `/painel`, A sua Lua no ano → Ativo. O cartão do mapa e de "O seu
ano" (agora com o preço) e o botão de compra aparecem sozinhos. O calendário também entra no
kit dos três (rodada 20, `docs/kit.md`).

## Arquivos

| Arquivo | Papel |
|---|---|
| `calendario_lunar.py` | O motor: lunações, eclipses (com hora), Mercúrio retrógrado, Revolução Lunar, casa e pontos tocados, fuso |
| `montar_calendario.py` | Do cálculo aos eventos com texto: completo, amostra, tela e o `.ics` |
| `rotas_ocidental.py` | `POST /api/ocidental/calendario` (amostra), `/calendario/completo`, `/calendario/pdf`, `GET /calendario-lunar/agenda.ics`, `POST /api/live/ocidental/token/calendario` |
| `gerar_pdf_ocidental.gerar_pdf_calendario` | O PDF |
| `static/ocidental/calendario-lunar.html` + `conteudo/ocidental/calendario-lunar.yaml` | A página e a sua moldura de texto |
| `acesso.emitir_token_calendario` / `abrir_token_calendario` | O token cifrado |
| `conteudo/ocidental/textos/calendario/` (repositório privado) | Os 100 textos (`revisado: false`); os eclipses usam `previsao/eclipses.yaml` |

## Método

| Item | Decisão |
|---|---|
| Efemérides | Swiss Ephemeris, modo Moshier, tropical, geocêntrico aparente (as mesmas do mapa e da previsão) |
| Lua nova / cheia | Elongação Lua − Sol em 0° / 180°: amostra diária e bisseção (erro numérico < 1 s). Signo e grau = os da **Lua** (na cheia, o Sol está no signo oposto) |
| Eclipses | A busca de "O seu ano" (`previsao.eclipses_entre`), agora com o instante do máximo. O eclipse aparece junto da lunação que acompanha (máximo a menos de 1 dia), com a hora do máximo à parte. Conta também o penumbral de 18/07/2027 (magnitude 0,001): o catálogo da NASA e os calendários astrológicos o listam; o timeanddate o chama de "quase eclipse". Igual a "O seu ano" |
| Mercúrio retrógrado | Estações = velocidade de Mercúrio passando por zero (bisseção). Entra todo período que toca os 12 meses, mesmo começado antes (aparece no 1º dia) ou terminando depois. A casa é a do grau onde ele estaciona retrógrado; o texto é o da casa. A volta direta aparece como evento curto, sem texto |
| Revolução Lunar | `swe.mooncross_ut`: a Lua de volta à longitude da Lua natal (~13 no período). Texto pelo signo da Lua natal (o mesmo a cada mês), mostrado na seção própria |
| Ponto natal tocado | Conjunção até **3°** (`ORBE_PONTO`) com Sol, Lua, Mercúrio, Vênus, Marte, Júpiter, Saturno, Ascendente e Meio do Céu |
| Sem hora | Sem casas, sem Ascendente e Meio do Céu e sem a Lua natal (ao meio-dia ela pode estar ~7° fora). Ficam o signo e os outros planetas, com os avisos. **Sem Revolução Lunar**: com até 7° de erro na Lua, a data sairia até ~13 h errada |
| Fuso | Horário de Brasília por padrão; a pessoa escolhe outro dos quatro do Brasil (Brasília, Manaus, Rio Branco, Noronha; sem horário de verão desde 2019). O fuso muda a hora e, perto da meia-noite, o dia; o período é sempre o mesmo. Não entra no token: o mesmo link abre em qualquer fuso (`?fuso=` na página e no `.ics`) |
| Hora mostrada | Cortada no minuto, como o timeanddate (04:11:47 é 04:11) |

## Sem dado de nascimento no link, no arquivo de agenda e no log

O link do calendário é `/calendario-lunar?token=oc-cal-…`, e **só isso**. O token é o
próprio pedido (data, hora, latitude e longitude com 4 casas, mês de início) cifrado e
autenticado com AES-GCM; a chave sai do `PADMINI_SECRET` (HKDF, rótulo próprio). Sem o
segredo, ninguém lê o nascimento nem forja um token; token alterado, de outro segredo ou
de outro produto não abre (402). O completo, o PDF e o `.ics` recebem só o token e o
fuso; a página manda `Referrer-Policy: no-referrer`. Assim, a URL que fica no log de
acesso, no histórico do navegador e na descrição de cada evento da agenda não carrega
nenhum dado de nascimento. O nome não entra no token, no PDF nem no `.ics`. O registro
do `/live` (`live_geracoes`) vai sem nome, data e local.

## O arquivo de agenda (.ics)

RFC 5545: um evento **de dia inteiro** por data (`DTSTART;VALUE=DATE`), a hora exata e
a casa no título ("🌑 Lua nova em Escorpião · 04:02 · casa 2"), o texto e o link (só o
token) na descrição, `TRANSP:TRANSPARENT` (não ocupa a agenda), linhas dobradas em 75
octetos, vírgula e ponto e vírgula escapados, `UID` estável (reimportar não duplica) e
sem dado da pessoa. Nome da agenda: "Valderez · a sua Lua". Mercúrio retrógrado tem um
evento no começo e outro na volta direta.

Conferido com a biblioteca `icalendar`, que lê o arquivo inteiro: 44 eventos para São
Paulo 1990. **A importação no Google Agenda e no iPhone fica para o Nicolas** (daqui não
há como abrir os dois apps). Roteiro: no iPhone, abrir o link "Colocar na minha agenda"
no Safari → "Adicionar tudo"; no Google Agenda (computador), baixar o arquivo →
Configurações › Importar e exportar › Importar.

## Amostra e venda

- Amostra (com e-mail, como todo produto da ocidental): os eventos dos **próximos 30
  dias**. O 1º com metade do texto na tela e inteiro por e-mail; os outros, só dia, hora
  e título. O texto pago nunca vai para o navegador (teste).
- **Nenhum e-mail de marketing novo:** a página não tem a caixa da sequência e o servidor
  grava `aceita_sequencia = false` para o calendário (sem lembrete, sem boas-vindas).
- O PDF: A4 retrato, capa com o período e o fuso, introduções, **um mês por página**
  (a grade do mês com os ícones das fases desenhados e, embaixo, os eventos com o texto),
  fechamento e a assinatura com a foto da Dona Valderez (`foto-valderez-rosto`; sem ela,
  a roda) e a frase de `revisao.yaml`.

## /live

Aba "A sua Lua no ano", igual à de "O seu ano": aparece com o produto ativo no estado do
site ou no "tudo liberado" (prévia: para todos; produção: só no navegador logado no
painel). A rota `/api/live/ocidental/token/calendario` usa a mesma sessão (sem sessão,
401; produto escondido, 404) e devolve o token cifrado e o link. Na tela, a amostra (as
luas dos próximos 30 dias e o texto da primeira) acima da linha dourada; o resto abaixo.

## Validação (19/out/2026)

Referências copiadas em `testes/dados/referencias_calendario.json`, com a fonte de cada
uma; teste `testes/test_calendario_lunar.py`. **Critério do brief: até 2 minutos.**

**Lunações** (timeanddate.com, fases em UTC, o site corta os segundos):

| Ano | Fase | Luas | Diferença (motor − referência) |
|---|---|---|---|
| 2026 | nova | 12 | +0,02 a +0,85 min |
| 2026 | cheia | 13 | +0,02 a +1,00 min |
| 2027 | nova | 13 | +0,07 a +0,62 min |
| 2027 | cheia | 12 | −0,02 a +0,94 min |

Como a referência corta os segundos, a diferença fica entre 0 e 1 minuto; as 50 batem no
minuto mostrado.

**Eclipses** (timeanddate.com, máximo em UTC):

| Data | Tipo | Referência | Motor | Diferença |
|---|---|---|---|---|
| 17/02/2026 | solar anular | 12:12:04 | 12:11:54 | −10 s |
| 03/03/2026 | lunar total | 11:33:46 | 11:33:43 | −3 s |
| 12/08/2026 | solar total | 17:46:06 | 17:45:57 | −9 s |
| 28/08/2026 | lunar parcial | 04:12:53 | 04:12:58 | +5 s |
| 06/02/2027 | solar anular | 15:59:37 | 15:59:40 | +3 s |
| 20/02/2027 | lunar penumbral | 23:12:52 | 23:12:51 | −1 s |
| 02/08/2027 | solar total | 10:06:40 | 10:06:40 | 0 s |
| 17/08/2027 | lunar penumbral | 07:13:49 | 07:13:52 | +3 s |

**Revolução Lunar**: astro-seek (calculadora de retornos, hora local de São Paulo). O
brief pedia o astro.com, que exige conta e não abre daqui; o astro-seek é a mesma fonte
das validações das rodadas 12 e 13.

| Mapa | Lua natal | Retornos em 2027 | Diferença |
|---|---|---|---|
| São Paulo 1990 (sp-1990) | Capricórnio 29°59' | 14 | −0,41 a +0,57 min |
| Rio 1995 (rio-1995) | Touro 15°37' | 13 | −0,40 a +0,55 min |

O astro-seek arredonda o minuto e o calendário corta: a hora mostrada pode diferir 1
minuto (19:11 lá, 19:10 aqui). Em cada retorno o teste confere também que a Lua do motor
está a menos de 1" da Lua natal.

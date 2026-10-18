# Padmini — contexto para quem for mexer no código

Site de astrologia védica (Jyotish) para o mercado brasileiro, modelo freemium:
amostra grátis → paga na Cakto → recebe por e-mail um link assinado que abre o completo.
Sócios: Nicolas (produto/tecnologia) e Pedro Monteiro (conteúdo, lives no TikTok).

## Duas versões no mesmo código: védica e ocidental
**Para trocar a versão que está no ar: na Render, abra o serviço → Environment, mude
`PADMINI_SISTEMA` para `ocidental` (ou `vedica`) e salve.** A Render reinicia sozinha;
não precisa de deploy nem de mexer em código. Sem a variável, fica `vedica`.
Valor digitado errado = o site não sobe (erro claro no log), em vez de subir pela metade.
**Antes de virar para `ocidental`:** `python scripts/pronto_para_virar.py` lista o que ainda
bloqueia (oferta sem link de checkout, texto não revisado, página falando da védica).

- `sistema.py` é o único lugar que lê a variável; tudo o que muda por versão pergunta para ele.
- Copy e preços por versão: `conteudo/vedica/…` e `conteudo/ocidental/…`.
- Link já entregue nunca quebra: o token diz a versão (védica sem prefixo, ocidental `oc-`),
  e o completo abre na versão comprada qualquer que seja a do ar.
- O webhook reconhece as ofertas das duas versões, qualquer que seja a ativa.
- `testes/test_sistema.py` compara a védica com uma foto tirada antes do interruptor
  (`testes/dados/vedica_html`). Mudou a védica de propósito? `python scripts/foto_vedica.py`
  e diga no commit o que mudou.
- Nada da védica se apaga: os testes dela continuam verdes em todo PR.

## Fontes de verdade
- **Código:** este repositório (`github.com/nicki-arch/padmini`, branch `master`).
  Cópias de código em outros lugares (ex.: Claude Project) podem estar desatualizadas — não confiar nelas.
- **Estado, decisões e pendências:** no Claude Project "Projeto Padmini":
  `claude/LEIA-PRIMEIRO.md` (ponto de entrada), `claude/decisoes.md`, `claude/checklist-de-lancamento.md`.
- **Produção:** https://padmini.com.br (Render, serviço `srv-dalfcj3l550s73b38jmg`,
  deploy automático a cada push na `master`). O endereço `padmini.onrender.com`
  continua respondendo e é usado pelo ping diário, que assim não depende de DNS.
  **Domínio novo (rodada 18):** `https://valderezastrologia.com.br` passa a ser o principal
  quando a Render tiver `PADMINI_SITE_URL` e `PADMINI_DOMINIO_PRINCIPAL`; aí o
  `padmini.com.br` só redireciona (301, com caminho e query), menos `/webhook/*` e `/api/*`
  (o webhook da Stripe continua nele). Operação e ordem em `docs/dominio.md`.
- **Conteúdo proprietário fora do repositório público (rodada 10, decisão de 6/out/2026).**
  Os textos de interpretação — `base_significacoes.py` (védica), `conteudo/ocidental/textos/`
  e `conteudo/ocidental/blog/` — passam a morar no repositório PRIVADO
  `github.com/nicki-arch/padmini-conteudo`, nos mesmos caminhos relativos. O `build.sh` clona
  esse repositório na hora do build (Render) e o `.github/workflows/testes.yml` faz o mesmo no
  CI, com um token de leitura só daquele repo: `PADMINI_CONTEUDO_TOKEN` na Render (serviços
  `padmini` e `padmini-previa`) e o secret `CONTEUDO_REPO_TOKEN` no GitHub.
  **A Render precisa rodar `bash build.sh`** (Settings → Build Command), não só
  `pip install -r requirements.txt`: o `render.yaml` não é lido, porque os serviços foram
  criados pelo painel. **Falha fechada, em duas travas:** sem o token (ou sem os arquivos no repo
  privado) o `build.sh` para com mensagem clara; e se o site subir sem os textos mesmo assim, o
  `app.py` não inicia (`conteudo_privado.exigir()`, a mensagem diz o que falta).
  Os caminhos ficam no `.gitignore` e `testes/test_conteudo_fora_do_repo.py` falha se algum
  voltar a ser versionado. **Numa sessão nova o checkout não tem esses arquivos — não é
  regressão.** Para rodar local: clone o `padmini-conteudo` ao lado e use
  `PADMINI_CONTEUDO_DIR=../padmini-conteudo` (ou `bash scripts/buscar_conteudo.sh` com a mesma
  variável, que copia para cá). Para editar texto, mexa no `padmini-conteudo` (PR lá) e faça um
  novo deploy da Render: o site só muda no próximo build.
  **Revisão da Dona Valderez (rodada 12.1): a planilha do Google `padmini-revisao-textos` é a
  fonte; não gere .xlsx novo.** O robô `sincronizar planilha` do `padmini-conteudo` (todo dia às
  07:13 e por "Run workflow") grava "aprovado? = sim" nos YAMLs, faz o deploy e acrescenta na
  planilha as linhas dos textos novos: rodada com texto novo não pede upload de planilha. Ele usa
  a regra de `revisao.py` / `scripts/importar_revisao.py` daqui (não duplicar). Configuração e
  recusados: `LEIA-ME.md` do `padmini-conteudo`. `exportar_revisao.py` / `importar_revisao.py
  --conteudo ../padmini-conteudo` ficam só como reserva sem internet.
- **Licença:** código sob AGPL-3.0 (`LICENSE`); textos, copy, ilustrações e as marcas
  "Valderez Astrologia" e "Padmini" com todos os direitos reservados (seção "Licença" do
  `README.md`). Os textos já estiveram públicos e continuam no histórico do Git (ocidentais
  desde 26/set, védicos desde 16/set): a rodada 10 protege daqui para a frente.

## Mapa do código
| Arquivo | Papel |
|---|---|
| `app.py` | FastAPI: páginas, `/api/*`, `/webhook/cakto` |
| `compute_chart.py` | Cálculo do mapa (Swiss Ephemeris, sideral Lahiri, whole sign) |
| `detectar_fatos.py`, `montar_texto.py`, `base_significacoes.py` | Fatos do mapa → texto; IA (Claude) só reescreve. `base_significacoes.py` vem do repo privado |
| `conteudo_privado.py` + `scripts/buscar_conteudo.sh` | **Onde estão os textos (rodada 10)**: a pasta do conteúdo (`PADMINI_CONTEUDO_DIR` ou a raiz), o que falta e a trava da subida; o script do build/CI que clona o `padmini-conteudo` e copia para os mesmos caminhos |
| `compatibilidade.py` | Guna Milan / Ashtakoot (36 pontos), doshas |
| `acesso.py` | Token HMAC que libera o completo (sem token = 402) |
| `cakto.py` | Webhook: assinatura HMAC `v1=` sobre `{timestamp}.{corpo}`; dados de nascimento vêm no `sck` |
| `pagamento.py` + `pendentes.py` | **Checkout próprio com a Stripe (rodada 11, só ocidental)**: `PADMINI_PAGAMENTO=cakto\|stripe` (padrão cakto; valor errado = não sobe) e `PADMINI_VENDAS_TESTE=1` (abre a venda só naquele serviço; só com stripe + `sk_test_`, senão não sobe). O pedido nasce em `pedidos_pendentes` antes do pagamento (preço do `ofertas.yaml`, nunca do navegador; cupom no servidor); a Stripe recebe só o id opaco e o e-mail. Não pago sai em 7 dias. Ver `docs/stripe.md` |
| `rotas_checkout.py` + `stripe_api.py` + `static/ocidental/comprar.js`, `checkout.html`, `obrigado.html` | **Checkout próprio (rodada 11, Fase 2)**: botão → `POST /api/checkout` (sem preço, sem dado pessoal na URL) → pendente + Checkout Session (`ui_mode=embedded_page`, `price_data` do catálogo; a Stripe recebe só nome do produto, preço, e-mail e o id opaco) → `/checkout/{id}` (Embedded Checkout) → `/obrigado/{id}` (só o webhook confirma). CSP da Stripe só em `/checkout/` (`seguranca.CSP_STRIPE`). Tudo 404 com a Cakto |
| `/webhook/stripe` (`app.py`) | **Webhook da Stripe (rodada 11, Fase 3)**: assinatura com `STRIPE_WEBHOOK_SECRET` (sem = 401), idempotente por evento (`eventos_stripe`) e por pedido (transição para `pago` uma vez); busca a sessão de novo antes de entregar; entrega por `_entregar_leitura`, o MESMO caminho da Cakto (`pedidos.origem_pagamento`). Expirado = abandono; reembolso/contestação = status + alerta. Eventos em `docs/stripe.md` |
| `scripts/relatorio_vendas.py` | **Vendas do mês na Stripe por produto** (`--mes AAAA-MM`): bruto, taxa, reembolsos, contestações e líquido, das balance transactions + `pedidos`; CSV sem dado pessoal (rodada 11, Fase 4) |
| `entrega.py` | Link assinado + e-mail (Resend) |
| `static/afiliado.js` | Monta o link do checkout: dados no `sck`, afiliado/cupom dobrados em `utm_*` |
| `mapa_ocidental.py` | Motor ocidental: tropical, Placidus (Porfírio nos polos), nodo verdadeiro, aspectos e orbes num lugar só. Validado contra 11 mapas do astro-seek (`testes/dados/referencias_ocidental.json`) |
| `montar_texto_ocidental.py` + `conteudo/ocidental/textos/` (repo privado) | Mapa → texto (YAML, `revisado: false` em cada texto; `python scripts/revisao_textos.py` conta o que falta revisar). **Rodada 12:** as 10 dimensões do mapa ativas; Carreira, Dinheiro, Família e Propósito são compostas (cúspide + planetas na casa + regente; Nodo Norte), com versão sem hora e aviso, e planeta repetido entra só como referência (`mt.dimensao_composta`, tabela em `docs/ocidental.md`). Aspectos: `aspectos_sociais` → `aspectos_pessoais` → peças |
| `previsao.py` + `montar_previsao.py` + `static/ocidental/seu-ano.html` | **"O seu ano", previsão dos próximos 12 meses (rodada 13)**: o motor (trânsitos dos lentos com orbe 1°, retrogradação num período só, ingressos em casa, eclipses, Revolução Solar no local de nascimento, pesos e os 3 temas; método e validação contra o astro-seek em `docs/previsao.md`), a montagem com os textos do repo privado (`textos/previsao/`, nunca IA) e a página `/seu-ano`. **OCULTO no catálogo** (404; abre com `?previa=` ou link pago). O token leva o mês de início (`acesso.chave_previsao`): o link abre sempre o mesmo ano comprado. Amostra: títulos dos 3 temas + começo do 1º na tela, o 1º inteiro por e-mail. **Venda pronta e desligada (Fase 4):** preço decidido na rodada 16 (R$47 no `ofertas.yaml`), mas o produto continua `oculto` e o checkout recusa o que o catálogo não vende (teste trava ligar sem preço), Stripe como o mapa, cartão "O seu ano" no `/mapa` e e-mail de aniversário 30 dias antes (`sequencias.rodar_aniversarios`, só com consentimento), tudo só com o produto ativo. Para ligar: no `/painel`, O seu ano → Ativo (rodada 15; o preço já está no `ofertas.yaml`). **Rodada 17:** temas com 45+ dias no período, pelo menos um harmônico e um planeta no máximo 2 vezes (`previsao.temas`, parâmetros e antes/depois em `docs/previsao.md`); aba "O seu ano" no `/live` (`/api/live/ocidental/token/previsao`) e e-mail de aniversário ligam juntos com o produto ativo no estado do site |
| `rotas_ocidental.py` + `static/ocidental/` | API `/api/ocidental/*`, páginas e `/live` da versão ocidental; `gerar_pdf_ocidental.py` é o PDF. **Sem texto por IA (rodada 16, 16/out):** nenhum botão, prompt ou chamada à IA na ocidental; `texto_ia: true` recebe 422 (`rotas_ocidental.recusar_texto_ia`) e o `/api/config` não traz `texto_ia_disponivel` com a ocidental no ar. A védica continua com a IA (por isso o `anthropic` fica no `requirements.txt`) |
| `revisao.py` + `scripts/exportar_revisao.py` / `importar_revisao.py` | Regras de tom e tamanho da revisão da família, num lugar só. **Desde a rodada 12.1 a fonte é a planilha do Google, sincronizada pelo robô do `padmini-conteudo`**, que importa `revisao` e `importar_revisao.planejar`/`SIM`: mudar a assinatura deles quebra o robô (os testes dele rodam lá). Os scripts xlsx ficam só de reserva; a planilha não vai para o git |
| `numerologia.py` | Numerologia pitagórica (versão ocidental): regras de Y/W e do Caminho de Vida em `docs/ocidental.md` |
| `scripts/pronto_para_virar.py` | O que falta para trocar `PADMINI_SISTEMA` para `ocidental` (sai com 1 se houver bloqueio) |
| `scripts/gerar_og_ocidental.py` | Gera as imagens de compartilhamento `static/og-oc-*.png` da versão ocidental |
| `tarot.py` | Tarot (versão ocidental): 78 cartas, sorteio no servidor, ID da tiragem com selo HMAC — o link pago abre as mesmas cartas da amostra |
| `paleta.py` + `marca.py` | **Cores e fontes de cada versão, fonte única** (tela, e-mail, PDF, imagens) e o símbolo da marca da ocidental. `static/ocidental/tema.css` é GERADO de `paleta.py` (`python scripts/gerar_tema_css.py`). **Desde 29/set a marca pública da ocidental é "Valderez Astrologia"** (Padmini é a produtora): tokens e pares de contraste do pacote `docs/design/valderez-1.0/` (referência, não servido); vitrine em `/estilo?previa=<PADMINI_PREVIA_CHAVE>` |
| `static/valderez/` + `static/ocidental/_cabecalho.html`, `_rodape.html`, `_head_valderez.html` | Fontes WOFF2 do próprio site (com as licenças OFL), a roda (símbolo), favicon, SVGs (< 30 KB, sem texto embutido); `casca.css` (cabeçalho, rodapé, menu, cookies, em todas as páginas ocidentais) e `componentes.css` (páginas já vestidas com o pacote, sem `base.css`). Nada de Google Fonts na ocidental. Fases: `docs/valderez.md` |
| `exemplos_ocidental.py` + `static/ocidental/movimento.*` | Casais de exemplo da home e da página do casal (nascimentos fictícios, **calculados pelo motor**, nunca número à mão) e a rosa das 8 dimensões (SVG, também no completo). Movimento só com `prefers-reduced-motion: no-preference` |
| `static/ocidental/_menu.html` | Menu com os 4 produtos em todas as páginas ocidentais (no celular, `details/summary` no cabeçalho). Nenhuma página ocidental usa o `base.css` (é só da védica). `dados_estruturados.py`: JSON-LD da home (Organization, WebSite, FAQPage do YAML; nunca avaliação inventada) |
| `blog.py` + `conteudo/ocidental/blog/` | Blog (só ocidental). Artigo só vai ao ar com `revisado: true`; rascunho abre com `?previa=`. `depoimentos.py` + `conteudo/ocidental/depoimentos.yaml`: só depoimento real com `autorizado_em`; vazio = seção some. Ver `docs/ocidental.md` (round 5) |
| `produtos_ocidental.py` + `conteudo/ocidental/produtos.yaml` + `static/ocidental/produto.html` | **Páginas de produto da ocidental (rodada 9, Fase C)**: o modelo completo (capa, o que recebe, como funciona, trecho real calculado na hora, perguntas, me avise). Ocultos (comunidade, cursos, consulta) prontos com `rascunho: true`, respondendo 404 até o `catalogo.yaml` ligar |
| `icones.py` + `static/valderez/icones/` | **Ícones de traço (rodada 9.1)**, um SVG por ícone; o YAML pede pelo nome (`icone: sol`), o template chama `icone(...)`. A roda é só a marca, nunca ícone de lista. Grades de capas: colunas por `catalogo.colunas` (nenhum cartão sozinho) |
| `roda_mapa.py` | A roda do mapa natal desenhada no servidor (SVG na leitura completa, reportlab no PDF), com os aspectos do próprio mapa. Glifos: Noto Sans Symbols (+ Symbols 2 só para o ☉) |
| `sinastria.py` | Sinastria ocidental: aspectos cruzados, casas, 8 dimensões e o índice (método próprio, pesos em `docs/ocidental.md`). **O nome do índice mora só em `conteudo/ocidental/marca.yaml`** (nos textos, `{indice}`; no código, `textos.NOME_INDICE`) |
| `docs/ocidental.md` | Decisões de método da versão ocidental (orbes, nodo, sem hora, validação) |
| `sistema.py` | `PADMINI_SISTEMA` (vedica \| ocidental): páginas, termos/privacidade (`LEGAIS`), e-mails e tokens de cada versão |
| `estado_site.py` + `painel.py` + `/painel` (`static/ocidental/painel.html`) | **Painel de controle do site (rodada 15)**: modo (`aberto` / `lista_espera` / `manutencao` = 503 "Voltamos já" / `tudo_liberado`), venda, estado de cada produto e páginas escondíveis (`/blog`, `/links`, `/leituras`), sem deploy. **O YAML é o padrão; quem manda no ar é o painel** (tabelas `config_site` e `config_site_historico`, cache de 15 s, banco fora do ar = último estado conhecido + alerta). Senha `PADMINI_PAINEL_SENHA` (16+; sem ela, 404), sessão de 12 h, CSRF, 5 falhas/15 min. "Tudo liberado" vale para todos só na prévia (Stripe `sk_test_`); na produção, só no navegador logado (faixa "Modo teste", completo sem pagar, nunca a venda; páginas assim não entram no cache). `PADMINI_CAPTURA` só como padrão inicial: não usar mais. Ver `docs/painel.md` |
| `catalogo.py` + `conteudo/ocidental/catalogo.yaml` | **O que está no ar na ocidental (rodada 9; desde a rodada 15 o YAML é o padrão e o /painel manda)**: estado de cada produto (`ativo` / `em_breve` = "me avise" / `oculto` = 404 e some de menu, rodapé, sitemap), ordem, dimensões do mapa natal e o **interruptor de venda `vendas_abertas`** (false = nenhum preço, botão ou link da Cakto em página nem e-mail; lembrete, carrinho e boas-vindas parados). Menu, home, rodapé e `/leituras` saem daqui. Token, `/live`, webhook e `/minhas-leituras` não olham para o catálogo. Nos testes, o `conftest` abre a venda; `@pytest.mark.catalogo_real` usa o YAML como está |
| `ilustracoes.py` + `conteudo/ocidental/ilustracoes.yaml` + `static/ilustracoes/<conjunto>/` | **Ilustrações trocáveis (rodada 9)**: o template pede a VAGA (`ilustracao("dim-sol")`, `ilustracao_url(...)`), nunca o arquivo; vaga que falta cai no conjunto reserva e depois num fundo liso. `python scripts/checar_ilustracoes.py [conjunto]` confere nomes, proporção, tamanho mínimo e < 300 KB (teste roda no CI). **Fotos da Dona Valderez (rodada 19.1):** vagas `foto-valderez` (arco grande) e `foto-valderez-rosto` (arcos pequenos), `opcional: true`; os templates chamam `marca.retrato(vaga, …)`, que mostra a roda quando o arquivo falta |
| `static/valderez/v2.css` + `conteudo/ocidental/mapa.yaml` | **Visual 2.0 (rodada 9, pacote valderez-design-2.0)**: home, `/mapa` (formulário → calculando → amostra por dimensões), `/lista`, 404/500, em breve, `/leituras` (`<body class="vz">`). Tokens `--vz-*` em `paleta.VZ` (pares de contraste em `PARES_VZ`), fontes Fraunces/Figtree/Noto Sans Symbols 2. Marca = a roda (`static/valderez/roda*.svg`, `marca.roda()`); favicons PNG e og:image da home: `python scripts/gerar_marca.py`. A amostra recebe da API só as 1–2 primeiras frases de cada dimensão (`mt.dimensoes_amostra`); o desfocado é enfeite |
| `conteudo/ocidental/revisao.yaml` + `textos.frase_revisao` | **Regra de honestidade**: frase sobre a revisão da Dona Valderez com `quando_revisado` / `enquanto_isso`; "revisado" só aparece quando todos os textos tiverem `revisado: true` (teste) |
| `ofertas.py` + `conteudo/<versão>/ofertas.yaml` | **Preço e link de checkout, fonte única.** O app troca os marcadores (`__PRECO_COMPAT__`, `__CHECKOUT_MAPA__`…) no HTML ao servir, e o `cakto.py` tira daí o código da oferta. Mudou o preço? Só o YAML. Preço na tela sempre por `ofertas.moeda` / `{{ x \| moeda }}` (R$96,52, nunca R$96.52); preço com cupom é calculado de `cupom_percentual`; `taxa_plataforma` (topo do YAML) é a taxa da Cakto mostrada ao lado do preço |
| `enderecos.py` + `conteudo/ocidental/marca.yaml` | **Endereço do site, e-mail de contato e redes, fonte única (rodada 18)**: `SITE_URL` (`PADMINI_SITE_URL` ou o `site` do YAML) para canonical, `og:*`, sitemap, JSON-LD e e-mails; nos templates `{{ site }}`, `{{ site_host }}`, `{{ contato }}`, `{{ redes }}`. Nunca `padmini.com.br` nem o e-mail escrito à mão em `static/ocidental/` (teste). O 301 do domínio antigo (`PADMINI_DOMINIO_PRINCIPAL`, vazio = desligado) também mora aqui. Ver `docs/dominio.md`. Rede com `ativa: false` no `marca.yaml` some do site inteiro (`enderecos.REDES` = só as ativas; o Instagram está assim desde a rodada 19.1, até o perfil abrir sem login) |
| `pagina_links.py` + `static/ocidental/links.html` + `conteudo/ocidental/links.yaml` | **`/links`, o link da bio (rodada 19, só ocidental)**: a bio de cada rede aponta para `/links?utm_source=<rede>`; a página repassa a origem (utm_source ou "links", `utm_medium=bio` e `utm_campaign=links` quando faltam, mais ref/cupom/utm_* de `ORIGEM_ACEITA`) a TODO link interno, no HTML do servidor (sem depender de cookie). Botões do catálogo (ativo que vende, com preço e "de" riscado; até 2 em breve). Com a lista de espera ligada abre igual e o principal vai para `/lista`. Na Stripe, só o canal (utm_source/medium/campaign) vai no `metadata`. `scripts/relatorio_origem.py --desde AAAA-MM-DD`: amostras, "me avise" e pedidos pagos por utm_source, só contagens |
| `cidades.py` + `data/cidades_index.tsv` | Autocomplete de cidades (GeoNames) |
| `gerar_pdf.py` | PDF do completo |
| `static/live.html` + rotas `/live`, `/api/live/*` | Modo live do Pedro: senha (`PADMINI_LIVE_SENHA`) → cookie assinado de 12h → token do completo sem pagamento, com log em `live_geracoes` |
| `db.py` | Postgres opcional (`DATABASE_URL`): pedidos, lista de espera (`leads`), cache do texto da IA. Erro no banco nunca impede entrega |
| `limites.py` | Limite de requisições por IP (429): cálculo, PDF, IA, cidades, lista, senha do live |
| `seguranca.py` | Cabeçalhos de segurança (CSP, HSTS, anti-iframe, Referrer-Policy). Serviço externo novo → incluir na CSP |
| `rotas_ocidental.entregar_amostra` + `static/ocidental/amostra-email.js` + `_campo_email.html` | **Ocidental (rodada 6): sem e-mail não há amostra** (422). A API devolve só a parte da tela (`tela_*`); o resto vai por e-mail. E-mail que não sai = tela inteira + alerta. Completo com token e `/live` não pedem e-mail |
| `static/ocidental/consentimento.js` | **Aviso de cookies + pixels (Meta, TikTok, Google), só ocidental.** Nada de terceiro (nem PostHog) antes do "Aceitar"; IDs por env (`PADMINI_META_PIXEL`, `PADMINI_TIKTOK_PIXEL`, `PADMINI_GOOGLE_TAG`, `PADMINI_GOOGLE_ADS_LEAD`); vazio = não carrega nem entra na CSP (`seguranca.CSP_PIXELS`). Nenhum dado pessoal nos eventos |
| `marketing.py` + `static/amostra-email.js` | Amostra por e-mail, lembrete (`/api/tarefas/lembretes`), carrinho abandonado, venda cruzada, descadastro (`/descadastrar`). Nas duas versões: cada e-mail sai na versão **do registro** (coluna `sistema`), nunca na do ar; copy em `marketing.TEXTOS` |
| `/minhas-leituras` (`app.py`) + `static/ocidental/minhas-leituras.html` | **Recuperar leituras sem login** (ocidental): um e-mail com todos os links de `pedidos`; resposta sempre igual (não revela quem comprou), envio em segundo plano, limites por IP e por e-mail |
| `sequencias.py` | **Sequências de e-mail (rodada 6, ocidental)**: boas-vindas D+1/3/6 (só com a caixa `aceita_sequencia`; para ao comprar) e pós-compra D+2/7/14. Tarefa diária `/api/tarefas/sequencias`; `envios_sequencia` garante um passo por pessoa por dia e nunca o mesmo passo duas vezes |
| `alertas.py` | E-mail para a equipe (`PADMINI_ALERTA_EMAIL`): pedido pago sem entrega, e-mail que não saiu, erro 500 |
| `.github/workflows/` | `testes` (CI), `pos-deploy` (smoke de hora em hora; **nunca** no push, senão trava o deploy da Render), `tarefas` (lembretes diários + limpeza de marketing: descadastro ou 24 meses sem interação, `db.limpar_marketing`), `backup` (semanal, criptografado), `manter-ativo` |
| `docs/melhorias-2026-09.md` | O que entrou em 25/set (preços, e-mails de venda, alertas, backup) e a configuração pendente |
| `docs/seguranca.md` | **Revisão de segurança (25/set/2026)**: o que foi corrigido, limites, pendências |
| `static/lista.html` + `/api/lista` | Lista de espera e **"me avise"** (`static/ocidental/_me_avise.html` + `me-avise.js`, `interesse` = chave do catálogo; na ocidental nome e WhatsApp obrigatórios, o aviso por WhatsApp depende da caixa própria). Lista de espera do lançamento. O modo "Lista de espera" do `/painel` (antes, `PADMINI_CAPTURA=1`, que segue valendo só como padrão) trava home/mapa/compat e manda para `/lista` (links de entrega com `token`, quem tem `?previa=<PADMINI_PREVIA_CHAVE>` e o navegador logado no painel passam) |

## Regras (cada uma vem de um erro real)
1. **Rodar os testes antes de commitar:** `python -m pytest -q testes`. Tudo verde ou não sobe.
   Os testes do banco precisam de `TEST_DATABASE_URL` (Postgres local); no CI rodam sempre.
2. **Ler o diffstat antes de commitar.** Arquivo de produção encolhendo centenas de linhas = suspeito
   (parte 16: stubs de teste de `cidades.py`/`gerar_pdf.py` foram para produção e travaram o site).
3. **Nunca sobrepor o repositório com outro diretório em bloco.** Copiar só o que mudou de propósito.
4. **Segurança falha fechada:** sem segredo configurado, webhook e completo recusam
   (parte 17: o webhook aceitava qualquer POST). Testar o caminho de rejeição, não só o de aceite.
5. **Integração externa: ler a doc oficial antes.** A Cakto só repassa `utm_*` e `sck` ao webhook.
6. **Bug encontrado = teste novo** em `testes/` que falharia com o bug.
7. **Depois de cada deploy:** `python scripts/smoke_producao.py`.
8. Não gravar CPF nem dados de cartão no banco (vêm no payload da Cakto).
9. `PADMINI_MODO_ABERTO=1` só em staging, **nunca** em produção.
10. **O repositório público é o que cumpre a licença AGPL do Swiss Ephemeris** (publicar
    o código, com o `LICENSE` AGPL-3.0, é a via gratuita, em vez de comprar a licença
    profissional, CHF 700 — revisitar quando houver faturamento). Por isso o conteúdo
    proprietário (textos de interpretação védicos e ocidentais, rascunhos do blog) fica
    fora dele, no `padmini-conteudo` — ver "Fontes de verdade" —, em vez de o repositório
    inteiro virar privado. **Nunca recolocar esses arquivos aqui.** Ressalva (não é parecer
    jurídico): a AGPL talvez alcance conteúdo de que o programa precisa para rodar ("obra
    combinada"); revisar com advogado quando houver faturamento.

11. **O `sck` é dado do comprador, não prova de pagamento.** Qual produto entregar sai só da
    oferta paga que a Cakto informa (`cakto.produto_pago`). Ver `docs/seguranca.md`.

12. **Preço nunca escrito à mão em HTML** (a página do casal anunciou R$127 em vez de R$97):
    sempre `{{ ofertas.<produto>.preco }}`. Há teste que procura "R$" + número nos HTML.
13. **E-mail de marketing só com consentimento e com descadastro** (`marketing.py`); na
    dúvida (sem banco), não manda.

## Commits
Mensagens em português, explicando o porquê. Sem force-push na `master`.

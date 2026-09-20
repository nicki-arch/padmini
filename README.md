# Padmini — Astrologia Védica (v0.6)

Site com dois produtos de astrologia védica (Jyotish), em modelo **freemium** (amostra grátis → paga para ver o completo):

- **Mapa individual** — Ascendente, nakshatra da Lua, fase de vida (dasha) e o mapa completo.
- **Compatibilidade de casal** (produto-âncora) — Guna Milan / Ashtakoot, 8 kootas = 36 pontos, doshas e Mangal.

Visual "Lótus à meia-luz" (full dark), com design system compartilhado (`static/base.css`).

## Rotas

Páginas: `/` (home), `/mapa`, `/compatibilidade`, `/privacidade`, `/termos`.
API: `POST /api/mapa`, `POST /api/compatibilidade`, `POST /api/pdf`, `GET /api/cidades`, `GET /api/config`, `POST /webhook/cakto`.

Cada endpoint de produto aceita `nivel: "amostra" | "completo"`. A **amostra é sempre grátis**; o **completo exige token** (ver "Acesso ao completo").

## Publicação

Roda no Render (https://padmini.onrender.com), ligado ao GitHub: cada `git push` na `master` publica em 1–2 min.

**Variáveis de ambiente no Render:**

| Variável | Para quê |
|---|---|
| `ANTHROPIC_API_KEY` | Texto por IA (opcional; o botão de IA só aparece se existir) |
| `PADMINI_MODELO` | Trocar o modelo (padrão `claude-sonnet-5`) |
| `PADMINI_SECRET` | **Obrigatório em produção** — assina os tokens do completo |
| `PADMINI_MODO_ABERTO` | `1` libera o completo sem token. **Só em staging — NUNCA em produção** |
| `PADMINI_SITE_URL` | Base dos links de entrega (padrão `https://padmini.com.br`) |
| `PADMINI_CAKTO_WEBHOOK_SECRET` | Verifica a origem do webhook da Cakto |
| `PADMINI_CAKTO_PROD_MAPA` / `_COMPAT` | IDs dos produtos na Cakto (fallback p/ identificar o produto) |
| `RESEND_API_KEY` | Envio do e-mail de entrega (via Resend). Sem ela, o webhook devolve o link para envio manual |
| `PADMINI_EMAIL_FROM` | Remetente do e-mail (padrão `Padmini <nao-responda@padmini.com.br>`) |
| `PADMINI_POSTHOG_KEY` | Métricas de funil (PostHog). Em branco = desligado; nada é carregado |
| `PADMINI_POSTHOG_HOST` | Host do PostHog (padrão `https://us.i.posthog.com`; use `https://eu.i.posthog.com` na região UE) |

**Antes de publicar ao público:** definir `PADMINI_SECRET`; **não** definir `PADMINI_MODO_ABERTO`; revisar as páginas legais.

## Acesso ao completo (gate)

O completo e o PDF são pagos, então o servidor os bloqueia (HTTP 402) sem um **token assinado** (`acesso.py`, HMAC sobre os dados de nascimento).

- **Teste local/staging:** `PADMINI_MODO_ABERTO=1` libera tudo; ou gere um token com `python emitir_token.py mapa 1990-09-15 14:30 -30.03 -51.21` (precisa de `PADMINI_SECRET`).
- **Produção:** o token vem do webhook (abaixo).

## Webhook da Cakto (entrega automática)

Fluxo: amostra → o botão de compra leva ao checkout da Cakto **carregando os dados de nascimento** como parâmetros `pd_*` (montados em `afiliado.js → linkCheckout`) → após o pagamento, a Cakto chama `POST /webhook/cakto` → o backend confere a origem, lê o produto/e-mail/dados, **emite o token** e **manda o e-mail** (`entrega.py`) com o link do completo (`/mapa?...&token=...` ou `/compatibilidade?...&token=...`). Abrir esse link renderiza o relatório completo.

**⚠️ ADAPTAR À CAKTO** (ver comentários no topo de `cakto.py`) — três coisas a confirmar no painel/documentação da Cakto:
1. **Assinatura do webhook** (header/segredo) — hoje conferimos `PADMINI_CAKTO_WEBHOOK_SECRET`.
2. **Nomes de status** de "aprovado" (lista `APROVADOS` em `cakto.py`).
3. **Repasse dos `pd_*`** ao webhook (custom params/metadata). Se a Cakto não repassar, será preciso outra ponte (ex.: guardar o pedido por um id).

Sem `RESEND_API_KEY`, o webhook responde com o `link` no corpo — dá para copiar e enviar à mão no soft launch.

## Métricas de funil (opcional)

`static/analytics.js` mede o funil com **PostHog**, e só liga se `PADMINI_POSTHOG_KEY` existir (em branco, o site funciona igual e nada é carregado). Toda a atribuição de afiliado/campanha (`ref`, `utm_*`) entra em cada evento, para medir a conversão por origem (TikTok, afiliado).

Eventos: `pageview` (automático), `amostra_gerada`, `checkout_click`, `completo_aberto`, `card_baixado`, `feedback` — todos com `{ produto: "mapa" | "compat" }`. A API `window.padTrack(evento, props)` fica disponível sempre; se as métricas estiverem desligadas, é um no-op silencioso.

## Rodar no Windows

Dê dois cliques em **`iniciar.bat`** (baixa `uv`, cria Python 3.11 em `.venv/`, instala libs, pede a chave da Anthropic e sobe em http://127.0.0.1:8000). Para reinstalar, apague `.venv` e `.ferramentas`.

O índice de cidades (`data/cidades_index.tsv`) já vem pronto; para refazer, `python baixar_dados.py`.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `compute_chart.py` | Cálculo do mapa: Lahiri, casas por signo inteiro, nó médio, fuso automático |
| `detectar_fatos.py` | Regras clássicas: dignidades, combustão, yogas, doshas |
| `compatibilidade.py` | Motor de compatibilidade (8 kootas, doshas, Mangal, paywall) |
| `base_significacoes.py` | Textos interpretativos: mapa + kootas/doshas de casal (rascunho, revisar) |
| `montar_texto.py` | Monta os relatórios (mapa e casal) e os prompts para o Claude |
| `acesso.py` | Gate do completo (token HMAC) |
| `emitir_token.py` | CLI para emitir token de acesso ao completo |
| `entrega.py` | Link do completo + envio do e-mail (Resend) |
| `cakto.py` | Parsing/verificação do webhook da Cakto (adaptar) |
| `gerar_pdf.py` | Relatório completo em PDF (sem IA) |
| `cidades.py` / `baixar_dados.py` | Busca local de cidades (GeoNames) |
| `app.py` | Servidor web (FastAPI) — rotas acima, incluindo `/webhook/cakto` |
| `static/base.css` | Design system (tokens + componentes). Ver `design-system.md` |
| `static/home.html` · `index.html` · `compatibilidade.html` | Páginas (home, mapa, casal) |
| `static/privacidade.html` · `termos.html` | Páginas legais (modelo) |
| `static/afiliado.js` | Atribuição de afiliado + montagem do link de checkout (`pd_*`) |
| `static/analytics.js` | Métricas de funil (PostHog, opcional) + `window.padTrack` |
| `static/og-*.png` | Imagens Open Graph (versionadas no repo) |

## Testes

```
python testes/test_referencias.py        # 5 mapas conhecidos vs Cosmolica (tolerância 2')
python testes/test_compatibilidade.py    # invariantes do motor + tabela de validação (5 casais)
```

A validação de compatibilidade contra o Prokerala (`validacao-compatibilidade.md`) ainda está pendente — **gate antes de cobrar**.

## Pendências conhecidas

- **Validar** as tabelas preliminares de compatibilidade (Vashya, meio de Yoni, direção de Gana) contra o Prokerala.
- **Cakto:** confirmar os 3 pontos de `cakto.py` e configurar as variáveis de ambiente do webhook.
- **Páginas legais** são modelo — revisar com advogado e preencher os campos [entre colchetes].
- Textos de planeta em cada casa (108) ainda não existem.
- Raj Yoga só por conjunção; Neecha Bhanga só condição principal; Mangal Dosha (individual) sem cancelamento.
- Busca de cidades entende só o nome; nomes estrangeiros aparecem em inglês.
- **Licença AGPL** do Swiss Ephemeris: site público obriga a publicar o código, ou comprar a licença profissional.
- GeoNames (CC BY 4.0) exige o crédito do rodapé.

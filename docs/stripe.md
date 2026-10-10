# Checkout próprio com a Stripe (rodada 11)

Brief de 8/out/2026 (substitui a Fase B do brief da rodada 8). A Cakto continua: o
webhook dela funciona nos dois modos. A Stripe vale só para a **versão ocidental**
(a que tem catálogo); a védica não muda.

## Os interruptores (`pagamento.py`)

| Variável | Valores | O que faz |
|---|---|---|
| `PADMINI_PAGAMENTO` | `cakto` (padrão) \| `stripe` | Quem cobra. Valor desconhecido = o site não sobe (como `PADMINI_SISTEMA`). |
| `PADMINI_VENDAS_TESTE` | `1` | Abre a venda **só naquele serviço**, sem mexer no `catalogo.yaml`. Aceito só com `PADMINI_PAGAMENTO=stripe` e `STRIPE_SECRET_KEY` de teste (`sk_test_…` ou `rk_test_…`). Com chave de produção, sem chave ou com a Cakto, o site não sobe e diz por quê. Produtos `em_breve` continuam em breve. |

As mensagens de erro dizem o **prefixo** da chave (`sk_live_…`), nunca a chave.

## O pedido pendente (`pendentes.py`, tabela `pedidos_pendentes`)

Na Cakto os dados de nascimento iam no `sck` da URL do checkout. Na Stripe ficam com a
gente: o pedido nasce no nosso banco **antes** do pagamento, e a Stripe recebe só o
`id` opaco dele (em `metadata` e `client_reference_id`) e o e-mail (`customer_email`).

| Coluna | O que é |
|---|---|
| `id` | 24 caracteres aleatórios (`secrets.token_urlsafe(18)`); não diz nada da pessoa nem do produto |
| `sistema` | `ocidental` |
| `itens` | `[{chave, dados, valor_centavos}]` — a chave do catálogo, os dados daquela leitura (mesmo formato de `cakto.dados_nascimento`) e o preço calculado no servidor. Um item por compra nesta rodada |
| `email`, `nome` | o e-mail do contato; o nome de quem é a leitura |
| `consentimentos` | `{aceita_sequencia}` (a caixa da amostra) |
| `rastreio` | `ref`, `cupom`, `utm_*` (fica conosco, não vai para a Stripe) |
| `cupom` | o código, se vale para o produto |
| `valor_centavos`, `moeda` | total, em centavos de `brl` |
| `stripe_session_id` | a Checkout Session criada para ele (uma só) |
| `estado` | `aberto` → `pago` \| `expirado` \| `falhou`. `pago` é final |

- **Preço:** nunca do navegador. O corpo do `POST /api/checkout` não tem campo de preço
  (o que vier a mais é descartado) e o valor sai do `ofertas.yaml`. O cupom
  (`cupom_codigos` + `cupom_percentual`) é aplicado aqui, não por código promocional da
  Stripe. Sem a taxa da plataforma da Cakto (R$0,99): na Stripe a pessoa paga o preço.
- **Limpeza:** não pagos com mais de 7 dias saem na tarefa diária
  (`/api/tarefas/limpeza` → `db.limpar_pendentes`). Os pagos ficam (a compra também
  está em `pedidos`).
- **Sem banco não há checkout** (falha fechada): os dados da leitura precisam estar lá
  quando o webhook chegar. A prévia precisa de `DATABASE_URL`.

## Para o Nicolas / Cowork (configuração)

Só por variável de ambiente, nunca no repositório nem em log. Primeiro só na
`padmini-previa`, em modo de teste:

| Serviço | Variável | Valor |
|---|---|---|
| `padmini-previa` | `PADMINI_PAGAMENTO` | `stripe` |
| `padmini-previa` | `PADMINI_VENDAS_TESTE` | `1` |
| `padmini-previa` | `STRIPE_SECRET_KEY` | `sk_test_…` |
| `padmini-previa` | `STRIPE_PUBLISHABLE_KEY` | `pk_test_…` |
| `padmini-previa` | `STRIPE_WEBHOOK_SECRET` | `whsec_…` do endpoint abaixo |
| `padmini-previa` | `DATABASE_URL` | um Postgres (pode ser outro banco que o de produção) |
| `padmini-previa` | `PADMINI_SITE_URL` | o endereço da prévia (é para lá que a Stripe devolve: `return_url`) |

No painel da Stripe (modo de teste): ativar cartão, Pix, Apple Pay e Google Pay em
*Settings → Payment methods*; marca e cores em *Settings → Branding*; e **registrar o domínio** da
prévia (e depois `padmini.com.br`) em *Settings → Payment method domains* — sem isso o Apple Pay
não aparece no checkout embutido (docs.stripe.com/payments/payment-methods/pmd-registration).

A produção só troca para `stripe` quando o Nicolas decidir abrir a venda.

## O checkout (Fase 2: `rotas_checkout.py`, `stripe_api.py`, `static/ocidental/comprar.js`)

1. **Botão de compra** (`/mapa`, `/compatibilidade`, `/numerologia`, `/tarot`): no modo `stripe` ele
   leva `data-comprar="<produto>"` e o `comprar.js` manda para `POST /api/checkout` o produto, os
   dados da leitura, o e-mail, a caixa da sequência e a origem (`ref`, `cupom`, `utm_*`). **Sem preço**
   e sem dado pessoal na URL (acabou o `sck` no modo stripe). Com a Cakto, o botão é o de sempre.
2. **`POST /api/checkout`**: valida (422), confere `catalogo.vende(produto)` (404 para `em_breve`,
   `oculto` ou venda fechada), monta o pendente (preço do catálogo, cupom no servidor), grava (sem
   banco = 503), cria a Checkout Session e devolve `{"url": "/checkout/{id}"}`. A Stripe recebe:
   `ui_mode=embedded_page`, `mode=payment`, `line_items[].price_data` (nome do produto + preço, em
   BRL), `customer_email`, `client_reference_id` e `metadata.pedido` (o id opaco, também no
   `payment_intent_data.metadata`), `return_url=/obrigado/{id}`, `locale=pt-BR`. Chave de
   idempotência = o id do pedido. Os meios de pagamento vêm do painel.
3. **`/checkout/{id}`**: resumo (produto, de quem é a leitura, preço) + o Embedded Checkout
   (`js.stripe.com/endive/stripe.js`, mesma versão da API do servidor, `2026-09-30.endive`). O
   `client_secret` vem por `GET /api/checkout/{id}` (só pedido aberto). Pedido pago → "já foi pago";
   expirado/falho → "expirou, comece de novo".
4. **`/obrigado/{id}`** (o `return_url`): pergunta `GET /api/checkout/{id}/estado` a cada 3 s (10 s
   depois de 2 min, até 30 min). **Só o webhook confirma** (Fase 3): enquanto o pedido não está
   `pago` não há link, mesmo com a sessão da Stripe paga. Sessão `complete` + `unpaid` = "aguardando
   o Pix"; sessão `open` = "o pagamento não foi concluído".
5. **Sem a taxa da Cakto** (R$0,99) nas páginas, e a copy diz "pagamento seguro pela Stripe"
   (`pagamento_stripe` / `resposta_stripe` nos YAML). Sem order bump na sinastria.
6. **E-mails** (lembrete, boas-vindas, pós-compra): no modo stripe o botão leva à página do produto
   (`marketing.link_site`), não ao checkout: dado de nascimento não vai em URL.
7. **Segurança**: a CSP libera a Stripe **só em `/checkout/`** (`seguranca.CSP_STRIPE`, origens de
   "Checkout" + "Stripe.js" da doc, sem `maps.googleapis.com`), e só lá o `Permissions-Policy` deixa
   `payment` para a Stripe (Apple Pay / Google Pay no iframe). O Stripe.js não depende do aceite de
   cookies. Limites: 10 checkouts por IP a cada 10 min; 240 consultas de estado.

Fases seguintes (webhook, privacidade, relatório) completam esta página.

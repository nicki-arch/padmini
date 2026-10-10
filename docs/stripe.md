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

A produção só troca para `stripe` quando o Nicolas decidir abrir a venda.

Fases seguintes (checkout, webhook, privacidade, relatório) completam esta página.

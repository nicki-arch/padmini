# Segurança do Padmini

Registro da revisão de segurança de **25/set/2026** e do que ficou implementado.
Mantenha este arquivo atualizado quando mexer em webhook, token, limites ou cabeçalhos.

## Resumo do que foi corrigido

| # | Gravidade | Problema | Correção | Onde |
|---|---|---|---|---|
| 1 | 🔴 Grave | O `sck` (montado no navegador) decidia o produto entregue: pagava-se o mapa (R$47) com `sck=c~…` na URL e o webhook entregava a compatibilidade (R$97). | O produto vem só do que a Cakto diz que foi pago (`offer.id`, `checkoutUrl`, `product.id`). Se o `sck` pedir outro produto, ou se a oferta paga não for reconhecida, **não sai link**: o pedido é gravado como pendente (entrega manual). | `cakto.produto_pago`, `cakto.produto_do_evento`, `app._processar_pedido` |
| 1b | 🔴 Grave (latente) | Com o código do order bump vazio, **qualquer** bump com `sck` de casal virava os 2 mapas. | Sem código configurado, o bump não é reconhecido (falha fechada). | `cakto.e_bump_mapas_do_casal` |
| 2 | 🔴 Grave | `/api/compatibilidade` chamava a IA (Claude) na amostra grátis com `texto_ia=true`, sem cache. Um script em loop gerava custo sem limite. | IA só no `nivel=completo` com token válido; o texto fica guardado no banco (um por casal, como já era no mapa); cada chamada nova à IA também tem limite por IP. | `app.compatibilidade` |
| 3 | 🟠 Médio | O PostHog recebia a URL inteira: token do relatório pago, data/hora/local e nome (links de entrega e `sck` do checkout via autocapture). | `before_send`/`sanitize_properties` trocam o valor desses parâmetros por `[removido]` em qualquer texto do evento. `utm_*`, `ref` e `cupom` continuam. | `static/analytics.js` |
| 4 | 🟠 Médio | Sem limite de requisições: força bruta na senha do live, lixo na lista de espera, mapas/PDF em loop derrubando a instância. | Limite por IP em memória (janela deslizante), com resposta 429 e `Retry-After`. | `limites.py` |
| 5 | 🟠 Médio | Nenhum cabeçalho de segurança. | CSP, HSTS, `X-Frame-Options: DENY`, `Referrer-Policy`, `nosniff`, `Permissions-Policy` em toda resposta. | `seguranca.py` |
| 6 | 🟡 Baixo | Nome do comprador (vem do `sck`) entrava cru no HTML do e-mail. | `html.escape` no nome e nos links. | `entrega.py` |
| 7 | 🟡 Baixo | Webhook sem checagem de idade do timestamp (replay). | Assinatura do header só vale com `X-Cakto-Timestamp` de até 5 min de diferença (igual ao exemplo oficial da Cakto). | `cakto.metodo_de_verificacao` |
| 7b | 🟡 Baixo | `is_aprovado` aceitava "paid/approved/success…" em **qualquer** campo `status`/`type` do payload, inclusive no bloco da adquirente. | Só `event == purchase_approved` (quando vier) e `data.status` em `paid`/`approved`. | `cakto.is_aprovado` |
| 7c | 🟡 Baixo | `hmac.compare_digest` com texto não-ASCII (senha do live ou `secret` do webhook com acento) dava erro 500. | Comparação feita em bytes: responde 401. | `app.live_entrar`, `cakto._iguais` |

Todos os itens têm teste em `testes/test_seguranca.py` (e 2 em `testes/test_db.py`) que **falha
com o código antigo**. Conferido: 30 dos 39 testes novos falham se o código de produção for
revertido. Os outros são testes de regressão do comportamento que já estava certo.

## Limites por IP (`limites.py`)

| Limite | Cota | Onde |
|---|---|---|
| Cálculo (mapa/casal, amostra ou completo) | 60 / min | `/api/mapa`, `/api/compatibilidade` |
| PDF | 20 / min | `/api/pdf` |
| Chamada **nova** à IA (a que sai do cache não conta) | 20 / hora | `texto_ia` no mapa e no casal |
| Busca de cidades | 300 / min | `/api/cidades` |
| Lista de espera | 20 / 10 min | `/api/lista` |
| Senha do live: **erros** por IP | 5 / 15 min | `/api/live/entrar` |
| Senha do live: **erros** no total (todos os IPs) | 30 / hora | `/api/live/entrar` |

- Os números são folgados de propósito: operadoras de celular no Brasil colocam muita gente
  atrás do mesmo IP (CGNAT), e numa live muita gente chega junta. Se aparecer reclamação de
  "Muitas tentativas seguidas", aumente o número em `limites.py`.
- O IP vem de `CF-Connecting-IP` (Cloudflare, na frente da Render), depois do 1º item de
  `X-Forwarded-For`, e por último da conexão.
- Os contadores ficam em memória: zeram a cada deploy e contam por instância. Hoje a Render
  roda **1 instância**. Se um dia forem várias, o limite efetivo fica multiplicado.
- **Efeito colateral aceito do teto global do live:** sob ataque, o login do live pode ficar
  travado por até 1h para todo mundo. **O Pedro deve entrar antes de começar a live**, porque
  a sessão dura 12h e não é afetada pelo limite.

## Cabeçalhos de segurança (`seguranca.py`)

A CSP libera só o próprio site, o Google Fonts e o PostHog. As origens do PostHog saem de
`PADMINI_POSTHOG_HOST`.
**Ao adicionar um serviço externo** (outro analytics, pixel da Meta, CDN, widget), inclua a
origem dele em `seguranca.politica_csp()`. Se não incluir, o navegador bloqueia e aparece um erro
"Content Security Policy" no console. O teste `test_csp_cobre_recursos_externos_das_paginas`
pega os casos de `<script src>` e `<link rel=stylesheet>` nas páginas.

Conferido num navegador real (Chromium headless): home, mapa, compatibilidade, lista, live,
privacidade, termos, link de entrega do mapa (com download do PDF), link de entrega do casal e
a amostra pelo formulário, **sem nenhum bloqueio de CSP**.

Limitação conhecida: as páginas têm `<script>` e `onclick` inline, então `script-src` inclui
`'unsafe-inline'`. A CSP ainda impede carregar script de outro domínio, mandar dados para
outro domínio (`connect-src`) e embutir o site num iframe. Mas uma injeção de HTML com script
inline executaria. Hoje o front-end escapa tudo o que vai para `innerHTML`, e não há XSS
conhecido.

## Webhook da Cakto: o que mudou e o que falta ligar

Validação (ver `cakto.metodo_de_verificacao`):
1. **Assinatura no header** (`X-Cakto-Signature: v1=…` sobre `{timestamp}.{corpo}`), com
   timestamp de até 5 min. É a forma recomendada pela Cakto.
2. **`secret` no corpo**: continua aceito porque não deu para confirmar em produção que as
   entregas reais chegam assinadas (nenhum webhook nos logs da Render dos últimos 30 dias).
   Essa forma **não protege contra replay**: quem captura um corpo leva o segredo junto.

O app agora registra no log da Render como cada webhook foi validado:
`webhook: origem provada por assinatura` ou `… por corpo`.

➡️ **Pendência (Nicolas):** depois das primeiras vendas, procure essa linha no log da Render.
Se aparecer sempre `assinatura`, crie na Render a variável
`PADMINI_CAKTO_EXIGIR_ASSINATURA=1`. Isso desliga a forma 2 e não precisa de deploy, só
reiniciar o serviço.

### Pedidos "pendentes" (entrega manual)
O webhook responde 200 e grava o pedido **sem link** (coluna `link` nula) quando:
- o `sck` não trouxe os dados de nascimento (já era assim);
- **novo:** a oferta paga não é reconhecida, ou o `sck` pede outro produto que não o pago.

Para achar esses pedidos no banco:
```sql
SELECT criado_em, cakto_id, produto, email, rastreio->>'sck' AS sck
FROM pedidos WHERE link IS NULL ORDER BY criado_em DESC;
```
Um `sck` de casal num pedido de `mapa` (ou o contrário) é quase certamente tentativa de
fraude. Entregue só o que foi pago.

### Order bump "casal + 2 mapas"
Continua sem código em `conteudo/ofertas.yaml` (a oferta ainda não existe na Cakto). **Quando
criar a oferta, preencha o `checkout` dela no YAML** (ou `PADMINI_CAKTO_OFERTA_BUMP_MAPAS`).
Sem isso, o bump agora é ignorado (antes, qualquer bump virava os 2 mapas).

## O que ficou de fora (decisão de produto, não implementado)

- **Links do completo não expiram nem podem ser revogados.** Quem recebe um link repassado
  tem acesso para sempre, e reembolso/chargeback não corta o acesso. Para revogar, seria
  preciso uma lista de tokens bloqueados no banco, consultada em `acesso.completo_liberado`,
  alimentada pelos eventos `refund`/`chargeback` da Cakto.
- **Tirar `'unsafe-inline'` da CSP:** exige mover os scripts inline das páginas para arquivos
  `.js` e trocar `onclick="…"` por `addEventListener`.
- **Gravação de sessão do PostHog:** se for ligada no painel do PostHog, ela grava a tela,
  inclusive o relatório. Hoje não está ligada no código. Se ligar, use
  `session_recording: { maskAllInputs: true, maskTextSelector: "#resultado" }` no
  `analytics.js`.

## Checklist ao mexer em segurança
- [ ] `python -m pytest -q testes` verde (com `TEST_DATABASE_URL` para os testes do banco).
- [ ] Caminho de **rejeição** testado, não só o de aceite (regra 4 do CLAUDE.md).
- [ ] Depois do deploy: `python scripts/smoke_producao.py`. Ele agora também confere os
      cabeçalhos de segurança e que a IA não sai na amostra grátis.

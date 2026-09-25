# Atualização para o Claude Project "Projeto Padmini": segurança (25/set/2026)

> Esta sessão do Claude Code não tem acesso de escrita ao Claude Project. Copie cada bloco
> abaixo para o arquivo indicado. O registro técnico completo está em `docs/seguranca.md` no
> repositório.

---

## → `claude/LEIA-PRIMEIRO.md` (seção de estado atual)

**Segurança (25/set/2026):** revisão completa feita e corrigida na branch
`claude/epic-hawking-40469f` (aguardando merge na `master`). Principais pontos: o webhook não
confia mais no `sck` para decidir o produto (dava para pagar R$47 e levar o de R$97); a IA não
roda mais na amostra grátis do casal; limites de requisição por IP; cabeçalhos de segurança
(CSP/HSTS); o PostHog não recebe mais o token nem os dados de nascimento. Detalhes e
pendências em `docs/seguranca.md` no repositório.

---

## → `claude/decisoes.md`

### 25/set/2026: Segurança: o produto entregue sai só da oferta paga
- **Decisão:** o webhook decide o que entregar pelo que a Cakto informa como pago (`offer.id`,
  `checkoutUrl`, `product.id`). O `sck` só carrega os dados de nascimento.
- **Por quê:** o `sck` é montado no navegador e pode ser editado na URL do checkout. Antes,
  pagar o mapa (R$47) com um `sck` de casal entregava a compatibilidade (R$97).
- **Consequência:** se a oferta paga não for reconhecida, ou se o `sck` pedir outro produto, o
  pedido fica **pendente** (gravado no banco sem link) para entrega manual. A consulta SQL está
  em `docs/seguranca.md`.

### 25/set/2026: Order bump só é reconhecido com o código da oferta configurado
- Antes, com o código vazio, qualquer bump num checkout de casal virava os 2 mapas.
- Agora, sem código no `ofertas.yaml` (ou em `PADMINI_CAKTO_OFERTA_BUMP_MAPAS`), o bump é
  ignorado. **Ao criar a oferta na Cakto, preencher o YAML.**

### 25/set/2026: Texto por IA só no relatório pago
- A compatibilidade chamava o Claude na amostra grátis (custo aberto para qualquer script).
  Agora a IA só roda no completo com token, e o texto fica guardado no banco (um por casal).

### 25/set/2026: Limites por IP e cabeçalhos de segurança
- Limites em memória (1 instância na Render): cálculo 60/min, PDF 20/min, IA nova 20/h,
  cidades 300/min, lista 20 a cada 10 min, senha do live 5 erros a cada 15 min por IP e 30
  erros/h no total.
- Os números são folgados por causa do CGNAT das operadoras de celular (muita gente no mesmo
  IP durante a live).
- CSP, HSTS, anti-iframe e `Referrer-Policy` em toda resposta. **Serviço externo novo
  (pixel, analytics, CDN) precisa entrar na CSP** em `seguranca.py`.

### 25/set/2026: PostHog não recebe token nem dados de nascimento
- `analytics.js` troca o valor de `token`, `sck`, data/hora/lat/lon/nome/cidade (e `a_*`/`b_*`)
  por `[removido]` antes de enviar qualquer evento. `utm_*`, `ref` e `cupom` continuam, para a
  atribuição.

### 25/set/2026: Não implementado (decisão de produto em aberto)
- Links do completo continuam **sem validade e sem revogação**, inclusive após
  reembolso/chargeback. Caminho sugerido: lista de tokens bloqueados no banco, alimentada pelos
  eventos `refund`/`chargeback`.

---

## → `claude/checklist-de-lancamento.md`

- [ ] **Fazer o merge** da branch `claude/epic-hawking-40469f` (correções de segurança) na `master`
      e rodar `python scripts/smoke_producao.py` depois do deploy. O smoke agora confere também
      os cabeçalhos e a IA fora da amostra.
- [ ] Depois das primeiras vendas reais: no log da Render, procurar
      `webhook: origem provada por assinatura`. Se todas vierem assim, criar
      `PADMINI_CAKTO_EXIGIR_ASSINATURA=1` na Render (desliga a validação pelo `secret` do corpo,
      que não protege contra replay).
- [ ] Olhar os pedidos pendentes (`link IS NULL` na tabela `pedidos`) a cada dia de vendas.
      Um `sck` de casal em pedido de mapa é tentativa de fraude: entregar só o que foi pago.
- [ ] Ao criar o order bump "casal + 2 mapas" na Cakto: preencher o `checkout` dele em
      `conteudo/ofertas.yaml`.
- [ ] Pedro: entrar no `/live` **antes** de começar a transmissão (a sessão dura 12h; sob
      ataque, o login pode ficar travado por até 1h).
- [ ] Ao adicionar um pixel ou analytics novo: incluir a origem na CSP (`seguranca.py`).
- [ ] Senha do live (`PADMINI_LIVE_SENHA`) longa e aleatória (16+ caracteres): o limite de
      tentativas ajuda, mas não substitui uma senha forte.

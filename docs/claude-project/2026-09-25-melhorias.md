# Atualização para o Claude Project "Projeto Padmini": melhorias (25/set/2026, parte 2)

> Copie cada bloco para o arquivo indicado no Claude Project. O registro técnico está em
> `docs/melhorias-2026-09.md` no repositório.

---

## → `claude/LEIA-PRIMEIRO.md` (estado atual)

**Melhorias (25/set/2026):**
- Preços errados corrigidos: a página do casal dizia R$127, e agora todo preço sai do
  `ofertas.yaml`. A nota aparece como "14", não "14.0".
- E-mails de venda: amostra por e-mail, um lembrete (só com consentimento), recuperação de
  carrinho abandonado e venda cruzada no e-mail de entrega. Todos têm link de descadastro.
- Card compartilhável com o endereço em destaque e botão de compartilhar no celular.
- Operação: alertas por e-mail para a equipe, backup semanal criptografado e conferência
  automática depois de cada deploy.
- Cada peça fica desligada até ser configurada (ver checklist).

---

## → `claude/decisoes.md`

### 25/set/2026: Preço só no ofertas.yaml, inclusive nas páginas
A página do casal anunciava "completo por R$127" (o riscado). Todo "R$" dos HTML agora vem
do YAML, e um teste impede preço escrito à mão.

### 25/set/2026: E-mails de venda, sempre com consentimento
- **Amostra por e-mail:** vai só para quem pediu.
- **Lembrete:** um único, só se a pessoa marcar a caixa, que vem desmarcada.
- **Carrinho abandonado:** um e-mail por pessoa e oferta a cada 7 dias.
- Todos têm descadastro. Quem se descadastra não recebe mais marketing, mas continua
  recebendo a entrega das compras.
- Sem banco, não sai marketing (não há como evitar repetição).

### 25/set/2026: Venda cruzada no e-mail de entrega
Quem compra o casal recebe o link do mapa individual de cada um, com o checkout preenchido.
Quem compra o mapa recebe o convite para a compatibilidade. Cupom opcional via
`cupom_pos_compra` no YAML.

### 25/set/2026: Backup próprio, criptografado
O Supabase grátis não tem backup para baixar. Um workflow semanal faz o `pg_dump`,
criptografa com senha (o repositório é público) e guarda 90 dias no GitHub.

### 25/set/2026: Não implementado
- **Revisão dos textos:** é trabalho do Pedro, no repositório `padmini-conteudo`. Visto no
  card: "trabalhar os pontos abaixo" aparece onde não há nada abaixo.
- **Prova social:** só com depoimentos reais e autorizados.

---

## → `claude/checklist-de-lancamento.md`

- [ ] Fazer o merge do PR de melhorias e conferir o workflow `pos-deploy` verde no GitHub
      (aba Actions).
- [ ] Render → Environment: `PADMINI_ALERTA_EMAIL` (e-mails da equipe, separados por vírgula).
- [ ] Render → Environment e GitHub → Secrets: `PADMINI_TAREFAS_CHAVE`, com o **mesmo**
      valor nos dois lugares (liga os lembretes).
- [ ] GitHub → Secrets: `BACKUP_DATABASE_URL` (Supabase → Connection string → **Session
      pooler**) e `BACKUP_SENHA` (guardar também num gerenciador de senhas).
- [ ] Cakto → webhook: marcar o evento **Abandono de checkout**.
- [ ] Conferir que `RESEND_API_KEY` está na Render (sem ela, nenhum e-mail sai).
- [ ] Pedro: revisar os textos de interpretação (repositório `padmini-conteudo`), começando
      pelas frases das faixas de nota que aparecem no card.
- [ ] (Opcional) Criar na Cakto um cupom para quem comprou e colocar em `cupom_pos_compra`
      no `ofertas.yaml`.

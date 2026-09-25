# Melhorias de 25/set/2026: erros de preço, e-mails de venda e operação

Continuação da revisão de segurança (`docs/seguranca.md`). Três frentes:
**(1)** erros visíveis no site, **(2)** trazer de volta quem não comprou na hora,
**(5)** saber quando algo quebra.

## 1. Erros corrigidos

| Erro | Correção |
|---|---|
| A página do casal dizia "relatório completo por **R$127**" (o preço riscado), e não R$97. | Todos os preços das páginas saem do `conteudo/ofertas.yaml`: casal, mapa, lista de espera e linha do combo. O teste `test_nenhum_preco_escrito_a_mao_nos_html` falha se alguém escrever "R$" à mão num HTML. |
| "Com **14.0** de 36 pontos" (ponto à americana e ".0"). | `compatibilidade.nota_br`: "14", "14,5". Vale na frase da amostra, no placar, nas 8 dimensões e no modo live. |
| Os textos de interpretação nunca foram revisados por uma pessoa. | **Não dá para resolver em código.** Os textos moram no repositório privado `padmini-conteudo` e precisam da leitura do Pedro. Visto no card: a frase "trabalhar os pontos **abaixo**" aparece no card compartilhável, onde não há nada abaixo. Vale reescrever essa faixa em `COMPAT_FAIXA`. |

## 2. Vender mais com o mesmo tráfego

### 2a. Amostra por e-mail (`static/amostra-email.js`, `POST /api/amostra/email`)
Depois da amostra (mapa ou casal), aparece "Receber esta amostra por e-mail".
- O e-mail traz a amostra e um botão **direto para o checkout da Cakto, já com os dados de
  nascimento no `sck`**, igual ao botão do site (há teste garantindo que o `sck` é idêntico).
- A caixa "Pode me mandar um lembrete depois" vem **desmarcada**. Lembrete é marketing e só
  sai com consentimento (LGPD).
- O bloco só aparece se `RESEND_API_KEY` estiver configurada.
- Contra uso indevido (mandar e-mail com a nossa marca para terceiros): 10 envios por IP a
  cada 10 min e 3 por endereço a cada 24h.

### 2b. Lembrete (`POST /api/tarefas/lembretes`, workflow `tarefas.yml`)
Uma vez por dia (11h07 de Brasília), o GitHub Actions chama a rota com a chave
`PADMINI_TAREFAS_CHAVE`. Cada pessoa recebe **um único** lembrete, e só quando todas as
condições abaixo valem:
- autorizou o lembrete;
- pediu a amostra entre 24h e 72h antes;
- não comprou nada depois;
- não se descadastrou.

### 2c. Carrinho abandonado (evento `checkout_abandonment` da Cakto)
O mesmo `/webhook/cakto`, com a mesma verificação de assinatura, trata o evento. Sai **um**
e-mail de recuperação por pessoa e oferta a cada 7 dias, nunca para quem se descadastrou ou
comprou nas últimas 24h.
- O link volta para o mesmo checkout **se** ele ainda tiver o `sck` (dados de nascimento).
  Se não tiver, vai para a página do produto, que refaz a amostra e monta o link certo. Assim a
  compra não vira entrega manual.
- Sem banco configurado não sai nada, porque não haveria como evitar repetição.
- ➡️ **Precisa assinar o evento** "Abandono de checkout" no webhook, no painel da Cakto.

### 2d. Card compartilhável
- O rodapé ficou grande e na cor da marca: "Façam o teste de vocês, de graça:
  **padmini.com.br**". Antes era um texto pequeno e apagado.
- No celular, o botão vira "Compartilhar card ↗" e abre o menu do sistema (Instagram,
  WhatsApp…) com a imagem. Onde isso não existe, continua baixando o arquivo.
- Evento `card_compartilhado` no PostHog.

### 2e. Venda cruzada no e-mail de entrega
- Quem comprou **o casal** recebe, no mesmo e-mail, um link para o **mapa individual de cada
  um**, com o checkout já preenchido com os dados daquela pessoa.
- Quem comprou **o mapa** recebe um convite para a compatibilidade (vai para o site, porque
  faltam os dados do par).
- Cupom opcional: `cupom_pos_compra` na oferta do `ofertas.yaml`. O cupom precisa existir na
  Cakto.

### 2f. Prova social: não implementado
Não há depoimentos reais ainda, e inventar está fora de questão. Quando houver, peçam
autorização por escrito e coloquem no `conteudo/home.yaml`.

### Descadastro (`/descadastrar`)
Todo e-mail de marketing (lembrete, recuperação) e o da amostra têm link de descadastro
assinado (HMAC com `PADMINI_SECRET`).
- Abrir o link só **mostra** um botão; é o clique que descadastra. Leitores de e-mail e
  antivírus abrem links sozinhos e não podem descadastrar ninguém por engano.
- Quem se descadastra entra em `email_optout` e não recebe mais marketing. O e-mail de
  entrega de compra continua saindo.

### Tabelas novas (criadas sozinhas na subida do app, com RLS e sem acesso pela API pública)
`amostras_email`, `abandonos`, `email_optout`.

## 5. Operação

### 5a. Alertas por e-mail (`alertas.py`)
Vão para `PADMINI_ALERTA_EMAIL` (pode ser mais de um, separados por vírgula):
| Quando | Repetição |
|---|---|
| Pedido **pago** que ficou sem entrega automática (sck divergente, oferta desconhecida, sem dados) | todo caso |
| E-mail de entrega que **não saiu** (vem com o link, para mandar à mão) | todo caso |
| Erro 500 no site | no máximo 1 a cada 15 min |
| Webhook recusado por assinatura inválida | no máximo 1 por hora |
| Lembretes que falharam | no máximo 1 a cada 6h |

Sem `PADMINI_ALERTA_EMAIL`, os alertas só vão para o log da Render.

### 5b. Backup semanal criptografado (`.github/workflows/backup.yml`)
O Supabase está no plano **grátis**, que não tem backup para baixar (conferido em 25/set).
- Toda segunda às 3h23, um `pg_dump` é criptografado com `BACKUP_SENHA` (AES-256) e fica 90
  dias como artefato do workflow.
- O repositório é público, por isso a criptografia é obrigatória: sem ela, qualquer um
  baixaria os e-mails dos clientes.
- Como restaurar: veja o comentário no topo do arquivo.

### 5c. Conferência do site de hora em hora (`.github/workflows/pos-deploy.yml`)
- De hora em hora, o workflow confere se o commit mais novo da `master` está no ar (campo
  `versao` do `/api/saude`, vindo de `RENDER_GIT_COMMIT`). Se o commit tiver mais de 30 min e
  ainda não estiver no ar, falha: o deploy travou. Depois roda `scripts/smoke_producao.py`
  contra padmini.com.br.
- **Não roda no push, de propósito.** A Render só publica depois que *todas* as verificações
  do commit passam. A 1ª versão deste workflow rodava no push e esperava o deploy: um esperou
  o outro e o deploy travou (25/set, destravado à mão).
- Se falhar, o GitHub manda e-mail para o dono do repositório.
- O smoke ganhou 3 checagens: a chave das tarefas, o link de descadastro falso e o preço da
  página do casal.

## Configuração que falta (Nicolas)

| Onde | O quê | Para quê |
|---|---|---|
| Render → Environment | `PADMINI_ALERTA_EMAIL` = seu e-mail (e o do Pedro, com vírgula) | alertas |
| Render → Environment | `PADMINI_TAREFAS_CHAVE` = texto aleatório longo | lembretes |
| GitHub → Settings → Secrets → Actions | `PADMINI_TAREFAS_CHAVE` = **o mesmo** valor | lembretes |
| GitHub → Secrets | `BACKUP_DATABASE_URL` = connection string **Session pooler** do Supabase | backup |
| GitHub → Secrets | `BACKUP_SENHA` = senha longa, guardada **também** fora do GitHub | backup |
| Cakto → webhook | marcar o evento **Abandono de checkout** | carrinho abandonado |
| Render | conferir se `RESEND_API_KEY` está lá (sem ela, nada de e-mail sai) | todos os e-mails |

Enquanto nada disso for configurado, cada peça fica desligada sem quebrar nada. Os
workflows avisam "não configurado" e terminam verdes.

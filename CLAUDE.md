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
- **`base_significacoes.py` mora em um repositório PRIVADO separado**
  (`github.com/nicki-arch/padmini-conteudo`), não neste. Isso mantém o texto de
  interpretação — o diferencial do produto — fora de um repositório que precisa ser
  público (ver regra 10). `build.sh` (Render) e o passo equivalente em
  `.github/workflows/testes.yml` buscam o arquivo de lá na hora do build/CI, usando
  `PADMINI_CONTEUDO_TOKEN` / secret `CONTEUDO_REPO_TOKEN` (token de leitura, só
  daquele repo). Se você está numa sessão nova e o arquivo não existe no checkout,
  é isso — não é regressão. Para editar o conteúdo, mexa no repo `padmini-conteudo`.

## Mapa do código
| Arquivo | Papel |
|---|---|
| `app.py` | FastAPI: páginas, `/api/*`, `/webhook/cakto` |
| `compute_chart.py` | Cálculo do mapa (Swiss Ephemeris, sideral Lahiri, whole sign) |
| `detectar_fatos.py`, `montar_texto.py`, `base_significacoes.py` | Fatos do mapa → texto; IA (Claude) só reescreve |
| `compatibilidade.py` | Guna Milan / Ashtakoot (36 pontos), doshas |
| `acesso.py` | Token HMAC que libera o completo (sem token = 402) |
| `cakto.py` | Webhook: assinatura HMAC `v1=` sobre `{timestamp}.{corpo}`; dados de nascimento vêm no `sck` |
| `entrega.py` | Link assinado + e-mail (Resend) |
| `static/afiliado.js` | Monta o link do checkout: dados no `sck`, afiliado/cupom dobrados em `utm_*` |
| `mapa_ocidental.py` | Motor ocidental: tropical, Placidus (Porfírio nos polos), nodo verdadeiro, aspectos e orbes num lugar só. Validado contra 11 mapas do astro-seek (`testes/dados/referencias_ocidental.json`) |
| `montar_texto_ocidental.py` + `conteudo/ocidental/textos/` | Mapa → texto (YAML, `revisado: false` em cada texto; `python scripts/revisao_textos.py` conta o que falta revisar) |
| `rotas_ocidental.py` + `static/ocidental/` | API `/api/ocidental/*`, páginas e `/live` da versão ocidental; `gerar_pdf_ocidental.py` é o PDF |
| `revisao.py` + `scripts/exportar_revisao.py` / `importar_revisao.py` | Planilha de revisão da família (xlsx ↔ YAML); regras de tom e tamanho num lugar só. A planilha não vai para o git |
| `numerologia.py` | Numerologia pitagórica (versão ocidental): regras de Y/W e do Caminho de Vida em `docs/ocidental.md` |
| `scripts/pronto_para_virar.py` | O que falta para trocar `PADMINI_SISTEMA` para `ocidental` (sai com 1 se houver bloqueio) |
| `scripts/gerar_og_ocidental.py` | Gera as imagens de compartilhamento `static/og-oc-*.png` da versão ocidental |
| `tarot.py` | Tarot (versão ocidental): 78 cartas, sorteio no servidor, ID da tiragem com selo HMAC — o link pago abre as mesmas cartas da amostra |
| `sinastria.py` | Sinastria ocidental: aspectos cruzados, casas, 8 dimensões e o Índice Padmini (método próprio, pesos em `docs/ocidental.md`) |
| `docs/ocidental.md` | Decisões de método da versão ocidental (orbes, nodo, sem hora, validação) |
| `sistema.py` | `PADMINI_SISTEMA` (vedica \| ocidental): páginas, termos/privacidade (`LEGAIS`), e-mails e tokens de cada versão |
| `ofertas.py` + `conteudo/<versão>/ofertas.yaml` | **Preço e link de checkout, fonte única.** O app troca os marcadores (`__PRECO_COMPAT__`, `__CHECKOUT_MAPA__`…) no HTML ao servir, e o `cakto.py` tira daí o código da oferta. Mudou o preço? Só o YAML |
| `cidades.py` + `data/cidades_index.tsv` | Autocomplete de cidades (GeoNames) |
| `gerar_pdf.py` | PDF do completo |
| `static/live.html` + rotas `/live`, `/api/live/*` | Modo live do Pedro: senha (`PADMINI_LIVE_SENHA`) → cookie assinado de 12h → token do completo sem pagamento, com log em `live_geracoes` |
| `db.py` | Postgres opcional (`DATABASE_URL`): pedidos, lista de espera (`leads`), cache do texto da IA. Erro no banco nunca impede entrega |
| `limites.py` | Limite de requisições por IP (429): cálculo, PDF, IA, cidades, lista, senha do live |
| `seguranca.py` | Cabeçalhos de segurança (CSP, HSTS, anti-iframe, Referrer-Policy). Serviço externo novo → incluir na CSP |
| `marketing.py` + `static/amostra-email.js` | Amostra por e-mail, lembrete (`/api/tarefas/lembretes`), carrinho abandonado, venda cruzada, descadastro (`/descadastrar`) |
| `alertas.py` | E-mail para a equipe (`PADMINI_ALERTA_EMAIL`): pedido pago sem entrega, e-mail que não saiu, erro 500 |
| `.github/workflows/` | `testes` (CI), `pos-deploy` (smoke de hora em hora; **nunca** no push, senão trava o deploy da Render), `tarefas` (lembretes diários), `backup` (semanal, criptografado), `manter-ativo` |
| `docs/melhorias-2026-09.md` | O que entrou em 25/set (preços, e-mails de venda, alertas, backup) e a configuração pendente |
| `docs/seguranca.md` | **Revisão de segurança (25/set/2026)**: o que foi corrigido, limites, pendências |
| `static/lista.html` + `/api/lista` | Lista de espera do lançamento. `PADMINI_CAPTURA=1` trava home/mapa/compat e manda para `/lista` (links de entrega com `token` e quem tem `?previa=<PADMINI_PREVIA_CHAVE>` passam) |

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
    o código é a via gratuita, em vez de comprar a licença comercial). Por isso o
    conteúdo proprietário (significações) foi para fora dele — ver acima — em vez de
    o repositório inteiro virar privado.

11. **O `sck` é dado do comprador, não prova de pagamento.** Qual produto entregar sai só da
    oferta paga que a Cakto informa (`cakto.produto_pago`). Ver `docs/seguranca.md`.

12. **Preço nunca escrito à mão em HTML** (a página do casal anunciou R$127 em vez de R$97):
    sempre `{{ ofertas.<produto>.preco }}`. Há teste que procura "R$" + número nos HTML.
13. **E-mail de marketing só com consentimento e com descadastro** (`marketing.py`); na
    dúvida (sem banco), não manda.

## Commits
Mensagens em português, explicando o porquê. Sem force-push na `master`.

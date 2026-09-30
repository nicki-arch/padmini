# Marca Valderez Astrologia na versão ocidental (rodada visual, 29/set/2026)

A marca pública da versão ocidental passa a ser **Valderez Astrologia**. Dona Valderez
(avó do Pedro, ~40 anos de astrologia) revisa os textos e aparece nos vídeos; Padmini
é a produtora por trás (tecnologia, site, checkout, e-mail). O domínio continua
`padmini.com.br` nesta rodada; domínio novo e remetente de e-mail são outra etapa.

Pacote de design (feito fora do repositório): `docs/design/valderez-1.0/` — só
referência, **não é servido**. Comece por `LEIA-ME.md` e `documentacao/integracao-fastapi.md`.

## Onde mora
| O quê | Onde |
|---|---|
| Tokens (cores dos temas claro/escuro, tipografia, espaços, raios, sombras) e os 44 pares de contraste aprovados | `paleta.py` (`VALDEREZ`, `PARES_APROVADOS`, `TIPOGRAFIA`…). Teste confere com `tokens/tokens.json` do pacote |
| CSS dos tokens | `static/ocidental/tema.css`, **gerado** (`python scripts/gerar_tema_css.py`) |
| Símbolo, favicon | `marca.py` (SVG, favicon, PDF); arquivos em `static/valderez/*.svg` gerados dele (teste confere) |
| Fontes | `static/valderez/fontes/*.woff2` (Cormorant Garamond 500/600, Inter 400/600) com as licenças OFL. Os mesmos TTF de `fontes/` (PDF). **Nada de Google Fonts na ocidental** |
| Cabeçalho, rodapé, menu, cookies | `static/ocidental/_cabecalho.html`, `_rodape.html`, `_menu.html`, `_head_valderez.html` + `static/valderez/casca.css` — em todas as páginas ocidentais |
| Componentes do pacote | `static/valderez/componentes.css` — páginas já vestidas de novo (não carregam o `base.css`) |
| Imagens de compartilhamento | `scripts/gerar_og_ocidental.py` → `static/og-oc-*.png` |

### Temas
Tema claro na página (`<html data-theme="light">`), blocos escuros com
`data-theme="dark"` (cabeçalho, rodapé), sem seguir o tema do sistema. Os tokens
novos (`--background`, `--surface`, `--text`…) só existem dentro de `[data-theme]`,
porque o `base.css` tem apelidos antigos com os mesmos nomes (`--surface`, `--accent`)
que as páginas legadas usam. As páginas que ainda estão no `base.css` recebem os
nomes antigos (`--ground`, `--ink`, `--saffron`…) apontando para o **tema escuro**
da Valderez — ficam coerentes até serem vestidas de novo.

## Fases
- **A (este PR):** fundação (tokens, fontes, símbolo, favicon, og:image), casca em todas
  as páginas, `/lista` no desenho do pacote, aviso de cookies, `/estilo`, página de
  descadastro, JSON-LD com o nome novo.
- **B (feita):** home, `/mapa` (formulário, carregando, amostra e o completo com sumário),
  PDF, e-mails (marca, cores e o nome no remetente), `/minhas-leituras`, termos/privacidade
  (a marca trocada no texto; responsável e CNPJ iguais), 404 da tela do pacote (HTTP 404),
  a taxa da plataforma no bloco de preço, a CSP da ocidental sem Google Fonts.
- **C (feita):** compatibilidade, numerologia, tarot, blog (lista e artigo) e `/live` com os
  componentes do pacote, sem fluxo novo; o nome do índice da sinastria numa chave só. Nenhuma
  página da ocidental usa mais o `base.css` (o antigo `static/ocidental/componentes.css` saiu).

### Fase C: como ficou
- **Nome do índice**: `conteudo/ocidental/marca.yaml` → `indice:`. Nos YAMLs de texto (páginas,
  `textos/sinastria.yaml`, blog) ele é escrito `{indice}` (como os `{a}`/`{b}` que os textos já
  usam); `textos.com_indice()` troca na leitura. O código lê `textos.NOME_INDICE`; os templates,
  a variável `indice`. Para renomear: a linha da `marca.yaml` + `python scripts/gerar_og_ocidental.py`
  (a imagem da sinastria tem o nome) + deploy. O endereço do artigo
  (`/blog/como-ler-o-indice-padmini`) não muda, para link compartilhado não quebrar.
- **Rosa das 8 dimensões, cartas do tarot e card do casal** ainda desenham com os nomes antigos
  (tema escuro): ficam em blocos `data-theme="dark"` (`.rosa-bloco`, `.mesa`, `.cardc`).
- **`/live`** é todo no tema escuro do pacote (tela de transmissão). A linha que separa o grátis
  do pago ficou dourada (`gold`); o aviso diz "linha dourada" (antes, "laranja").
- **Card do casal (imagem)**: Cormorant + Inter do site, cores do tema escuro, símbolo novo,
  "Valderez" no topo, arquivo `valderez-<a>-<b>.png`.

### Fase B: como ficou
- **Estados do `/mapa`** (`#estado-form`, `#estado-carregando`, `#resultado`): a mesma página;
  o completo só é desenhado com a resposta autorizada da API (token válido), como antes.
  Erro de validação → foco e `aria-invalid` no primeiro campo; resultado → foco no título.
- **Aviso "foi para o seu e-mail"** só com `email.enviado` do servidor
  (`static/ocidental/amostra-email.js`); e-mail que falha = amostra inteira + alerta (rodada 6).
- **Taxa da plataforma**: `taxa_plataforma` no topo do `conteudo/ocidental/ofertas.yaml`; o
  `ofertas.py` a põe em cada oferta (não vira oferta para o webhook). O bloco mostra o preço e
  "+ R$0,99 de taxa da plataforma" — sem total calculado.
- **E-mails**: tema claro (`paleta.EMAIL["ocidental"]`), "Valderez Astrologia" no topo e na
  assinatura (`sistema.MARCA`, `sistema.ASSINATURA_EMAIL`). O remetente continua o endereço de
  `PADMINI_EMAIL_FROM` (domínio atual, sem DNS novo); só o nome exibido vira "Valderez
  Astrologia" (`entrega.remetente_do_email`, pela marca `<!-- versao:ocidental -->` do topo).
  A védica sai byte a byte como antes.
- **PDF**: Cormorant Garamond + Inter (os TTF de `fontes/`), cores do tema claro, símbolo novo.
- **404**: `app._nao_encontrada` — só para página HTML da ocidental; API, `/static`, webhook e a
  védica continuam com o JSON de sempre. Com a captura ligada, a 404 leva para a lista.
- **CSP**: a ocidental não libera `fonts.googleapis.com`/`fonts.gstatic.com`; a védica e os links
  de entrega da védica (token sem prefixo) continuam liberando (`seguranca.precisa_google_fonts`).

## Decisões em que o pacote e o site divergiram
- **`/lista` no celular:** o pacote põe a ilustração antes do formulário. Aqui o formulário
  vem logo depois do título (quem chega do TikTok vê os campos na primeira tela); as
  vantagens, a revisão da Dona Valderez e a ilustração vêm depois.
- **Seções que o pacote não desenhou** (vantagens, revisão, WhatsApp, interesse): mantidas,
  com os componentes do pacote (`.vantagens`, `.destaque`, `.escolha` em `componentes.css`).
- **Cookies:** "Aceitar" e "Recusar" com a mesma classe (`.button`), como pede o pacote.
- **Fontes da ocidental = famílias da védica.** O teste "nada antigo na ocidental" deixou de
  proibir Cormorant/Inter (continua proibindo as cores da védica e o Google Fonts).
- **Cabeçalho:** o botão de ação do pacote virou "Fazer meu mapa natal" (/mapa); na `/lista`
  não há menu (com a captura, as outras páginas voltam para a lista).
- **`/mapa` no celular:** os selos da introdução somem abaixo de 1100px para os campos subirem
  à primeira tela; o formulário vem antes da ilustração (no desktop, como no pacote).
- **Home:** a ordem de antes (como funciona → produtos → tradição → 8 dimensões → card do casal
  → depoimentos → perguntas → fechamento), com hero, ilustração e blocos escuros do pacote.
  A "tradição de família" ganhou a ilustração dos papéis (o "o que você recebe" do pacote).
- **Leitura completa:** sumário lateral (`.toc`) com posições, aspectos, elementos e cada seção.
- **SVGs do pacote** com fonte embutida (~190 KB) não são servidos: símbolo em SVG + nome em
  HTML; `papeis.svg` sem texto (≈1 KB).

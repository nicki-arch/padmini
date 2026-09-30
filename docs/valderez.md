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
- **B:** home, `/mapa` (formulário, carregando, amostra), leitura completa, PDF, e-mails,
  `/minhas-leituras`, termos/privacidade (tipografia), 404, linha da taxa no bloco de preço.
- **C:** compatibilidade, numerologia, tarot, blog, `/live`; nome do "Índice Padmini" numa chave só.

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
- **SVGs do pacote** com fonte embutida (~190 KB) não são servidos: símbolo em SVG + nome em
  HTML; `papeis.svg` sem texto (≈1 KB).

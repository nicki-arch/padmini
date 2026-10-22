# O /painel (rodada 15)

Uma tela, no celular, que muda o estado do site em segundos e sem deploy: o modo do site,
o interruptor de venda, o estado de cada produto e as páginas que podem ser escondidas.

## Como entrar

1. Na Render, em cada serviço (`padmini` e `padmini-previa`), crie
   `PADMINI_PAINEL_SENHA` com **16 caracteres ou mais**. Podem ser senhas diferentes. Sem a
   variável, ou com menos de 16 caracteres, o `/painel` responde 404.
2. Abra `https://<site>/painel`, digite a senha e escolha quem está mexendo (Nicolas ou
   Pedro). O nome vai para o histórico.
3. A sessão dura 12 horas. Trocar a senha na Render derruba as sessões abertas.

O login tem limite: 5 senhas erradas por IP bloqueiam por 15 minutos (e 30 no total por hora).

## Quem manda no ar (precedência)

| O quê | 1º: painel (banco) | 2º: sem nada salvo | 3º: sem nada |
|---|---|---|---|
| Modo do site | `config_site.modo` | `PADMINI_CAPTURA=1` → lista de espera | aberto |
| Venda aberta | `config_site.vendas_abertas` | `vendas_abertas` do `catalogo.yaml` | — |
| Estado do produto | `config_site.produto:<chave>` | `estado` no `catalogo.yaml` | — |
| Página visível | `config_site.pagina:<rota>` | visível | visível |

Por cima disso, sem mudar o que está salvo:

- `PADMINI_VENDAS_TESTE=1` (só com Stripe de teste) abre a venda no serviço em que estiver;
- o modo "tudo liberado" (ver abaixo).

O primeiro deploy, sem nada salvo, deixa o site igual ao de antes. O banco é lido no máximo
a cada 15 segundos: uma mudança aparece no site em até 15 s. Se o banco cair, o site fica
com o último estado conhecido (sem nenhum, o YAML) e sai um alerta para
`PADMINI_ALERTA_EMAIL`. O painel nunca derruba o site.

**Depois do painel, não use mais `PADMINI_CAPTURA`.** Ela continua aceita só como padrão
inicial, enquanto o painel não salvou um modo.

## Os quatro modos

| Modo | O público vê | Continua funcionando |
|---|---|---|
| Aberto | o site conforme os produtos e a venda | tudo |
| Lista de espera | home, mapa e produtos mandam para `/lista` | links com token, `/live`, webhooks, termos, privacidade, `/painel` |
| Manutenção | "Voltamos já", HTTP 503 com `Retry-After: 300` | o mesmo da linha acima, `/api/saude`, checkout e "obrigado" de quem já estava pagando, `/minhas-leituras`. Pedido novo de compra não abre |
| Tudo liberado | **prévia**: todo produto ativo, venda de teste aberta, rascunhos do blog, `noindex` em tudo. **Produção**: o site normal | tudo |

O navegador logado no painel passa pela lista de espera e pela manutenção.

### "Tudo liberado" na produção

Vale **só nos navegadores logados no painel**. Eles veem os produtos ocultos e em breve como
ativos, a leitura completa sem pagar e a faixa fixa "Modo teste: só você está vendo assim".
Depois de pedir uma amostra, a faixa mostra "Abrir a leitura completa".

A venda real não abre por esse modo: preço, botão de compra e checkout seguem o estado
público. Compra de teste se faz na prévia, com o cartão 4242 ou Pix de teste.

O botão "Ver tudo liberado só para mim" faz o mesmo sem mudar o modo do site.

Nada disso vaza: páginas montadas com o cookie do painel não entram no cache de páginas,
e o `/api/config` e o sitemap nunca olham o cookie.

### Prévia ou produção?

É **prévia** só com `PADMINI_PAGAMENTO=stripe` e chave `sk_test_`/`rk_test_`. Qualquer outra
coisa conta como produção: na dúvida, o "tudo liberado" não vale para o público.

## Venda e produtos

- **Abrir a venda na produção** pede `ABRIR` digitado na confirmação. Não abre se algum
  produto ativo (com `oferta` no catálogo) estiver sem preço no `ofertas.yaml`; o painel diz qual.
- Com a venda aberta, um produto sem preço não pode ficar ativo.
- Produto sem `oferta` no catálogo (comunidade, cursos, consulta) nunca é vendido, nem no
  "tudo liberado".
- **O kit (rodada 20)** é uma linha como as outras, mas só vende com ele ativo E os três
  produtos dele ativos (mapa, O seu ano, A sua Lua no ano). Enquanto faltar algum, a linha
  mostra "precisa de … ativos" e, com o kit ativo, o resumo diz "kit … parado". Ver
  `docs/kit.md`.
- Preço continua só no `ofertas.yaml` (PR + deploy). O painel não mexe em preço.

## Páginas

Podem ser escondidas: `/blog`, `/links` e `/leituras`. Escondida, a página responde 404 e
sai do menu, do rodapé e do sitemap. `/cursos` é um produto do catálogo: é controlado como
produto (Ativo · Em breve · Oculto).

Nunca podem ser escondidas: home, termos, privacidade, `/lista`, links com token,
`/minhas-leituras`, checkout, webhooks, `/api/*` e o próprio `/painel`.

## Histórico e aviso

Toda mudança grava em `config_site_historico` (o quê, de quê para quê, quando e quem),
aparece nas 20 últimas mudanças da tela e manda um e-mail curto para
`PADMINI_ALERTA_EMAIL`, por exemplo "Nicolas mudou o site para Lista de espera às 14:03".

## O que o painel não faz

Não mexe em preço, chaves, variáveis da Render, Stripe ou Cakto. Não apaga dados e não
mostra dado de cliente.

## Smoke

O `/api/config` traz `modo_site`, `produtos_ativos` e (rodada 20.3) `produtos_em_breve`: as
rotas de produto ativas e "em breve" para o público. Oculto nunca aparece ali.
O smoke se ajusta:

- **páginas de produto** (rodada 20.3): as rotas vêm do `catalogo.yaml` do repositório e o
  estado do `/api/config`: ativo ou em breve → 200, oculto → 404, toda página "em breve" mostra
  "em breve", e a checagem de 404 usa um produto oculto naquele momento (nenhum = passa com o
  aviso "nenhum oculto"). Esconder ou ligar produto no painel não derruba mais o smoke;
- **manutenção**: confere o 503 e o que continua de pé;
- **tudo liberado na produção**: confere que o público não vê nada a mais;
- **sempre**: o `/painel` sem login mostra só o formulário de senha (ou 404 sem a variável),
  e uma ação sem login é recusada.

## Código

- `estado_site.py`: o estado (a fonte única).
- `painel.py`: a sessão, o CSRF e as ações.
- `app.py`: as rotas `/painel*` e os middlewares (cookie do painel, manutenção).
- `static/ocidental/painel.html`: a tela.
- `static/ocidental/manutencao.html`: "Voltamos já".
- `static/ocidental/modo-teste.js`: a faixa.
- Tabelas `config_site` e `config_site_historico` (`db.py`).

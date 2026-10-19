# O kit dos três (rodada 20)

**Mapa natal completo + "O seu ano" + "A sua Lua no ano", num pagamento só: R$97, com
"de R$141" riscado** (decisões do Nicolas de 19/out/2026; o "de" é a soma dos PREÇOS dos
três, 3 × R$47, não a soma dos "de" — proposta do Cowork). Preço em
`conteudo/ocidental/ofertas.yaml` → `kit` (trocar o "de" é uma linha).

## O que é, no catálogo

`conteudo/ocidental/catalogo.yaml` → produto `kit`, com `inclui: [mapa, previsao,
calendario]`. Um produto com `inclui` é um **pacote**: não tem rota nem página própria
(`entrada: /mapa` é onde a compra começa) e nunca entra no menu, na home, no rodapé, no
sitemap nem no "me avise" (`catalogo.visiveis()` deixa os kits de fora). O `catalogo.py`
recusa na subida um kit que inclui produto inexistente, sem oferta, repetido, outro kit ou
menos de dois produtos.

## A trava

`catalogo.vende("kit")` só é verdadeiro com, ao mesmo tempo:

1. a venda aberta e o próprio kit **ativo para o público** (painel → YAML);
2. **os três produtos que ele inclui à venda** (`catalogo.vende` de cada um);
3. o checkout próprio (`PADMINI_PAGAMENTO=stripe`): o kit não existe na Cakto.

Com qualquer um dos três oculto (ou em breve), o kit não aparece em lugar nenhum (nem
desabilitado) e o `POST /api/checkout` dele responde 404, **mesmo com o kit marcado como
ativo no painel**. O "tudo liberado só para mim" do navegador logado mostra os produtos mas
não vende (como sempre); o "tudo liberado" da prévia vende tudo, o kit junto. No `/painel`,
a linha do kit avisa "precisa de Mapa natal, O seu ano e A sua Lua no ano ativos" enquanto
faltar algum, e o resumo conta o kit parado quando ele está ativo.

## Onde aparece (só quando vende)

Sempre como a segunda opção, nunca uma página a mais no caminho:

- nas amostras do `/mapa`, de `/seu-ano` e de `/calendario-lunar`, embaixo do botão de
  compra avulsa (`static/ocidental/_kit_opcao.html`): "Leve os três por ~~R$141~~ R$97: o
  mapa completo, O seu ano e a sua Lua no ano". Usa os dados já digitados (o mesmo
  `padCorpoCompra` da página, com `produto: "kit"`);
- na `/links`, logo abaixo do botão principal (`pagina_links.botoes` → `kits`), levando ao
  `/mapa` com a origem;
- em "Todas as leituras", um cartão a mais.

A copy mora em `catalogo.yaml` → `kit` (sem "promoção", sem contador, sem prazo).
`/api/config` → `kits_a_venda` lista os kits à venda (vazio com o kit oculto; o smoke usa).

## Um pedido, três entregas

O checkout cria UM pedido pendente (`itens: [{chave: kit, dados, valor_centavos: 9700}]`):
uma pessoa, uma data de nascimento e o mês de início (o da compra). A Stripe recebe um item
("Os três: …", R$97), o e-mail, e no metadata só `pedido` e os três `utm` (nada de
nascimento). Quando o webhook confirma o pagamento (cartão ou Pix) e o valor confere (9700
centavos, BRL), `_entregar_leitura` emite os três links (`entrega.links_do_kit`): o token do
mapa completo, o de "O seu ano" (início no mês da compra) e o token cifrado do calendário.
Um e-mail (`entrega.email_kit_html`) com um botão por leitura; os PDFs saem de cada página,
como na compra avulsa. Em `pedidos`, uma linha `ocidental:kit` com os três links, um por
linha. O `/obrigado` mostra os três botões (`/api/checkout/{id}/estado` → `links`) e
"Minhas leituras" lista os três com o nome de cada um.

Reembolso ou contestação: como os outros (o `status` do pedido muda e a equipe é avisada);
os links já entregues continuam abrindo. Abandono (sessão expirada): o e-mail de sempre,
com o link para o `/mapa`.

## E-mails de venda: o kit conta como os três

`catalogo.que_tem(compras)` transforma "ocidental:kit" em mapa + O seu ano + calendário.
Assim, quem tem o kit não recebe oferta de nenhum dos três:

- pós-compra (a escada): o próximo degrau pula o que a pessoa já tem;
- boas-vindas e lembrete da amostra: não saem para um produto que a pessoa já tem
  (nem de uma compra ANTERIOR à amostra, regra nova que vale para todos os produtos);
- venda cruzada do e-mail de entrega: não oferece o que a pessoa já tem;
- aniversário de "O seu ano": não vai para quem comprou "O seu ano" ou o kit nos últimos
  12 meses (o ano dela está coberto; vale para os dois, regra nova desta rodada).

## Bug achado e corrigido nesta rodada

O webhook da Stripe só entregava os produtos que a Cakto conhece (`cakto.PRODUTOS`): um
pagamento de "O seu ano" (ou do calendário) teria caído em "valor diferente — entregar à
mão". Agora vale a lista do checkout próprio (`pendentes.PRODUTOS`); teste em
`testes/test_rodada20.py`.

## Para ligar (Nicolas, no /painel)

O seu ano → Ativo, A sua Lua no ano → Ativo, kit → Ativo. Os textos de "O seu ano" e do
calendário ainda não foram revisados pela Dona Valderez: ligar antes da revisão é decisão
do Nicolas.

# Padmini — retrospectiva, estado atual e próximos passos

Atualizado em 17/set/2026 (site publicado, correções de interface e relatório em PDF). Versão anterior: 15/set.

## Resumo

- Retomamos o Padmini com um objetivo duplo: ter uma ferramenta própria de mapa védico e usar o projeto para aprender a criar produto, usar IA e, depois, anunciar.
- Construímos um site funcional: formulário, cálculo do mapa, regras clássicas, relatório em 4 seções e versão escrita por IA. Desde 16/set ele **está no ar** em https://padmini.onrender.com (Render, plano grátis), com relatório completo em PDF desde 17/set.
- A arquitetura ficou boa: o código calcula, as regras decidem os fatos, e a IA só reescreve o que recebeu.
- Os maiores erros de percurso foram construir antes de olhar a concorrência e gastar tempo tentando rodar o site no Windows, quando o produto é 100% online.
- A próxima decisão não é técnica: é **o que exatamente vamos vender**, já que a Cosmolica entrega um mapa védico completo de graça em português.

---

## 1. O que aconteceu, em ordem

1. **Retomada.** O material técnico antigo (`mapa-vedico.skill`) tinha se perdido. Descobrimos que o Pedro já fazia mapas à mão, pedindo ao Claude, e dava de graça aos clientes dele.
2. **Redefinição.** Objetivo: ter uma ferramenta de consulta própria e aprender no caminho.
3. **Motor de cálculo.** Nicolas escolheu motor próprio em vez de API paga. A biblioteca `vedicastro` estava com instalação quebrada, então usamos o `pyswisseph` direto.
4. **Conteúdo.** Definimos o formato: regras em código apontam os fatos do mapa, cada fato tem um texto curto e a IA só costura esses textos. Isso combate o texto genérico (efeito Barnum).
5. **Desvio: VedicAstroAPI.** Tentamos ver como a API deles funciona. O teste grátis não liberou o endpoint de horóscopo. Único ganho: eles cobram PDF à parte, como add-on.
6. **Motor pronto.** Cálculo com fuso e horário de verão automáticos, detecção de fatos, textos (v1) e relatório em 4 seções.
7. **Texto por IA.** Ligado com a chave da Anthropic (Claude Sonnet 5, cerca de 20 s por mapa). Corrigimos dois vícios do texto: falar em "o material" e trocar "signo próprio" por "casa própria".
8. **Concorrência.** A Cosmolica entrega de graça, em português, quase tudo o que planejávamos vender.
9. **Site v0.2.** Busca de cidades, diagrama do mapa, linha do tempo das fases e botão de texto por IA. O teste com 500 mapas aleatórios achou dois erros de regra, já corrigidos (detalhes na seção 3).
10. **Desvio: rodar no Windows.** Três tentativas: o `.env` foi bloqueado para ferramentas remotas, o conda deu erro de SSL e por fim trocamos para o `uv`. Essa versão ainda não foi testada.
11. **Hospedagem.** Comparamos GitHub + Render, Replit e Base44. O Replit tem conector oficial para o Claude.

---

## 2. O que existe hoje

| Peça | O que faz | Estado |
|---|---|---|
| `compute_chart.py` | Calcula o mapa: Lahiri, casas por signo inteiro, nó médio, fuso e horário de verão automáticos, hora média local antes da hora padrão, retrógrados | **Validado** contra a Cosmolica em 5 mapas conhecidos (seção 2.1) |
| `detectar_fatos.py` | Dignidades, combustão, cazimi, Gaja Kesari, Pancha Mahapurusha, yogakaraka, Raj Yoga (só conjunção), Neecha Bhanga (condição principal), Mangal Dosha (a partir do Ascendente) | Funciona. 500 mapas sem erro |
| `base_significacoes.py` | Textos: 12 ascendentes, 27 nakshatras, 9 fases, 21 dignidades, combustão, yogas e doshas | Completo para o relatório atual. Escrito por IA, sem revisão. Faltam os 108 textos de planeta em cada casa |
| `montar_texto.py` | Monta o relatório e o pedido para o Claude | Funciona |
| `app.py` + `static/index.html` | Site: formulário, busca de cidades, diagrama, tabela, relatório, fases, botão de IA, avisos de horário | Funciona no meu ambiente; testado em computador e celular |
| `cidades.py` + `baixar_dados.py` | Busca local de cidades (GeoNames, 171 mil cidades) | Funciona |
| `iniciar.bat` | Instala e roda o site no Windows | **Não testado.** Deixou de ser prioridade |
| `significacoes-schema-e-regras.md` | Especificação das regras e do formato dos textos | Referência |

### 2.1 Validação do cálculo (15/set/2026)

Cinco mapas conhecidos (Obama, Einstein, Churchill, JFK e Marilyn Monroe) foram comparados com a Cosmolica.
- **Resultado:** os graus de todos os planetas bateram com diferença de até 1 minuto de arco, assim como o Ascendente, as casas e os planetas retrógrados.
- **Einstein:** para Ulm em 1879, antes da hora padrão, a Cosmolica usa a hora média de Berlim, que difere 13 minutos da de Ulm. Com a hora média local de Ulm, o nosso Ascendente (11°38' Câncer tropical, 19°28' Gêmeos sideral) bate com o valor publicado; o da Cosmolica fica cerca de 3° atrás.
- **Correções feitas no teste:**
  - hora média local calculada pela longitude;
  - datas aceitas a partir de 1800;
  - detecção de planetas retrógrados, que também ajusta o limite de combustão de Mercúrio e Vênus.
- **Teste automático:** `testes/test_referencias.py`. Rodar antes de qualquer mudança no cálculo.
- **Achados sobre a busca de cidades:**
  - ela só entende o nome da cidade;
  - "Blenheim Palace" leva a Blenheim, na Nova Zelândia (o certo é Woodstock, Inglaterra).

### 2.2 Publicação, correções e PDF (16–17/set/2026)

- **Publicação:** GitHub (`nicki-arch/padmini`, branch `master`) ligado ao Render (serviço `padmini`, região Ohio, plano grátis). Cada `git push` publica sozinho em 1 a 2 minutos. O `.gitignore` foi corrigido para o índice de cidades ir junto. Vercel e Cloudflare foram descartados: o plano grátis da Vercel proíbe uso comercial, e o Cloudflare não roda o `pyswisseph`.
- **Fluxo de trabalho:** o Claude edita e faz o commit na pasta `Documentos\Padmini`; o Nicolas só roda `git push` no terminal da pasta (é o único passo que exige o login dele no GitHub). O conector do Render permite ao Claude acompanhar as publicações.
- **Correções de interface:**
  - a lista de sugestões de cidade cobria o botão "Gerar meu mapa";
  - no iPhone, o campo de data aparecia em branco e, no computador, podia sair no formato americano. Data e hora viraram campos de texto com máscara (dd/mm/aaaa e hh:mm), iguais em qualquer aparelho.
- **Relatório completo em PDF** (`gerar_pdf.py`, botão "Baixar relatório completo"), 6 a 8 páginas, sem IA e sem custo por download:
  - capa com dados de nascimento, resumo e o mapa sul-indiano;
  - planetas com grau, casa, nakshatra, pada e dignidade, e o que cada planeta representa;
  - a leitura do site;
  - as 12 casas com tema, signo, regente, onde o regente está e planetas presentes;
  - fases Vimshottari com idades e os subperíodos (antardashas) da fase atual e da seguinte;
  - glossário, método e aviso.
  Testado com 43 mapas (incluindo recém-nascido, 1800 e 1850 e signo com todos os planetas).
- **Atenção:** uma cópia antiga da chave real da Anthropic estava na área de trabalho do Claude e foi apagada. A chave antiga precisa ser revogada no painel da Anthropic, se ainda não foi.

**Onde o código está:**
- no projeto Padmini (cópia de todos os arquivos);
- no GitHub (`nicki-arch/padmini`) e publicado no Render;
- na pasta `Documentos\Padmini` do computador do Nicolas;
- no meu ambiente de trabalho, que é temporário e some ao fim da sessão.

**Sobras no computador:**
- um `.env` com o texto de exemplo "SUA-CHAVE", sem a chave real;
- um arquivo `.e`, sem uso, que pode ser apagado.

---

## 3. Avaliação: foi o jeito mais inteligente?

### O que foi bem feito

- **Arquitetura.** Separar cálculo, regras e escrita é o que torna o produto confiável. A IA não inventa astrologia: ela reescreve o que as regras encontraram.
- **Testar em volume.** Rodar 500 mapas aleatórios revelou dois problemas que um teste isolado não pegaria:
  - o Mangal Dosha aparecia em cerca de 90% dos mapas, o que vira alarme genérico;
  - o yogakaraka era marcado para ascendentes que não têm.
- **Validação contra a tradição.** O código achou sozinho que Vênus é yogakaraka para Ascendente em Capricórnio, o que bate com a regra clássica.
- **Detalhes que evitam erro real.** O fuso e o horário de verão históricos são automáticos, e o site avisa quando a hora informada não existiu ou aconteceu duas vezes naquele dia.
- **Nada se perde de novo.** Tudo está salvo no projeto e no computador.
- **Custo baixo.** Motor próprio, sem API paga de cálculo, e cidades sem serviço externo.

### O que não foi o mais inteligente (principalmente condução do Claude)

- **Faltou um roteiro no início.** A sessão foi de pergunta em pergunta, e o Nicolas se perdeu três vezes. Deveríamos ter fechado um plano curto, com pontos de checagem, antes de construir.
- **Construímos antes de olhar a concorrência.** A pesquisa inicial do projeto já listava a Cosmolica e o portalastral (mapa por IA a R$ 4,99). Isso deveria ter sido checado antes de escrever código, porque muda o que vale a pena vender.
- **Contrariamos o próprio princípio do projeto,** que é validar antes de automatizar. O Nicolas escolheu conscientemente ter a ferramenta primeiro, então não é um erro de decisão, mas o risco continua: ainda não sabemos se alguém pagaria.
- **O desvio da VedicAstroAPI** rendeu pouco para o tempo gasto.
- **O desvio de rodar no Windows** foi o maior desperdício. Para um produto 100% online, o caminho direto era publicar numa hospedagem. As três versões do `iniciar.bat` saíram sem teste real no Windows.
- **Afirmei sem checar** que não havia forma de operar o Replit por aqui. Existe um conector oficial.
- **Faltou validação externa do cálculo.** Ainda não comparamos nossos mapas com outra ferramenta (Cosmolica, Prokerala ou Jagannatha Hora).
- **Segurança.** A chave da Anthropic e as chaves da VedicAstroAPI foram coladas no chat. Vale apagá-las e criar novas.

---

## 4. Pendências e riscos

| Tema | Risco | O que fazer |
|---|---|---|
| **Posicionamento** | Cobrar por algo que a Cosmolica dá de graça | Definir o diferencial (seção 5) |
| **Validação do cálculo** | Um erro de Ascendente ou nakshatra destrói a credibilidade | Feito (seção 2.1); manter o teste automático |
| **Conteúdo** | Textos sem revisão; risco de erro ou de texto genérico | Revisão por alguém que entenda de Jyotish antes de cobrar |
| **Licença do Swiss Ephemeris (AGPL)** | Site público exige publicar o código, ou comprar a licença profissional | Decidir antes de abrir ao público (não sou advogado) |
| **Custo da IA** | O site já está no ar e o botão de texto por IA não tem limite | Limitar uso por pessoa, ou liberar o texto por IA só no produto pago, antes de divulgar o link |
| **Chaves expostas** | Uso indevido | Apagar e criar novas (Anthropic e VedicAstroAPI) |
| **LGPD** | Data e local de nascimento são dados pessoais | Não guardar nada por enquanto; ter aviso de privacidade antes de coletar e-mail |
| **Regras simplificadas** | Raj Yoga só por conjunção; Mangal Dosha sem regras de cancelamento | Evoluir numa v2, com revisão |

---

## 5. Decisões que só o Nicolas (e o Pedro) podem tomar

**1. O que vender, dado que o mapa básico já é grátis no mercado.** Opções, que podem ser combinadas:
- **(a) Mapa grátis como porta de entrada:** o site capta contatos e a receita vem de um produto seguinte.
- **(b) Leitura com curadoria humana:** o Pedro revisa ou complementa o texto e entrega pelo WhatsApp. É um serviço, não uma calculadora.
- **(c) Produtos de nicho:** nome do bebê pela nakshatra (Namakarana), compatibilidade para casais, relatório do ano, datas favoráveis.
- **(d) Formato como upsell:** PDF bonito ou relatório longo como compra extra, como a VedicAstroAPI faz.
- **(e) Ritual diário por assinatura** (vem do documento "horoscopo_tarot_produto"): vender autoconhecimento e orientação diária, não "astrologia".
  - O mapa grátis é a porta de entrada; a assinatura entrega o conteúdo do dia.
  - A astrologia védica tem uma camada diária própria: a nakshatra do dia, o Panchang e a fase de dasha de cada pessoa. É algo que a Cosmolica (uma calculadora) não entrega como hábito.
  - Pergunta a validar: **as pessoas voltam e pagam por uma experiência diária?**

**2. Onde hospedar.** Decidido em 16/set: GitHub + Render, no plano grátis (o site "dorme" sem uso e leva uns 30 s para acordar). Plano pago de US$ 7/mês quando for ao público.

**3. Licença:** abrir o código (AGPL) ou comprar a licença profissional do Swiss Ephemeris.

**4. Revisão de conteúdo:** quem revisa e quando.

---

## 6. Próximos passos recomendados

**Etapa 1 — deixar pronto para teste (1 a 2 sessões)**
1. Apagar as chaves expostas e criar novas (Anthropic: nova chave já está no Render; falta confirmar que a antiga foi revogada).
2. ~~Conferir o cálculo~~ — feito em 15/set (seção 2.1).
3. ~~Escolher a hospedagem e publicar~~ — feito em 16/set (seção 2.2).
4. ~~Relatório em PDF~~ — feito em 17/set (seção 2.2).
5. Limitar o texto por IA antes de mandar o link para mais gente.

**Etapa 2 — testar valor com gente real (1 a 2 semanas)**
4. O Pedro manda o link para 5–10 clientes, no lugar do mapa feito à mão.
5. Perguntar três coisas a cada um:
   - o que achou mais certeiro;
   - o que faltou;
   - pagaria quanto, e por qual versão.
6. Comparar com um mapa que o Pedro fez à mão: o nosso precisa ser claramente melhor.
7. **Teste do ritual diário, sem construir nada:** por 1 a 2 semanas, o Pedro manda pelo WhatsApp uma mensagem curta e personalizada por dia para 5 a 10 pessoas. Eu gero as mensagens com o motor. Observar quem lê, quem responde e quem sente falta quando a mensagem para.

**Etapa 3 — decidir o produto com base no teste**
8. Escolher entre as opções a–e da seção 5 e definir preço.
9. Só então: pagamento (com PIX), contas de usuário, captação de contatos, domínio, medição de acessos e os primeiros anúncios.

**Sobre a tecnologia (referência: documento "horoscopo_tarot_produto")**
- **Manter** o motor atual em Python. Ele já segue a arquitetura recomendada no documento: cálculo determinístico → regras → IA só na linguagem.
- **Adicionar só quando houver necessidade real:**
  - PostHog (medição) já na publicação, porque tem plano grátis e é o que responde se o produto funciona;
  - Supabase (contas e banco) quando existir assinatura;
  - pagamento com PIX quando houver o que vender;
  - Next.js só se a página atual limitar o produto.
- **Regra de custo:** não chamar a IA para o que pode ser calculado ou escrito antes. Cálculo uma vez, textos-base prontos, IA só para a personalização.

---

## 7. Possibilidades futuras (backlog)

- **Conteúdo:** 108 textos de planeta em cada casa (entram direto no PDF, na página das casas); mapa D9; textos para os subperíodos de dasha (as datas já estão no PDF); Sade Sati e trânsitos.
- **PDF:** versão com o texto por IA; PDF como produto pago (opção d da seção 5).
- **Novos produtos:** compatibilidade (Ashtakoot, 36 pontos); nome do bebê pela nakshatra; relatório anual; datas favoráveis (Muhurta e Panchang).
- **Camada diária** (se o teste do ritual der certo): leitura do dia pelo trânsito da Lua sobre o mapa da pessoa, nakshatra do dia, momento da fase de dasha.
- **Outras formas de interpretação,** como no plano original: tarot (sorteio + textos por carta e posição) e numerologia (cálculo + textos). As duas são simples de calcular; o trabalho está no conteúdo.
- **"Pergunte ao seu mapa":** conversa com a IA usando o mapa da pessoa. Precisa de limites claros (sem saúde, dinheiro ou previsões) e controle de custo.
- **Canais:**
  - atendimento pelo WhatsApp (n8n + Claude), que automatiza o que o Pedro faz hoje;
  - páginas de conteúdo para aparecer no Google, como a Cosmolica faz;
  - anúncios, a parte de aprendizado de tráfego;
  - uma skill do Claude com o motor, para o Pedro usar direto no Claude.
- **Expansão:** outros idiomas, depois de validar no Brasil.

---

## 8. Como o processo melhora com o tempo

**Produto (depois que o site estiver no ar)**
- **Medir cada parte do relatório:** um botão "isso fez sentido?" em cada seção mostra quais textos funcionam e quais precisam ser reescritos.
- **Medir o funil:** visitas → mapas gerados → leitura até o fim → contato → compra. Assim se sabe onde as pessoas desistem.
- **Revisar em lotes:** a cada rodada, reescrever os textos com pior avaliação e passá-los por alguém que entenda de Jyotish, em vez de revisar tudo de uma vez.
- **Mapas de referência fixos:** guardar 10 mapas já conferidos com outra ferramenta e rodar o teste automático a cada mudança. Qualquer diferença aparece na hora.
- **Qualidade do texto por IA:** ler uma amostra toda semana com um teste simples: se a frase serviria para qualquer outro mapa, ela é genérica e precisa sair.
- **Custo:** acompanhar quanto a IA gasta por mapa e por mês.
- **Automatizar só o que já foi validado à mão:** por exemplo, o atendimento pelo WhatsApp (n8n) depois que o fluxo manual do Pedro estiver comprovado.

**Trabalho entre Nicolas e Claude**
- **Código com histórico (GitHub):** permite desfazer erros e ver o que mudou.
- **Um lugar só onde o site roda** (a hospedagem), sem instalações locais.
- **Fluxograma no Lucid atualizado** sempre que uma etapa mudar.

## 9. Documentos

- **Fluxograma geral no Lucid:** "Padmini — fluxograma geral (set 2026)", ID `a26002b2-3c89-4d68-b5bd-049bed5c480e`.
- **Fluxograma antigo** "Padmini": ID `2b68670b-a846-46f8-9ca0-64fc5df6ded5`. Reflete o plano anterior.
- **Dois rascunhos com erro no Lucid**, marcados "[rascunho com erro — pode apagar]": podem ser apagados.

## 10. Como trabalhar daqui pra frente (para ninguém se perder)

- **Uma meta por sessão,** dita no começo. Ao final, um resumo curto do que mudou e do próximo passo.
- **Este documento é o mapa do projeto.** Decisões novas entram aqui.
- **Antes de construir algo novo,** responder: quem usa, por que pagaria, e o que já existe de graça.
- **Antes de dizer que algo não dá,** o Claude checa os conectores e ferramentas disponíveis.

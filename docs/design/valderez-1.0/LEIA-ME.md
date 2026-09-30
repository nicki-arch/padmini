# Valderez Astrologia — entrega de design 1.0

Pacote independente para um desenvolvedor aplicar ao site FastAPI + templates HTML existente. Não substitui o backend. A pasta master não foi modificada.

## Abrir
Abra `index.html` no navegador. Todos os arquivos usam caminhos relativos e fontes locais; não é necessário instalar dependências. Alternativa: execute `python -m http.server 8770 --bind 127.0.0.1` nesta pasta e acesse `http://127.0.0.1:8770`.

## Estrutura
- `tokens/`: JSON com funções, escalas, dois temas e todas as combinações de contraste aprovadas; relatório legível em Markdown.
- `assets/css/`: tokens e componentes em CSS puro, compartilhados pelas telas. Sem framework ou JavaScript.
- `assets/fonts/`: Inter e Cormorant Garamond locais, com licenças OFL.
- `assets/img/`: ilustrações vetoriais originais de elementos celestes e papéis sobrepostos.
- `componentes/`: fragmentos HTML copiáveis, catálogo claro e catálogo escuro. Fragmentos não são documentos completos; os catálogos mostram o resultado.
- `telas/`: sete arquivos responsivos: home, três estados do mapa, leitura completa, lista e 404.
- `previas-400/`: páginas com uma janela de 400px para cada tela; o mesmo CSS serve desktop/tablet/mobile.
- `marca/`: logos horizontais e símbolos para fundos claros/escuros, favicon e compartilhamento 1200×630 em SVG. Inclui PNG de compartilhamento 1200×630 e fontes incorporadas nos SVGs com texto.
- `documentacao/`: integração, estados, direitos/proveniência e verificações.
- `referencias-visuais/`: capturas de desktop e celular da entrega.

## Escopo
Esta entrega atende às telas pedidas no briefing atual, não reimplementa as 14 rotas do produto. `documentacao/integracao-fastapi.md` mapeia as demais rotas ao sistema visual. Textos entre colchetes são marcações; rótulos operacionais e o aviso solicitado de envio são exemplos de interface. Nenhum preço comercial nem depoimento foi criado. A linha “+ R$0,99 de taxa da plataforma” reproduz o pedido explícito; o desenvolvedor deve usar a oferta real também no total.

Formulários e botões de compra são referências sem envio. HTML/CSS mostra normal, hover, foco, desabilitado, carregando e estados auxiliares. Menu móvel, FAQ e sugestões nativas de cidade podem ser usados sem JavaScript. Cookies Aceitar/Recusar têm dimensões e destaque iguais; persistência da escolha é tarefa da integração.

O aviso “o restante foi para o seu e-mail” só deve aparecer se o backend confirmar o envio correspondente. Não é indicação de liberação da leitura paga.

Não publique o catálogo, os exemplos com placeholders nem a leitura paga estática como produto real. O desenvolvedor deve reaproveitar a autorização de compra e os contratos já existentes. Não há segredos, dados de clientes, base interpretativa privada, imagens de banco ou scripts de terceiros no pacote.

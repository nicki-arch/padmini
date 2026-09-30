# Estados e comportamento

| Componente | Estados incluídos | Integração esperada |
|---|---|---|
| Botões primário/secundário | Normal, hover real e forçado, foco real e forçado, disabled, loading | Usar disabled para bloquear ação durante requisição e aria-busy para comunicar processamento |
| Texto/data/hora | Normal, hover, foco, disabled, readonly, erro | Mensagem ligada por aria-describedby; erro não depende só de cor |
| Cidade | Normal com datalist, hover, foco, disabled, buscando, vazio, erro, selecionado | Lista nativa possui seus estados de opção; preencher de fonte real e validar ID |
| Consentimento | Desmarcado, marcado, desabilitado, inválido; hover/foco nativos | Rótulo inteiro clicável; não pré-selecionar na tela de captura |
| Cartão | Normal, carregando, vazio, falha | Não anunciar conteúdo fictício como calculado |
| Preço | Normal, hover, foco, desabilitado, carregando | Valor é placeholder; linha de taxa foi solicitada; checkout real no servidor |
| Cookies | Aviso; botões iguais com hover/foco/disabled/loading herdados | Aceitar/recusar não executam ação no HTML estático; integrar escolha e revisão |
| Menu | Desktop, móvel fechado/aberto | details controla teclado, estado e expansão |
| FAQ | Fechada e aberta no catálogo; interação nativa | summary acessível por teclado |
| Artigo/rodapé | Estático; links com hover/foco | Substituir destinos #privacidade/#termos/#contato pelos reais |

Classes `.is-hover` e `.is-focus` só servem para fotografar estados. Não aplicar na implementação final. Não existe animação fora de `prefers-reduced-motion: no-preference`. Em movimento reduzido o indicador fica estático e o texto continua visível.

Telas do mapa separam visualmente cada etapa para revisão. Não há simulação automática de cálculo ou envio. Não foi implementado backend. Componentes adicionais não substituem contratos do app existente.

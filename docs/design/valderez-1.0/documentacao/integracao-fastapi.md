# Integração ao FastAPI e templates HTML

1. Copiar `assets/` para uma pasta versionada dentro dos estáticos existentes, por exemplo `static/valderez/`. Não substituir rotas, configurações ou arquivos de lógica existentes.
2. Extrair cabeçalho/rodapé dos fragmentos para includes Jinja; montar um `base.html`. Carregar primeiro tokens.css, depois components.css. Ajustar os caminhos com `url_for('static', path='valderez/css/tokens.css')` e o equivalente para os demais arquivos. O nome real da montagem estática deve ser conferido no app.
3. Manter `lang="pt-BR"`, viewport, títulos únicos e pular para conteúdo. Remover barra “REFERÊNCIA” após substituir e validar os textos. O noindex é deliberado neste pacote; a decisão por rota cabe ao lançamento.
4. Converter as telas em templates sem usar `|safe` em textos de usuário. Renderizar dados e valores vindos dos contratos existentes. Preço, total e taxa devem ser coerentes com o checkout. Não converter placeholders em valores comerciais.
5. Os três arquivos `mapa-*` representam estados de `/mapa`, não três rotas novas. O app pode renderizar um deles pelo estado de servidor ou atualizar um container com o código próprio já existente. Preservar campos e erros ao falhar; mover foco para o primeiro erro após validação. Ao concluir, mover foco para o título do resultado (tabindex=-1 temporário) e anunciar status sem duplicação.
6. Campo cidade: o datalist usa sugestões de marcação. Na integração, preencher com resultados reais, guardar o identificador canônico em campo hidden e limpar a seleção quando o texto mudar; validar cidade no servidor. Coordenadas, fuso histórico e cálculo não podem ser inferidos apenas do texto livre. Se o datalist não atender ao suporte de leitores de tela escolhido, implementar combobox próprio com setas/Enter/Escape e aria-expanded/aria-activedescendant, sem bibliotecas externas. Não adicionar role=combobox ao datalist nativo.
7. Datas/horas: limites e obrigatoriedade vêm do contrato real; não inventar hora quando desconhecida. Nome opcional, e-mail obrigatório para o fluxo com continuação por e-mail. Checkbox deve refletir a finalidade real: não confundir aceite necessário com autorização promocional opcional.
8. Envio: o aviso exato solicitado pertence ao estado de confirmação do envio, não ao clique nem à geração do mapa. Mostrar falha/reenvio se houver erro. Especificar qual continuação gratuita foi enviada e o que continua reservado ao pago.
9. Completo: renderizar somente após autorização no servidor. Ocultar HTML por CSS ou alternar uma query string nunca autoriza conteúdo pago. Preservar checkout, associação ao nascimento, atribuição, webhook e links pessoais existentes. Não incluir exemplos completos em rotas públicas reais.
10. Lista: conectar ao endpoint existente, validar servidor, tratar sucesso neutro, falha e duplicidade sem divulgar cadastros. Botões neste pacote usam type=button para evitar envios acidentais; na integração usar type=submit e o método/endpoint corretos. Nunca enviar dados de nascimento por GET.
11. Cookies: ambas as escolhas devem persistir a preferência e fechar o aviso; tags opcionais só podem seguir a escolha correspondente. Não há armazenamento nem analytics no pacote. Permitir revisar a escolha no rodapé. Validar as finalidades com a operação.
12. Menu e FAQ usam details/summary. O menu móvel empilha em painel flutuante; não é modal e não prende o foco. O navegador controla expansão e teclado. Para menu ativo, aplicar aria-current=page ao link real. Evitar IDs repetidos ao incluir fragmentos (o catálogo é só referência de estados).
13. A página 404 precisa retornar HTTP 404 no app. A estética não altera o status da resposta.

## As 14 rotas do produto
| Rota | Aplicação desta entrega |
|---|---|
| / | home.html; decidir com produto se equivale a /mapa no lançamento |
| /mapa | mapa-formulario, mapa-carregando, mapa-amostra e leitura-completa, conforme estado autorizado |
| /compatibilidade | Aplicar componentes à interface existente; sem novo fluxo nesta entrega |
| /numerologia | Aplicar componentes quando retomar investimento; sem nova tela |
| /tarot | Mesmo critério de numerologia |
| /lista | lista.html |
| /minhas-leituras | Campo de e-mail, botão e status; reaproveitar contratos de reenvio |
| /privacidade | Tipografia de artigo, cabeçalho e rodapé; texto revisado existente |
| /termos | Mesmo padrão da privacidade |
| /descadastrar | Botão secundário e status; preservar validação do link |
| /blog | Cartões existentes quando houver conteúdo revisado |
| /blog/<artigo> | Fragmento artigo.html; substituir conteúdo e fontes |
| /live | Componentes de formulário/resultado; manter proteção existente |
| /estilo | Catálogo interno; controle real de acesso quando hospedado |

## Responsive e cor
Base mobile 0–767; tablet 768–1099; desktop a partir de 1100px. Desktop de referência 1440px; mobile 400px. Tema claro para leitura e formulários; tema escuro para abertura, navegação e fechamento. `data-theme` controla blocos explicitamente, sem preferência automática do sistema. Não usar texto claro em destaque claro: usar onAccent. O rosa original decorativo foi ajustado nos tokens semânticos para legibilidade.

## Marca
SVGs de texto têm as fontes incorporadas e não dependem de instalação para renderização no navegador. No editor vetorial, instalar as fontes fornecidas se necessário. O símbolo e o favicon são apenas formas geométricas. PNG 1200×630 serve como modelo de compartilhamento; substituir colchetes e endereço antes de configurar og:image. O símbolo é uma proposta original de refinamento desta entrega, não uma alegação de registro de marca.

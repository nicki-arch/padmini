"""
Padmini — base de significações (v1).

Cobre o que o Mapa Védico Essencial precisa: Ascendente (12), Lua por
nakshatra (27), fase atual de Vimshottari (9), dignidades dos 7 grahas
clássicos, combustão, yogas e doshas detectados por detectar_fatos.py.
Ainda NÃO cobre planeta×casa (108 combinações) — fica para a v2.

Também cobre o produto de compatibilidade (Guna Milan): as 8 kootas por
faixa de pontuação, os doshas de casal (Bhakoot, Nadi) com cancelamento,
Mangal do casal e a moldura por faixa de nota total.

Conteúdo redigido por IA como ponto de partida. Precisa de revisão por
astrólogo antes de uso comercial. Regra de escrita: cada texto amarra um
fato específico a uma consequência específica; nada que sirva para
qualquer pessoa (anti-Barnum). Em compatibilidade, uma regra a mais:
nenhum texto condena o casal — nota baixa vira "ponto de atenção", nunca
"não vai dar certo".
"""

NOME_PT = {
    "Surya": "Sol", "Chandra": "Lua", "Mangala": "Marte", "Budha": "Mercúrio",
    "Guru": "Júpiter", "Shukra": "Vênus", "Shani": "Saturno", "Rahu": "Rahu", "Ketu": "Ketu",
}

SIGNO_PT = {
    "Mesha": "Áries", "Vrishabha": "Touro", "Mithuna": "Gêmeos", "Karka": "Câncer",
    "Simha": "Leão", "Kanya": "Virgem", "Tula": "Libra", "Vrishchika": "Escorpião",
    "Dhanu": "Sagitário", "Makara": "Capricórnio", "Kumbha": "Aquário", "Meena": "Peixes",
}

LAGNA = {
    "Mesha": "Com Ascendente em Áries, a pessoa se apresenta ao mundo pela iniciativa: age primeiro e ajusta depois. A mesma rapidez que abre caminhos também gera atritos quando os outros precisam de mais tempo.",
    "Vrishabha": "Com Ascendente em Touro, a presença é calma e constante. A pessoa confia no que pode tocar e construir aos poucos, e custa a mudar de rumo depois que decide.",
    "Mithuna": "Com Ascendente em Gêmeos, a pessoa entra nas situações pela conversa e pela curiosidade. Adapta-se rápido, mas pode dispersar a energia entre interesses demais.",
    "Karka": "Com Ascendente em Câncer, a pessoa lê o ambiente pelo clima emocional antes de qualquer outra coisa. Protege quem ama com firmeza e se fecha quando sente o terreno inseguro.",
    "Simha": "Com Ascendente em Leão, a pessoa ocupa espaço sem precisar pedir. Precisa sentir que o que faz tem dignidade e reconhecimento, e perde o fôlego em papéis invisíveis.",
    "Kanya": "Com Ascendente em Virgem, a pessoa se apresenta pela competência e pelo cuidado com os detalhes. O olhar crítico que resolve problemas também pode se voltar contra ela mesma.",
    "Tula": "Com Ascendente em Libra, a pessoa busca equilíbrio e acordo em cada interação. Tem talento para mediar, e o desafio é não adiar decisões para manter a paz.",
    "Vrishchika": "Com Ascendente em Escorpião, a pessoa observa antes de se revelar e percebe o que não está sendo dito. Atravessa crises com resistência, mas confia devagar.",
    "Dhanu": "Com Ascendente em Sagitário, a pessoa é movida por sentido e horizonte: estudo, viagem, fé ou causa. Fala com franqueza, às vezes antes de medir o efeito.",
    "Makara": "Com Ascendente em Capricórnio, a pessoa se apresenta pela seriedade e pelo compromisso com resultados de longo prazo. Amadurece cedo e tende a colher mais na segunda metade da vida.",
    "Kumbha": "Com Ascendente em Aquário, a pessoa pensa em sistemas e coletivos antes do caso individual. Valoriza independência e pode parecer distante mesmo quando se importa.",
    "Meena": "Com Ascendente em Peixes, a pessoa é permeável ao ambiente e às emoções dos outros. Tem sensibilidade artística ou espiritual, e precisa de limites claros para não se diluir.",
}

NAKSHATRA = {
    "Ashwini": {"regente": "Ketu", "deidade": "Ashwini Kumaras",
                "texto": "Lua em Ashwini dá reação emocional rápida e vontade de resolver na hora. É a nakshatra dos curadores celestes: há impulso de socorrer, e pouca paciência com o que demora."},
    "Bharani": {"regente": "Shukra", "deidade": "Yama",
                "texto": "Lua em Bharani carrega intensidade e senso de responsabilidade pelo que começa. A pessoa sustenta processos pesados até o fim, mas pode se sobrecarregar tentando carregar tudo sozinha."},
    "Krittika": {"regente": "Surya", "deidade": "Agni",
                 "texto": "Lua em Krittika, regida pelo fogo, dá uma emoção que corta: franqueza, senso de justiça e pouca tolerância a meias-verdades. O desafio é aquecer sem queimar quem está perto."},
    "Rohini": {"regente": "Chandra", "deidade": "Brahma",
               "texto": "Lua em Rohini marca forte ligação com conforto, beleza e prazer dos sentidos. Não é superficialidade: o mundo sensorial é, para essa pessoa, um caminho legítimo de conexão com a vida."},
    "Mrigashira": {"regente": "Mangala", "deidade": "Soma",
                   "texto": "Lua em Mrigashira, simbolizada pelo cervo, dá uma mente que busca sempre: novas ideias, lugares e respostas. A inquietação é fonte de descoberta e também de dificuldade em se fixar."},
    "Ardra": {"regente": "Rahu", "deidade": "Rudra",
              "texto": "Lua em Ardra, regida por Rudra, associa o crescimento emocional a tempestades: perdas e rupturas que depois limpam o terreno. A pessoa pensa com intensidade e aprende melhor depois de uma crise."},
    "Punarvasu": {"regente": "Guru", "deidade": "Aditi",
                  "texto": "Lua em Punarvasu, a nakshatra do retorno, dá capacidade rara de recomeçar. Depois de um revés, a pessoa volta ao ponto de equilíbrio sem ressentimento duradouro."},
    "Pushya": {"regente": "Shani", "deidade": "Brihaspati",
               "texto": "Lua em Pushya, considerada a mais auspiciosa das nakshatras, dá vocação para nutrir e sustentar os outros com disciplina. A pessoa se sente bem quando é útil, e precisa lembrar de receber também."},
    "Ashlesha": {"regente": "Budha", "deidade": "Nagas",
                 "texto": "Lua em Ashlesha dá inteligência emocional aguda, quase instintiva, para ler pessoas e situações. O risco é usar essa percepção para controlar em vez de compreender."},
    "Magha": {"regente": "Ketu", "deidade": "Pitris",
              "texto": "Lua em Magha, regida pelos ancestrais, dá forte senso de linhagem, tradição e dignidade. A pessoa se sente responsável por honrar de onde veio, às vezes com rigidez."},
    "Purva Phalguni": {"regente": "Shukra", "deidade": "Bhaga",
                       "texto": "Lua em Purva Phalguni dá necessidade real de prazer, descanso e convívio. A criatividade floresce no lazer, e a pessoa se esgota em rotinas sem alegria."},
    "Uttara Phalguni": {"regente": "Surya", "deidade": "Aryaman",
                        "texto": "Lua em Uttara Phalguni, ligada a Aryaman, deus dos contratos e da amizade, dá lealdade e senso de compromisso. A pessoa cumpre o que promete e espera o mesmo dos outros."},
    "Hasta": {"regente": "Chandra", "deidade": "Savitar",
              "texto": "Lua em Hasta, simbolizada pela mão, dá habilidade manual, prática e comercial. A pessoa se acalma fazendo e resolvendo, e fica ansiosa quando não tem como agir."},
    "Chitra": {"regente": "Mangala", "deidade": "Vishvakarma",
               "texto": "Lua em Chitra, a nakshatra do arquiteto celeste, dá senso estético apurado e vontade de criar algo bem-feito. Há exigência com a forma, a própria e a dos outros."},
    "Swati": {"regente": "Rahu", "deidade": "Vayu",
              "texto": "Lua em Swati, regida pelo vento, dá necessidade de independência e movimento. A pessoa se adapta como um broto que dobra sem quebrar, mas sofre quando se sente presa."},
    "Vishakha": {"regente": "Guru", "deidade": "Indra-Agni",
                 "texto": "Lua em Vishakha dá foco em metas e determinação para alcançá-las. A satisfação vem da conquista, e a pessoa precisa cuidar para que o objetivo não apague o caminho."},
    "Anuradha": {"regente": "Shani", "deidade": "Mitra",
                 "texto": "Lua em Anuradha, ligada a Mitra, deus da amizade, dá talento para criar vínculos duradouros e cooperar em grupo. A devoção a pessoas e causas é profunda e persistente."},
    "Jyeshtha": {"regente": "Budha", "deidade": "Indra",
                 "texto": "Lua em Jyeshtha, a nakshatra do mais velho, dá senso de responsabilidade e proteção sobre os outros. Vem com necessidade de reconhecimento e alguma dificuldade em mostrar vulnerabilidade."},
    "Mula": {"regente": "Ketu", "deidade": "Nirriti",
             "texto": "Lua em Mula, simbolizada pelas raízes, dá impulso de ir ao fundo das coisas, mesmo que isso signifique desmontar o que existe. A pessoa busca a verdade essencial e tolera mal respostas rasas."},
    "Purva Ashadha": {"regente": "Shukra", "deidade": "Apas",
                      "texto": "Lua em Purva Ashadha, ligada às águas, dá convicção e poder de persuasão. A pessoa acredita no que defende e raramente se dá por vencida numa discussão."},
    "Uttara Ashadha": {"regente": "Surya", "deidade": "Vishvadevas",
                       "texto": "Lua em Uttara Ashadha dá senso ético firme e vitórias que vêm devagar, mas ficam. A pessoa sustenta princípios mesmo quando custa caro no curto prazo."},
    "Shravana": {"regente": "Chandra", "deidade": "Vishnu",
                 "texto": "Lua em Shravana, a nakshatra da escuta, dá capacidade de aprender ouvindo e de guardar conhecimento. A pessoa se conecta pelo que ouve, e é sensível ao que dizem sobre ela."},
    "Dhanishta": {"regente": "Mangala", "deidade": "Vasus",
                  "texto": "Lua em Dhanishta, simbolizada pelo tambor, dá senso de ritmo, música e prosperidade. A pessoa funciona bem em grupo e em movimento, e pode ter dificuldade na intimidade a dois."},
    "Shatabhisha": {"regente": "Rahu", "deidade": "Varuna",
                    "texto": "Lua em Shatabhisha, a nakshatra das cem curas, dá uma mente investigativa e reservada. A pessoa precisa de solidão para se recompor e tende a buscar soluções pouco convencionais."},
    "Purva Bhadrapada": {"regente": "Guru", "deidade": "Aja Ekapada",
                         "texto": "Lua em Purva Bhadrapada dá intensidade idealista: a pessoa se entrega a causas com fervor. Pode oscilar entre extremos antes de encontrar um meio-termo."},
    "Uttara Bhadrapada": {"regente": "Shani", "deidade": "Ahir Budhnya",
                          "texto": "Lua em Uttara Bhadrapada, ligada à serpente das profundezas, dá calma, profundidade e controle emocional. A pessoa sustenta pressão sem demonstrar e ganha sabedoria com o tempo."},
    "Revati": {"regente": "Budha", "deidade": "Pushan",
               "texto": "Lua em Revati, a última nakshatra, ligada ao protetor dos viajantes, dá compaixão e vontade de guiar os outros. A pessoa se sente responsável por quem está perdido, às vezes além do que consegue."},
}

DASHA = {
    "Ketu": "fase de Ketu (7 anos): desapego, interiorização e cortes. O que já não tem sentido tende a cair, e a atenção se volta para o que é essencial.",
    "Shukra": "fase de Vênus (20 anos, a mais longa): relacionamentos, conforto, arte e prazer ganham peso. É um período para construir parcerias e qualidade de vida.",
    "Surya": "fase do Sol (6 anos): identidade, autoridade e relação com figuras de poder e com o pai. A pessoa é chamada a assumir posição e visibilidade.",
    "Chandra": "fase da Lua (10 anos): vida emocional, lar, mãe e necessidades de segurança em primeiro plano. Mudanças de casa e de rotina são comuns.",
    "Mangala": "fase de Marte (7 anos): energia, ação e conflito. Bom período para iniciar projetos com coragem, e também para aprender a dosar a força.",
    "Rahu": "fase de Rahu (18 anos): ambição, desejo de novidade e caminhos pouco convencionais. Crescimento rápido, com risco de perder o chão.",
    "Guru": "fase de Júpiter (16 anos): expansão, estudo, ensino e orientação. Mentores, filhos e fé tendem a ter papel importante.",
    "Shani": "fase de Saturno (19 anos): responsabilidade, esforço e construção lenta. O que é feito com disciplina neste período tende a durar.",
    "Budha": "fase de Mercúrio (17 anos): aprendizado, comunicação, comércio e habilidades práticas. A mente fica mais ativa e versátil.",
}

GRAHA_DIGNIDADE = {
    "Surya": {
        "exaltado": "O Sol exaltado em Áries dá clareza de propósito e liderança natural: a autoridade vem sem esforço para prová-la.",
        "debilitado": "O Sol debilitado em Libra faz a pessoa buscar validação externa antes de agir. A autoconfiança se constrói nas relações, não isolada delas.",
        "proprio": "O Sol em Leão, seu próprio signo, dá identidade forte e senso claro de quem se é. A dificuldade, quando existe, é abrir espaço para os outros brilharem.",
    },
    "Chandra": {
        "exaltado": "A Lua exaltada em Touro dá estabilidade emocional rara: a pessoa se acalma sozinha, sem depender das circunstâncias.",
        "debilitado": "A Lua debilitada em Escorpião intensifica a vida emocional a ponto de ser difícil descansar dela. A mesma intensidade que dá profundidade dificulta o desapego.",
        "proprio": "A Lua em Câncer, seu próprio signo, dá vida emocional estável e nutridora. O lar e os vínculos próximos funcionam como base real de segurança.",
    },
    "Mangala": {
        "exaltado": "Marte exaltado em Capricórnio canaliza a energia com estratégia: a ação é disciplinada e tende a dar resultado concreto.",
        "debilitado": "Marte debilitado em Câncer faz a raiva e a assertividade passarem pelo filtro emocional. A pessoa pode reagir de forma indireta em vez de enfrentar abertamente.",
        "proprio": "Marte em signo próprio (Áries ou Escorpião) dá coragem, iniciativa e capacidade de se defender sem hesitar.",
    },
    "Budha": {
        "exaltado": "Mercúrio exaltado em Virgem dá mente analítica, precisa e organizada, com talento para detalhes, números e linguagem.",
        "debilitado": "Mercúrio debilitado em Peixes faz o pensamento funcionar mais por intuição e imagem do que por lógica linear. Isso favorece a criação e atrapalha a organização.",
        "proprio": "Mercúrio em Gêmeos, signo próprio, dá raciocínio ágil, curiosidade ampla e facilidade de comunicação.",
    },
    "Guru": {
        "exaltado": "Júpiter exaltado em Câncer amplia a capacidade de cuidar, ensinar e expandir pelo vínculo afetivo. A sabedoria dessa pessoa nasce da experiência, não só do estudo.",
        "debilitado": "Júpiter debilitado em Capricórnio gera cautela onde seria natural confiar e expandir. A expansão vem depois de testar a estrutura.",
        "proprio": "Júpiter em signo próprio (Sagitário ou Peixes) dá fé e senso de propósito que sustentam a pessoa mesmo sem garantias externas.",
    },
    "Shukra": {
        "exaltado": "Vênus exaltada em Peixes dá amor generoso e sensibilidade artística refinada. A pessoa ama de forma idealista e às vezes pouco prática.",
        "debilitado": "Vênus debilitada em Virgem faz o afeto passar pelo crivo da crítica. A pessoa demonstra amor servindo, e pode ter dificuldade em relaxar no prazer.",
        "proprio": "Vênus em signo próprio (Touro ou Libra) dá facilidade para relacionamentos, gosto estético e capacidade de criar harmonia ao redor.",
    },
    "Shani": {
        "exaltado": "Saturno exaltado em Libra dá senso de justiça, paciência e responsabilidade nas relações. A pessoa constrói autoridade pela imparcialidade.",
        "debilitado": "Saturno debilitado em Áries cria tensão entre pressa e disciplina. As lições de paciência chegam por frustração até a pessoa aprender a esperar.",
        "proprio": "Saturno em signo próprio (Capricórnio ou Aquário) dá persistência e capacidade de construir estruturas duradouras.",
    },
}

COMBUSTAO = {
    "Chandra": "A Lua muito próxima do Sol (perto da lua nova) faz as necessidades emocionais ficarem em segundo plano diante da vontade e dos objetivos.",
    "Mangala": "Marte combusto faz a energia e a assertividade se apagarem diante da vontade central. A pessoa pode ter dificuldade em se impor por conta própria.",
    "Budha": "Mercúrio combusto subordina o raciocínio próprio à identidade e à vontade. A clareza mental existe, mas fica ofuscada até a pessoa aprender a dizer o que pensa sem medo de contrariar.",
    "Guru": "Júpiter combusto enfraquece a confiança nos próprios valores e em conselheiros. A fé e a orientação precisam ser construídas de forma mais consciente.",
    "Shukra": "Vênus combusta faz o afeto e o prazer ficarem a serviço da própria identidade. Nos relacionamentos, a pessoa pode ter dificuldade em se colocar no lugar do outro.",
    "Shani": "Saturno combusto cria tensão entre autoridade própria e disciplina externa. Relações com figuras de autoridade tendem a ser desafiadoras.",
}

CAZIMI = "{planeta} está praticamente colado ao Sol (cazimi, a menos de 1°). Diferente da combustão comum, essa fusão é tradicionalmente lida como fortalecedora: as qualidades de {planeta} ficam integradas à vontade central."

YOGAS = {
    "gaja_kesari": "Júpiter em ângulo a partir da Lua (Gaja Kesari Yoga) dá mente expansiva e facilidade para inspirar confiança. É um dos yogas mais citados, então vale como reforço de temperamento, não como garantia de grandeza.",
    "pancha_mahapurusha": {
        "ruchaka": "Marte forte em ângulo (Ruchaka Yoga) dá coragem física, liderança em situações de pressão e capacidade de competir.",
        "bhadra": "Mercúrio forte em ângulo (Bhadra Yoga) dá inteligência prática, eloquência e habilidade em negócios e comunicação.",
        "hamsa": "Júpiter forte em ângulo (Hamsa Yoga) marca alguém com presença ética reconhecível: a sabedoria aparece na forma como a pessoa se porta.",
        "malavya": "Vênus forte em ângulo (Malavya Yoga) dá charme, gosto refinado e facilidade para atrair conforto e boas parcerias.",
        "sasa": "Saturno forte em ângulo (Sasa Yoga) dá autoridade construída com disciplina e capacidade de liderar grupos e estruturas.",
    },
    "yogakaraka": "{planeta} rege ao mesmo tempo a casa {rege_kendra} (ângulo) e a casa {rege_trikona} (trígono). Por isso, {planeta} é o planeta mais benéfico deste mapa (yogakaraka), e a fase regida por esse planeta tende a ser das mais produtivas.",
    "raj_yoga": "{regente_kendra} (regente de ângulo) e {regente_trikona} (regente de trígono) estão juntos em {signo}. Essa associação é um Raj Yoga clássico, indicativo de reconhecimento e status. É comum o suficiente para não ser tratado como raro, mas é real como fator de força.",
    "neecha_bhanga": "{planeta} está debilitado, mas o regente do signo onde ele está ({dispositor}) ocupa um ângulo. É o cancelamento de debilitação (Neecha Bhanga): a fraqueza inicial tende a virar força depois de esforço e amadurecimento.",
}

DOSHA = {
    "mangal_dosha": "Marte ocupa uma posição sensível em relação a {referencias} (Mangal Dosha). Na tradição, isso pede atenção à forma como a pessoa expressa assertividade nos relacionamentos. Não é uma sentença, e cerca de metade das pessoas tem alguma forma dessa configuração.",
}

# ===========================================================================
# COMPATIBILIDADE (Guna Milan) — textos por koota, dosha de casal e faixa.
#
# Uso: o motor (compatibilidade.py) decide os pontos; a função banda_koota()
# traduz obtido/max em "forte" | "medio" | "fraco"; aqui estão os trechos
# correspondentes. Kootas binárias (Varna, Bhakoot, Nadi) só têm "forte" e
# "fraco" — o seletor cai no mais próximo. Cada trecho é combinável (1-2
# frases) e nunca condena o casal.
# ===========================================================================
KOOTA = {
    "Varna": {
        "tema": "postura diante da vida",
        "descricao": "Varna fala da postura de fundo diante da vida — o ritmo interior com que cada um se coloca no mundo.",
        "forte": "Vocês partem de uma postura de fundo parecida: o jeito de encarar responsabilidades e o próprio ritmo conversam, o que dá uma base silenciosa de entendimento no dia a dia.",
        "fraco": "Vocês encaram a vida a partir de posturas diferentes — um mais movido pela ação, o outro pela reflexão ou pelo cuidado. É a koota de menor peso das oito: não define nada sozinha, só pede que cada um respeite o tempo do outro.",
    },
    "Vashya": {
        "tema": "atração e influência mútua",
        "descricao": "Vashya mede a atração e a influência natural de um sobre o outro — quem puxa quem, e com que facilidade.",
        "forte": "A atração e a influência entre vocês fluem nos dois sentidos: vocês se puxam com naturalidade, sem que um precise se impor sobre o outro.",
        "medio": "A atração existe, mas a influência não é totalmente simétrica — em alguns assuntos um tende a conduzir mais. Funciona bem quando isso é combinado, não assumido em silêncio.",
        "fraco": "A influência entre vocês puxa mais para um lado. Não é um problema por si; só pede atenção para a relação não virar um conduzindo e o outro apenas seguindo.",
    },
    "Tara": {
        "tema": "bem-estar e sorte da relação",
        "descricao": "Tara olha o bem-estar da relação — se a convivência tende a somar energia aos dois ou a desgastar.",
        "forte": "A convivência tende a somar: a presença de um faz bem ao outro, e a relação parece dar sorte aos dois. Bom presságio para a vida dividida no dia a dia.",
        "medio": "O bem-estar flui mais num sentido do que no outro — um costuma ser mais 'porto seguro' na relação. Nada grave, mas vale revezar quem sustenta quem.",
        "fraco": "A energia da convivência pede cuidado: em fases difíceis, vocês podem cansar um ao outro em vez de recarregar. Descanso e espaço individual ajudam mais aqui do que na média dos casais.",
    },
    "Yoni": {
        "tema": "encaixe físico e instintivo",
        "descricao": "Yoni fala do encaixe físico e instintivo — a química do corpo e o instinto de um diante do outro.",
        "forte": "O encaixe físico e instintivo é um dos pontos fortes de vocês: há química natural e um conforto no corpo que não precisa ser forçado.",
        "medio": "A química é boa, com ritmos que às vezes diferem — momentos de mais e de menos sintonia física. Falar de desejo abertamente rende mais do que esperar adivinhação.",
        "fraco": "O instinto físico de vocês funciona em ritmos bem diferentes. Isso não impede intimidade boa, mas ela vem mais de comunicação e paciência do que de química automática.",
    },
    "Graha Maitri": {
        "tema": "sintonia mental e amizade",
        "descricao": "Graha Maitri mede a sintonia mental e a amizade de fundo — se, tirando a paixão, vocês seriam amigos.",
        "forte": "Tirando o romance, vocês seriam amigos: há sintonia mental e um respeito que sustenta a relação nos dias sem paixão. É uma das bases mais sólidas que um casal pode ter.",
        "medio": "A amizade existe, mas exige tradução: vocês pensam de formas diferentes e às vezes precisam de um esforço extra para se entender. Quando esse esforço vira hábito, funciona bem.",
        "fraco": "As mentes de vocês seguem lógicas distintas, o que pode gerar desencontros em conversas comuns. Em compensação, diferença de pensamento também traz complementaridade — desde que os dois queiram entender o do outro.",
    },
    "Gana": {
        "tema": "temperamento",
        "descricao": "Gana compara o temperamento de fundo — o tipo de energia com que cada um reage ao mundo.",
        "forte": "Os temperamentos de vocês combinam: reagem ao mundo com uma energia parecida, o que reduz o número de atritos bobos no dia a dia.",
        "medio": "Os temperamentos são diferentes, mas conciliáveis — um mais suave, o outro mais intenso. Costuma dar certo quando cada um respeita o jeito do outro em vez de tentar corrigi-lo.",
        "fraco": "Vocês têm temperamentos de naturezas distintas, e é normal a mesma situação ser lida de formas opostas. Aqui, nomear a diferença ('a gente reage diferente a isso') evita que ela vire briga.",
    },
    "Bhakoot": {
        "tema": "vínculo emocional e prosperidade",
        "descricao": "Bhakoot mede o vínculo emocional e a prosperidade que a relação tende a trazer para a vida dos dois.",
        "forte": "O vínculo emocional entre vocês tende a fortalecer a vida dos dois — a relação soma em bem-estar e projetos, em vez de dividir energia.",
        "fraco": "A posição das Luas de vocês marca um ponto de atenção clássico sobre o rumo comum (o Bhakoot dosha). Na prática, pede que vocês cuidem para caminhar na mesma direção nas decisões grandes. Veja abaixo se a tradição já o neutraliza no caso de vocês.",
    },
    "Nadi": {
        "tema": "vitalidade e saúde a longo prazo",
        "descricao": "Nadi olha a vitalidade da relação no longo prazo — a compatibilidade das energias mais profundas dos dois.",
        "forte": "As energias de fundo de vocês são complementares, bom sinal para a vitalidade da relação no longo prazo. É a koota de maior peso, e vocês pontuam bem nela.",
        "fraco": "As Luas de vocês compartilham a mesma Nadi (o Nadi dosha), a koota de maior peso. É o ponto de atenção mais citado em compatibilidade — e também um dos que mais têm regras de alívio. Veja abaixo se alguma se aplica a vocês.",
    },
}

# Doshas de casal: texto quando presente e alívio quando cancelado (parihara).
COMPAT_DOSHA = {
    "bhakoot": {
        "texto": "As Luas de vocês formam o Bhakoot dosha — um ponto de atenção sobre o vínculo emocional e o rumo comum da vida.",
        "texto_cancelamento": "A própria tradição, porém, considera esse ponto neutralizado aqui: os regentes dos signos lunares de vocês se dão bem (ou são o mesmo planeta), o que dissolve boa parte do peso prático do dosha.",
    },
    "nadi": {
        "texto": "As Luas de vocês estão na mesma Nadi — o Nadi dosha, o ponto de maior peso do sistema. Lido como atenção à vitalidade da relação; nunca como impedimento.",
        "texto_cancelamento": "E aqui vem o alívio que a tradição prevê: a configuração de vocês cai numa das regras clássicas de cancelamento do Nadi dosha, o que reduz muito o seu peso prático.",
    },
}

# Mangal (Manglik) do casal — por situação retornada por mangal_do_casal().
MANGAL_CASAL = {
    "anulado": "Os dois carregam a configuração de Marte chamada Manglik. Quando isso acontece nos dois, a tradição entende que o dosha se anula entre vocês — as intensidades se equilibram em vez de colidir.",
    "atencao": "Um de vocês tem a configuração de Marte chamada Manglik. Sozinha, não impede nada; é um convite a lidar com assertividade e temperamento de forma consciente dentro da relação.",
    "ausente": "Nenhum de vocês carrega a configuração Manglik de Marte — um fator a menos de atenção na leitura de casal.",
}

# Moldura pela nota total (usa {total}). Sempre não-fatalista.
COMPAT_FAIXA = {
    "excepcional": "Com {total} de 36 pontos, vocês estão numa faixa de encaixe rara: a maioria das dimensões que a tradição mede soma a favor da relação.",
    "forte": "Com {total} de 36 pontos, vocês se encaixam onde mais importa. É uma base forte, com pontos de atenção que dá para trabalhar de olhos abertos.",
    "boa com atencao": "Com {total} de 36 pontos, a base de vocês é boa e alguns pontos pedem cuidado. O número sozinho não conta a história: o que decide é quais dimensões pesam mais para vocês dois.",
    "requer trabalho": "Com {total} de 36 pontos, vocês são diferentes em coisas que importam. Isso não quer dizer 'não vai dar certo' — quer dizer que a relação pede mais conversa e intenção do que a média. Muita gente com essa nota vive relações felizes; a diferença é escolher trabalhar os pontos abaixo.",
}

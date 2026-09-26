# Versão ocidental — decisões de método

Rodada 1 (26/set/2026). Tudo aqui vive atrás de `PADMINI_SISTEMA=ocidental`
(ver `sistema.py`); com `vedica` (padrão) nada disto aparece no site.

## Mapa natal (`mapa_ocidental.py`)

| Tema | Decisão | Por quê |
|---|---|---|
| Zodíaco | Tropical | É o da astrologia ocidental |
| Efemérides | Swiss Ephemeris, modo Moshier (`FLG_MOSEPH`) | Sem arquivo de efemérides; erro medido contra o astro-seek ≤ 8" nos planetas |
| Fuso / horário de verão | `julian_day_utc` da védica (zoneinfo) | Já resolve o histórico brasileiro; 4 casos de horário de verão conferidos |
| Casas | Placidus; Porfírio dentro do círculo polar | Placidus não existe acima de ~66°; o resultado diz qual foi usado |
| Nodo | Verdadeiro | Padrão do astro.com (a tabela padrão deles lista "TrueNode"); o astro-seek usa o médio por padrão |
| Quíron | Fora | O Moshier não tem |
| Aspectos | 0°, 60°, 90°, 120°, 180° | Maiores |
| Orbes | 8°; 10° com Sol ou Lua; sextil 6° | Brief; definidos só em `orbe_maximo` |
| Aspectos no mapa | 10 planetas + Ascendente e MC; Nodo fora | Nodo lido por signo e casa |
| "Aspectos principais" do completo | Sem os de geração (lento × lento), até 14, do mais exato | Urano–Netuno não é da pessoa |
| Destaque da amostra | O aspecto mais exato que envolve Sol, Lua, Mercúrio, Vênus, Marte ou Ascendente | Idem |
| Elementos/modalidades | 10 planetas + Ascendente, peso igual | Simples de explicar |
| Regentes | Modernos | Brief |
| Graus na tela | Truncados no minuto (29°59'58" → 29°59') | Como os sites mostram; arredondar parece o signo seguinte |
| Sem hora | Meio-dia local; sem Ascendente, MC, casas; Lua marcada incerta se muda de signo no dia; aspectos da Lua fora | Nada inventado |

## Validação

`testes/dados/referencias_ocidental.json`: 11 mapas copiados do
horoscopes.astro-seek.com em 26/set/2026 (URL de cada um no arquivo; tropical,
Placidus, "Lunar Nodes (True)", fuso automático). Inclui São Paulo 1987, Rio
1995, Porto Alegre 2005 e Brasília 2010 em horário de verão, Lisboa e Londres.
Resultado: **11 de 11 batem a menos de 1'** — planetas até 8", nodo até 30",
casas e Ascendente/MC até 8"; casa de cada planeta e retrogradação iguais.

## Textos

`conteudo/ocidental/textos/` — ver o `LEIA.md` da pasta. 339 textos, todos com
`revisado: false`. Os testes conferem tamanho (60–120 palavras), ausência de
previsão de saúde/morte/dinheiro e que todo aspecto possível entre pessoais
tem texto.

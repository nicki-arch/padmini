"""
Padmini — cores e fontes de cada versão do site. FONTE ÚNICA, também para o que
não é CSS: e-mails (entrega.py, marketing.py), PDFs (gerar_pdf.py,
gerar_pdf_ocidental.py), imagens de compartilhamento
(scripts/gerar_og_ocidental.py), cartas do tarot e /live.

  - "vedica": os valores de sempre ("Lótus à meia-luz": ameixa, açafrão). O CSS
    dela continua sendo o static/base.css; aqui estão os mesmos números, para o
    e-mail e o PDF.
  - "ocidental": "Almanaque" (rodada 3). A astrologia ocidental, o tarot e a
    numerologia chegaram ao Brasil pelos almanaques, pelos atlas celestes e pelo
    baralho Rider-Waite (1909, litografia de cores chapadas com contorno): azul
    de tinta de impressão, papel creme, ouro velho e zarcão. O CSS dela é o
    static/ocidental/tema.css, GERADO daqui (python scripts/gerar_tema_css.py;
    há teste que confere que o arquivo está em dia).

Contrastes (WCAG) estão em docs/marca-ocidental.md e na página /estilo, calculados
por `contraste()` abaixo. Regra do base.css: texto de corpo entre 10:1 e 13:1 e
nada legível abaixo de 4,5:1.
"""

# ---------------------------------------------------------------------------
# Tela (tokens CSS). Os nomes são os do base.css: --saffron é "o acento
# principal" e --blush "o segundo acento", qualquer que seja a cor da versão.
# ---------------------------------------------------------------------------
TELA = {
    "vedica": {
        "ground": "#2b1a29", "ground-2": "#3a2438", "ground-3": "#482d45",
        "ink": "#ece2d8", "muted": "#cbb4aa", "faint": "#a89089",
        "saffron": "#e7a24a", "blush": "#e2a89d", "sage": "#93a37e",
        "on-accent": "#2a1608", "accent-hover": "#efb161", "erro": "#f6a9a0",
        "card-a": "#301d2d", "card-b": "#3f2740", "bar-base": "#f4e9dc",
        "card-marca": '"पद्मिनी"', "glow-alfa": .10,
    },
    "ocidental": {
        "ground": "#121a2b",    # azul-tinta profundo (tinta de impressão, não céu de aplicativo)
        "ground-2": "#19223a",  # superfície
        "ground-3": "#212c45",  # superfície elevada / campos
        "ink": "#e6dac3",       # papel creme quente
        "muted": "#c6b99e",
        "faint": "#a59a82",
        "saffron": "#d4a23a",   # ouro velho (fosco, sem brilho): botão e destaque
        "blush": "#e2744f",     # zarcão queimado: segundo acento
        "sage": "#9aab84",      # sálvia de apoio
        "on-accent": "#17120a", # texto sobre o botão ouro
        "accent-hover": "#e0b456",
        "erro": "#f2a493",
        "card-a": "#19223a", "card-b": "#212c45",  # o card do casal: mesma tinta, sem roxo
        "bar-base": "#e6dac3",
        "card-marca": "none",   # nada de devanágari na ocidental
        "glow-alfa": 0,         # sem brilho: fundo chapado, como papel impresso
    },
}

# Transparências derivadas (bordas, realces). Mesma lógica nas duas versões.
_ALFA = {"line": .18, "line-2": .10, "line-forte": .26}
_ALFA_ACENTO = {"accent-soft": .14, "accent-hl": .16, "accent-borda": .32, "card-marca-cor": .09}

# ---------------------------------------------------------------------------
# Fontes (CSS). A ocidental troca Cormorant Garamond + Inter por:
#   - Young Serif (títulos): serifa de impressão antiga, de tipo "inchado" de
#     tinta, que aguenta tamanho pequeno no fundo escuro (o nome das cartas sai a
#     15px). IM Fell English é mais "almanaque", mas imita o defeito da impressão
#     e fica borrada em tela e em tamanho pequeno; Newsreader é boa, mas neutra
#     demais para marcar a mudança. Young Serif só tem o peso 400 e não tem
#     itálico: a ênfase vira a segunda tinta (zarcão), como na impressão a duas
#     cores, e `font-synthesis: none` impede negrito/itálico falsos.
#   - Source Sans 3 (corpo): sans humanista, de leitura longa, com acentos do
#     português completos. Figtree é mais geométrica.
# ---------------------------------------------------------------------------
FONTES = {
    "vedica": {"serif": "'Cormorant Garamond', Georgia, 'Times New Roman', serif",
               "sans": "'Inter', system-ui, -apple-system, sans-serif",
               "google": "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500"
                         "&family=Inter:wght@400;500;600&display=swap"},
    "ocidental": {"serif": "'Young Serif', Georgia, 'Times New Roman', serif",
                  "sans": "'Source Sans 3', 'Segoe UI', system-ui, -apple-system, sans-serif",
                  "google": "https://fonts.googleapis.com/css2?family=Young+Serif"
                            "&family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&display=swap"},
}

# ---------------------------------------------------------------------------
# E-mail (HTML de e-mail: cor fixa, sem CSS externo nem fonte baixada).
# ---------------------------------------------------------------------------
EMAIL = {
    "vedica": {"fundo": "#241522", "texto": "#f4e9dc", "acento": "#e7a24a", "sobre_acento": "#2a1608",
               "suave": "#c9b1a6", "fraco": "#8f7a76", "linha": "#4a3346", "acento2": "#e2a89d",
               "fonte": "Arial,Helvetica,sans-serif", "fonte_marca": "Georgia,serif", "raio_botao": "999px"},
    "ocidental": {"fundo": "#121a2b", "texto": "#e6dac3", "acento": "#d4a23a", "sobre_acento": "#17120a",
                  "suave": "#c6b99e", "fraco": "#a59a82", "linha": "#2c3957", "acento2": "#e2744f",
                  "fonte": "'Source Sans 3','Segoe UI',Arial,Helvetica,sans-serif",
                  "fonte_marca": "'Young Serif',Georgia,serif", "raio_botao": "6px"},
}

# ---------------------------------------------------------------------------
# Papel (PDF: fundo claro, impresso). A ocidental usa as mesmas tintas do
# almanaque, escurecidas para ler bem no papel.
# ---------------------------------------------------------------------------
PAPEL = {
    "vedica": {"tinta": "#1f1a2e", "tinta_suave": "#5b5470", "noite": "#2a2350", "acento": "#c2410c",
               "acento_suave": "#fbe7d6", "superficie": "#f3ece0", "fundo": "#faf6ef", "linha": "#e4dccd",
               "lotus": "#e08a3c", "harmonico": "#2f7d6d",
               "fonte_titulo": ("Cormorant", "Cormorant-Medium.ttf"),
               "fonte_titulo_forte": ("Cormorant-SemiBold", "Cormorant-SemiBold.ttf"),
               "fonte_titulo_italico": ("Cormorant-Italic", "Cormorant-Italic.ttf"),
               "fonte_corpo": ("Inter", "Inter-Regular.ttf"),
               "fonte_corpo_forte": ("Inter-SemiBold", "Inter-SemiBold.ttf")},
    "ocidental": {"tinta": "#121a2b", "tinta_suave": "#4a5468", "noite": "#121a2b", "acento": "#a8401f",
                  "acento_suave": "#f4e2d6", "superficie": "#efe7d4", "fundo": "#faf6ec", "linha": "#ddd2bb",
                  "lotus": "#9a7314", "harmonico": "#4f6b45",
                  "fonte_titulo": ("YoungSerif", "YoungSerif-Regular.ttf"),
                  "fonte_titulo_forte": ("YoungSerif", "YoungSerif-Regular.ttf"),
                  "fonte_titulo_italico": ("YoungSerif", "YoungSerif-Regular.ttf"),
                  "fonte_corpo": ("SourceSans3", "SourceSans3-Regular.ttf"),
                  "fonte_corpo_forte": ("SourceSans3-SemiBold", "SourceSans3-SemiBold.ttf")},
}

# Cores e fontes que eram da marca védica e não podem aparecer na ocidental
# (o teste procura por elas nas páginas, e-mails, PDFs e imagens).
ANTIGAS = ["#e7a24a", "#e2a89d", "#2b1a29", "#241522", "#3a2438", "#482d45", "#efb161", "#e08a3c",
           "rgba(231,162,74", "231,162,74", "Cormorant", "family=Inter", "'Inter'", "पद्मिनी"]


def _rgb(hexa: str) -> tuple[int, int, int]:
    h = hexa.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgba(hexa: str, alfa: float) -> str:
    r, g, b = _rgb(hexa)
    return f"rgba({r},{g},{b},{alfa:g})"


def tela(sistema: str) -> dict:
    """Todos os tokens CSS da versão (com as transparências derivadas)."""
    t = dict(TELA[sistema])
    for k, a in _ALFA.items():
        t[k] = rgba(t["ink"], a)
    for k, a in _ALFA_ACENTO.items():
        t[k] = rgba(t["saffron"], a)
    t["bar-trilha"] = rgba(t.pop("bar-base"), .14)
    t["glow"] = rgba(t["saffron"], t.pop("glow-alfa"))
    t["focus"] = t["saffron"]
    t["serif"], t["sans"] = FONTES[sistema]["serif"], FONTES[sistema]["sans"]
    return t


def email(sistema: str) -> dict:
    return EMAIL[sistema]


def papel(sistema: str) -> dict:
    return PAPEL[sistema]


def luminancia(hexa: str) -> float:
    def canal(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(hexa)
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def contraste(a: str, b: str) -> float:
    """Razão de contraste WCAG entre duas cores (1 a 21)."""
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


NOMES = {"ground": ("Tinta (fundo)", "fundo da página"), "ground-2": ("Tinta clara", "cards e superfícies"),
         "ground-3": ("Tinta elevada", "campos e superfície elevada"), "ink": ("Papel", "texto principal"),
         "muted": ("Papel envelhecido", "texto secundário"), "faint": ("Papel apagado", "notas e placeholder"),
         "saffron": ("Ouro velho", "botão, destaque, traço da marca"), "blush": ("Zarcão", "segundo acento, ênfase"),
         "sage": ("Sálvia", "apoio (ok/positivo)"), "on-accent": ("Tinta do botão", "texto sobre o ouro"),
         "erro": ("Erro", "mensagens de erro")}


def contrastes(sistema: str = "ocidental") -> list[dict]:
    """Cada cor de texto contra cada fundo, com a regra do base.css: corpo entre
    10:1 e 13:1; o resto (e o texto do botão) nada abaixo de 4,5:1."""
    t = tela(sistema)
    fundos = ("ground", "ground-2", "ground-3")
    linhas = []
    for cor in ("ink", "muted", "faint", "saffron", "blush", "sage", "erro"):
        for f in fundos:
            r = contraste(t[cor], t[f])
            corpo = cor == "ink"
            linhas.append({"texto": NOMES[cor][0], "fundo": NOMES[f][0], "razao": r,
                           "regra": "corpo: 10 a 13" if corpo else "≥ 4,5",
                           "passa": 10 <= r <= 13 if corpo else r >= 4.5})
    r = contraste(t["on-accent"], t["saffron"])
    linhas.append({"texto": NOMES["on-accent"][0], "fundo": NOMES["saffron"][0], "razao": r, "regra": "≥ 4,5",
                   "passa": r >= 4.5})
    return linhas

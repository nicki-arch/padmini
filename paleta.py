"""
Padmini — cores e fontes de cada versão do site. FONTE ÚNICA, também para o que
não é CSS: e-mails (entrega.py, marketing.py), PDFs (gerar_pdf.py,
gerar_pdf_ocidental.py), imagens de compartilhamento
(scripts/gerar_og_ocidental.py), cartas do tarot e /live.

  - "vedica": os valores de sempre ("Lótus à meia-luz": ameixa, açafrão). O CSS
    dela continua sendo o static/base.css; aqui estão os mesmos números, para o
    e-mail e o PDF.
  - "ocidental": marca "Valderez Astrologia" (29/set/2026; pacote de design em
    docs/design/valderez-1.0/). Tema claro para leitura e formulários e blocos
    escuros (cabeçalho, rodapé, abertura) marcados com `data-theme`, sem seguir o
    tema do sistema. Os tokens são os de docs/design/valderez-1.0/tokens/tokens.json
    (`VALDEREZ` abaixo; há teste que confere). O CSS dela é o
    static/ocidental/tema.css, GERADO daqui (python scripts/gerar_tema_css.py;
    há teste que confere que o arquivo está em dia). A rodada 3 ("Almanaque")
    ficou no histórico do git.

Contrastes (WCAG): a védica segue a regra do base.css (texto de corpo entre 10:1 e
13:1, nada legível abaixo de 4,5:1); a ocidental só usa os pares aprovados no
tokens.json do pacote (`PARES_APROVADOS`), todos AA. Calculados por `contraste()`
abaixo e mostrados em /estilo.
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
    # Ocidental: as páginas ainda no base.css (as que as fases B e C da rodada
    # visual vão vestir de novo) usam os nomes antigos. Eles apontam para o tema
    # ESCURO da Valderez (VALDEREZ["dark"], abaixo): mesma estrutura de antes
    # (fundo escuro, texto claro, um acento), só com as cores e os pares aprovados.
    "ocidental": {
        "ground": "#091321",    # dark.background
        "ground-2": "#122034",  # dark.surface
        "ground-3": "#122034",  # dark.surface (o pacote tem dois níveis; campos têm borda)
        "ink": "#F8F3EF",       # dark.text
        "muted": "#C8CCD8",     # dark.textSecondary
        "faint": "#A8B1C4",     # dark.textMuted
        "saffron": "#D9B9D0",   # dark.accent: botão e destaque
        "blush": "#DCB1CF",     # dark.rose: segundo acento
        "sage": "#9CD8B4",      # dark.success
        "on-accent": "#142234", # dark.onAccent
        "accent-hover": "#EAD3E3",
        "erro": "#FFADB9",
        "card-a": "#122034", "card-b": "#091321",
        "bar-base": "#F8F3EF",
        "card-marca": "none",   # nada de devanágari na ocidental
        "glow-alfa": 0,
    },
}

# Transparências derivadas (bordas, realces). Mesma lógica nas duas versões.
_ALFA = {"line": .18, "line-2": .10, "line-forte": .26}
_ALFA_ACENTO = {"accent-soft": .14, "accent-hl": .16, "accent-borda": .32, "card-marca-cor": .09}

# ---------------------------------------------------------------------------
# Fontes (CSS). A ocidental (Valderez) usa Cormorant Garamond (títulos e marca,
# pesos 500 e 600) e Inter (texto, formulário, navegação, pesos 400 e 600) —
# as mesmas famílias da védica, mas servidas pelo próprio site em WOFF2
# (static/valderez/fontes/, com as licenças OFL), sem Google Fonts. São os
# mesmos arquivos de fontes/ (o PDF usa os TTF de lá).
# ---------------------------------------------------------------------------
FONTES = {
    "vedica": {"serif": "'Cormorant Garamond', Georgia, 'Times New Roman', serif",
               "sans": "'Inter', system-ui, -apple-system, sans-serif",
               "google": "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500"
                         "&family=Inter:wght@400;500;600&display=swap"},
    "ocidental": {"serif": "'Cormorant Garamond', Georgia, serif",
                  "sans": "Inter, Arial, sans-serif",
                  # (família, peso, arquivo em static/valderez/fontes/)
                  "arquivos": [("Inter", 400, "Inter-Regular.woff2"), ("Inter", 600, "Inter-SemiBold.woff2"),
                               ("Cormorant Garamond", 500, "Cormorant-Medium.woff2"),
                               ("Cormorant Garamond", 600, "Cormorant-SemiBold.woff2")]},
}

# ---------------------------------------------------------------------------
# Valderez Astrologia (ocidental): os tokens do pacote de design, com os nomes do
# tokens.json. "light" é o tema da página; "dark" vale dentro de blocos com
# data-theme="dark" (cabeçalho, rodapé, abertura). Não combinar tokens à toa:
# só os pares de PARES_APROVADOS (texto ≥ 4,5:1; contorno e foco ≥ 3:1).
# ---------------------------------------------------------------------------
VALDEREZ = {
    "light": {"background": "#F7F3F0", "surface": "#FFFFFF", "text": "#142234", "textSecondary": "#495365",
              "textMuted": "#656474", "accent": "#715078", "accentHover": "#593C61", "onAccent": "#FFFFFF",
              "border": "#827587", "error": "#A12D46", "success": "#216342", "focus": "#715078",
              "rose": "#80506F", "gold": "#796039"},
    "dark": {"background": "#091321", "surface": "#122034", "text": "#F8F3EF", "textSecondary": "#C8CCD8",
             "textMuted": "#A8B1C4", "accent": "#D9B9D0", "accentHover": "#EAD3E3", "onAccent": "#142234",
             "border": "#8692A9", "error": "#FFADB9", "success": "#9CD8B4", "focus": "#E2BCD9",
             "rose": "#DCB1CF", "gold": "#D9BE8D"},
}

# Os pares aprovados do tokens.json: (primeiro plano, fundo, mínimo). Os mesmos
# nos dois temas.
_TEXTOS = ("text", "textSecondary", "textMuted", "accent", "error", "success", "rose", "gold")
PARES_APROVADOS = ([(c, f, 4.5) for c in _TEXTOS for f in ("background", "surface")]
                   + [("onAccent", "accent", 4.5), ("onAccent", "accentHover", 4.5)]
                   + [(c, f, 3.0) for c in ("border", "focus") for f in ("background", "surface")])

# Medidas do pacote (tokens.json): tipografia (tamanho/entrelinha em px, celular
# e a partir de 1100px), raios, sombras, espaçamento, layout.
TIPOGRAFIA = {"h1": ((42, 46), (64, 68)), "h2": ((34, 40), (44, 50)), "h3": ((28, 34), (30, 36)),
              "h4": ((24, 30), (24, 30)), "body": ((16, 28), (16, 28)), "caption": ((14, 22), (14, 22)),
              "button": ((14, 20), (14, 20))}
ESPACOS = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 48, "4xl": 64, "5xl": 96}
RAIOS = {"control": 8, "card": 16, "pill": 999}
SOMBRAS = {"card": "0 12px 32px rgba(9,19,33,.10)", "paper": "0 20px 42px rgba(9,19,33,.18)"}
LAYOUT = {"container": 1200, "article": 720, "gutter": (24, 32, 40)}  # gutter: celular, tablet, desktop


# ---------------------------------------------------------------------------
# E-mail (HTML de e-mail: cor fixa, sem CSS externo nem fonte baixada).
# ---------------------------------------------------------------------------
EMAIL = {
    "vedica": {"fundo": "#241522", "texto": "#f4e9dc", "acento": "#e7a24a", "sobre_acento": "#2a1608",
               "suave": "#c9b1a6", "fraco": "#8f7a76", "linha": "#4a3346", "acento2": "#e2a89d",
               "fonte": "Arial,Helvetica,sans-serif", "fonte_marca": "Georgia,serif", "raio_botao": "999px"},
    # Valderez (fase B da rodada visual): o tema CLARO do pacote, o de leitura.
    # Fundo "background", texto "text", botão "accent" com "onAccent"; os textos
    # de apoio são textSecondary/textMuted, todos em pares aprovados no fundo claro.
    # O e-mail não baixa fonte: onde a Cormorant/Inter não existir, cai no Georgia/Arial.
    "ocidental": {"fundo": "#F7F3F0", "texto": "#142234", "acento": "#715078", "sobre_acento": "#FFFFFF",
                  "suave": "#495365", "fraco": "#656474", "linha": "#827587", "acento2": "#80506F",
                  "fonte": "Inter,Arial,Helvetica,sans-serif",
                  "fonte_marca": "'Cormorant Garamond',Georgia,serif", "raio_botao": "999px"},
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
    # Valderez: tinta = text, acento = accent (títulos e filetes), noite = o azul
    # do tema escuro (capa); fontes = os TTF de fontes/ (os mesmos WOFF2 do site).
    "ocidental": {"tinta": "#142234", "tinta_suave": "#495365", "noite": "#091321", "acento": "#715078",
                  "acento_suave": "#F7F3F0", "superficie": "#F7F3F0", "fundo": "#FFFFFF", "linha": "#827587",
                  "lotus": "#80506F", "harmonico": "#216342",
                  # os mesmos nomes (e arquivos) que o gerar_pdf.py registra; sem itálico,
                  # como no pacote (Cormorant 500/600, Inter 400/600)
                  "fonte_titulo": ("Cormorant", "Cormorant-Medium.ttf"),
                  "fonte_titulo_forte": ("Cormorant-SemiBold", "Cormorant-SemiBold.ttf"),
                  "fonte_titulo_italico": ("Cormorant", "Cormorant-Medium.ttf"),
                  "fonte_corpo": ("Inter", "Inter-Regular.ttf"),
                  "fonte_corpo_forte": ("Inter-SemiBold", "Inter-SemiBold.ttf")},
}

# Cores que eram da marca védica e não podem aparecer na ocidental (o teste
# procura por elas nas páginas, e-mails, PDFs e imagens). As FAMÍLIAS de fonte
# saíram da lista na rodada visual da Valderez: o pacote de design usa Cormorant
# Garamond + Inter, como a védica — mas servidas pelo site, nunca pelo Google
# (o link do Google Fonts continua proibido na ocidental).
ANTIGAS = ["#e7a24a", "#e2a89d", "#2b1a29", "#241522", "#3a2438", "#482d45", "#efb161", "#e08a3c",
           "rgba(231,162,74", "231,162,74", "fonts.googleapis", "fonts.gstatic", "पद्मिनी"]


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


NOMES = {"ground": ("Fundo", "fundo da página"), "ground-2": ("Superfície", "cards e superfícies"),
         "ground-3": ("Superfície elevada", "campos e superfície elevada"), "ink": ("Texto", "texto principal"),
         "muted": ("Texto secundário", "texto secundário"), "faint": ("Texto apagado", "notas e placeholder"),
         "saffron": ("Acento", "botão, destaque"), "blush": ("Segundo acento", "ênfase"),
         "sage": ("Apoio", "apoio (ok/positivo)"), "on-accent": ("Texto do botão", "texto sobre o acento"),
         "erro": ("Erro", "mensagens de erro")}


def contrastes(sistema: str = "ocidental") -> list[dict]:
    """Os contrastes da versão.

    Ocidental (Valderez): cada par aprovado no tokens.json, nos dois temas, com o
    mínimo dele (4,5:1 texto; 3:1 contorno e foco).
    Védica: cada cor de texto contra cada fundo, com a regra do base.css (corpo
    entre 10:1 e 13:1; o resto e o texto do botão, nada abaixo de 4,5:1)."""
    if sistema == "ocidental":
        linhas = []
        for tema in ("light", "dark"):
            v = VALDEREZ[tema]
            for cor, fundo, minimo in PARES_APROVADOS:
                r = contraste(v[cor], v[fundo])
                linhas.append({"tema": tema, "texto": cor, "fundo": fundo, "cor_texto": v[cor], "cor_fundo": v[fundo],
                               "razao": r, "regra": f"≥ {minimo:g}".replace(".", ","), "passa": r >= minimo})
        return linhas
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


def valderez_css(tema: str) -> dict:
    """Os tokens de um tema da Valderez com os nomes do CSS do pacote
    (textSecondary → --text-secondary)."""
    import re
    return {re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), k): v for k, v in VALDEREZ[tema].items()}

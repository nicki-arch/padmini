"""
Valderez Astrologia (versão ocidental) — a RODA do mapa natal, desenhada no
servidor a partir do motor (mapa_ocidental.py). Rodada 9, a partir da
referência do pacote valderez-design-2.0 (referencia-codigo/roda.py).

    setores dos 12 signos (cor por elemento) com os glifos, marcas de grau,
    cúspides das casas (eixos AC/DC e MC/IC mais fortes) e os números das casas,
    AC e MC, os planetas (afastados quando ficam juntos) e os aspectos maiores
    (harmonia: trígono e sextil, tracejados; tensão: quadratura e oposição).

Um desenho só, descrito como uma lista de formas (`formas()`), com duas saídas:
`svg()` para a página da leitura completa e `desenhar_pdf()` para o PDF. Sem a
hora de nascimento não há casas nem AC/MC: a roda começa em Áries, à esquerda.
Os aspectos desenhados são os do mapa — nunca um exemplo fixo.
"""
import math
from html import escape

import mapa_ocidental as mo
import paleta

SIGNOS = list(mo.SIGNO_PT)
GLIFO_SIGNO = dict(zip(SIGNOS, "♈♉♊♋♌♍♎♏♐♑♒♓"))
GLIFO_PONTO = {"sol": "☉", "lua": "☽", "mercurio": "☿", "venus": "♀", "marte": "♂", "jupiter": "♃",
               "saturno": "♄", "urano": "♅", "netuno": "♆", "plutao": "♇", "nodo_norte": "☊"}
ELEMENTO = {"aries": "fogo", "leao": "fogo", "sagitario": "fogo", "touro": "terra", "virgem": "terra",
            "capricornio": "terra", "gemeos": "ar", "libra": "ar", "aquario": "ar", "cancer": "agua",
            "escorpiao": "agua", "peixes": "agua"}
PONTOS = ["sol", "lua", "mercurio", "venus", "marte", "jupiter", "saturno", "urano", "netuno", "plutao", "nodo_norte"]
PESSOAIS = {"sol", "lua", "mercurio", "venus", "marte"}
HARMONIA, TENSAO = ("trigono", "sextil"), ("quadratura", "oposicao")
V = paleta.VZ


def _ponto(mapa, nome):
    return mapa["pontos"].get(nome)


def formas(mapa: dict, lado: float = 300) -> list[tuple]:
    """As formas da roda, em coordenadas de tela (y para baixo), num quadrado de `lado`."""
    c = lado / 2
    r1, r2, r3 = lado * .48, lado * .40, lado * .245
    casas = mapa.get("casas")
    base = casas["ascendente"] if casas else 0.0

    def pt(lon, r):
        t = math.radians(180 + (lon - base))
        return c + r * math.cos(t), c - r * math.sin(t)

    f = []
    for i, s in enumerate(SIGNOS):
        a0, a1 = i * 30, (i + 1) * 30
        contorno = [pt(a0 + k * 2, r1) for k in range(16)] + [pt(a1 - k * 2, r2) for k in range(16)]
        f.append(("poligono", contorno, V[f"elemento-{ELEMENTO[s]}"]))
        gx, gy = pt(a0 + 15, (r1 + r2) / 2)
        f.append(("texto", gx, gy, GLIFO_SIGNO[s], "glifo", lado * .052, V["vinho"], False))
    for i in range(12):
        f.append(("linha", *pt(i * 30, r1), *pt(i * 30, r2), V["ouro-linha"], .8, False, 1))
    for g in range(0, 360, 5):
        f.append(("linha", *pt(g, r2), *pt(g, r2 - (lado * .018 if g % 10 == 0 else lado * .01)), V["ouro-linha"], .6, False, 1))
    f.append(("circulo", c, c, r1, None, V["ouro"], 1.6, 1))
    f.append(("circulo", c, c, r2, None, V["ouro"], 1, 1))
    f.append(("circulo", c, c, r3, V["miolo"], V["ouro"], .8, 1))
    if casas:
        cus = casas["cuspides"]
        for i, lon in enumerate(cus):
            eixo = i in (0, 3, 6, 9)
            f.append(("linha", *pt(lon, r2), *pt(lon, r3), V["vinho"] if eixo else V["linha-casa"], 1.4 if eixo else .7, False, 1))
            prox = cus[(i + 1) % 12]
            meio = lon + ((prox - lon) % 360) / 2
            f.append(("texto", *pt(meio, r3 + lado * .022), str(i + 1), "texto", lado * .026, V["tinta-3"], False))
        for lon, rotulo in ((casas["ascendente"], "AC"), (casas["meio_do_ceu"], "MC")):
            f.append(("texto", *pt(lon, r1 + lado * .035), rotulo, "texto", lado * .03, V["vinho"], True))
    # planetas, afastando os que ficam muito perto
    pos = sorted((mapa["pontos"][n]["longitude"], n) for n in PONTOS if n in mapa["pontos"])
    mostra = [p[0] for p in pos]
    for _ in range(30):
        for i in range(len(mostra)):
            j = (i + 1) % len(mostra)
            d = (mostra[j] - mostra[i]) % 360
            if d < 9:
                mostra[i] -= (9 - d) / 2
                mostra[j] += (9 - d) / 2
    rp = (r2 + r3) / 2 + lado * .035
    for (lon, n), lon_mostra in zip(pos, mostra):
        f.append(("linha", *pt(lon, r2), *pt(lon, r2 - lado * .03), V["vinho"], 1.2, False, 1))
        gx, gy = pt(lon_mostra, rp)
        f.append(("circulo", gx, gy, lado * .034, V["branco"], None, 0, .92))
        f.append(("texto", gx, gy, GLIFO_PONTO[n], "glifo", lado * .05, V["tinta"] if n in PESSOAIS else V["tinta-2"], False))
    # aspectos do mapa (os maiores), entre os planetas e o nodo
    for a in mapa["aspectos"]:
        if a["tipo"] not in HARMONIA + TENSAO or a["a"] not in GLIFO_PONTO or a["b"] not in GLIFO_PONTO:
            continue
        x1, y1 = pt(mapa["pontos"][a["a"]]["longitude"], r3)
        x2, y2 = pt(mapa["pontos"][a["b"]]["longitude"], r3)
        tenso = a["tipo"] in TENSAO
        f.append(("linha", x1, y1, x2, y2, V["erro"] if tenso else V["ouro"], .9, not tenso, .75))
    return f


def descricao(mapa: dict, nome: str = "") -> str:
    """O texto alternativo da roda (leitor de tela)."""
    p = mapa["pontos"]
    partes = [f"Sol em {p['sol']['signo_pt']}", f"Lua em {p['lua']['signo_pt']}"]
    if "ascendente" in p:
        partes.append(f"Ascendente em {p['ascendente']['signo_pt']}")
    return f"Roda do mapa natal{' de ' + nome if nome else ''}: " + ", ".join(partes)


def svg(mapa: dict, nome: str = "", lado: int = 300) -> str:
    fonte_glifo = "'Noto Sans Symbols','Noto Sans Symbols 2','Segoe UI Symbol','DejaVu Sans',sans-serif"
    fonte_texto = "Figtree,'Segoe UI',sans-serif"
    saida = []
    for forma in formas(mapa, lado):
        tipo = forma[0]
        if tipo == "poligono":
            _, pts, cor = forma
            d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"
            saida.append(f'<path d="{d}" fill="{cor}"/>')
        elif tipo == "linha":
            _, x1, y1, x2, y2, cor, larg, tracejada, opac = forma
            extra = (' stroke-dasharray="3 2"' if tracejada else "") + (f' opacity="{opac}"' if opac != 1 else "")
            saida.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{cor}" stroke-width="{larg}"{extra}/>')
        elif tipo == "circulo":
            _, cx, cy, r, fundo, borda, larg, opac = forma
            saida.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fundo or "none"}"'
                         + (f' stroke="{borda}" stroke-width="{larg}"' if borda else "")
                         + (f' opacity="{opac}"' if opac != 1 else "") + "/>")
        else:
            _, x, y, txt, fonte, tam, cor, negrito = forma
            familia = fonte_glifo if fonte == "glifo" else fonte_texto
            saida.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" dominant-baseline="central" '
                         f'font-family="{familia}" font-size="{tam:.1f}"{" font-weight=" + chr(34) + "700" + chr(34) if negrito else ""} '
                         f'fill="{cor}">{escape(txt)}</text>')
    return (f'<svg class="roda-svg" viewBox="-12 -12 {lado + 24} {lado + 24}" role="img" '
            f'aria-label="{escape(descricao(mapa, nome), quote=True)}">' + "".join(saida) + "</svg>")


# Glifos que não estão na Noto Sans Symbols e vêm da Symbols 2
SO_NA_SYMBOLS_2 = {"☉"}


def desenhar_pdf(canvas, mapa: dict, x: float, y: float, lado: float, fonte_glifo: str, fonte_texto: str,
                 fonte_texto_forte: str, fonte_glifo_2: str | None = None) -> None:
    """A mesma roda no reportlab: (x, y) é o canto inferior esquerdo do quadrado.
    O PDF não tem fonte de reserva por caractere: o ☉ vai com a `fonte_glifo_2`."""
    from reportlab.lib.colors import HexColor

    def p(px, py):
        return x + px, y + lado - py

    canvas.saveState()
    for forma in formas(mapa, lado):
        tipo = forma[0]
        if tipo == "poligono":
            _, pts, cor = forma
            caminho = canvas.beginPath()
            caminho.moveTo(*p(*pts[0]))
            for q in pts[1:]:
                caminho.lineTo(*p(*q))
            caminho.close()
            canvas.setFillColor(HexColor(cor))
            canvas.drawPath(caminho, fill=1, stroke=0)
        elif tipo == "linha":
            _, x1, y1, x2, y2, cor, larg, tracejada, opac = forma
            canvas.setStrokeColor(HexColor(cor))
            canvas.setStrokeAlpha(opac)
            canvas.setLineWidth(larg)
            canvas.setDash(3, 2) if tracejada else canvas.setDash()
            canvas.line(*p(x1, y1), *p(x2, y2))
            canvas.setDash()
            canvas.setStrokeAlpha(1)
        elif tipo == "circulo":
            _, cx, cy, r, fundo, borda, larg, opac = forma
            if fundo:
                canvas.setFillColor(HexColor(fundo))
                canvas.setFillAlpha(opac)
            if borda:
                canvas.setStrokeColor(HexColor(borda))
                canvas.setLineWidth(larg)
            canvas.circle(*p(cx, cy), r, stroke=1 if borda else 0, fill=1 if fundo else 0)
            canvas.setFillAlpha(1)
        else:
            _, tx, ty, txt, fonte, tam, cor, negrito = forma
            nome = fonte_glifo if fonte == "glifo" else (fonte_texto_forte if negrito else fonte_texto)
            if fonte == "glifo" and txt in SO_NA_SYMBOLS_2 and fonte_glifo_2:
                nome = fonte_glifo_2
            canvas.setFillColor(HexColor(cor))
            canvas.setFont(nome, tam)
            px, py = p(tx, ty)
            canvas.drawCentredString(px, py - tam * .35, txt)
    canvas.restoreState()

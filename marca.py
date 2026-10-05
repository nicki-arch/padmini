"""
Valderez Astrologia (versão ocidental) — o símbolo da marca.

A rosa dos ventos celeste do pacote de design (docs/design/valderez-1.0/marca/
simbolo-claro.svg): um círculo, oito raios e a estrela de quatro pontas no
centro. Só formas geométricas, sem texto (o nome "Valderez / Astrologia" vai em
HTML, com a fonte do site). Um desenho só, definido aqui, que vira:
  - SVG para as páginas (`svg()`), com a cor do texto em volta (currentColor);
  - o favicon (`favicon_uri()`), no quadrado escuro do pacote;
  - traço de reportlab para o PDF (`desenhar_pdf()`).
A védica continua com o lótus de sempre (preenchido, dois tons, no base.css).
"""
from pathlib import Path
from urllib.parse import quote

import paleta

# ---------------------------------------------------------------------------
# Rodada 9 (5/out/2026): o símbolo da marca passa a ser a RODA com os 12 signos
# (pacote valderez-design-2.0, marca/valderez-roda-glifos*.svg), em todos os
# tamanhos. Os arquivos servidos ficam em static/valderez/: roda.svg (ouro e
# vinho, para fundo claro), roda-claro.svg (para o rodapé escuro) e favicon.svg;
# favicon-32/192/512.png e a og:image saem dela (scripts/gerar_marca.py).
# A estrela de oito raios abaixo continua só onde a fase C ainda vai trocar
# (cartas do tarot, card do casal, PDF).
# ---------------------------------------------------------------------------
PASTA = Path(__file__).parent / "static" / "valderez"
RODA = PASTA / "roda.svg"
RODA_CLARA = PASTA / "roda-claro.svg"
FAVICON = PASTA / "favicon.svg"


def roda_svg(clara: bool = False) -> str:
    """O SVG da roda (o arquivo servido), para quem precisa do desenho inline."""
    return (RODA_CLARA if clara else RODA).read_text(encoding="utf-8")


def roda(tamanho: int = 48, clara: bool = False, classe: str = "", rotulo: str = "") -> str:
    """<img> da roda (o arquivo é baixado uma vez e fica no cache do navegador)."""
    arquivo = "roda-claro.svg" if clara else "roda.svg"
    cls = f' class="{classe}"' if classe else ""
    escondido = "" if rotulo else ' aria-hidden="true"'
    return (f'<img{cls} src="/static/valderez/{arquivo}" width="{tamanho}" height="{tamanho}" '
            f'alt="{rotulo}"{escondido}>')

# Grade de 64×64 (y para baixo, como no SVG).
CIRCULO = (32, 32, 24)       # cx, cy, r — traço com opacidade .65
OPACIDADE_CIRCULO = .65
RAIOS = [((32, 5), (32, 59)), ((5, 32), (59, 32)), ((13, 13), (51, 51)), ((13, 51), (51, 13))]
# estrela de quatro pontas, preenchida
ESTRELA = [(32, 16), (36, 28), (48, 32), (36, 36), (32, 48), (28, 36), (16, 32), (28, 28)]
TRACO = 1.7


def raios_d() -> str:
    return "".join(f"M{a[0]} {a[1]}L{b[0]} {b[1]}" for a, b in RAIOS)


def estrela_d() -> str:
    return "M" + "L".join(f"{x} {y}" for x, y in ESTRELA) + "Z"


def _desenho(cor: str, estrela: str, traco: float) -> str:
    cx, cy, r = CIRCULO
    return (f'<g fill="none" stroke="{cor}" stroke-width="{traco:g}" stroke-linecap="round" stroke-linejoin="round">'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" opacity=".65"/><path d="{raios_d()}"/></g>'
            f'<path d="{estrela_d()}" fill="{estrela}"/>')


def svg(tamanho: int = 44, cor: str = "currentColor", astro: str = "currentColor", traco: float = TRACO,
        rotulo: str = "", classe: str = "") -> str:
    """O símbolo em SVG para as páginas. Por padrão herda a cor do texto em
    volta (currentColor): o CSS decide (no cabeçalho, var(--rose))."""
    aria = f'role="img" aria-label="{rotulo}"' if rotulo else 'aria-hidden="true" focusable="false"'
    cls = f' class="{classe}"' if classe else ""
    return (f'<svg{cls} xmlns="http://www.w3.org/2000/svg" width="{tamanho}" height="{tamanho}" viewBox="0 0 64 64" '
            f'{aria}>{_desenho(cor, astro, traco)}</svg>')


def svg_arquivo(cor: str, fundo: str | None = None) -> str:
    """O símbolo como arquivo .svg (cores fixas), para static/valderez/."""
    t = paleta.VALDEREZ["dark"]
    if fundo:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
                f'<rect width="64" height="64" rx="14" fill="{fundo}"/><g transform="translate(5 5) scale(.84)">'
                f'{_desenho(cor, cor, TRACO)}</g></svg>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64" role="img" '
            f'aria-label="Símbolo Valderez Astrologia">{_desenho(cor or t["rose"], cor or t["rose"], TRACO)}</svg>')


def favicon_svg() -> str:
    """O favicon (rodada 9): a roda, do pacote valderez-design-2.0 (marca/favicon.svg)."""
    return FAVICON.read_text(encoding="utf-8")


def favicon_uri(sistema: str = "ocidental") -> str:
    """data: URI do favicon (o mesmo desenho de static/valderez/favicon.svg)."""
    return "data:image/svg+xml," + quote(favicon_svg(), safe=" :/=,'")


def desenhar_pdf(canvas, x: float, y: float, tamanho: float, cor, astro=None, traco: float = TRACO) -> None:
    """O mesmo desenho no reportlab (x, y = canto inferior esquerdo)."""
    s = tamanho / 64
    canvas.saveState()
    canvas.translate(x, y + tamanho)
    canvas.scale(s, -s)
    canvas.setStrokeColor(cor)
    canvas.setLineWidth(traco)
    canvas.setLineCap(1)
    canvas.setLineJoin(1)
    cx, cy, r = CIRCULO
    canvas.saveState()
    canvas.setStrokeAlpha(OPACIDADE_CIRCULO)
    canvas.circle(cx, cy, r, stroke=1, fill=0)
    canvas.restoreState()
    for a, b in RAIOS:
        canvas.line(a[0], a[1], b[0], b[1])
    p = canvas.beginPath()
    p.moveTo(*ESTRELA[0])
    for pt in ESTRELA[1:]:
        p.lineTo(*pt)
    p.close()
    canvas.setFillColor(astro or cor)
    canvas.drawPath(p, fill=1, stroke=0)
    canvas.restoreState()


def _meia(v: float) -> str:
    return f"{v / 2:g}"


def tracos_d() -> str:
    """O contorno (círculo + raios) como um `d` só, na grade de 32×32 — para quem
    desenha o próprio SVG ou canvas (cartas do tarot, card do casal)."""
    cx, cy, r = (_meia(v) for v in CIRCULO)
    circ = f"M{float(cx) - float(r):g} {cy}a{r} {r} 0 1 0 {2 * float(r):g} 0a{r} {r} 0 1 0 {-2 * float(r):g} 0"
    return circ + "".join(f"M{_meia(a[0])} {_meia(a[1])}L{_meia(b[0])} {_meia(b[1])}" for a, b in RAIOS)


def astro_d() -> str:
    """A estrela de quatro pontas (preenchida), na grade de 32×32."""
    return "M" + "L".join(f"{_meia(x)} {_meia(y)}" for x, y in ESTRELA) + "Z"

"""
Padmini (versão ocidental) — a marca: a flor de lótus em traço de gravura.

Padmini quer dizer "a do lótus", e o lótus não é só da Índia: fica. Na versão
ocidental ele é redesenhado como gravura de almanaque — linha única, sem
preenchimento chapado de dois tons — com um pequeno astro de quatro pontas no
centro. Um desenho só, definido aqui como lista de comandos, que vira:
  - SVG para as páginas (`svg()`), para o favicon (`favicon_uri()`, traço mais
    grosso para funcionar a 16px) e para as imagens de compartilhamento;
  - traço de reportlab para o PDF (`desenhar_pdf()`).
A versão védica continua com o lótus de sempre (preenchido, dois tons).
"""
from urllib.parse import quote

import paleta

# Grade de 32×32 (y para baixo, como no SVG). ("M", x, y) / ("C", x1, y1, x2, y2, x, y) / ("L", x, y)
PETALA_CENTRAL = [("M", 16, 4.5), ("C", 19.8, 8.6, 20.6, 14.2, 16, 20.5), ("C", 11.4, 14.2, 12.2, 8.6, 16, 4.5)]
PETALA_ESQ = [("M", 14.6, 21.2), ("C", 10.4, 22.4, 5.6, 20.2, 3.6, 13.4), ("C", 8.4, 13.2, 12.2, 15.8, 14.6, 21.2)]
PETALA_DIR = [("M", 17.4, 21.2), ("C", 21.6, 22.4, 26.4, 20.2, 28.4, 13.4), ("C", 23.6, 13.2, 19.8, 15.8, 17.4, 21.2)]
BASE = [("M", 7, 25.5), ("L", 25, 25.5)]
TRACOS = [PETALA_CENTRAL, PETALA_ESQ, PETALA_DIR, BASE]
# astro de quatro pontas, no centro da pétala do meio
ASTRO = [("M", 16, 9.6), ("L", 16.85, 12.15), ("L", 19.4, 13), ("L", 16.85, 13.85), ("L", 16, 16.4),
         ("L", 15.15, 13.85), ("L", 12.6, 13), ("L", 15.15, 12.15), ("Z",)]


def _d(cmds) -> str:
    partes = []
    for c in cmds:
        partes.append(c[0] + " ".join(f"{v:g}" for v in c[1:]))
    return "".join(partes)


def svg(tamanho: int = 30, cor: str = "var(--saffron)", astro: str = "var(--blush)", traco: float = 1.6,
        rotulo: str = "", classe: str = "") -> str:
    """O lótus em SVG para as páginas. As cores vão em `style` (atributo de
    apresentação não aceita var(--...)): por padrão, as tintas do tema."""
    aria = f'role="img" aria-label="{rotulo}"' if rotulo else 'aria-hidden="true"'
    cls = f' class="{classe}"' if classe else ""
    return (f'<svg{cls} width="{tamanho}" height="{tamanho}" viewBox="0 0 32 32" {aria}>'
            f'<path d="{"".join(_d(t) for t in TRACOS)}" style="fill:none;stroke:{cor};stroke-width:{traco:g};'
            f'stroke-linecap:round;stroke-linejoin:round"/>'
            f'<path d="{_d(ASTRO)}" style="fill:{astro}"/></svg>')


def tracos_d() -> str:
    """O `d` do contorno do lótus (grade 32×32), para quem desenha o próprio SVG."""
    return "".join(_d(t) for t in TRACOS)


def astro_d() -> str:
    return _d(ASTRO)


def favicon_uri(sistema: str = "ocidental") -> str:
    """data: URI do favicon (traço grosso: a 16px o traço fino some)."""
    t = paleta.tela(sistema)
    bruto = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
             f'<rect width="32" height="32" rx="6" fill="{t["ground"]}"/>'
             f'<path d="{"".join(_d(x) for x in TRACOS)}" fill="none" stroke="{t["saffron"]}" stroke-width="2.4" '
             f'stroke-linecap="round" stroke-linejoin="round"/><path d="{_d(ASTRO)}" fill="{t["blush"]}"/></svg>')
    return "data:image/svg+xml," + quote(bruto, safe=" :/=,'")


def desenhar_pdf(canvas, x: float, y: float, tamanho: float, cor, astro=None, traco: float = 1.6) -> None:
    """O mesmo desenho no reportlab (x, y = canto inferior esquerdo)."""
    s = tamanho / 32
    canvas.saveState()
    canvas.translate(x, y + tamanho)
    canvas.scale(s, -s)
    canvas.setStrokeColor(cor)
    canvas.setLineWidth(traco)
    canvas.setLineCap(1)
    canvas.setLineJoin(1)
    for cmds in TRACOS + [ASTRO]:
        p = canvas.beginPath()
        for c in cmds:
            if c[0] == "M":
                p.moveTo(*c[1:])
            elif c[0] == "L":
                p.lineTo(*c[1:])
            elif c[0] == "C":
                p.curveTo(*c[1:])
            else:
                p.close()
        if cmds is ASTRO:
            canvas.setFillColor(astro or cor)
            canvas.drawPath(p, fill=1, stroke=0)
        else:
            canvas.drawPath(p, fill=0, stroke=1)
    canvas.restoreState()

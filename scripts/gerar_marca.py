"""
Gera, a partir da roda da marca (static/valderez/roda.svg e favicon.svg), as
imagens que não podem ser SVG (rodada 9):

    python scripts/gerar_marca.py

  - static/valderez/favicon-32.png, favicon-192.png, favicon-512.png;
  - static/og-oc-home.png (1200×630): a imagem de compartilhamento da home, da
    lista e das páginas sem imagem própria — a roda, o nome e a frase, no creme.

Desenha com o Chromium do Playwright (o mesmo dos prints), com as fontes do
próprio site. Rodar de novo quando a roda ou o nome mudarem.
"""
import base64
import glob
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
VALDEREZ = RAIZ / "static" / "valderez"


def _b64(arq: Path) -> str:
    return base64.b64encode(arq.read_bytes()).decode()


def _html_og() -> str:
    fr, fg = _b64(VALDEREZ / "fontes" / "Fraunces.woff2"), _b64(VALDEREZ / "fontes" / "Figtree.woff2")
    roda = _b64(VALDEREZ / "roda.svg")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:F;src:url(data:font/woff2;base64,{fr}) format('woff2');font-weight:400 600}}
@font-face{{font-family:G;src:url(data:font/woff2;base64,{fg}) format('woff2');font-weight:400 700}}
html,body{{margin:0;width:1200px;height:630px;background:#FBF6F1}}
body{{display:flex;align-items:center;gap:64px;padding:0 96px;box-sizing:border-box;
background:radial-gradient(circle at 18% 50%,#F8E6DE 0,#FBF6F1 60%)}}
img{{width:360px;height:360px;flex:none}}
b{{display:block;font:500 92px/1 F;color:#2B2230}}
i{{display:block;font:600 18px/1.6 G;font-style:normal;letter-spacing:.32em;text-transform:uppercase;color:#7E5A1E;margin:6px 0 28px}}
p{{margin:0;font:italic 400 34px/1.3 F;color:#8C3F55;max-width:560px}}
</style></head><body><img src="data:image/svg+xml;base64,{roda}"><div><b>Valderez</b><i>Astrologia</i>
<p>O céu de quando você nasceu, lido com cuidado.</p></div></body></html>"""


def main() -> int:
    from playwright.sync_api import sync_playwright
    exe = (glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome") or [None])[0]
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        favicon = (VALDEREZ / "favicon.svg").read_text(encoding="utf-8")
        for lado in (32, 192, 512):
            pg = b.new_page(viewport={"width": lado, "height": lado})
            svg = favicon.replace("<svg ", f'<svg width="{lado}" height="{lado}" ', 1)
            pg.set_content(f'<html><body style="margin:0;background:transparent">{svg}</body></html>')
            pg.screenshot(path=str(VALDEREZ / f"favicon-{lado}.png"), omit_background=True)
            pg.close()
        pg = b.new_page(viewport={"width": 1200, "height": 630})
        pg.set_content(_html_og())
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(RAIZ / "static" / "og-oc-home.png"))
        b.close()
    print("favicon-32/192/512.png e og-oc-home.png gerados")
    return 0


if __name__ == "__main__":
    sys.exit(main())

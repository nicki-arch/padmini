"""
Gera as imagens de compartilhamento (og:image, 1200×630) da versão ocidental:

    python scripts/gerar_og_ocidental.py

Grava static/og-oc-<página>.png. Desenho próprio (tipografia + a lótus da
marca), no mesmo estilo das imagens da védica, sem nenhuma imagem de terceiros
e sem a marca em sânscrito (que é da versão védica). Precisa do Playwright com
o Chromium; as fontes vêm do Google Fonts.

Mudou o texto de alguma? Edite IMAGENS abaixo e rode de novo.
"""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

IMAGENS = {
    "home": ("Astrologia para autoconhecimento",
             "O céu de quando você <em>nasceu</em>, lido com cuidado.",
             "Mapa natal · sinastria · numerologia · tarot · amostra grátis"),
    "mapa": ("Mapa natal",
             "Seu Sol, sua Lua e seu <em>Ascendente</em> — e o resto do céu.",
             "Astrologia ocidental (tropical) · amostra grátis"),
    "compatibilidade": ("Sinastria do casal",
                        "Onde o mapa de um toca o mapa do <em>outro</em>.",
                        "8 dimensões · Índice Padmini (método próprio) · amostra grátis"),
    "numerologia": ("Numerologia",
                    "Os <em>números</em> do seu nome e da sua data.",
                    "Numerologia pitagórica · Caminho de Vida grátis"),
    "tarot": ("Tarot",
              "Situação, Desafio e <em>Conselho</em>: tire as suas 3 cartas.",
              "Baralho de 78 cartas · as cartas são grátis"),
}

MODELO = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;1,500&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>
  html,body{margin:0;width:1200px;height:630px;overflow:hidden}
  body{background:radial-gradient(1100px 500px at 30% -10%,#3a2428,transparent),#241522;color:#f3e9e0;
       font-family:Inter,sans-serif;position:relative}
  .marca{position:absolute;left:80px;top:74px;display:flex;align-items:center;gap:16px;
         font:500 36px 'Cormorant Garamond',serif}
  .eyebrow{position:absolute;left:80px;top:178px;font-size:17px;letter-spacing:.28em;text-transform:uppercase;
           color:#e7a24a;font-weight:600}
  h1{position:absolute;left:80px;top:212px;margin:0;width:900px;font:500 76px/1.05 'Cormorant Garamond',serif}
  h1 em{color:#e2a89d}
  .rodape{position:absolute;left:80px;bottom:68px;font-size:21px;color:#cbb4aa}
  .lotus{position:absolute;right:70px;bottom:40px;opacity:.16}
</style></head><body>
<div class="marca"><svg width="34" height="34" viewBox="0 0 32 32"><path d="M16 5c3 4 4 8 0 14-4-6-3-10 0-14z" fill="#e7a24a"/><path d="M4 14c5 0 9 3 12 7-5 2-10 0-12-7zM28 14c-5 0-9 3-12 7 5 2 10 0 12-7z" fill="#e2a89d"/></svg>Padmini</div>
<div class="eyebrow">{eyebrow}</div>
<h1>{titulo}</h1>
<div class="rodape">{rodape}</div>
<svg class="lotus" width="230" height="230" viewBox="0 0 32 32"><path d="M16 5c3 4 4 8 0 14-4-6-3-10 0-14z" fill="#e7a24a"/><path d="M4 14c5 0 9 3 12 7-5 2-10 0-12-7zM28 14c-5 0-9 3-12 7 5 2 10 0 12-7z" fill="#e2a89d"/></svg>
</body></html>"""


def main() -> int:
    from playwright.sync_api import sync_playwright
    exe = "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        pagina = navegador.new_context(viewport={"width": 1200, "height": 630},
                                       ignore_https_errors=bool(os.environ.get("OG_IGNORAR_TLS"))).new_page()
        for nome, (eyebrow, titulo, rodape) in IMAGENS.items():
            html = MODELO.replace("{eyebrow}", eyebrow).replace("{titulo}", titulo).replace("{rodape}", rodape)
            pagina.set_content(html, wait_until="networkidle")
            pagina.evaluate("document.fonts.ready")
            destino = RAIZ / "static" / f"og-oc-{nome}.png"
            pagina.screenshot(path=str(destino))
            print(destino.relative_to(RAIZ))
        navegador.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

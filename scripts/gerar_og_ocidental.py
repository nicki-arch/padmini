"""
Gera as imagens de compartilhamento (og:image, 1200×630) da versão ocidental:

    python scripts/gerar_og_ocidental.py

Grava static/og-oc-<página>.png. Marca Valderez Astrologia (29/set/2026): o
desenho de docs/design/valderez-1.0/marca/compartilhamento-1200x630.svg, com as
cores do tema escuro e as fontes de paleta.py e o símbolo de marca.py.
Nenhuma imagem de terceiros, nenhum devanágari. Precisa do Playwright com o
Chromium; as fontes são os TTF de fontes/ (sem rede).

Mudou o texto de alguma? Edite IMAGENS abaixo e rode de novo.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

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

def _fontes_locais() -> str:
    """@font-face com os TTF de fontes/ embutidos (os mesmos do PDF e, em WOFF2, do
    site): a imagem não depende de rede e sai igual toda vez."""
    import base64
    faces = [("Cormorant Garamond", 500, "Cormorant-Medium.ttf"), ("Cormorant Garamond", 600, "Cormorant-SemiBold.ttf"),
             ("Inter", 400, "Inter-Regular.ttf"), ("Inter", 600, "Inter-SemiBold.ttf")]
    return "\n".join(
        f"@font-face{{font-family:'{nome}';font-weight:{peso};src:url(data:font/ttf;base64,"
        f"{base64.b64encode((RAIZ / 'fontes' / arq).read_bytes()).decode()}) format('truetype')}}"
        for nome, peso, arq in faces)


def modelo() -> str:
    """HTML da imagem, no desenho de docs/design/valderez-1.0/marca/compartilhamento-1200x630.svg:
    cores do tema escuro (paleta.VALDEREZ), fontes de paleta.py, símbolo de marca.py."""
    import marca
    import paleta
    v, f = paleta.VALDEREZ["dark"], paleta.FONTES["ocidental"]
    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>
{_fontes_locais()}
  html,body{{margin:0;width:1200px;height:630px;overflow:hidden}}
  body{{background:{v['background']};color:{v['text']};font-family:{f['sans']};position:relative}}
  .marca{{position:absolute;left:80px;top:92px;font:500 46px/1 {f['serif']};color:{v['text']}}}
  .marca small{{display:block;margin-top:18px;font:400 16px/1 {f['sans']};letter-spacing:.3em;color:{v['rose']}}}
  .eyebrow{{position:absolute;left:80px;top:222px;font:600 16px/1 {f['sans']};letter-spacing:.2em;text-transform:uppercase;color:{v['rose']}}}
  h1{{position:absolute;left:80px;top:254px;margin:0;width:640px;font:600 54px/1.08 {f['serif']};color:{v['text']}}}
  h1 em{{font-style:normal;color:{v['rose']}}}
  .desc{{position:absolute;left:80px;top:440px;width:690px;font:400 21px/1.4 {f['sans']};color:{v['textSecondary']}}}
  .filete{{position:absolute;left:80px;top:532px;width:520px;height:1px;background:{v['textMuted']}}}
  .site{{position:absolute;left:80px;top:556px;font:400 20px/1 {f['sans']};color:{v['rose']}}}
  .ceu{{position:absolute;left:790px;top:70px}}
</style></head><body>
<div class="marca">Valderez<small>ASTROLOGIA</small></div>
<div class="eyebrow">{{eyebrow}}</div>
<h1>{{titulo}}</h1>
<div class="desc">{{rodape}}</div>
<div class="filete"></div>
<div class="site">padmini.com.br</div>
<svg class="ceu" width="460" height="460" viewBox="0 0 460 460" aria-hidden="true">
  <circle cx="230" cy="230" r="230" fill="{v['surface']}"/>
  <g fill="none" stroke="{v['border']}" stroke-width="1"><circle cx="230" cy="230" r="195"/><circle cx="230" cy="230" r="150"/>
  <path d="M230 -5V465M10 230H450"/></g>
  <g transform="translate(134 134) scale(3)" style="color:{v['rose']}">{marca.svg(64, traco=1.7)}</g>
</svg>
</body></html>"""


def main() -> int:
    from playwright.sync_api import sync_playwright
    exe = "/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None
    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        pagina = navegador.new_context(viewport={"width": 1200, "height": 630},
                                       ).new_page()
        for nome, (eyebrow, titulo, rodape) in IMAGENS.items():
            html = modelo().replace("{eyebrow}", eyebrow).replace("{titulo}", titulo).replace("{rodape}", rodape)
            pagina.set_content(html, wait_until="networkidle")
            pagina.evaluate("document.fonts.ready")
            if not pagina.evaluate("document.fonts.check('600 54px \"Cormorant Garamond\"') && "
                                   "document.fonts.check('400 22px \"Inter\"')"):
                raise RuntimeError("as fontes não carregaram; a imagem sairia com a fonte errada")
            destino = RAIZ / "static" / f"og-oc-{nome}.png"
            pagina.screenshot(path=str(destino))
            print(destino.relative_to(RAIZ))
        navegador.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

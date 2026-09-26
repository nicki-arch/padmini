"""
Gera as imagens de compartilhamento (og:image, 1200×630) da versão ocidental:

    python scripts/gerar_og_ocidental.py

Grava static/og-oc-<página>.png. Identidade "Almanaque" (rodada 3): cores e
fontes de paleta.py, o lótus em traço de marca.py, filete duplo de almanaque.
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
    """@font-face com os TTF de fontes/ embutidos (os mesmos do PDF): a imagem não
    depende de rede e sai igual toda vez."""
    import base64
    faces = [("Young Serif", 400, "YoungSerif-Regular.ttf"), ("Source Sans 3", 400, "SourceSans3-Regular.ttf"),
             ("Source Sans 3", 600, "SourceSans3-SemiBold.ttf")]
    return "\n".join(
        f"@font-face{{font-family:'{nome}';font-weight:{peso};src:url(data:font/ttf;base64,"
        f"{base64.b64encode((RAIZ / 'fontes' / arq).read_bytes()).decode()}) format('truetype')}}"
        for nome, peso, arq in faces)


def modelo() -> str:
    """HTML da imagem: cores e fontes de paleta.py, o lótus de marca.py."""
    import marca
    import paleta
    t, f = paleta.tela("ocidental"), paleta.FONTES["ocidental"]
    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>
{_fontes_locais()}
  html,body{{margin:0;width:1200px;height:630px;overflow:hidden}}
  body{{background:{t['ground']};color:{t['ink']};font-family:{f['sans']};position:relative}}
  /* filete duplo de almanaque, em vez de brilho */
  .moldura{{position:absolute;inset:26px;border:2px solid {t['saffron']}}}
  .moldura::after{{content:"";position:absolute;inset:8px;border:1px solid {paleta.rgba(t['saffron'], .5)}}}
  .marca{{position:absolute;left:80px;top:74px;display:flex;align-items:center;gap:16px;
         font:400 36px {f['serif']};color:{t['saffron']}}}
  .eyebrow{{position:absolute;left:80px;top:176px;font-size:28px;letter-spacing:.2em;font-variant-caps:all-small-caps;
           color:{t['saffron']};font-weight:600}}
  h1{{position:absolute;left:80px;top:218px;margin:0;width:880px;font:400 68px/1.1 {f['serif']}}}
  h1 em{{font-style:normal;color:{t['blush']}}}
  .rodape{{position:absolute;left:80px;bottom:72px;font-size:22px;color:{t['muted']}}}
  .lotus{{position:absolute;right:80px;bottom:56px;opacity:.9}}
</style></head><body>
<div class="moldura"></div>
<div class="marca">{marca.svg(40, cor=t['saffron'], astro=t['blush'], traco=1.8)}Padmini</div>
<div class="eyebrow">{{eyebrow}}</div>
<h1>{{titulo}}</h1>
<div class="rodape">{{rodape}}</div>
{marca.svg(210, cor=t['saffron'], astro=t['blush'], traco=1.1, classe='lotus')}
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
            if not pagina.evaluate("document.fonts.check('400 68px \"Young Serif\"') && "
                                   "document.fonts.check('400 22px \"Source Sans 3\"')"):
                raise RuntimeError("as fontes não carregaram; a imagem sairia com a fonte errada")
            destino = RAIZ / "static" / f"og-oc-{nome}.png"
            pagina.screenshot(path=str(destino))
            print(destino.relative_to(RAIZ))
        navegador.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

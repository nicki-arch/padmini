"""
Gera static/ocidental/tema.css — o tema "Almanaque" da versão ocidental — a
partir de paleta.py (fonte única das cores e fontes):

    python scripts/gerar_tema_css.py

O tema é carregado DEPOIS do static/base.css nas páginas de static/ocidental/ e
só redefine tokens (cores, famílias) e uns poucos detalhes de impressão. Os
componentes continuam no base.css. Há teste que confere que o arquivo gravado
é o que este script gera (mudou a paleta? rode de novo).
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import paleta  # noqa: E402

DESTINO = RAIZ / "static" / "ocidental" / "tema.css"

# Tokens que vêm da paleta, na ordem em que aparecem no base.css.
ORDEM = ["ground", "ground-2", "ground-3", "ink", "muted", "faint", "saffron", "blush", "sage",
         "line", "line-2", "line-forte", "accent-soft", "on-accent", "focus", "accent-hover", "accent-hl",
         "accent-borda", "glow", "erro", "card-a", "card-b", "card-marca", "card-marca-cor", "bar-trilha",
         "serif", "sans"]

DETALHES = """
/* — Detalhes de impressão (almanaque) — */
/* Young Serif só tem o peso 400 e não tem itálico: nada de negrito ou itálico
   falsos. A ênfase é a segunda tinta (zarcão), como na impressão a duas cores. */
html { font-synthesis: none; }
h1, h2, h3, .marca, .fb-pergunta, .faq summary, .cardc .score { font-weight: 400; }
h1 em, .mark, .insight, .cardc .insight, .dim .dn { font-style: normal; }
h1 em { color: var(--blush); }
/* Rótulos em versaletes espaçados (SITUAÇÃO, DESAFIO…). */
.eyebrow, .cardc .who, .cardc .scorelab {
  text-transform: none; font-variant-caps: all-small-caps; letter-spacing: .16em; font-size: 14px; }
/* Filetes finos em vez de caixas com sombra. */
.cardc, .auto ul { box-shadow: none; }
.cardc { border-radius: 10px; }
.cardc::after { content: none; }
.rule { background: var(--line); }
"""


def gerar() -> str:
    t = paleta.tela("ocidental")
    linhas = [f"  --{k}: {t[k]};" for k in ORDEM]
    contrastes = "\n".join(
        f"     {k:<7} {t[k]}  {paleta.contraste(t[k], t['ground'])}:1 no fundo · "
        f"{paleta.contraste(t[k], t['ground-3'])}:1 na superfície elevada"
        for k in ("ink", "muted", "faint", "saffron", "blush", "sage"))
    return (
        "/* ==========================================================================\n"
        "   Padmini — tema \"Almanaque\" da versão OCIDENTAL.\n"
        "   GERADO por scripts/gerar_tema_css.py a partir de paleta.py: não editar à mão.\n"
        "   Carregado depois do base.css; só troca tokens e detalhes de impressão.\n"
        "   Contrastes (WCAG):\n"
        f"{contrastes}\n"
        f"     botão   {t['on-accent']} sobre {t['saffron']}  {paleta.contraste(t['on-accent'], t['saffron'])}:1\n"
        "   ========================================================================== */\n"
        ":root {\n" + "\n".join(linhas) + "\n  --radius: 10px;\n}\n" + DETALHES
    )


def main() -> int:
    DESTINO.write_text(gerar(), encoding="utf-8")
    print(DESTINO.relative_to(RAIZ))
    return 0


if __name__ == "__main__":
    sys.exit(main())

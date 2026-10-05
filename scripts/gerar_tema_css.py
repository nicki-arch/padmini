"""
Gera static/ocidental/tema.css — os tokens da versão ocidental (marca Valderez
Astrologia) — a partir de paleta.py (fonte única das cores e fontes):

    python scripts/gerar_tema_css.py

O arquivo tem três partes:
  1. @font-face das fontes servidas pelo site (static/valderez/fontes/, WOFF2);
  2. os tokens do pacote de design (docs/design/valderez-1.0/tokens/): tema
     claro em [data-theme="light"] e escuro em [data-theme="dark"], sem seguir o
     tema do sistema; mais medidas (tipografia, espaços, raios, sombras);
  3. os nomes antigos (--ground, --ink, --saffron…) no :root, apontando para o
     tema escuro da Valderez: ainda desenham a rosa das 8 dimensões
     (exemplos_ocidental.py), as cartas do tarot (_carta.html) e o card do casal
     (canvas); por isso aparecem dentro de blocos data-theme="dark".
Os tokens novos ficam só dentro de [data-theme] (a página inteira tem um).

Há teste que confere que o arquivo gravado é o que este script gera (mudou a
paleta? rode de novo).
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import paleta  # noqa: E402

DESTINO = RAIZ / "static" / "ocidental" / "tema.css"

# Tokens antigos que vêm da paleta, na ordem em que aparecem no base.css.
ORDEM = ["ground", "ground-2", "ground-3", "ink", "muted", "faint", "saffron", "blush", "sage",
         "line", "line-2", "line-forte", "accent-soft", "on-accent", "focus", "accent-hover", "accent-hl",
         "accent-borda", "glow", "erro", "card-a", "card-b", "card-marca", "card-marca-cor", "bar-trilha",
         "serif", "sans"]


def _fontes() -> str:
    return "\n".join(
        f"@font-face {{ font-family: '{familia}'; src: url('/static/valderez/fontes/{arquivo}') format('woff2'); "
        f"font-weight: {peso}; font-style: normal; font-display: swap; }}"
        for familia, peso, arquivo in paleta.FONTES["ocidental"]["arquivos"])


def _fontes_vz() -> str:
    return "\n".join(
        f"@font-face {{ font-family: '{familia}'; src: url('/static/valderez/fontes/{arquivo}') format('woff2'); "
        f"font-weight: {pesos}; font-style: {estilo}; font-display: swap; }}"
        for familia, pesos, estilo, arquivo in paleta.FONTES_VZ["arquivos"])


def _vz() -> str:
    """Tokens do visual 2.0 (rodada 9): --vz-<nome> e as fontes."""
    linhas = [f"  --vz-{k}: {v};" for k, v in paleta.VZ.items()]
    linhas += [f"  --vz-f-titulo: {paleta.FONTES_VZ['titulo']};", f"  --vz-f-texto: {paleta.FONTES_VZ['texto']};",
               f"  --vz-f-glifos: {paleta.FONTES_VZ['glifos']};"]
    return ":root {\n" + "\n".join(linhas) + "\n}\n"


def _tema(nome: str) -> str:
    esquema = "light" if nome == "light" else "dark"
    linhas = [f"  --{k}: {v};" for k, v in paleta.valderez_css(nome).items()]
    return "\n".join(linhas) + f"\n  color-scheme: {esquema};"


def _medidas() -> str:
    f = paleta.FONTES["ocidental"]
    linhas = [f"  --font-sans: {f['sans']};", f"  --font-editorial: {f['serif']};"]
    linhas += [f"  --radius-{k}: {v}px;" for k, v in paleta.RAIOS.items()]
    linhas += [f"  --shadow-{k}: {v};" for k, v in paleta.SOMBRAS.items()]
    linhas += [f"  --container: {paleta.LAYOUT['container']}px;", f"  --article: {paleta.LAYOUT['article']}px;",
               f"  --gutter: {paleta.LAYOUT['gutter'][0]}px;"]
    linhas += [f"  --space-{k}: {v}px;" for k, v in paleta.ESPACOS.items()]
    for k, (celular, _) in paleta.TIPOGRAFIA.items():
        linhas += [f"  --{k}-size: {celular[0]}px;", f"  --{k}-line: {celular[1]}px;"]
    desktop = " ".join(f"--{k}-size: {d[0]}px; --{k}-line: {d[1]}px;" for k, (c, d) in paleta.TIPOGRAFIA.items()
                       if c != d)
    return (":root {\n" + "\n".join(linhas) + "\n}\n"
            f"@media (min-width: 768px) {{ :root {{ --gutter: {paleta.LAYOUT['gutter'][1]}px; }} }}\n"
            f"@media (min-width: 1100px) {{ :root {{ --gutter: {paleta.LAYOUT['gutter'][2]}px; {desktop} }} }}\n")


def gerar() -> str:
    t = paleta.tela("ocidental")
    antigos = "\n".join(f"  --{k}: {t[k]};" for k in ORDEM)
    contrastes = "\n".join(
        f"     {c['tema']:<5} {c['texto']:<13} sobre {c['fundo']:<11} {c['razao']}:1 ({c['regra']})"
        for c in paleta.contrastes("ocidental"))
    return (
        "/* ==========================================================================\n"
        "   Valderez Astrologia — tokens da versão OCIDENTAL.\n"
        "   GERADO por scripts/gerar_tema_css.py a partir de paleta.py: não editar à mão.\n"
        "   Pacote de design: docs/design/valderez-1.0/. Pares de contraste aprovados (WCAG):\n"
        f"{contrastes}\n"
        "   ========================================================================== */\n"
        + _fontes() + "\n" + _fontes_vz() + "\n\n"
        "/* Visual 2.0 (rodada 9, pacote valderez-design-2.0). Contraste dos pares usados:\n"
        + "\n".join(f"   {c['texto']:<12} sobre {c['fundo']:<7} {c['razao']}:1 ({c['regra']})" for c in paleta.contrastes_vz())
        + " */\n" + _vz() + "\n"
        "/* Nomes antigos, para as páginas ainda no base.css (tema escuro da Valderez).\n"
        "   Vêm ANTES dos temas: --on-accent, --accent-hover e --focus existem nos dois\n"
        "   conjuntos, e na mesma especificidade o tema (depois) é que vale. */\n"
        ":root {\n" + antigos + "\n  --radius: 12px;\n}\n"
        + _medidas() + "\n"
        "/* Tema claro (página) e escuro (blocos com data-theme=\"dark\"). */\n"
        '[data-theme="light"] {\n' + _tema("light") + "\n}\n"
        '[data-theme="dark"] {\n' + _tema("dark") + "\n}\n"
    )


def main() -> int:
    DESTINO.write_text(gerar(), encoding="utf-8")
    print(DESTINO.relative_to(RAIZ))
    return 0


if __name__ == "__main__":
    sys.exit(main())

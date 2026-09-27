"""
Padmini (versão ocidental) — os EXEMPLOS da vitrine e a ROSA das oito dimensões.

Exemplos (round 5): casais de exemplo da home e da página da sinastria. Os
nascimentos são inventados, mas tudo o que aparece (índice, notas, ponto forte,
textos) sai do mesmo cálculo que o site faz para quem preenche o formulário —
nada é número escrito à mão. A página diz que são nascimentos fictícios.

Rosa: as oito dimensões da sinastria desenhadas como pétalas; o comprimento de
cada pétala é a nota (0 a 100). Um desenho só, em SVG, para a home, a página da
sinastria e o relatório completo (a API devolve o SVG pronto). As cores são as
tintas do tema (var(--…)), então a rosa segue a paleta da versão.
"""

import math
from datetime import date
from functools import lru_cache
from html import escape

import sinastria as si

# Nascimentos fictícios (nomes inventados). Escolhidos para mostrar índices e
# pontos fortes diferentes; se o motor mudar, os números mudam junto.
CASAIS = (
    {"a": {"nome": "Júlia", "data": "2000-10-17", "hora": "13:15", "lat": -23.5505, "lon": -46.6333, "cidade": "São Paulo"},
     "b": {"nome": "Marcos", "data": "1999-11-24", "hora": "16:30", "lat": -19.9167, "lon": -43.9345, "cidade": "Belo Horizonte"}},
    {"a": {"nome": "Ana", "data": "1988-02-16", "hora": "20:45", "lat": -23.5505, "lon": -46.6333, "cidade": "São Paulo"},
     "b": {"nome": "Rafael", "data": "1996-02-14", "hora": "04:00", "lat": -22.9068, "lon": -43.1729, "cidade": "Rio de Janeiro"}},
    {"a": {"nome": "Bia", "data": "1986-12-03", "hora": "16:45", "lat": -22.9068, "lon": -43.1729, "cidade": "Rio de Janeiro"},
     "b": {"nome": "Caio", "data": "1990-06-03", "hora": "11:45", "lat": -8.0476, "lon": -34.8770, "cidade": "Recife"}},
)

ROTULO_CURTO = {"atracao": "Atração", "emocoes": "Emoções", "comunicacao": "Comunicação", "afeto": "Afeto",
                "identidade": "Identidade", "crescimento": "Crescimento", "compromisso": "Compromisso",
                "dia_a_dia": "Dia a dia"}


def _mapa(p: dict) -> dict:
    import rotas_ocidental as ro
    mapa, _ = ro.calcular(ro.PedidoMapaOcidental(**{**p, "data": date.fromisoformat(p["data"])}))
    return mapa


@lru_cache(maxsize=None)
def casais() -> tuple[dict, ...]:
    """Os casais de exemplo já calculados: nomes, índice, notas, a rosa e o
    relatório completo (para a prévia da página da sinastria)."""
    import montar_texto_ocidental as mt
    saida = []
    for c in CASAIS:
        ma, mb = _mapa(c["a"]), _mapa(c["b"])
        sin = si.calcular_sinastria(ma, mb)
        rel = mt.montar_sinastria(sin, ma, mb, c["a"]["nome"], c["b"]["nome"], "completo")
        notas = {k: d["nota"] for k, d in sin["dimensoes"].items()}
        saida.append({"nomes": {"a": c["a"]["nome"], "b": c["b"]["nome"]}, "indice": sin["indice"],
                      "faixa": si.faixa(sin["indice"]), "notas": notas, "relatorio": rel,
                      "ponto_forte": rel["ponto_forte"]["titulo"], "ponto_atencao": rel["ponto_atencao"]["titulo"],
                      "rosa": rosa_svg(notas, rel["ponto_forte"]["chave"], rotulos=False),
                      "rosa_grande": rosa_svg(notas, rel["ponto_forte"]["chave"], rotulos=True)})
    return tuple(saida)


def _p(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def rosa_svg(notas: dict, destaque: str | None = None, rotulos: bool = True, classe: str = "rosa") -> str:
    """As oito dimensões em pétalas. `notas` = {chave: 0..100 ou None}; None
    (sem hora de ninguém) vira uma pétala tracejada no meio, sem preenchimento.
    `destaque` = a chave do ponto mais forte (pétala na segunda tinta)."""
    chaves = list(si.DIMENSOES)
    T = 320 if rotulos else 200
    cx = cy = T / 2
    raio = 108 if rotulos else 92
    r0 = 10
    partes = []
    # guias: 50 (neutro) e 100
    for frac, estilo in ((0.5, "stroke-dasharray:2 4"), (1.0, "")):
        partes.append(f'<circle cx="{_p(cx)}" cy="{_p(cy)}" r="{_p(r0 + (raio - r0) * frac)}" '
                      f'style="fill:none;stroke:var(--line);stroke-width:1;{estilo}"/>')
    for i, k in enumerate(chaves):
        ang = -math.pi / 2 + i * 2 * math.pi / len(chaves)
        ux, uy = math.cos(ang), math.sin(ang)
        nx, ny = -uy, ux
        # raio da guia até a borda
        partes.append(f'<line x1="{_p(cx + ux * r0)}" y1="{_p(cy + uy * r0)}" x2="{_p(cx + ux * raio)}" '
                      f'y2="{_p(cy + uy * raio)}" style="stroke:var(--line);stroke-width:.6"/>')
        nota = notas.get(k)
        vazia = nota is None
        comp = r0 + (raio - r0) * ((50 if vazia else max(nota, 4)) / 100)
        larg = min(comp * 0.3, 26)
        meio = r0 + (comp - r0) * 0.5
        tx, ty = cx + ux * comp, cy + uy * comp
        c1 = (cx + ux * meio + nx * larg, cy + uy * meio + ny * larg)
        c2 = (cx + ux * meio - nx * larg, cy + uy * meio - ny * larg)
        bx, by = cx + ux * r0 * 0.4, cy + uy * r0 * 0.4
        d = (f"M{_p(bx)} {_p(by)}Q{_p(c1[0])} {_p(c1[1])} {_p(tx)} {_p(ty)}"
             f"Q{_p(c2[0])} {_p(c2[1])} {_p(bx)} {_p(by)}Z")
        cor = "var(--blush)" if k == destaque else "var(--saffron)"
        if vazia:
            estilo = f"fill:none;stroke:var(--faint);stroke-width:1.2;stroke-dasharray:3 3"
        else:
            estilo = f"fill:{cor};fill-opacity:.28;stroke:{cor};stroke-width:1.4;stroke-linejoin:round"
        partes.append(f'<path class="petala" style="{estilo};--i:{i}" d="{d}"/>')
        if rotulos:
            lx, ly = cx + ux * (raio + 16), cy + uy * (raio + 16)
            ancora = "middle" if abs(ux) < 0.3 else ("start" if ux > 0 else "end")
            base = ly + (4 if abs(uy) < 0.3 else (12 if uy > 0 else -2))
            valor = "—" if vazia else str(nota)
            partes.append(f'<text x="{_p(lx)}" y="{_p(base)}" text-anchor="{ancora}" '
                          f'style="fill:var(--muted);font:600 11px var(--sans);letter-spacing:.06em">'
                          f'{escape(ROTULO_CURTO[k].upper())} <tspan style="fill:var(--ink)">{valor}</tspan></text>')
    partes.append(f'<circle cx="{_p(cx)}" cy="{_p(cy)}" r="3" style="fill:var(--saffron)"/>')
    rotulo = "Rosa das oito dimensões: " + ", ".join(
        f"{ROTULO_CURTO[k]} {'sem dados' if notas.get(k) is None else notas[k]}" for k in chaves)
    margem = 92 if rotulos else 0
    return (f'<svg class="{classe}" viewBox="{-margem} 0 {T + 2 * margem} {T}" role="img" '
            f'aria-label="{escape(rotulo, quote=True)}">{"".join(partes)}</svg>')

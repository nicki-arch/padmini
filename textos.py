"""
Padmini — copy das páginas, lida de `conteudo/<pagina>.yaml`.

Existe para separar o que é **texto** (o que a pessoa lê, e que muda toda vez
que se testa uma headline nova) do que é **estrutura** (o desenho dos blocos, o
CSS, os ícones). Antes, mudar uma frase da home significava abrir um HTML de
190 linhas e achar a frase no meio da marcação.

A divisão é essa e só essa:
  - palavra que aparece na tela  → `conteudo/*.yaml`
  - marcação, ícone, estilo      → `static/*.html`
  - preço e link de checkout     → `conteudo/ofertas.yaml` (o webhook também usa)

Os textos são escritos por nós, não vêm de fora, então HTML simples dentro
deles (<em>, <strong>) é permitido e sai como HTML — é assim que o título da
home tem uma palavra em itálico. Um teste garante que não entre <script>.
"""

from pathlib import Path

import yaml

PASTA = Path(__file__).parent / "conteudo"

_lidos: dict[str, dict] = {}


def da_pagina(pagina: str) -> dict:
    """`da_pagina("home")` → conteúdo de conteudo/home.yaml. Página sem arquivo
    devolve {} (as páginas de app quase não têm copy fixa)."""
    if pagina not in _lidos:
        arquivo = PASTA / f"{pagina}.yaml"
        _lidos[pagina] = (yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {}
                          if arquivo.exists() else {})
    return _lidos[pagina]

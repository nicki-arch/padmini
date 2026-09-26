"""
Padmini — copy das páginas, lida de `conteudo/<versão>/<pagina>.yaml`
(versão = `vedica` ou `ocidental`, ver sistema.py).

Existe para separar o que é **texto** (o que a pessoa lê, e que muda toda vez
que se testa uma headline nova) do que é **estrutura** (o desenho dos blocos, o
CSS, os ícones). Antes, mudar uma frase da home significava abrir um HTML de
190 linhas e achar a frase no meio da marcação.

A divisão é essa e só essa:
  - palavra que aparece na tela  → `conteudo/<versão>/*.yaml`
  - marcação, ícone, estilo      → `static/*.html`
  - preço e link de checkout     → `conteudo/<versão>/ofertas.yaml` (o webhook também usa)

Os textos são escritos por nós, não vêm de fora, então HTML simples dentro
deles (<em>, <strong>) é permitido e sai como HTML — é assim que o título da
home tem uma palavra em itálico. Um teste garante que não entre <script>.
"""

from pathlib import Path

import yaml

import sistema as _sistema

PASTA = Path(__file__).parent / "conteudo"

_lidos: dict[tuple[str, str], dict] = {}


def da_pagina(pagina: str, sistema: str | None = None) -> dict:
    """`da_pagina("home", "vedica")` → conteúdo de conteudo/vedica/home.yaml.
    Sem `sistema`, usa a versão no ar. Página sem arquivo devolve {} (as
    páginas de app quase não têm copy fixa)."""
    sistema = sistema or _sistema.ativo()
    if (sistema, pagina) not in _lidos:
        arquivo = PASTA / sistema / f"{pagina}.yaml"
        _lidos[(sistema, pagina)] = (yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {}
                                     if arquivo.exists() else {})
    return _lidos[(sistema, pagina)]

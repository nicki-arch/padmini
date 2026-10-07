"""Configuração comum dos testes."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import conteudo_privado  # noqa: E402,F401  (PADMINI_CONTEUDO_DIR: textos do repo privado, rodada 10)
import limites  # noqa: E402


@pytest.fixture(autouse=True)
def _zerar_limites():
    """Os limites por IP são em memória e todo teste vem do mesmo "IP"
    (testclient): sem zerar, a suíte inteira estouraria a cota."""
    limites.limpar_todos()
    yield
    limites.limpar_todos()


# ---------------------------------------------------------------------------
# Catálogo da ocidental (rodada 9). O YAML de produção está com a venda FECHADA
# (vendas_abertas: false) e só o mapa natal ativo. Os testes anteriores à rodada
# 9 protegem o site vendendo — que é exatamente o "com true, tudo volta como
# hoje" do brief —, então rodam com a venda aberta e os 4 produtos ativos.
# Teste que quer o catálogo de verdade marca @pytest.mark.catalogo_real.
# ---------------------------------------------------------------------------
def pytest_configure(config):
    config.addinivalue_line("markers", "catalogo_real: usa conteudo/ocidental/catalogo.yaml como está")


def _limpar_paginas():
    app = sys.modules.get("app")
    if app is not None:
        app._paginas_prontas.clear()


@pytest.fixture(autouse=True)
def _catalogo_vendendo(request):
    import copy

    import catalogo
    original = catalogo.dados()
    if request.node.get_closest_marker("catalogo_real") is None:
        aberto = copy.deepcopy(original)
        aberto["vendas_abertas"] = True
        for p in aberto["produtos"]:
            if p["chave"] in ("mapa", "compat", "numerologia", "tarot"):
                p["estado"] = "ativo"
        catalogo.usar(aberto)
    else:
        catalogo.usar(catalogo.carregar())
    _limpar_paginas()
    yield
    catalogo.usar(original)
    _limpar_paginas()

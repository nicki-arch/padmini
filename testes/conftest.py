"""Configuração comum dos testes."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import limites  # noqa: E402


@pytest.fixture(autouse=True)
def _zerar_limites():
    """Os limites por IP são em memória e todo teste vem do mesmo "IP"
    (testclient): sem zerar, a suíte inteira estouraria a cota."""
    limites.limpar_todos()
    yield
    limites.limpar_todos()

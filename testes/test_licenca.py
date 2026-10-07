"""
Rodada 10, fase 1: o repositório publica o código sob AGPL-3.0 (é assim que cumpre a
licença do Swiss Ephemeris) e diz, no README, que o conteúdo editorial não está coberto.
"""
import hashlib
from pathlib import Path

# Sem importar o app: este teste roda também em PR de fork, sem o conteúdo privado.
RAIZ = Path(__file__).resolve().parents[1]

# md5 do texto oficial da FSF (https://www.gnu.org/licenses/agpl-3.0.txt)
MD5_AGPL3 = "eb1e647870add0502f8f010b19de32af"


def test_licenca_agpl_e_o_texto_oficial():
    assert hashlib.md5((RAIZ / "LICENSE").read_bytes()).hexdigest() == MD5_AGPL3


def test_readme_separa_codigo_e_conteudo():
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    secao = readme[readme.index("## Licença"):readme.index("## Pendências")]
    for trecho in ("AGPL-3.0", "Swiss Ephemeris", "todos os direitos reservados", "Valderez Astrologia",
                   "Padmini", "aquarela-2026", "Open Font License"):
        assert trecho in secao, trecho

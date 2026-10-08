"""
Rodada 10: os textos de interpretação NÃO ficam no repositório público.

Moram no repositório privado nicki-arch/padmini-conteudo e entram só no build
(scripts/buscar_conteudo.sh). Este arquivo é a rede de segurança contra um
`git add .` que republique os textos, e confere que build e site falham fechados
sem eles. Não importa o app nem lê os textos: roda também em PR de fork.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from conteudo_privado import CAMINHOS as PRIVADOS  # noqa: E402
SCRIPT = RAIZ / "scripts" / "buscar_conteudo.sh"


def _git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True)


def versionados(caminhos=PRIVADOS) -> list[str]:
    r = _git("ls-files", "--", *caminhos)
    if r.returncode != 0:
        pytest.skip("sem git (checkout sem histórico): não há o que conferir")
    return [l for l in r.stdout.splitlines() if l.strip()]


def test_nenhum_texto_de_interpretacao_versionado():
    achados = versionados()
    assert achados == [], (
        "Estes arquivos são o conteúdo proprietário e moram no repositório PRIVADO "
        f"nicki-arch/padmini-conteudo; tire-os do repositório público (git rm --cached): {achados}")


def test_gitignore_segura_os_caminhos():
    for caminho in ("base_significacoes.py", "conteudo/ocidental/textos/planetas_signos.yaml",
                    "conteudo/ocidental/textos/LEIA.md", "conteudo/ocidental/blog/rascunho.yaml"):
        r = _git("check-ignore", "-q", "--no-index", caminho)
        if r.returncode == 128:
            pytest.skip("sem git")
        assert r.returncode == 0, f"{caminho} não está no .gitignore"


def test_a_copy_publica_das_paginas_continua_versionada():
    # o que já aparece no site fica no público (o brief da rodada 10): não ignorar demais
    for arquivo in ("conteudo/ocidental/catalogo.yaml", "conteudo/ocidental/ofertas.yaml",
                    "conteudo/ocidental/marca.yaml", "conteudo/ocidental/revisao.yaml",
                    "conteudo/ocidental/produtos.yaml", "conteudo/ocidental/mapa.yaml"):
        assert versionados([arquivo]) == [arquivo], arquivo


# ------------------------------------------------------------------ build falha fechado
def _rodar_script(tmp_path, **env):
    ambiente = {k: v for k, v in os.environ.items() if k not in ("PADMINI_CONTEUDO_TOKEN", "PADMINI_CONTEUDO_DIR")}
    ambiente.update(env)
    destino = tmp_path / "checkout"
    destino.mkdir()
    r = subprocess.run(["bash", str(SCRIPT)], cwd=destino, env=ambiente, capture_output=True, text=True)
    return r, destino


def _repo_privado_falso(pasta: Path) -> Path:
    (pasta / "conteudo" / "ocidental" / "textos").mkdir(parents=True)
    (pasta / "conteudo" / "ocidental" / "blog").mkdir(parents=True)
    (pasta / "base_significacoes.py").write_text("NOME_PT = {}\n", encoding="utf-8")
    (pasta / "conteudo" / "ocidental" / "textos" / "ascendente.yaml").write_text("a: 1\n", encoding="utf-8")
    return pasta


@pytest.mark.skipif(not shutil.which("bash"), reason="sem bash")
def test_build_sem_token_falha_com_mensagem_clara(tmp_path):
    r, _ = _rodar_script(tmp_path)
    assert r.returncode != 0
    assert "PADMINI_CONTEUDO_TOKEN" in r.stderr and "nicki-arch/padmini-conteudo" in r.stderr


@pytest.mark.skipif(not shutil.which("bash"), reason="sem bash")
def test_build_com_repo_incompleto_falha(tmp_path):
    privado = _repo_privado_falso(tmp_path / "privado")
    shutil.rmtree(privado / "conteudo" / "ocidental" / "blog")
    r, _ = _rodar_script(tmp_path, PADMINI_CONTEUDO_DIR=str(privado))
    assert r.returncode != 0 and "conteudo/ocidental/blog" in r.stderr


@pytest.mark.skipif(not shutil.which("bash"), reason="sem bash")
def test_build_copia_para_os_mesmos_caminhos(tmp_path):
    privado = _repo_privado_falso(tmp_path / "privado")
    r, destino = _rodar_script(tmp_path, PADMINI_CONTEUDO_DIR=str(privado))
    assert r.returncode == 0, r.stderr
    assert (destino / "base_significacoes.py").is_file()
    assert (destino / "conteudo" / "ocidental" / "textos" / "ascendente.yaml").is_file()
    assert (destino / "conteudo" / "ocidental" / "blog").is_dir()


def test_build_sh_nao_tem_mais_o_modo_de_transicao():
    build = (RAIZ / "build.sh").read_text(encoding="utf-8")
    assert "bash scripts/buscar_conteudo.sh" in build and "set -euo pipefail" in build
    assert "fase de transição" not in build and "elif [ -f" not in build


# ------------------------------------------------------------------ site falha fechado
def test_site_sem_os_textos_nao_sobe(tmp_path):
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    env = {**os.environ, "PADMINI_CONTEUDO_DIR": str(vazio), "PADMINI_SECRET": "x"}
    r = subprocess.run([sys.executable, "-c", "import app"], cwd=RAIZ, env=env, capture_output=True, text=True)
    assert r.returncode != 0
    assert "ConteudoAusente" in r.stderr and "base_significacoes.py" in r.stderr and "bash build.sh" in r.stderr

"""
Rodada 10.1: o espelho público nicki-arch/padmini-codigo (AGPL) com o código, sem os textos.

A trava (scripts/publicar_codigo.py), a lista de exclusão (publico-excluir.txt), o
workflow que publica e o link "Código-fonte" do rodapé (conteudo/site.yaml).
"""
import importlib.util
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("publicar_codigo", RAIZ / "scripts" / "publicar_codigo.py")
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)


def _arvore(tmp_path: Path) -> Path:
    """Uma árvore mínima que pode ser publicada."""
    raiz = tmp_path / "arvore"
    (raiz / "publico").mkdir(parents=True)
    (raiz / "publico" / "README.md").write_text("# espelho\n", encoding="utf-8")
    (raiz / "README.md").write_text("# README do privado\n", encoding="utf-8")
    (raiz / "LICENSE").write_text("GNU AFFERO GENERAL PUBLIC LICENSE\n", encoding="utf-8")
    (raiz / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (raiz / "conteudo" / "ocidental").mkdir(parents=True)
    (raiz / "conteudo" / "ocidental" / "catalogo.yaml").write_text("vendas_abertas: false\n", encoding="utf-8")
    return raiz


# ------------------------------------------------------------------ a trava
def test_arvore_limpa_passa(tmp_path):
    raiz = _arvore(tmp_path)
    assert pc.main([str(raiz)]) == 0
    assert (raiz / "README.md").read_text(encoding="utf-8") == "# espelho\n"  # o README do espelho
    assert not (raiz / "publico").exists()


@pytest.mark.parametrize("caminho", ["conteudo/ocidental/textos/planetas_signos.yaml",
                                     "conteudo/ocidental/textos/LEIA.md",
                                     "conteudo/ocidental/blog/rascunho.yaml",
                                     "base_significacoes.py"])
def test_texto_na_arvore_trava_a_publicacao(tmp_path, caminho, capsys):
    raiz = _arvore(tmp_path)
    (raiz / caminho).parent.mkdir(parents=True, exist_ok=True)
    (raiz / caminho).write_text("sol_em_aries: Um texto falso de interpretação.\n", encoding="utf-8")
    assert pc.main([str(raiz)]) == 1
    assert "conteúdo proprietário" in capsys.readouterr().err


# montados em partes para este arquivo não parecer um segredo para a própria trava
SEGREDOS_FALSOS = {
    "Stripe": "sk_" + "live_" + "a1B2c3D4e5F6g7H8",
    "Resend": "re_" + "Abc12345_" + "Xyz98765Qwe",
    "PostHog": "phc_" + "A" * 30,
    "GitHub": "ghp_" + "b" * 36,
    "GitHub fine-grained": "github_pat_" + "C" * 40,
    "Anthropic": "sk-" + "ant-" + "d" * 30,
}


@pytest.mark.parametrize("nome", list(SEGREDOS_FALSOS))
def test_segredo_com_valor_trava(tmp_path, nome):
    raiz = _arvore(tmp_path)
    (raiz / "config.py").write_text(f'CHAVE = "{SEGREDOS_FALSOS[nome]}"\n', encoding="utf-8")
    assert pc.problemas(raiz), nome


def test_arquivo_env_trava_mas_nome_de_variavel_nao(tmp_path):
    raiz = _arvore(tmp_path)
    (raiz / "app.py").write_text('import os\nCHAVE = os.environ.get("PADMINI_POSTHOG_KEY", "phc_teste")\n',
                                 encoding="utf-8")
    assert pc.problemas(raiz) == []  # nome de variável e valor de teste curto não são segredo
    (raiz / ".env").write_text("X=1\n", encoding="utf-8")
    assert any(".env" in p for p in pc.problemas(raiz))


def test_sem_licenca_nao_publica(tmp_path):
    raiz = _arvore(tmp_path)
    (raiz / "LICENSE").unlink()
    assert pc.main([str(raiz)]) == 1


def test_nunca_roda_no_proprio_checkout():
    assert pc.main([str(RAIZ)]) == 2


# ------------------------------------------------------------------ a lista de exclusão
def test_lista_tira_documentos_internos_e_dados_com_texto(tmp_path):
    raiz = _arvore(tmp_path)
    for c in ("testes/dados/vedica_html/api_mapa_completo.json", "docs/design/prints/x.jpg",
              "static/ilustracoes/aquarela-2026/dim-sol.webp", "PLANO.md", "docs/claude-project/notas.md",
              "docs/seguranca.md", "docs/melhorias-2026-09.md",
              # o que FICA
              "docs/ocidental.md", "seguranca.py", "static/ocidental/home.html", "testes/test_app.py",
              "testes/dados/referencias_ocidental.json"):
        (raiz / c).parent.mkdir(parents=True, exist_ok=True)
        (raiz / c).write_text("x", encoding="utf-8")
    saiu = pc.aplicar_exclusoes(raiz, pc.ler_lista())
    assert set(saiu) == {"testes/dados/vedica_html/api_mapa_completo.json", "docs/design/prints/x.jpg",
                         "static/ilustracoes/aquarela-2026/dim-sol.webp", "PLANO.md", "docs/claude-project/notas.md",
                         "docs/seguranca.md", "docs/melhorias-2026-09.md"}
    assert not (raiz / "docs" / "design").exists()  # pasta vazia também sai


def _versionados() -> list[str]:
    r = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("sem git")
    return r.stdout.splitlines()


def test_lista_nunca_tira_codigo_que_roda_o_site():
    """A AGPL pede o código correspondente ao que roda: nenhum .py, template, CSS ou JS do site."""
    padroes = pc.ler_lista()
    codigo = [c for c in _versionados()
              if not c.startswith(("testes/", "docs/"))
              and (c.endswith((".py", ".sh", ".txt", ".yml", ".yaml", ".toml", ".cfg"))
                   or (c.startswith("static/") and c.endswith((".html", ".css", ".js", ".svg"))))]
    assert codigo
    excluido = [c for c in codigo if any(pc._bate(c, p) for p in padroes)]
    assert excluido == [], excluido


def test_a_arvore_real_pode_ser_publicada(tmp_path):
    """A master de agora: git archive HEAD, como o workflow faz."""
    if shutil.which("git") is None:
        pytest.skip("sem git")
    tar = tmp_path / "arvore.tar"
    r = subprocess.run(["git", "archive", "-o", str(tar), "HEAD"], cwd=RAIZ, capture_output=True)
    if r.returncode != 0:
        pytest.skip("checkout sem histórico")
    raiz = tmp_path / "arvore"
    with tarfile.open(tar) as t:
        t.extractall(raiz)
    if not (raiz / "publico" / "README.md").is_file():
        pytest.skip("HEAD anterior à rodada 10.1")
    assert pc.main([str(raiz)]) == 0
    for privado in pc.CAMINHOS:
        assert not (raiz / privado).exists(), privado
    assert not (raiz / "testes" / "dados" / "vedica_html").exists()


# ------------------------------------------------------------------ workflow e README do espelho
def test_workflow_publica_sem_force_push():
    wf = (RAIZ / ".github" / "workflows" / "codigo-publico.yml").read_text(encoding="utf-8")
    assert "branches: [master]" in wf and "workflow_dispatch" in wf
    assert "git archive HEAD" in wf and "scripts/publicar_codigo.py" in wf
    assert 'sync: padmini@${GITHUB_SHA}' in wf and "git diff --cached --quiet" in wf
    assert "CODIGO_PUBLICO_TOKEN" in wf and "nicki-arch/padmini-codigo" in wf
    assert not re.search(r"push[^\n]*(--force|-f\b|\+HEAD)", wf)


def test_readme_do_espelho():
    readme = (RAIZ / "publico" / "README.md").read_text(encoding="utf-8")
    for trecho in ("padmini.com.br", "Affero General Public License", "LICENSE", "espelho",
                   "Pull requests e issues não são aceitos", "todos os direitos reservados",
                   "textos de interpretação", "ilustrações", "marcas"):
        assert trecho in readme, trecho


# ------------------------------------------------------------------ o link do rodapé
def test_link_codigo_fonte_numa_chave_so():
    import yaml
    url = yaml.safe_load((RAIZ / "conteudo" / "site.yaml").read_text(encoding="utf-8"))["codigo_fonte"]
    assert url == "https://github.com/nicki-arch/padmini-codigo"
    for f in (RAIZ / "static").rglob("*.html"):
        texto = f.read_text(encoding="utf-8")
        assert "github.com/nicki-arch/padmini\"" not in texto and "github.com/nicki-arch/padmini-codigo" not in texto, \
            f"{f.name}: o endereço vem de conteudo/site.yaml ({{{{ codigo_fonte }}}})"


@pytest.mark.parametrize("versao", ["vedica", "ocidental"])
@pytest.mark.parametrize("rota", ["/", "/mapa", "/privacidade", "/termos"])
def test_rodape_abre_o_repositorio_publico(monkeypatch, versao, rota):
    from test_app import app_mod, cliente
    monkeypatch.setenv("PADMINI_SISTEMA", versao)
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    app_mod._paginas_prontas.clear()
    html = cliente.get(rota, headers={"accept": "text/html"}).text
    app_mod._paginas_prontas.clear()
    assert re.search(r'href="https://github\.com/nicki-arch/padmini-codigo"[^>]*>Código-fonte<', html), (versao, rota)
    assert "{{" not in html

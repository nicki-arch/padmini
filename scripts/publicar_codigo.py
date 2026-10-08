"""
Monta a árvore do espelho público `nicki-arch/padmini-codigo` (rodada 10.1) e confere
que ela pode ser publicada.

    git archive HEAD | tar -x -C /tmp/arvore
    python scripts/publicar_codigo.py /tmp/arvore      # sai com 1 se não puder publicar

O site usa o Swiss Ephemeris sob a AGPL-3.0: o código que roda em padmini.com.br precisa
estar disponível para quem usa o site. O repositório `padmini` é privado (o histórico
dele ainda tem os textos até 7/out), então o código vai para um espelho público, sem
histórico antigo, atualizado pelo workflow `.github/workflows/codigo-publico.yml`.

O que este script faz na árvore (que é uma cópia; nunca mexe no checkout):
  1. tira o que está em `publico-excluir.txt` (documentos internos, dados de teste com
     texto renderizado, prints) — código que roda o site nunca entra nessa lista;
  2. troca o README.md pelo `publico/README.md` (o do espelho) e tira a pasta `publico/`;
  3. TRAVA: falha se sobrar qualquer arquivo do conteúdo proprietário
     (`conteudo_privado.CAMINHOS`: textos, blog, base_significacoes.py) ou algo que pareça
     segredo (.env, chaves sk_/re_/phc_ com valor, tokens do GitHub, chave privada).
"""
import fnmatch
import re
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from conteudo_privado import CAMINHOS  # noqa: E402

LISTA = RAIZ / "publico-excluir.txt"
README_PUBLICO = Path("publico") / "README.md"

# Formato de segredo com valor (não basta o nome da variável): o que vazaria de fato.
SEGREDOS = [
    ("chave do Stripe", re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{12,}")),
    ("chave do Resend", re.compile(r"\bre_[A-Za-z0-9]{8,}_[A-Za-z0-9]{8,}")),
    ("chave do PostHog", re.compile(r"\bphc_[A-Za-z0-9]{20,}")),
    ("chave da Anthropic", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("token do GitHub", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})")),
    ("chave privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]
ARQUIVOS_DE_SEGREDO = (".env", ".env.*", "*.pem", "*.key", "id_rsa*")
BINARIOS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".pdf",
            ".gz", ".zip", ".xlsx", ".se1"}


def ler_lista(arquivo: Path = LISTA) -> list[str]:
    """Os padrões de `publico-excluir.txt`: um por linha, `#` comenta, `/` no fim = pasta."""
    padroes = []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if linha:
            padroes.append(linha.lstrip("/"))
    return padroes


def _bate(caminho: str, padrao: str) -> bool:
    if padrao.endswith("/"):
        pasta = padrao.rstrip("/")
        return caminho == pasta or caminho.startswith(pasta + "/") or fnmatch.fnmatch(caminho.split("/")[0], pasta)
    return fnmatch.fnmatch(caminho, padrao)


def _arquivos(raiz: Path) -> list[str]:
    return sorted(p.relative_to(raiz).as_posix() for p in raiz.rglob("*") if p.is_file() or p.is_symlink())


def aplicar_exclusoes(raiz: Path, padroes: list[str]) -> list[str]:
    """Apaga da árvore o que bate com algum padrão; devolve o que saiu."""
    saiu = [c for c in _arquivos(raiz) if any(_bate(c, p) for p in padroes)]
    for c in saiu:
        (raiz / c).unlink()
    for pasta in sorted((p for p in raiz.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if not any(pasta.iterdir()):
            pasta.rmdir()
    return saiu


def trocar_readme(raiz: Path) -> bool:
    """README.md do espelho no lugar do README do repositório privado."""
    origem = raiz / README_PUBLICO
    if not origem.is_file():
        return False
    shutil.copyfile(origem, raiz / "README.md")
    shutil.rmtree(raiz / README_PUBLICO.parent)
    return True


def problemas(raiz: Path) -> list[str]:
    """Tudo o que impede a publicação (vazio = pode publicar)."""
    erros = []
    for c in _arquivos(raiz):
        for privado in CAMINHOS:
            if c == privado or c.startswith(privado + "/"):
                erros.append(f"conteúdo proprietário: {c}")
        nome = c.rsplit("/", 1)[-1]
        if any(fnmatch.fnmatch(nome, p) for p in ARQUIVOS_DE_SEGREDO) and nome != ".env.example":
            erros.append(f"arquivo de segredo: {c}")
        if Path(c).suffix.lower() in BINARIOS:
            continue
        try:
            texto = (raiz / c).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for rotulo, regex in SEGREDOS:
            if regex.search(texto):
                erros.append(f"{rotulo} em {c}")
    for obrigatorio in ("LICENSE", "README.md"):
        if not (raiz / obrigatorio).is_file():
            erros.append(f"falta {obrigatorio} (AGPL: o espelho publica a licença junto)")
    return erros


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__.strip())
        return 2
    raiz = Path(args[0]).resolve()
    if raiz == RAIZ:
        print("ERRO: passe uma CÓPIA da árvore (git archive), nunca o próprio checkout.", file=sys.stderr)
        return 2
    saiu = aplicar_exclusoes(raiz, ler_lista())
    print(f"Excluídos pela publico-excluir.txt: {len(saiu)} arquivos.")
    if not trocar_readme(raiz):
        print("ERRO: falta publico/README.md (o README do espelho).", file=sys.stderr)
        return 1
    erros = problemas(raiz)
    if erros:
        print("NÃO PUBLICAR — a árvore tem o que não pode ir para o repositório público:", file=sys.stderr)
        for e in erros:
            print("  - " + e, file=sys.stderr)
        return 1
    print(f"OK: {len(_arquivos(raiz))} arquivos prontos para o padmini-codigo (sem textos nem segredos).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

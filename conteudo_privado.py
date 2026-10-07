"""
Padmini — onde estão os textos de interpretação (rodada 10).

Os textos são o ativo vendido e NÃO ficam no repositório público (que publica o
código sob AGPL-3.0, ver LICENSE e README). Moram no repositório PRIVADO
`nicki-arch/padmini-conteudo`, nos mesmos caminhos relativos:

    base_significacoes.py            versão védica
    conteudo/ocidental/textos/       versão ocidental (YAML)
    conteudo/ocidental/blog/         blog (artigos e rascunhos)

Na Render e no CI, `scripts/buscar_conteudo.sh` (chamado pelo `build.sh`) copia esses
arquivos para o checkout, então o padrão é a raiz do projeto. Para trabalhar com um
clone do repo privado ao lado (revisão da Dona Valderez, testes locais), aponte
`PADMINI_CONTEUDO_DIR` para ele: os scripts e o site leem de lá.

Segurança falha fechada (regra 4 do CLAUDE.md): sem os textos, o site não sobe
(`exigir()`, chamado na subida do app) e diz no log o que falta.
"""
import os
import sys
from pathlib import Path

PROJETO = Path(__file__).resolve().parent
VARIAVEL = "PADMINI_CONTEUDO_DIR"
REPO = "nicki-arch/padmini-conteudo"


def raiz() -> Path:
    """A pasta que tem o conteúdo: `PADMINI_CONTEUDO_DIR` ou, sem ela, a raiz do projeto."""
    outra = os.environ.get(VARIAVEL, "").strip()
    return Path(outra).expanduser().resolve() if outra else PROJETO


def _configurar() -> None:
    global RAIZ, TEXTOS, BLOG, VEDICA
    RAIZ = raiz()
    TEXTOS = RAIZ / "conteudo" / "ocidental" / "textos"
    BLOG = RAIZ / "conteudo" / "ocidental" / "blog"
    VEDICA = RAIZ / "base_significacoes.py"
    # Com o conteúdo em outra pasta, `import base_significacoes` tem de achar o de lá
    # primeiro (antes do de uma cópia antiga que tenha sobrado no projeto).
    if RAIZ != PROJETO and str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))


_configurar()


def tirar_argumento(argv: list[str]) -> list[str]:
    """`--conteudo PASTA` nos scripts (revisão da Dona Valderez) = PADMINI_CONTEUDO_DIR.
    Chamar ANTES de importar quem lê os textos (montar_texto_ocidental, revisao, blog).
    Devolve o argv sem a opção."""
    if "--conteudo" not in argv:
        return argv
    i = argv.index("--conteudo")
    if i + 1 >= len(argv):
        sys.exit("--conteudo precisa de uma pasta: um clone do nicki-arch/padmini-conteudo")
    os.environ[VARIAVEL] = argv[i + 1]
    _configurar()
    return argv[:i] + argv[i + 2:]


def faltando() -> list[str]:
    """O que falta para o site funcionar (vazio = tudo no lugar)."""
    falta = []
    if not VEDICA.is_file():
        falta.append("base_significacoes.py")
    if not TEXTOS.is_dir() or not any(TEXTOS.glob("*.yaml")):
        falta.append("conteudo/ocidental/textos/*.yaml")
    if not BLOG.is_dir():
        falta.append("conteudo/ocidental/blog/")
    return falta


def mensagem(falta: list[str]) -> str:
    return (f"Conteúdo privado ausente em {RAIZ}: {', '.join(falta)}. Os textos de interpretação "
            f"moram no repositório privado {REPO} e entram no build (bash build.sh, que roda "
            f"scripts/buscar_conteudo.sh com PADMINI_CONTEUDO_TOKEN). Na Render, confira que o "
            f"Build Command é `bash build.sh` e que PADMINI_CONTEUDO_TOKEN está definido. "
            f"Localmente, aponte {VARIAVEL} para um clone do {REPO}.")


class ConteudoAusente(RuntimeError):
    pass


def exigir() -> None:
    """Na subida do site: sem os textos, não sobe (em vez de subir pela metade)."""
    falta = faltando()
    if falta:
        raise ConteudoAusente(mensagem(falta))

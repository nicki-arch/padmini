"""
Valderez Astrologia (versão ocidental) — ILUSTRAÇÕES TROCÁVEIS (rodada 9).

O manifesto `conteudo/ocidental/ilustracoes.yaml` diz qual conjunto está ligado
e quais vagas existem. Quem desenha a página pede a VAGA:

    {{ ilustracao("dim-sol", classe="dim-img") }}   → <img …> (ou fundo liso)
    {{ ilustracao_url("hero-home") }}               → /static/ilustracoes/…webp

Vaga que faltar no conjunto ativo cai no conjunto reserva; se nenhum tiver, sai
um bloco liso na cor papel. Pedir uma vaga que não está no manifesto é erro de
programação (levanta KeyError): o teste pega antes de ir ao ar.
"""
from html import escape
from pathlib import Path

import yaml

RAIZ = Path(__file__).parent
MANIFESTO = RAIZ / "conteudo" / "ocidental" / "ilustracoes.yaml"
PASTA = RAIZ / "static" / "ilustracoes"

_dados = yaml.safe_load(MANIFESTO.read_text(encoding="utf-8")) or {}
VAGAS: dict = _dados.get("vagas") or {}


def arquivo(vaga: str, conjunto: str) -> Path:
    return PASTA / conjunto / f"{vaga}.webp"


def caminho(vaga: str) -> Path | None:
    """O arquivo que vale para a vaga (ativo → reserva), ou None."""
    if vaga not in VAGAS:
        raise KeyError(f"vaga {vaga!r} não existe em {MANIFESTO.name}")
    for conjunto in (_dados.get("conjunto_ativo"), _dados.get("conjunto_reserva")):
        if conjunto and arquivo(vaga, conjunto).exists():
            return arquivo(vaga, conjunto)
    return None


def url(vaga: str) -> str:
    """URL pública da vaga; '' se nenhum conjunto tiver o arquivo."""
    c = caminho(vaga)
    return "/" + c.relative_to(RAIZ).as_posix() if c else ""


def tag(vaga: str, classe: str = "", alt: str = "", largura: int | None = None, altura: int | None = None,
        carregar: str = "lazy") -> str:
    """<img> da vaga; sem arquivo, um <span> liso (cor papel) do mesmo tamanho."""
    cls = f' class="{escape(classe)}"' if classe else ""
    endereco = url(vaga)
    if not endereco:
        return f'<span{cls} data-vaga="{escape(vaga)}" style="display:block;background:#F5EAE2" aria-hidden="true"></span>'
    dims = (f' width="{largura}"' if largura else "") + (f' height="{altura}"' if altura else "")
    return (f'<img{cls} src="{endereco}" alt="{escape(alt)}" data-vaga="{escape(vaga)}"{dims} '
            f'loading="{carregar}" decoding="async">')

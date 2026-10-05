"""
Confere um conjunto de ilustrações antes de ligá-lo (rodada 9):

    python scripts/checar_ilustracoes.py                # o conjunto ativo
    python scripts/checar_ilustracoes.py aquarela-2027  # um conjunto novo

Para cada vaga de conteudo/ocidental/ilustracoes.yaml: o arquivo existe (WebP),
a proporção bate (2% de folga), o tamanho não é menor que o `minimo` e o arquivo
tem menos de 300 KB. Arquivo sobrando na pasta (vaga que não está no manifesto)
também é erro. Sai com 1 se algo falhar (o CI roda para o conjunto ativo).
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from PIL import Image  # noqa: E402

import ilustracoes  # noqa: E402

PESO_MAXIMO = 300 * 1024
FOLGA = 0.02


def conferir(conjunto: str) -> list[str]:
    pasta = ilustracoes.PASTA / conjunto
    if not pasta.is_dir():
        return [f"a pasta {pasta.relative_to(RAIZ)} não existe"]
    erros = []
    for vaga, spec in ilustracoes.VAGAS.items():
        arq = ilustracoes.arquivo(vaga, conjunto)
        if not arq.exists():
            erros.append(f"{vaga}: falta o arquivo {arq.name}")
            continue
        if arq.stat().st_size >= PESO_MAXIMO:
            erros.append(f"{vaga}: {arq.stat().st_size // 1024} KB (máximo 300 KB)")
        with Image.open(arq) as im:
            if im.format != "WEBP":
                erros.append(f"{vaga}: não é WebP ({im.format})")
            w, h = im.size
        pw, ph = spec["proporcao"]
        if abs(w / h - pw / ph) > FOLGA * (pw / ph):
            erros.append(f"{vaga}: {w}×{h} não tem a proporção {pw}:{ph}")
        mw, mh = spec["minimo"]
        if w < mw or h < mh:
            erros.append(f"{vaga}: {w}×{h} é menor que o mínimo {mw}×{mh}")
    for arq in sorted(pasta.iterdir()):
        if arq.stem not in ilustracoes.VAGAS:
            erros.append(f"{arq.name}: arquivo sobrando (vaga que não está no manifesto)")
    return erros


def main():
    conjunto = sys.argv[1] if len(sys.argv) > 1 else ilustracoes._dados["conjunto_ativo"]
    erros = conferir(conjunto)
    for e in erros:
        print("ERRO ", e)
    print(f"{conjunto}: {len(ilustracoes.VAGAS)} vagas, {len(erros)} erro(s)")
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()

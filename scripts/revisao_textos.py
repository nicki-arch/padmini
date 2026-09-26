"""
Quantos textos da versão ocidental ainda faltam revisar (campo `revisado`).
É a lista de trabalho da família do Pedro.

    python scripts/revisao_textos.py          # resumo por arquivo
    python scripts/revisao_textos.py --lista  # + cada texto que falta, arquivo e caminho

Revisou um texto? Troque `revisado: false` por `revisado: true` no YAML
(conteudo/ocidental/textos/). O LEIA.md da pasta explica o formato e o tom.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import montar_texto_ocidental as mt  # noqa: E402


def main():
    contagem = mt.contagem_de_revisao()
    revisados, total = contagem.pop("_total")
    print("Textos da versão ocidental (conteudo/ocidental/textos/)\n")
    for arquivo, (r, t) in contagem.items():
        print(f"  {arquivo + '.yaml':26s} {r:4d} de {t:4d} revisados · faltam {t - r}")
    print(f"\n  TOTAL: {revisados} de {total} revisados · faltam {total - revisados}")
    if "--lista" in sys.argv:
        print("\nFaltam:")
        for arquivo, caminho, no in mt.cada_texto():
            if not no.get("revisado"):
                print(f"  {arquivo}.yaml → {' / '.join(caminho)}")


if __name__ == "__main__":
    main()

"""
De onde vêm as pessoas (rodada 19): por utm_source, quantas amostras, "me avise" e
pedidos pagos desde uma data. O Cowork cruza com as visualizações dos vídeos (Real Oficial).

    python scripts/relatorio_origem.py --desde 2026-10-14
    python scripts/relatorio_origem.py --desde 2026-10-14 --csv

A bio de cada rede aponta para /links?utm_source=<rede>; a página repassa a origem a
todos os botões (pagina_links.py), e os formulários gravam em `amostras_email.origem`,
`leads.origem` ("me avise") e `pedidos.rastreio`. Sem utm_source: "(sem origem)".

Precisa de DATABASE_URL. Só contagens: nenhum e-mail, nome ou dado de nascimento.
A data é em horário de Brasília.
"""
import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FUSO = ZoneInfo("America/Sao_Paulo")
COLUNAS = ("utm_source", "amostras", "me_avise", "pedidos_pagos")


def linhas(contagem: dict) -> list[tuple]:
    """Mais amostras primeiro; a linha "total" no fim."""
    corpo = sorted(((f, c["amostras"], c["me_avise"], c["pedidos_pagos"]) for f, c in contagem.items()),
                   key=lambda r: (-r[1], -r[3], r[0]))
    total = ("total", *(sum(r[i] for r in corpo) for i in (1, 2, 3)))
    return [*corpo, total]


def tabela(rs: list[tuple]) -> str:
    largura = [max(len(str(r[i])) for r in [COLUNAS, *rs]) for i in range(len(COLUNAS))]
    def fmt(r):
        return "  ".join(str(v).ljust(largura[0]) if i == 0 else str(v).rjust(largura[i]) for i, v in enumerate(r))
    return "\n".join([fmt(COLUNAS), *(fmt(r) for r in rs)]) + "\n"


def csv(rs: list[tuple]) -> str:
    return "\n".join(";".join(str(v) for v in r) for r in [COLUNAS, *rs]) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--desde", required=True, help="AAAA-MM-DD (horário de Brasília)")
    ap.add_argument("--csv", action="store_true", help="CSV com ; em vez da tabela")
    args = ap.parse_args(argv)
    try:
        desde = datetime.combine(date.fromisoformat(args.desde), datetime.min.time(), FUSO)
    except ValueError:
        print("--desde precisa ser AAAA-MM-DD, ex.: 2026-10-14", file=sys.stderr)
        return 2
    import db
    if not db.ativo():
        print("Falta DATABASE_URL no ambiente.", file=sys.stderr)
        return 2
    rs = linhas(db.contagem_por_origem(desde))
    print(csv(rs) if args.csv else tabela(rs), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())

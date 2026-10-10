"""
Relatório de vendas do mês na Stripe (rodada 11), por produto: um CSV para o contador.

    python scripts/relatorio_vendas.py --mes 2026-10                 # imprime o CSV
    python scripts/relatorio_vendas.py --mes 2026-10 --saida out.csv

Precisa de STRIPE_SECRET_KEY (de leitura basta: uma chave restrita com Balance read e
Charges/Refunds/Disputes read) e de DATABASE_URL (para saber o produto de cada pagamento).

De onde vem cada número: das *balance transactions* da Stripe do mês (horário de
Brasília), que já trazem o valor, a taxa e o líquido de cada movimento:
  - `reporting_category` charge   → venda (bruto, taxa Stripe);
  - `reporting_category` refund   → reembolso;
  - `reporting_category` dispute* → contestação (chargeback) e a reversão dela;
e o produto sai de `pedidos` pelo PaymentIntent (`stripe_pagamento`). Pagamento sem pedido
nosso aparece como "sem_pedido". Só compras da Stripe: as da Cakto ficam no painel dela.

Nenhum dado pessoal: só produto, contagens e valores. Separador `;` e vírgula decimal,
para abrir direto na planilha em português. Valores em reais.
"""
import argparse
import csv
import io
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FUSO = ZoneInfo("America/Sao_Paulo")
COLUNAS = ("produto", "vendas", "bruto", "taxa_stripe", "reembolsos", "contestacoes", "liquido")


def intervalo(mes: str) -> tuple[int, int]:
    """'2026-10' → (início, fim) em segundos Unix, no horário de Brasília."""
    ano, m = (int(x) for x in mes.split("-"))
    inicio = datetime(ano, m, 1, tzinfo=FUSO)
    fim = datetime(ano + (m == 12), 1 if m == 12 else m + 1, 1, tzinfo=FUSO)
    return int(inicio.timestamp()), int(fim.timestamp())


def _pagamento_da_origem(origem) -> str:
    """O PaymentIntent de uma charge, refund ou dispute (expandidos ou não)."""
    if not isinstance(origem, dict):
        origem = getattr(origem, "to_dict", lambda: {})() if origem is not None else {}
    pi = origem.get("payment_intent")
    return pi.get("id", "") if isinstance(pi, dict) else str(pi or "")


def transacoes_da_stripe(mes: str) -> list[dict]:
    """As balance transactions do mês, já resumidas: categoria, valor, taxa, líquido (em
    centavos) e o PaymentIntent. Com paginação automática."""
    import stripe_api
    inicio, fim = intervalo(mes)
    lista = stripe_api._cliente().v1.balance_transactions.list(params={
        "created": {"gte": inicio, "lt": fim}, "limit": 100, "expand": ["data.source"]})
    saida = []
    for t in lista.auto_paging_iter():
        saida.append({"categoria": t.reporting_category, "valor": t.amount, "taxa": t.fee, "liquido": t.net,
                      "moeda": t.currency, "pagamento": _pagamento_da_origem(t.source)})
    return saida


def resumir(transacoes: list[dict], produto_do_pagamento: dict) -> list[dict]:
    """Uma linha por produto (mais o TOTAL), com os valores em centavos."""
    linhas = defaultdict(lambda: dict.fromkeys(COLUNAS[1:], 0))
    for t in transacoes:
        categoria = str(t.get("categoria") or "")
        if categoria not in ("charge", "refund", "dispute", "dispute_reversal"):
            continue  # taxas avulsas, transferências e saques não são de um produto
        produto = produto_do_pagamento.get(t.get("pagamento") or "", "sem_pedido")
        linha = linhas[produto]
        if categoria == "charge":
            linha["vendas"] += 1
            linha["bruto"] += t["valor"]
        elif categoria == "refund":
            linha["reembolsos"] += -t["valor"]
        else:
            linha["contestacoes"] += -t["valor"]
        linha["taxa_stripe"] += t["taxa"]
        linha["liquido"] += t["liquido"]
    resultado = [{"produto": p, **v} for p, v in sorted(linhas.items())]
    total = {"produto": "TOTAL", **{c: sum(r[c] for r in resultado) for c in COLUNAS[1:]}}
    return resultado + [total]


def _reais(centavos: int) -> str:
    return f"{Decimal(centavos) / 100:.2f}".replace(".", ",")


def csv_texto(linhas: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(COLUNAS)
    for r in linhas:
        w.writerow([r["produto"], r["vendas"]] + [_reais(r[c]) for c in COLUNAS[2:]])
    return buf.getvalue()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--mes", required=True, help="AAAA-MM (horário de Brasília)")
    ap.add_argument("--saida", help="arquivo CSV (padrão: imprime na tela)")
    args = ap.parse_args(argv)
    try:
        intervalo(args.mes)
    except ValueError:
        print("--mes precisa ser AAAA-MM, ex.: 2026-10", file=sys.stderr)
        return 2
    import db
    import pagamento
    if not pagamento.chave_secreta():
        print("Falta STRIPE_SECRET_KEY no ambiente.", file=sys.stderr)
        return 2
    if not db.ativo():
        print("Falta DATABASE_URL no ambiente (o produto de cada pagamento vem de `pedidos`).", file=sys.stderr)
        return 2
    texto = csv_texto(resumir(transacoes_da_stripe(args.mes), db.produtos_dos_pagamentos_stripe()))
    if args.saida:
        Path(args.saida).write_text(texto, encoding="utf-8")
        print(f"Relatório de {args.mes} em {args.saida}")
    else:
        print(texto, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Padmini — quem cobra: a Cakto ou a Stripe (rodada 11). Os interruptores de pagamento.

    PADMINI_PAGAMENTO=cakto     (padrão; é o que vale se a variável não existir)
    PADMINI_PAGAMENTO=stripe    checkout próprio, Stripe Embedded Checkout em /checkout/{id}

    PADMINI_VENDAS_TESTE=1      abre a venda SÓ neste serviço (a prévia), mesmo com
                                `vendas_abertas: false` no catálogo. Aceito só com
                                PADMINI_PAGAMENTO=stripe e chave de TESTE da Stripe
                                (sk_test_…/rk_test_…): com chave de produção (sk_live_),
                                sem chave ou com a Cakto, o site NÃO sobe e diz por quê.

Mesmo jeito do `sistema.py`: este módulo é o ÚNICO que lê essas variáveis, e valor
desconhecido derruba a subida com uma mensagem clara, em vez de pôr no ar um site que
cobra pelo caminho errado. Para trocar, na Render: Environment → a variável → salvar.

A Stripe vale só para a versão ocidental (é a que tem catálogo). A védica continua
vendendo pela Cakto, qualquer que seja o valor aqui. O webhook da Cakto continua
funcionando nos dois modos: uma compra feita na Cakto antes da troca é entregue.

As chaves da Stripe (`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`,
`STRIPE_WEBHOOK_SECRET`) só existem como variável de ambiente: nunca no repositório,
nunca no log (as mensagens abaixo dizem o PREFIXO da chave, nunca a chave).
"""

import os

MODOS = ("cakto", "stripe")
PADRAO = "cakto"
PREFIXOS_TESTE = ("sk_test_", "rk_test_")


class PagamentoInvalido(RuntimeError):
    pass


def validar(valor: str) -> str:
    v = str(valor or "").strip().lower()
    if v not in MODOS:
        raise PagamentoInvalido(
            f"PADMINI_PAGAMENTO={valor!r} não existe. Use 'cakto' ou 'stripe' "
            f"(ou apague a variável para ficar com '{PADRAO}').")
    return v


def modo() -> str:
    """Quem cobra. Valor desconhecido levanta PagamentoInvalido (o app chama na subida)."""
    bruto = os.environ.get("PADMINI_PAGAMENTO", "")
    return validar(bruto) if bruto.strip() else PADRAO


def stripe() -> bool:
    return modo() == "stripe"


def chave_secreta() -> str:
    return os.environ.get("STRIPE_SECRET_KEY", "").strip()


def chave_publica() -> str:
    return os.environ.get("STRIPE_PUBLISHABLE_KEY", "").strip()


def segredo_webhook() -> str:
    return os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()


def chave_de_teste(chave: str) -> bool:
    return str(chave or "").startswith(PREFIXOS_TESTE)


def _prefixo(chave: str) -> str:
    """Só o começo da chave, para a mensagem de erro (nunca a chave inteira)."""
    chave = str(chave or "")
    return chave[:8] + "…" if chave else "(vazia)"


def vendas_teste() -> bool:
    """PADMINI_VENDAS_TESTE=1: a venda abre neste serviço, só em modo de teste da Stripe.
    Combinação perigosa (chave de produção, Cakto, sem chave) levanta PagamentoInvalido:
    venda aberta "de teste" cobrando dinheiro de verdade é o erro que isto impede."""
    bruto = os.environ.get("PADMINI_VENDAS_TESTE", "").strip()
    if bruto in ("", "0"):
        return False
    if bruto != "1":
        raise PagamentoInvalido(
            f"PADMINI_VENDAS_TESTE={bruto!r} não existe. Use 1 (abre a venda de teste) "
            "ou apague a variável.")
    if modo() != "stripe":
        raise PagamentoInvalido(
            "PADMINI_VENDAS_TESTE=1 só vale com PADMINI_PAGAMENTO=stripe (e chave de teste "
            "da Stripe). Com a Cakto, abrir a venda cobraria de verdade: o site não sobe. "
            "Apague PADMINI_VENDAS_TESTE ou troque o pagamento para stripe.")
    chave = chave_secreta()
    if not chave_de_teste(chave):
        raise PagamentoInvalido(
            f"PADMINI_VENDAS_TESTE=1 exige STRIPE_SECRET_KEY de TESTE (sk_test_…), e a chave "
            f"configurada começa com {_prefixo(chave)}. Com chave de produção a venda de teste "
            "cobraria de verdade: o site não sobe. Use a chave do modo de teste ou apague "
            "PADMINI_VENDAS_TESTE.")
    return True


def validar_na_subida() -> tuple[str, bool]:
    """Chamado pelo app ao subir: (modo, venda de teste). Erro aqui = o site não sobe."""
    return modo(), vendas_teste()

"""
Rodada 11, Fase 4 — privacidade e termos com a Stripe, relatório de vendas e smoke.

  - /privacidade (e /termos) no modo stripe: Stripe como operadora, Ebanx no Pix, cartão
    que não passa pelo nosso servidor; no modo cakto, o texto de antes;
  - scripts/relatorio_vendas.py --mes AAAA-MM: CSV por produto (bruto, taxa Stripe,
    reembolsos, líquido), sem dado pessoal;
  - smoke: com a Stripe, /webhook/stripe recusa POST sem assinatura; com a Cakto, nada muda.
"""
import importlib.util
from types import SimpleNamespace

import pytest

import test_app as base  # configura o ambiente e o app

import app as app_mod  # noqa: E402
import stripe_api  # noqa: E402

RAIZ = base.RAIZ
cliente = base.cliente
HTML = {"accept": "text/html"}


def _carregar(nome):
    spec = importlib.util.spec_from_file_location(nome, RAIZ / "scripts" / f"{nome}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


relatorio = _carregar("relatorio_vendas")
smoke = _carregar("smoke_producao")


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    monkeypatch.delenv("PADMINI_PAGAMENTO", raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


# ------------------------------------------------------------------ privacidade e termos
def test_privacidade_no_modo_stripe(ocidental, monkeypatch):
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    html = cliente.get("/privacidade", headers=HTML).text
    assert "<strong>Stripe</strong> — operadora do pagamento" in html
    assert "<strong>Ebanx</strong>" in html and "Pix" in html
    assert "não passam pelo nosso servidor" in html
    assert "nunca os seus dados de nascimento" in html
    assert "apagado em 7 dias" in html
    assert "16 de outubro de 2026" in html  # rodada 16: saiu a Anthropic (texto por IA)
    assert "O pagamento acontece na página da Cakto" not in html
    assert "{%" not in html and "{{" not in html


def test_privacidade_com_a_cakto_e_a_de_antes(ocidental):
    html = cliente.get("/privacidade", headers=HTML).text
    assert "<strong>Cakto</strong> — processamento do pagamento e programa de afiliados." in html
    assert "Stripe" not in html and "Ebanx" not in html
    assert "16 de outubro de 2026" in html  # rodada 16: saiu a Anthropic (texto por IA)


def test_termos_no_modo_stripe(ocidental, monkeypatch):
    html = cliente.get("/termos", headers=HTML).text
    assert "processado pela plataforma <strong>Cakto</strong>" in html and "Stripe" not in html
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    app_mod._paginas_prontas.clear()
    html = cliente.get("/termos", headers=HTML).text
    assert "processado pela <strong>Stripe</strong>" in html and "<strong>Ebanx</strong>" in html
    assert "canal de reembolso da Cakto" not in html


def test_privacidade_da_vedica_nao_muda(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    corpo = cliente.get("/privacidade").content
    assert corpo == (RAIZ / "static" / "privacidade.html").read_bytes()


def test_config_diz_quem_cobra(monkeypatch):
    monkeypatch.delenv("PADMINI_PAGAMENTO", raising=False)
    assert cliente.get("/api/config").json()["pagamento"] == "cakto"
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    assert cliente.get("/api/config").json()["pagamento"] == "stripe"


# ------------------------------------------------------------------ relatório de vendas
def test_intervalo_do_mes_no_horario_de_brasilia():
    inicio, fim = relatorio.intervalo("2026-10")
    assert inicio == 1790823600  # 2026-10-01 00:00 em São Paulo (UTC−3)
    assert fim == 1793502000     # 2026-11-01 00:00
    assert relatorio.intervalo("2026-12")[1] == 1798772400  # vira o ano


TRANSACOES = [
    {"categoria": "charge", "valor": 3700, "taxa": 185, "liquido": 3515, "pagamento": "pi_a"},
    {"categoria": "charge", "valor": 3700, "taxa": 185, "liquido": 3515, "pagamento": "pi_b"},
    {"categoria": "charge", "valor": 9652, "taxa": 400, "liquido": 9252, "pagamento": "pi_c"},
    {"categoria": "refund", "valor": -3700, "taxa": 0, "liquido": -3700, "pagamento": "pi_b"},
    {"categoria": "dispute", "valor": -9652, "taxa": 1500, "liquido": -11152, "pagamento": "pi_c"},
    {"categoria": "charge", "valor": 1900, "taxa": 100, "liquido": 1800, "pagamento": "pi_x"},
    {"categoria": "payout", "valor": -10000, "taxa": 0, "liquido": -10000, "pagamento": ""},
]
PRODUTOS = {"pi_a": "ocidental:mapa", "pi_b": "ocidental:mapa", "pi_c": "ocidental:compat"}


def test_resumo_por_produto():
    linhas = {r["produto"]: r for r in relatorio.resumir(TRANSACOES, PRODUTOS)}
    assert linhas["ocidental:mapa"] == {"produto": "ocidental:mapa", "vendas": 2, "bruto": 7400, "taxa_stripe": 370,
                                        "reembolsos": 3700, "contestacoes": 0, "liquido": 3330}
    assert linhas["ocidental:compat"]["contestacoes"] == 9652 and linhas["ocidental:compat"]["liquido"] == -1900
    assert linhas["sem_pedido"]["vendas"] == 1  # pagamento sem pedido nosso aparece, não some
    total = linhas["TOTAL"]
    assert total["bruto"] == 7400 + 9652 + 1900 and total["vendas"] == 4
    assert total["liquido"] == 3330 - 1900 + 1800  # o saque (payout) não é venda


def test_csv_sem_dado_pessoal_e_com_virgula_decimal():
    texto = relatorio.csv_texto(relatorio.resumir(TRANSACOES, PRODUTOS))
    linhas = texto.splitlines()
    assert linhas[0] == "produto;vendas;bruto;taxa_stripe;reembolsos;contestacoes;liquido"
    assert "ocidental:mapa;2;74,00;3,70;37,00;0,00;33,30" in linhas
    assert linhas[-1].startswith("TOTAL;4;")
    assert "@" not in texto and "pi_" not in texto


def test_transacoes_lidas_da_stripe(monkeypatch):
    """Com objetos de verdade da biblioteca (StripeObject não é dict)."""
    import stripe
    t1 = stripe.BalanceTransaction.construct_from({
        "id": "txn_1", "object": "balance_transaction", "reporting_category": "charge", "amount": 3700, "fee": 185,
        "net": 3515, "currency": "brl",
        "source": {"id": "ch_1", "object": "charge", "payment_intent": "pi_a"}}, "sk_test_x")
    t2 = stripe.BalanceTransaction.construct_from({
        "id": "txn_2", "object": "balance_transaction", "reporting_category": "refund", "amount": -3700, "fee": 0,
        "net": -3700, "currency": "brl",
        "source": {"id": "re_1", "object": "refund", "payment_intent": {"id": "pi_a", "object": "payment_intent"}}},
        "sk_test_x")
    pedidos = []

    def listar(params=None, options=None):
        pedidos.append(params)
        return SimpleNamespace(auto_paging_iter=lambda: iter([t1, t2]))
    falso = SimpleNamespace(v1=SimpleNamespace(balance_transactions=SimpleNamespace(list=listar)))
    monkeypatch.setattr(stripe_api, "_cliente", lambda: falso)
    ts = relatorio.transacoes_da_stripe("2026-10")
    assert [(t["categoria"], t["pagamento"], t["valor"]) for t in ts] == [("charge", "pi_a", 3700),
                                                                          ("refund", "pi_a", -3700)]
    assert pedidos[0]["created"] == {"gte": 1790823600, "lt": 1793502000}
    assert pedidos[0]["expand"] == ["data.source"]


def test_relatorio_sem_chave_ou_mes_errado(monkeypatch, capsys):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    assert relatorio.main(["--mes", "2026-13"]) == 2
    assert relatorio.main(["--mes", "2026-10"]) == 2
    assert "STRIPE_SECRET_KEY" in capsys.readouterr().err


# ------------------------------------------------------------------ smoke
def test_smoke_com_a_cakto_continua_com_40_checagens():
    # rodada 16: + "sem texto por IA"; 16.1: + preço riscado do /mapa; 18: + 301 e webhook do
    # domínio antigo; 19: + /links; 15: + /painel sem login, ação sem login e "o público não
    # vê o modo teste"; 17: + token de "O seu ano" do /live sem sessão; 14: + token de "A sua
    # Lua no ano" do /live sem sessão e o calendário com token falso; 20: + o kit fora da venda
    # não aparece. Com a Stripe no ar, + 3 (rodada 20: o checkout fora da venda recusa) = 44.
    # Rodada 20.3: as páginas de produto seguem o painel. "/mapa 200", "/compatibilidade 200"
    # e "numerologia e tarot 200" viram UMA checagem (todas as rotas do catálogo); entra
    # "páginas em breve mostram em breve" (antes só a sinastria, dentro da de venda fechada) = 40.
    assert len(smoke.CHECAGENS) == 40
    nomes = [n for n, _ in smoke.CHECAGENS_STRIPE]
    assert len(nomes) == 3
    assert any("/webhook/stripe" in n for n in nomes) and any("fora da venda" in n for n in nomes)


def test_smoke_stripe_confere_o_401(monkeypatch):
    chamadas = []

    def req(caminho, corpo=None, timeout=90):
        chamadas.append((caminho, corpo))
        return (401, b"") if caminho == "/webhook/stripe" else (404, b"")
    monkeypatch.setattr(smoke, "req", req)
    assert smoke._stripe_webhook_sem_assinatura()
    assert smoke._stripe_checkout_inexistente()
    assert chamadas[0][0] == "/webhook/stripe" and "stripe-signature" not in str(chamadas[0][1]).lower()

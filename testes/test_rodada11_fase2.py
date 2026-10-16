"""
Rodada 11, Fase 2 — o checkout próprio: o botão chama POST /api/checkout, o servidor
grava o pedido pendente e cria a Checkout Session (Stripe simulada: nada de rede no CI),
/checkout/{id} mostra o resumo e monta o Embedded Checkout, /obrigado/{id} espera o webhook.

Do brief: preço adulterado é ignorado; em_breve/oculto → 404 no /api/checkout; com
vendas_abertas: false e sem PADMINI_VENDAS_TESTE não há botão e o /api/checkout recusa;
nenhum dado de nascimento na chamada à Stripe.
"""
import copy
import json
import os
import re
from types import SimpleNamespace

import pytest

import test_app as base  # configura o ambiente e o app

import app as app_mod  # noqa: E402
import catalogo  # noqa: E402
import db  # noqa: E402
import marketing  # noqa: E402
import pagamento  # noqa: E402
import stripe_api  # noqa: E402

cliente = base.cliente
HTML = {"accept": "text/html"}
TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
precisa_banco = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL não definida")

PESSOA = {"nome": "Ana Clara", "data": "1990-05-15", "hora": "14:30", "lat": -30.0331, "lon": -51.23,
          "cidade": "Porto Alegre, RS"}
BIA = {"nome": "Bia", "data": "1988-11-02", "hora": "08:15", "lat": -23.55, "lon": -46.63, "cidade": "São Paulo, SP"}


class SessoesFalsas:
    """No lugar de StripeClient.v1.checkout.sessions: guarda o que seria mandado."""
    def __init__(self):
        self.criadas, self.status = [], ("open", "unpaid")

    def create(self, params=None, options=None):
        self.criadas.append({"params": params, "options": options})
        n = len(self.criadas)
        return SimpleNamespace(id=f"cs_test_{n}", client_secret=f"cs_test_{n}_secret_abc")

    def retrieve(self, sid, params=None, options=None):
        return SimpleNamespace(id=sid, status=self.status[0], payment_status=self.status[1])


@pytest.fixture
def stripe_falsa(monkeypatch):
    sessoes = SessoesFalsas()
    falso = SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=sessoes)))
    monkeypatch.setattr(stripe_api, "_cliente", lambda: falso)
    stripe_api._cache_estado.clear()
    return sessoes


@pytest.fixture
def modo_stripe(monkeypatch):
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_" + "a" * 20)
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_" + "b" * 20)
    monkeypatch.delenv("PADMINI_VENDAS_TESTE", raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


@pytest.fixture
def banco(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_URL)
    assert db.iniciar()
    with db._conectar() as c:
        c.execute("TRUNCATE pedidos_pendentes")
    yield


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


def _comprar(**extra):
    corpo = {"produto": "mapa", "pessoa": PESSOA, "email": "ana@teste.com", "aceita_sequencia": True,
             "origem": {"ref": "PEDRO"}}
    corpo.update(extra)
    return cliente.post("/api/checkout", json=corpo)


def _id(r) -> str:
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert re.fullmatch(r"/checkout/[A-Za-z0-9_-]{20,}", url)
    return url.rsplit("/", 1)[1]


# ------------------------------------------------------------------ com a Cakto, nada muda
def test_com_a_cakto_o_checkout_proprio_nao_existe(monkeypatch):
    monkeypatch.delenv("PADMINI_PAGAMENTO", raising=False)
    assert _comprar().status_code == 404
    assert cliente.get("/checkout/" + "a" * 24, headers=HTML).status_code == 404
    assert cliente.get("/obrigado/" + "a" * 24, headers=HTML).status_code == 404
    assert cliente.get("/api/checkout/" + "a" * 24).status_code == 404


def test_com_a_cakto_o_botao_continua_na_cakto(ocidental, monkeypatch):
    monkeypatch.delenv("PADMINI_PAGAMENTO", raising=False)
    html = cliente.get("/mapa", headers=HTML).text
    assert "pay.cakto.com.br" in html and "/static/ocidental/comprar.js" not in html
    assert "const PAGAR_NA_STRIPE = false;" in html
    assert "de taxa da plataforma" in html


# ------------------------------------------------------------------ as páginas no modo Stripe
def test_no_modo_stripe_o_botao_chama_o_checkout_proprio(ocidental, modo_stripe):
    html = cliente.get("/mapa", headers=HTML).text
    assert "/static/ocidental/comprar.js" in html and 'data-comprar="mapa"' in html
    assert "pay.cakto.com.br" not in html          # nenhum link da Cakto
    assert "de taxa da plataforma\");" not in html and 'const TAXA = "";' in html  # sem a taxa da Cakto
    assert "pagamento seguro pela Stripe" in html
    for rota, produto in (("/compatibilidade", "compat"), ("/numerologia", "numerologia"), ("/tarot", "tarot")):
        h = cliente.get(rota, headers=HTML).text
        assert "/static/ocidental/comprar.js" in h and f'data-comprar="{produto}"' in h and "pay.cakto.com.br" not in h, rota
        assert "window.padCorpoCompra" in h, rota


def test_no_modo_stripe_a_home_fala_da_stripe(ocidental, modo_stripe):
    html = cliente.get("/", headers=HTML).text
    assert "pela Stripe" in html and "pela Cakto" not in html
    assert "de taxa da plataforma" not in html


def test_sinastria_no_modo_stripe_sem_order_bump(ocidental, modo_stripe):
    html = cliente.get("/compatibilidade", headers=HTML).text
    assert 'const PRECO_BUMP_MAPAS = "";' in html


@pytest.mark.catalogo_real
def test_venda_fechada_sem_botao_e_api_recusa(ocidental, modo_stripe, stripe_falsa):
    fechado = copy.deepcopy(catalogo.carregar())  # rodada 16: o YAML abriu; fecha como quem edita
    fechado["vendas_abertas"] = False
    catalogo.usar(fechado)
    html = cliente.get("/mapa", headers=HTML).text
    assert "/static/ocidental/comprar.js" not in html and 'data-comprar="' not in html
    assert _comprar().status_code == 404
    assert stripe_falsa.criadas == []


@pytest.mark.catalogo_real
def test_venda_de_teste_abre_o_botao(ocidental, modo_stripe, monkeypatch):
    monkeypatch.setenv("PADMINI_VENDAS_TESTE", "1")
    html = cliente.get("/mapa", headers=HTML).text
    assert "/static/ocidental/comprar.js" in html and 'data-comprar="mapa"' in html


@pytest.mark.parametrize("estado", ["em_breve", "oculto"])
def test_produto_fora_do_ar_responde_404(modo_stripe, stripe_falsa, estado):
    dados = copy.deepcopy(catalogo.dados())
    for p in dados["produtos"]:
        if p["chave"] == "compat":
            p["estado"] = estado
    catalogo.usar(dados)
    r = _comprar(produto="compat", pessoa=None, a=PESSOA, b=BIA)
    assert r.status_code == 404
    assert stripe_falsa.criadas == []


def test_sem_banco_nao_abre_checkout(modo_stripe, stripe_falsa, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert _comprar().status_code == 503
    assert stripe_falsa.criadas == []  # sem pedido gravado, nada vai para a Stripe


def test_sem_chaves_da_stripe_nao_abre_checkout(modo_stripe, stripe_falsa, monkeypatch):
    monkeypatch.delenv("STRIPE_PUBLISHABLE_KEY")
    assert _comprar().status_code == 503
    assert stripe_falsa.criadas == []


def test_corpo_invalido_e_422(modo_stripe):
    assert _comprar(email="nada").status_code == 422
    assert _comprar(pessoa={**PESSOA, "lat": 300}).status_code == 422
    assert _comprar(produto="bump_mapas_casal").status_code == 422


def test_cliente_sem_chave_secreta_recusa(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    with pytest.raises(stripe_api.StripeIndisponivel):
        stripe_api._cliente()


def test_parametros_da_sessao():
    pendente = {"id": "abc123abc123abc123abc123", "sistema": "ocidental", "email": "ana@teste.com", "moeda": "brl",
                "itens": [{"chave": "mapa", "valor_centavos": 3700, "dados": PESSOA}]}
    p = stripe_api.parametros_da_sessao(pendente, "https://previa.exemplo/")
    assert p["ui_mode"] == "embedded_page" and p["mode"] == "payment"
    assert p["return_url"] == "https://previa.exemplo/obrigado/abc123abc123abc123abc123"
    assert p["line_items"] == [{"quantity": 1, "price_data": {"currency": "brl", "unit_amount": 3700,
                                                               "product_data": {"name": "Mapa Natal completo"}}}]
    assert "payment_method_types" not in p  # cartão, Pix e carteiras vêm do painel


# ------------------------------------------------------------------ com o banco
@precisa_banco
def test_preco_adulterado_e_ignorado(banco, modo_stripe, stripe_falsa):
    r = _comprar(preco=1, valor_centavos=1, amount=1, unit_amount=1,
                 line_items=[{"price_data": {"unit_amount": 1}}])
    id_pedido = _id(r)
    assert db.pendente(id_pedido)["valor_centavos"] == 4700
    params = stripe_falsa.criadas[0]["params"]
    assert params["line_items"][0]["price_data"]["unit_amount"] == 4700
    assert len(params["line_items"]) == 1


@precisa_banco
def test_nenhum_dado_de_nascimento_vai_para_a_stripe(banco, modo_stripe, stripe_falsa):
    id_pedido = _id(_comprar())
    chamada = stripe_falsa.criadas[0]
    tudo = json.dumps(chamada, ensure_ascii=False)
    for dado in ("Ana Clara", "1990-05-15", "14:30", "-30.0331", "-51.23", "Porto Alegre", "PEDRO"):
        assert dado not in tudo, dado
    p = chamada["params"]
    assert p["metadata"] == {"pedido": id_pedido} and p["client_reference_id"] == id_pedido
    assert p["payment_intent_data"] == {"metadata": {"pedido": id_pedido}}
    assert p["customer_email"] == "ana@teste.com"
    assert chamada["options"] == {"idempotency_key": f"pedido-{id_pedido}"}
    lido = db.pendente(id_pedido)
    assert lido["stripe_session_id"] == "cs_test_1" and lido["estado"] == "aberto"
    assert lido["rastreio"] == {"ref": "PEDRO"}  # a origem fica conosco


@precisa_banco
def test_cupom_aplicado_no_servidor(banco, modo_stripe, stripe_falsa):
    _id(_comprar(produto="compat", pessoa=None, a=PESSOA, b=BIA, origem={"cupom": "PEDRO"}))
    assert stripe_falsa.criadas[0]["params"]["line_items"][0]["price_data"]["unit_amount"] == 9652
    _id(_comprar(produto="compat", pessoa=None, a=PESSOA, b=BIA, origem={"coupon": "pedro"}))
    assert stripe_falsa.criadas[1]["params"]["line_items"][0]["price_data"]["unit_amount"] == 9652


@precisa_banco
def test_tiragem_de_tarot_falsa_e_recusada(banco, modo_stripe, stripe_falsa):
    assert _comprar(produto="tarot", pessoa=None, tiragem="inventada").status_code == 422
    assert stripe_falsa.criadas == []


@precisa_banco
def test_stripe_fora_do_ar_marca_o_pedido_como_falho(banco, modo_stripe, monkeypatch):
    def quebra(*a, **k):
        raise stripe_api.StripeIndisponivel("teste")
    monkeypatch.setattr(stripe_api, "criar_sessao", quebra)
    assert _comprar().status_code == 503
    with db._conectar() as c:
        assert c.execute("SELECT estado FROM pedidos_pendentes").fetchall() == [("falhou",)]


@precisa_banco
def test_pagina_do_checkout(banco, modo_stripe, stripe_falsa):
    id_pedido = _id(_comprar(pessoa={**PESSOA, "nome": "<script>alert(1)</script>"}))
    r = cliente.get(f"/checkout/{id_pedido}", headers=HTML)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    html = r.text
    assert "Mapa Natal completo" in html and "R$47" in html
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert 'src="https://js.stripe.com/endive/stripe.js"' in html
    assert "cs_test_1_secret" not in html  # o client_secret vem por fetch, não no HTML
    assert "taxa da plataforma" not in html
    csp = r.headers["content-security-policy"]
    for origem in ("script-src", "https://js.stripe.com", "https://checkout.stripe.com", "https://hooks.stripe.com",
                   "https://api.stripe.com"):
        assert origem in csp
    assert "maps.googleapis.com" not in csp
    assert 'payment=(self "https://js.stripe.com"' in r.headers["permissions-policy"]


@precisa_banco
def test_stripe_so_na_pagina_do_checkout(banco, modo_stripe, stripe_falsa, ocidental):
    id_pedido = _id(_comprar())
    for rota in ("/mapa", "/", f"/obrigado/{id_pedido}"):
        r = cliente.get(rota, headers=HTML)
        assert "stripe.com" not in r.headers["content-security-policy"], rota
        assert "payment=()" in r.headers["permissions-policy"], rota
        assert "js.stripe.com" not in r.text, rota


@precisa_banco
def test_segredo_so_para_pedido_aberto(banco, modo_stripe, stripe_falsa):
    id_pedido = _id(_comprar())
    r = cliente.get(f"/api/checkout/{id_pedido}")
    assert r.json() == {"client_secret": "cs_test_1_secret_abc", "chave_publica": "pk_test_" + "b" * 20}
    db.marcar_pendente(id_pedido, "pago")
    assert cliente.get(f"/api/checkout/{id_pedido}").status_code == 409


@precisa_banco
@pytest.mark.parametrize("estado,texto", [("pago", "Este pedido já foi pago"), ("expirado", "Este pedido expirou"),
                                          ("falhou", "Este pedido expirou")])
def test_pagina_do_checkout_de_pedido_fechado(banco, modo_stripe, stripe_falsa, estado, texto):
    id_pedido = _id(_comprar())
    db.marcar_pendente(id_pedido, estado)
    html = cliente.get(f"/checkout/{id_pedido}", headers=HTML).text
    assert texto in html and "js.stripe.com" not in html


@precisa_banco
def test_pedido_que_nao_existe_e_404(banco, modo_stripe):
    for id_pedido in ("a" * 24, "curto", "../../etc"):
        assert cliente.get(f"/checkout/{id_pedido}", headers=HTML).status_code == 404
        assert cliente.get(f"/api/checkout/{id_pedido}/estado").status_code == 404


@precisa_banco
def test_obrigado_espera_o_webhook(banco, modo_stripe, stripe_falsa):
    id_pedido = _id(_comprar())
    html = cliente.get(f"/obrigado/{id_pedido}", headers=HTML).text
    assert f"/api/checkout/{id_pedido}/estado" in html and "Só um instante" in html
    # voltou sem pagar: a sessão continua aberta
    assert cliente.get(f"/api/checkout/{id_pedido}/estado").json() == {
        "estado": "aberto", "aguardando_pix": False, "link": None, "sessao": "open"}
    # Pix gerado e ainda não pago
    stripe_falsa.status = ("complete", "unpaid")
    stripe_api._cache_estado.clear()
    e = cliente.get(f"/api/checkout/{id_pedido}/estado").json()
    assert e["aguardando_pix"] is True and e["link"] is None
    # cartão pago, mas o webhook ainda não chegou: NÃO mostra link
    stripe_falsa.status = ("complete", "paid")
    stripe_api._cache_estado.clear()
    e = cliente.get(f"/api/checkout/{id_pedido}/estado").json()
    assert e["estado"] == "aberto" and e["link"] is None and e["aguardando_pix"] is False
    # o webhook marcou como pago (Fase 3): o link da leitura aparece
    db.marcar_pendente(id_pedido, "pago")
    e = cliente.get(f"/api/checkout/{id_pedido}/estado").json()
    assert e["estado"] == "pago" and "/mapa?" in e["link"] and "token=oc-" in e["link"]


# ------------------------------------------------------------------ e-mails
def test_emails_mandam_para_a_pagina_do_produto_no_modo_stripe(modo_stripe):
    link = marketing.link_checkout("mapa", PESSOA, "lembrete", "ocidental")
    assert "cakto" not in link and "sck" not in link and "/mapa?" in link
    assert "1990" not in link and "Ana" not in link
    assert "cakto" in marketing.link_checkout("mapa", PESSOA, "lembrete", "vedica")  # a védica não muda


def test_pagamento_stripe_le_a_variavel(monkeypatch):
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    assert pagamento.stripe()

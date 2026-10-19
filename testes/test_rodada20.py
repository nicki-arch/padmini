"""
Rodada 20: o preço do calendário (R$47, "de R$97") e o KIT dos três produtos (mapa natal +
"O seu ano" + calendário lunar, R$97, "de R$141").

Do brief (critérios de aceite):
  1. calendário com oferta, oculto: 404 ao público; à venda, o checkout entrega o link;
  2. kit à venda (os três ativos): aparece no /mapa, em /seu-ano, no calendário, na /links e
     em /leituras com "de R$141 por R$97"; a compra (cartão e Pix) entrega um e-mail com os
     três links, e os três abrem;
  3. com qualquer um dos três fora da venda, o kit some de todo lugar e o checkout recusa,
     mesmo com o kit ativo no painel;
  4. quem comprou o kit não recebe oferta de nenhum dos três;
  5. metadata da Stripe só com `pedido` e os 3 utm;
  6. smoke com as checagens novas.
"""
import copy
import hashlib
import hmac
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

import test_app as base  # configura o ambiente e o app
from test_rodada11_fase2 import banco, modo_stripe, precisa_banco, stripe_falsa  # noqa: F401  (fixtures)

import alertas  # noqa: E402
import app as app_mod  # noqa: E402
import catalogo  # noqa: E402
import db  # noqa: E402
import entrega  # noqa: E402
import estado_site  # noqa: E402
import marketing  # noqa: E402
import ofertas  # noqa: E402
import painel  # noqa: E402
import pendentes  # noqa: E402
import previsao  # noqa: E402
import sequencias  # noqa: E402
import stripe_api  # noqa: E402

cliente = base.cliente
HTML = {"accept": "text/html"}
TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
SEGREDO = "whsec_" + "teste" * 6
PESSOA = {"nome": "Ana Clara", "data": "1990-05-15", "hora": "14:30", "lat": -30.0331, "lon": -51.23,
          "cidade": "Porto Alegre, RS"}
TRES = ("mapa", "previsao", "calendario")
PAGINAS_DE_AMOSTRA = ("/mapa", "/seu-ano", "/calendario-lunar")
MARCAS_DO_KIT = ('data-comprar="kit"', "links-bt-kit", "capa-kit", 'class="kit-opcao"')


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    for v in ("PADMINI_CAPTURA", "PADMINI_VENDAS_TESTE"):
        monkeypatch.delenv(v, raising=False)
    estado_site.esquecer()
    app_mod._paginas_prontas.clear()
    yield
    estado_site.esquecer()
    app_mod._paginas_prontas.clear()


def ligar(*chaves, venda=True):
    """Simula o Nicolas ligando produtos no painel: estes ativos, o resto como no YAML."""
    dados = copy.deepcopy(catalogo.dados())
    dados["vendas_abertas"] = venda
    for p in dados["produtos"]:
        if p["chave"] in chaves:
            p["estado"] = "ativo"
        elif p["chave"] in ("kit",) + TRES:
            p["estado"] = "oculto"
    catalogo.usar(dados)
    app_mod._paginas_prontas.clear()


@pytest.fixture
def kit_a_venda(ocidental, modo_stripe):
    ligar("kit", *TRES)
    assert catalogo.vende("kit")
    yield


# ====================================================================== Fase 1: o calendário
@pytest.mark.catalogo_real
def test_calendario_com_preco_e_oculto(ocidental):
    o = ofertas.oferta("calendario", "ocidental")
    assert (o["preco"], o["preco_de"]) == (47, 97) and not o.get("checkout")
    assert catalogo.produto("calendario")["oferta"] == "calendario"
    assert catalogo.estado("calendario") == "oculto" and not catalogo.vende("calendario")
    assert cliente.get("/calendario-lunar", headers=HTML).status_code == 404


def test_calendario_oculto_checkout_recusa(ocidental, modo_stripe, stripe_falsa):
    r = cliente.post("/api/checkout", json={"produto": "calendario", "pessoa": PESSOA, "email": "ana@teste.com"})
    assert r.status_code == 404 and stripe_falsa.criadas == []


@precisa_banco
def test_calendario_a_venda_cria_o_pedido_de_47(ocidental, modo_stripe, stripe_falsa, banco):
    ligar("calendario")
    r = cliente.post("/api/checkout", json={"produto": "calendario", "pessoa": PESSOA, "email": "ana@teste.com",
                                            "preco": 1})
    assert r.status_code == 200, r.text
    item = stripe_falsa.criadas[0]["params"]["line_items"][0]["price_data"]
    assert item["unit_amount"] == 4700 and "A sua Lua no ano" in item["product_data"]["name"]
    pendente = db.pendente(r.json()["url"].rsplit("/", 1)[1])
    assert pendente["itens"][0]["dados"]["inicio"] == datetime.now(previsao.FUSO_DATAS).strftime("%Y-%m")


def test_cartao_do_calendario_mostra_o_preco(ocidental, modo_stripe):
    ligar("mapa", "calendario", "previsao")
    for rota in ("/mapa", "/seu-ano"):
        html = cliente.get(rota, headers=HTML).text
        cartao = html[html.index('id="cartao-calendario"'):]
        cartao = cartao[:cartao.index("</a>")]
        assert "R$47" in cartao and "R$97</s>" in cartao, rota


# ====================================================================== Fase 2: o kit no catálogo
@pytest.mark.catalogo_real
def test_kit_no_catalogo_e_nas_ofertas(ocidental):
    o = ofertas.oferta("kit", "ocidental")
    assert (o["preco"], o["preco_de"]) == (97, 141)
    assert o["preco_de"] == sum(ofertas.oferta(c, "ocidental")["preco"] for c in TRES)  # a soma dos preços
    kit = catalogo.produto("kit")
    assert kit["estado"] == "oculto" and kit["oferta"] == "kit" and kit["inclui"] == list(TRES)
    assert kit["rota"] is None and kit["entrada"] == "/mapa"
    assert not catalogo.vende("kit") and catalogo.kits_a_venda() == []


def test_kit_nunca_e_pagina_nem_menu(ocidental, modo_stripe):
    ligar("kit", *TRES)
    assert "kit" not in [p["chave"] for p in catalogo.visiveis()]
    assert "kit" not in catalogo.interesses()
    assert catalogo.por_rota(None) is None
    html = cliente.get("/", headers=HTML).text
    cab = html[html.index('<header class="cab">'):html.index("</header>")]
    assert "Os três" not in cab
    assert "None" not in cliente.get("/sitemap.xml").text


def test_catalogo_recusa_kit_mal_feito():
    for inclui in (["mapa", "nao-existe"], ["mapa"], ["mapa", "mapa"], ["mapa", "comunidade"]):
        dados = copy.deepcopy(catalogo.dados())
        kit = next(p for p in dados["produtos"] if p["chave"] == "kit")
        kit["inclui"] = inclui
        with pytest.raises(catalogo.CatalogoInvalido):
            catalogo.validar(dados)


def test_quem_inclui_e_que_tem():
    assert catalogo.inclui("kit") == list(TRES) and catalogo.inclui("mapa") == []
    assert catalogo.quem_inclui("previsao") == ["previsao", "kit"]
    assert catalogo.que_tem(["ocidental:kit"]) >= set(TRES)
    assert catalogo.que_tem(["ocidental:mapas_casal"]) >= {"mapa"}


# ====================================================================== a trava
@pytest.mark.parametrize("falta", TRES)
def test_trava_kit_ativo_sem_um_dos_tres_nao_vende(ocidental, modo_stripe, stripe_falsa, falta):
    ligar("kit", *[c for c in TRES if c != falta])
    assert catalogo.estado("kit") == "ativo" and not catalogo.vende("kit")
    for rota in PAGINAS_DE_AMOSTRA + ("/links", "/leituras"):
        html = cliente.get(rota + ("?previa=x" if rota != "/links" else ""), headers=HTML).text
        assert not any(m in html for m in MARCAS_DO_KIT), rota
    r = cliente.post("/api/checkout", json={"produto": "kit", "pessoa": PESSOA, "email": "ana@teste.com"})
    assert r.status_code == 404 and stripe_falsa.criadas == []
    assert cliente.get("/api/config").json()["kits_a_venda"] == []


def test_trava_kit_oculto_com_os_tres_ativos(ocidental, modo_stripe):
    ligar(*TRES)
    assert all(catalogo.vende(c) for c in TRES) and not catalogo.vende("kit")


def test_trava_venda_fechada(ocidental, modo_stripe):
    ligar("kit", *TRES, venda=False)
    assert not catalogo.vende("kit")


def test_trava_so_pela_stripe(ocidental, monkeypatch):
    """Com a Cakto, o kit não tem checkout: não aparece."""
    monkeypatch.setenv("PADMINI_PAGAMENTO", "cakto")
    ligar("kit", *TRES)
    assert all(catalogo.vende(c) for c in TRES) and not catalogo.vende("kit")
    assert 'data-comprar="kit"' not in cliente.get("/mapa", headers=HTML).text


def test_trava_vale_com_o_painel(ocidental, modo_stripe, monkeypatch):
    """O estado no ar vem do painel (estado_site), não do YAML: kit ativo no painel com o
    calendário oculto no painel não vende."""
    ligar(*TRES)
    salvo = {"produto:kit": "ativo", "produto:calendario": "oculto"}
    monkeypatch.setattr(estado_site, "salvo", lambda: dict(salvo))
    assert not catalogo.vende("kit")
    salvo["produto:calendario"] = "ativo"
    assert catalogo.vende("kit")


def test_modo_teste_do_navegador_logado_nao_vende_o_kit(ocidental, modo_stripe, monkeypatch):
    """O "tudo liberado só para mim" mostra os produtos, mas nunca abre a venda (estado público)."""
    monkeypatch.setattr(estado_site, "liberado_para_mim", lambda: True)
    assert catalogo.estado("kit") == "ativo" and not catalogo.vende("kit")


def test_tudo_liberado_da_previa_vende_o_kit(ocidental, modo_stripe, monkeypatch):
    monkeypatch.setattr(estado_site, "salvo", lambda: {"modo": "tudo_liberado"})
    assert estado_site.ambiente() == "previa" and catalogo.vende("kit")


# ====================================================================== Fase 3: onde o kit aparece
@pytest.mark.parametrize("rota", PAGINAS_DE_AMOSTRA)
def test_amostras_mostram_a_opcao_do_kit(kit_a_venda, rota):
    html = cliente.get(rota, headers=HTML).text
    assert 'data-comprar="kit"' in html and 'class="kit-opcao"' in html
    opcao = html[html.index('class="kit-opcao"'):]
    opcao = opcao[:opcao.index("</div>")]
    assert "Leve os três por" in opcao and "R$141</s>" in opcao and "R$97" in opcao
    assert "o mapa completo, O seu ano e a sua Lua no ano" in opcao
    # embaixo do botão de compra avulsa, dentro do mesmo cartão
    assert html.index('data-comprar="kit"') > html.index('id="comprar"')
    # o corpo da compra é o mesmo da página, só troca o produto
    assert 'produto === "kit" ? "kit"' in html
    for proibido in ("promoção", "Promoção", "só hoje", "últimas"):
        assert proibido not in opcao


def test_links_mostra_o_kit_logo_abaixo_do_principal(kit_a_venda):
    html = cliente.get("/links?utm_source=tiktok", headers=HTML).text
    assert "links-bt-kit" in html
    i_principal, i_kit = html.index("links-bt-1"), html.index("links-bt-kit")
    produtos = [m.start() for m in re.finditer(r'class="links-bt" ', html)]
    assert i_principal < i_kit < min(produtos)
    bt = html[i_kit:html.index("</a>", i_kit)]
    assert 'href="/mapa?utm_source=tiktok' in bt and "R$141</s>" in bt and "R$97" in bt
    assert 'data-destino="kit"' in bt


def test_leituras_mostra_o_cartao_do_kit(kit_a_venda):
    html = cliente.get("/leituras", headers=HTML).text
    assert "capa-kit" in html
    cartao = html[html.index("capa-kit"):]
    cartao = cartao[:cartao.index("</a>")]
    assert "Os três: mapa, O seu ano e a sua Lua" in cartao and "R$141</s>" in cartao and "R$97" in cartao
    assert 'href="/mapa"' in cartao


def test_api_config_lista_o_kit_so_a_venda(kit_a_venda):
    c = cliente.get("/api/config").json()
    assert c["kits_a_venda"] == ["kit"] and None not in c["produtos_ativos"]


def test_copy_do_kit_no_yaml():
    tk = catalogo.textos()["kit"]
    for campo in ("opcao_titulo", "opcao_texto", "opcao_botao", "opcao_miudo", "links_titulo", "links_linha",
                  "leituras_botao"):
        assert tk.get(campo), campo
    with open("static/ocidental/_kit_opcao.html", encoding="utf-8") as f:
        trecho = f.read()
    assert "Leve os três" not in trecho and "R$97" not in trecho and "R$141" not in trecho  # copy e preço de fora
    sem_jinja = re.sub(r"\{\{.*?\}\}|\{#.*?#\}", "", trecho, flags=re.S)
    assert "`" not in sem_jinja and "${" not in sem_jinja  # vai dentro do template de JavaScript


# ====================================================================== checkout do kit
@precisa_banco
def test_checkout_do_kit_um_pedido_de_97(kit_a_venda, stripe_falsa, banco):
    r = cliente.post("/api/checkout", json={"produto": "kit", "pessoa": PESSOA, "email": "ana@teste.com",
                                            "preco": 1, "valor": 1, "origem": {
                                                "utm_source": "tiktok", "utm_medium": "bio", "utm_campaign": "links",
                                                "ref": "PEDRO", "utm_content": "x"}})
    assert r.status_code == 200, r.text
    params = stripe_falsa.criadas[0]["params"]
    assert len(params["line_items"]) == 1
    item = params["line_items"][0]["price_data"]
    assert item["unit_amount"] == 9700 and item["product_data"]["name"].startswith("Os três")
    # critério 5: só o pedido e os 3 utm no metadata
    for md in (params["metadata"], params["payment_intent_data"]["metadata"]):
        assert set(md) == {"pedido", "utm_source", "utm_medium", "utm_campaign"}
    texto = repr(params)
    for dado in (PESSOA["data"], PESSOA["hora"], "Porto Alegre", "Ana Clara", "-30.0331", "PEDRO"):
        assert dado not in texto
    p = db.pendente(r.json()["url"].rsplit("/", 1)[1])
    assert p["valor_centavos"] == 9700 and len(p["itens"]) == 1 and p["itens"][0]["chave"] == "kit"
    assert p["itens"][0]["dados"]["inicio"] == datetime.now(previsao.FUSO_DATAS).strftime("%Y-%m")
    # a página de pagamento mostra o kit, com o "de" riscado
    html = cliente.get(r.json()["url"]).text
    assert "Os três" in html and "R$141</s>" in html and "R$97" in html


def test_kit_sem_pessoa_e_recusado(kit_a_venda, stripe_falsa):
    r = cliente.post("/api/checkout", json={"produto": "kit", "email": "ana@teste.com"})
    assert r.status_code == 422 and stripe_falsa.criadas == []


# ====================================================================== webhook: um pedido, três entregas
def _assinar(corpo: bytes) -> str:
    t = int(time.time())
    return f"t={t},v1=" + hmac.new(SEGREDO.encode(), f"{t}.".encode() + corpo, hashlib.sha256).hexdigest()


def _postar(evento: dict):
    corpo = json.dumps(evento).encode()
    return cliente.post("/webhook/stripe", content=corpo,
                        headers={"content-type": "application/json", "stripe-signature": _assinar(corpo)})


class SessoesPagas:
    def __init__(self):
        self.sessoes = {}

    def __call__(self, session_id):
        return self.sessoes[session_id]


@pytest.fixture
def webhook(monkeypatch, ocidental):
    if not TEST_URL:
        pytest.skip("TEST_DATABASE_URL não definida")
    monkeypatch.setenv("DATABASE_URL", TEST_URL)
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", SEGREDO)
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_" + "a" * 20)
    assert db.iniciar()
    with db._conectar() as c:
        c.execute("TRUNCATE pedidos_pendentes, eventos_stripe, pedidos, abandonos, email_optout, "
                  "amostras_email, envios_sequencia")
    monkeypatch.setattr(estado_site, "salvo", lambda: {})
    sessoes = SessoesPagas()
    monkeypatch.setattr(stripe_api, "sessao", sessoes)
    enviados, avisos = [], []
    monkeypatch.setattr(entrega, "enviar_email",
                        lambda para, assunto, html, *a, **k: enviados.append((para, assunto, html)) or True)
    monkeypatch.setattr(alertas, "alertar", lambda titulo, corpo="", *a, **k: avisos.append((titulo, corpo)))
    ligar("kit", *TRES)
    return {"sessoes": sessoes, "emails": enviados, "avisos": avisos}


def _pedido(w, produto="kit", pago=True, valor=None, sessao="cs_test_kit", meio="card") -> dict:
    corpo = {"produto": produto, "pessoa": PESSOA, "email": "ana@teste.com", "origem": {"utm_source": "tiktok"}}
    p = pendentes.montar(pendentes.PedidoCheckout.model_validate(corpo))
    assert db.criar_pendente(p) and db.ligar_sessao(p["id"], sessao, sessao + "_secret")
    w["sessoes"].sessoes[sessao] = {
        "id": sessao, "status": "complete", "payment_status": "paid" if pago else "unpaid",
        "amount_total": p["valor_centavos"] if valor is None else valor, "currency": "brl",
        "payment_intent": "pi_" + sessao, "meio_pagamento": meio, "client_reference_id": p["id"],
        "metadata": {"pedido": p["id"]}}
    return p


def _evento(tipo, p, sessao="cs_test_kit", id_evento="evt_kit", **obj):
    o = {"id": sessao, "object": "checkout.session", "payment_status": "paid", "client_reference_id": p["id"],
         "metadata": {"pedido": p["id"]}}
    o.update(obj)
    return {"id": id_evento, "object": "event", "type": tipo, "data": {"object": o}}


def _links_do_email(html: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r'href="(https?://[^"]+(?:/mapa|/seu-ano|/calendario-lunar)\?[^"]+)"', html)))


def _abre_os_tres(links: list[str]):
    """Os três links abrem a leitura COMPLETA (cada token vale para o seu produto)."""
    import html as _html
    por_rota = {urlparse(_html.unescape(l)).path: _html.unescape(l) for l in links}
    assert set(por_rota) == {"/mapa", "/seu-ano", "/calendario-lunar"}
    q = {k: v[0] for k, v in parse_qs(urlparse(por_rota["/mapa"]).query).items()}
    r = cliente.post("/api/ocidental/mapa", json={**PESSOA, "nivel": "completo", "token": q["token"]})
    assert r.status_code == 200, r.text
    q = {k: v[0] for k, v in parse_qs(urlparse(por_rota["/seu-ano"]).query).items()}
    hoje = datetime.now(previsao.FUSO_DATAS).strftime("%Y-%m")
    assert q["inicio"] == hoje
    r = cliente.post("/api/ocidental/previsao", json={**PESSOA, "nivel": "completo", "inicio": q["inicio"],
                                                      "token": q["token"]})
    assert r.status_code == 200, r.text
    q = parse_qs(urlparse(por_rota["/calendario-lunar"]).query)
    assert list(q) == ["token"] and q["token"][0].startswith("oc-cal-")  # só o token cifrado
    r = cliente.post("/api/ocidental/calendario/completo", json={"token": q["token"][0]})
    assert r.status_code == 200, r.text
    for link in por_rota.values():  # a página abre com o token, mesmo com o produto oculto
        u = urlparse(link)
        assert cliente.get(f"{u.path}?{u.query}", headers=HTML).status_code == 200, link


@pytest.mark.parametrize("meio,tipo", [("card", "checkout.session.completed"),
                                        ("pix", "checkout.session.async_payment_succeeded")])
def test_kit_pago_entrega_os_tres_num_email(webhook, meio, tipo):
    p = _pedido(webhook, meio=meio)
    r = _postar(_evento(tipo, p))
    assert r.status_code == 200, r.text
    assert r.json()["email_enviado"] is True
    assert len(webhook["emails"]) == 1 and webhook["avisos"] == []
    para, assunto, html = webhook["emails"][0]
    assert para == "ana@teste.com"
    for nome in ("Mapa natal", "O seu ano", "A sua Lua no ano"):
        assert f">{nome}</a>" in html
    assert "três leituras" in html
    links = _links_do_email(html)
    assert len(links) == 3
    _abre_os_tres(links)
    with db._conectar() as c:
        produto, link, forma, valor = c.execute("SELECT produto, link, forma_pagamento, valor FROM pedidos").fetchone()
    assert produto == "ocidental:kit" and len(link.split("\n")) == 3 and float(valor) == 97.0
    assert forma == ("pix" if meio == "pix" else "cartao")
    # repetir o evento não entrega de novo
    assert _postar(_evento(tipo, p, id_evento="evt_kit_2")).json().get("duplicado") is True
    assert len(webhook["emails"]) == 1


def test_obrigado_mostra_os_tres(webhook):
    p = _pedido(webhook)
    _postar(_evento("checkout.session.completed", p))
    e = cliente.get(f"/api/checkout/{p['id']}/estado").json()
    assert e["estado"] == "pago" and [x["nome"] for x in e["links"]] == ["Mapa natal", "O seu ano", "A sua Lua no ano"]
    _abre_os_tres([x["link"] for x in e["links"]])
    html = cliente.get(f"/obrigado/{p['id']}").text
    assert 'id="acoes-kit"' in html and "T.kit_titulo" in html
    assert '"kit_titulo"' in html and '"kit_texto"' in html


def test_minhas_leituras_lista_os_tres(webhook):
    p = _pedido(webhook)
    _postar(_evento("checkout.session.completed", p))
    leituras = db.leituras_do_email("ana@teste.com")
    html = entrega.email_minhas_leituras_html(leituras)
    assert "Os três: mapa, O seu ano e a sua Lua" in html
    for nome in ("Mapa natal →", "O seu ano →", "A sua Lua no ano →"):
        assert nome in html
    assert len(_links_do_email(html)) == 3


def test_kit_com_valor_diferente_nao_entrega(webhook):
    p = _pedido(webhook, valor=4700)
    r = _postar(_evento("checkout.session.completed", p))
    assert r.status_code == 200 and "pendente" in r.json()
    assert webhook["emails"] == [] and webhook["avisos"]


def test_kit_pix_pendente_espera(webhook):
    p = _pedido(webhook, pago=False, meio="pix")
    r = _postar(_evento("checkout.session.completed", p, payment_status="unpaid"))
    assert r.json().get("aguardando") == "unpaid" and webhook["emails"] == []


def test_reembolso_do_kit_marca_o_pedido_sem_cortar_os_links(webhook):
    p = _pedido(webhook)
    _postar(_evento("checkout.session.completed", p))
    r = _postar({"id": "evt_ref", "type": "charge.refunded",
                 "data": {"object": {"payment_intent": "pi_cs_test_kit", "refunded": True, "amount_refunded": 9700}}})
    assert r.json()["pedido_encontrado"] is True
    with db._conectar() as c:
        status, link = c.execute("SELECT status, link FROM pedidos").fetchone()
    assert status == "reembolsado" and len(link.split("\n")) == 3
    _abre_os_tres(link.split("\n"))  # os links já entregues continuam abrindo


@pytest.mark.parametrize("produto,rota", [("previsao", "/seu-ano"), ("calendario", "/calendario-lunar")])
def test_bug_o_seu_ano_e_o_calendario_pagos_na_stripe_sao_entregues(webhook, produto, rota):
    """Bug achado nesta rodada: o webhook da Stripe só entregava os produtos da Cakto
    (cakto.PRODUTOS); um pagamento de "O seu ano" virava "valor diferente" e ficava sem
    entrega. Agora vale a lista do checkout próprio."""
    p = _pedido(webhook, produto=produto, sessao="cs_" + produto)
    r = _postar(_evento("checkout.session.completed", p, sessao="cs_" + produto, id_evento="evt_" + produto))
    assert r.status_code == 200 and r.json().get("email_enviado") is True, r.text
    assert webhook["avisos"] == []
    assert rota + "?" in webhook["emails"][0][2]


def test_abandono_do_kit(webhook):
    p = _pedido(webhook, pago=False)
    with db._conectar() as c:
        c.execute("UPDATE pedidos_pendentes SET criado_em = now() - interval '2 days' WHERE id = %s", (p["id"],))
    r = _postar(_evento("checkout.session.expired", p, payment_status="unpaid"))
    assert r.json().get("email_enviado") is True
    html = webhook["emails"][0][2]
    assert "os três: o mapa natal, O seu ano e a sua Lua no ano" in html and "/mapa?" in html


# ====================================================================== Fase 4: e-mails de venda
def test_escada_pos_compra_conta_o_kit():
    assert sequencias.proxima_da_escada(["ocidental:kit"]) == "compat"
    assert sequencias.proxima_da_escada(["ocidental:previsao"]) == "mapa"


def test_venda_cruzada_nao_oferece_o_que_ja_tem(ocidental):
    ligar("mapa", "compat", "numerologia", "tarot")
    bloco = marketing.bloco_venda_cruzada("tarot", {"tiragem": "x"}, "ocidental", catalogo.que_tem(["ocidental:kit"]))
    assert "Mapa natal →" not in bloco and "Numerologia →" in bloco
    sem = marketing.bloco_venda_cruzada("tarot", {"tiragem": "x"}, "ocidental")
    assert "Mapa natal →" in sem


def test_quem_tem_o_kit_nao_recebe_boas_vindas_nem_lembrete_do_que_ja_tem(webhook, monkeypatch):
    p = _pedido(webhook)
    _postar(_evento("checkout.session.completed", p))
    webhook["emails"].clear()
    with db._conectar() as c:
        c.execute("UPDATE pedidos SET criado_em = now() - interval '40 days'")  # fora do pós-compra
    for produto in TRES:
        assert db.registrar_amostra_email("ana@teste.com", produto, {**PESSOA, "inicio": "2026-10"}, True,
                                          {}, "ocidental", True)
    with db._conectar() as c:
        c.execute("UPDATE amostras_email SET criado_em = now() - interval '2 days'")
    sequencias.rodar(datetime.now(timezone.utc) + timedelta(days=1))
    assert webhook["emails"] == []


def test_aniversario_nao_vai_para_quem_tem_o_kit(webhook):
    p = _pedido(webhook)
    _postar(_evento("checkout.session.completed", p))
    nasc = date.today() + timedelta(days=sequencias.DIAS_ANTES_DO_ANIVERSARIO)
    dados = {**PESSOA, "data": f"1990-{nasc:%m-%d}"}
    assert db.registrar_amostra_email("ana@teste.com", "mapa", dados, True, {}, "ocidental", True)
    assert db.registrar_amostra_email("bia@teste.com", "mapa", {**dados, "nome": "Bia"}, True, {}, "ocidental", True)
    alvo = sequencias.aniversarios_alvo(date.today())
    ja_tem = [f"ocidental:{k}" for k in catalogo.quem_inclui("previsao")]
    emails = {c["email"] for c in db.candidatos_aniversario(alvo, ja_tem=ja_tem)}
    assert emails == {"bia@teste.com"}
    assert {c["email"] for c in db.candidatos_aniversario(alvo)} == {"ana@teste.com", "bia@teste.com"}


# ====================================================================== o painel
def test_painel_avisa_que_o_kit_precisa_dos_tres(ocidental, monkeypatch):
    monkeypatch.setattr(painel, "_revisao_por_produto", lambda: {})
    monkeypatch.setattr(estado_site, "salvo", lambda: {"produto:kit": "ativo", "produto:mapa": "ativo"})
    kit = next(p for p in painel.produtos() if p["chave"] == "kit")
    assert "precisa de Mapa natal, O seu ano e A sua Lua no ano ativos" in kit["avisos"]
    assert kit["rota"] == "/mapa" and kit["kit_faltam"] == 2
    assert "kit Os três: mapa, O seu ano e a sua Lua parado (faltam 2 produtos ativos)" in painel.resumo()
    monkeypatch.setattr(estado_site, "salvo", lambda: {f"produto:{c}": "ativo" for c in ("kit",) + TRES})
    kit = next(p for p in painel.produtos() if p["chave"] == "kit")
    assert not any("precisa de" in a for a in kit["avisos"]) and "parado" not in painel.resumo()


@pytest.mark.catalogo_real
def test_painel_kit_oculto_nao_entra_no_resumo(monkeypatch):
    monkeypatch.setattr(painel, "_revisao_por_produto", lambda: {})
    monkeypatch.setattr(estado_site, "salvo", lambda: {})
    kit = next(p for p in painel.produtos() if p["chave"] == "kit")
    assert any("precisa de" in a for a in kit["avisos"])  # a linha avisa sempre
    assert "parado" not in painel.resumo()  # o resumo, só com o kit ligado


# ====================================================================== o smoke
@pytest.mark.catalogo_real
def test_smoke_kit_oculto(ocidental, modo_stripe, stripe_falsa, monkeypatch):
    from test_smoke import _local, smoke
    _local(monkeypatch)
    nomes = [n for n, _ in smoke.CHECAGENS]
    checagem = next(f for n, f in smoke.CHECAGENS if n.startswith("[kit]"))
    assert checagem() is True
    stripe = dict(smoke.CHECAGENS_STRIPE)
    fora = next(f for n, f in stripe.items() if "fora da venda" in n)
    assert fora() is True and stripe_falsa.criadas == []
    assert any(n.startswith("[kit]") for n in nomes)


def test_smoke_reprova_kit_aparecendo_fora_da_venda(ocidental, monkeypatch):
    from test_smoke import _local, smoke
    _local(monkeypatch)
    original = smoke.req
    monkeypatch.setattr(smoke, "req", lambda c, corpo=None, timeout=90: (
        (200, b'<a class="links-bt links-bt-kit">') if c == "/links" else original(c, corpo, timeout)))
    assert next(f for n, f in smoke.CHECAGENS if n.startswith("[kit]"))() is False

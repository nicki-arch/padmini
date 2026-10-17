"""
Rodada 16.1 (16/out/2026): preço de referência riscado, "de R$97 por R$47".

Decisão do Nicolas (pergunta 20; o risco do art. 37 do CDC está em decisoes.md):
`preco_de: 97` no mapa natal e em "O seu ano". Só MOSTRA: a Stripe cobra o `preco`.
Sem `preco_de`, nada muda. A védica não muda (foto em test_sistema.py). Catálogo de verdade.
"""
import copy
import json
import re
from types import SimpleNamespace

import pytest

from test_app import app_mod, cliente  # primeiro: define os segredos de teste
import db
import marketing
import ofertas
import rotas_ocidental
import sequencias
import stripe_api
from test_rodada11_fase2 import PESSOA, SessoesFalsas

pytestmark = pytest.mark.catalogo_real
HTML = {"accept": "text/html"}
RISCADO = '<s class="preco-de"><span class="sr-only">de </span>R$97</s><span class="sr-only">, por</span> R$47'


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.setenv("PADMINI_PREVIA_CHAVE", "previa-dos-testes")
    for v in ("PADMINI_CAPTURA", "PADMINI_VENDAS_TESTE", "PADMINI_PAGAMENTO"):
        monkeypatch.delenv(v, raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


@pytest.fixture
def stripe(monkeypatch, ocidental):
    """Checkout próprio (como a produção desde 11/out), com a Stripe e o banco simulados."""
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_" + "a" * 20)
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_" + "b" * 20)
    sessoes = SessoesFalsas()
    monkeypatch.setattr(stripe_api, "_cliente",
                        lambda: SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=sessoes))))
    pendentes_db = {}

    def criar(p):
        pendentes_db[p["id"]] = {**p, "estado": "aberto"}
        return True
    monkeypatch.setattr(db, "criar_pendente", criar)
    monkeypatch.setattr(db, "ligar_sessao", lambda i, s, c: pendentes_db[i].update(
        stripe_session_id=s, stripe_client_secret=c))
    monkeypatch.setattr(db, "pendente", lambda i: pendentes_db.get(i))
    app_mod._paginas_prontas.clear()
    return SimpleNamespace(sessoes=sessoes, pendentes=pendentes_db)


@pytest.fixture
def sem_preco_de(monkeypatch):
    """O YAML sem a linha `preco_de` (como quem a apaga para voltar atrás)."""
    copia = copy.deepcopy(ofertas.POR_SISTEMA["ocidental"])
    for chave in ("mapa", "previsao"):
        copia[chave]["preco_de"] = None
        copia[chave].pop("economia", None)
        copia[chave].pop("desconto", None)
    monkeypatch.setitem(ofertas.POR_SISTEMA, "ocidental", copia)
    app_mod._paginas_prontas.clear()


def _comprar(produto="mapa", **extra):
    return cliente.post("/api/checkout", json={"produto": produto, "pessoa": PESSOA, "email": "ana@teste.com",
                                               "aceita_sequencia": False, "origem": {}, **extra})


# ------------------------------------------------------------------ o YAML e o helper
def test_yaml_tem_o_preco_de_no_mapa_e_no_seu_ano():
    for chave in ("mapa", "previsao"):
        o = ofertas.oferta(chave, "ocidental")
        assert (o["preco"], o["preco_de"]) == (47, 97), chave
    # a védica não ganhou nada
    assert ofertas.oferta("mapa", "vedica")["preco_de"] is None


def test_helper_so_mostra_quando_o_de_e_maior():
    assert ofertas.html_preco_de({"preco": 47, "preco_de": 97}).startswith('<s class="preco-de">')
    assert ofertas.texto_preco({"preco": 47, "preco_de": 97}) == "de R$97 por R$47"
    for o in ({"preco": 47, "preco_de": None}, {"preco": 47}, {"preco": 47, "preco_de": 47}, {"preco": 47, "preco_de": 30}):
        assert ofertas.html_preco_de(o) == "" and ofertas.texto_preco(o) == "R$47", o


# ------------------------------------------------------------------ as páginas
def _paginas(stripe_ativo: bool) -> dict:
    return {rota: cliente.get(rota, headers=HTML).text for rota in ("/", "/mapa", "/leituras")}


@pytest.fixture
def seu_ano_ligado(ocidental):
    """"O seu ano" continua oculto; o riscado da lateral dele é conferido como se estivesse
    ligado (a lateral só mostra preço quando o catálogo vende o produto)."""
    import catalogo
    original = catalogo.dados()
    d = copy.deepcopy(original)
    next(p for p in d["produtos"] if p["chave"] == "previsao")["estado"] = "ativo"
    catalogo.usar(d)
    app_mod._paginas_prontas.clear()
    yield
    catalogo.usar(original)
    app_mod._paginas_prontas.clear()


@pytest.mark.parametrize("modo", ["cakto", "stripe"])
def test_paginas_mostram_de_97_por_47(request, modo, ocidental):
    if modo == "stripe":
        request.getfixturevalue("stripe")
    for rota, html in _paginas(modo == "stripe").items():
        assert RISCADO in html, rota
        assert "R$97" not in html.replace(RISCADO, ""), rota  # o 97 só aparece riscado
    mapa = cliente.get("/mapa", headers=HTML).text
    # lateral da amostra + o botão "Desbloquear por <s>R$97</s> R$47"
    assert mapa.count(RISCADO) >= 2
    assert "${esc(TA.botao_comprar)} " + RISCADO + "</a>" in mapa


@pytest.mark.parametrize("com_preco_de", [True, False])
def test_lateral_do_seu_ano(request, stripe, seu_ano_ligado, com_preco_de):
    if not com_preco_de:
        request.getfixturevalue("sem_preco_de")
    html = cliente.get("/seu-ano", headers=HTML).text
    if com_preco_de:
        assert f'<span class="preco">{RISCADO}</span>' in html
        assert "${esc(TA.botao_comprar)} " + RISCADO + "</a>" in html
    else:
        assert "preco-de" not in html and "${esc(TA.botao_comprar)} R$47</a>" in html


def test_o_riscado_nao_quebra_o_template_string_do_js():
    """A amostra é montada por JavaScript dentro de crases: o pedaço não pode ter ` nem ${."""
    h = ofertas.html_preco_de(ofertas.oferta("mapa", "ocidental"))
    assert "`" not in h and "${" not in h


def test_sem_preco_de_volta_a_mostrar_so_47(ocidental, sem_preco_de):
    for rota, html in _paginas(False).items():
        assert "preco-de" not in html and "R$97" not in html, rota
        assert "R$47" in html, rota


def test_sem_promocao_nem_prazo(ocidental):
    for rota, html in _paginas(False).items():
        baixo = html.lower()
        for proibido in ("promoção", "promocao", "tempo limitado", "por tempo", "só hoje", "contagem regressiva",
                         "últimas horas"):
            assert proibido not in baixo, (rota, proibido)
        assert not re.search(r"-\s?\d{2}\s?%", re.sub(r"<style.*?</style>|<script.*?</script>", "", html, flags=re.S)), rota


def test_o_seu_ano_continua_oculto(ocidental):
    cliente.cookies.clear()  # sem o cookie de prévia de outro teste
    assert cliente.get("/seu-ano", headers=HTML).status_code == 404


# ------------------------------------------------------------------ checkout e Stripe
def test_stripe_cobra_47_e_nunca_recebe_o_preco_de(stripe):
    r = _comprar()
    assert r.status_code == 200, r.text
    params = stripe.sessoes.criadas[-1]["params"]
    linha = params["line_items"][0]["price_data"]
    assert linha["unit_amount"] == 4700 and linha["currency"] == "brl"
    tudo = json.dumps(params, ensure_ascii=False)
    assert "9700" not in tudo and "97" not in re.sub(r'"(id|client_reference_id|pedido)": "[^"]*"', "", tudo)
    pid = r.json()["url"].rsplit("/", 1)[1]
    assert stripe.pendentes[pid]["valor_centavos"] == 4700


def test_resumo_do_checkout_mostra_97_riscado_e_47(stripe):
    pid = _comprar().json()["url"].rsplit("/", 1)[1]
    html = cliente.get(f"/checkout/{pid}", headers=HTML).text
    assert f'<span class="preco">{RISCADO}</span>' in html


def test_resumo_do_checkout_sem_preco_de(stripe, sem_preco_de):
    pid = _comprar().json()["url"].rsplit("/", 1)[1]
    html = cliente.get(f"/checkout/{pid}", headers=HTML).text
    assert '<span class="preco">R$47</span>' in html and "preco-de" not in html


def test_resumo_sem_riscado_se_o_valor_nao_e_o_de_tabela():
    """Com cupom (ou valor diferente do `preco`), o "de" não aparece: ele só compara com o preço de tabela."""
    pedido = {"valor_centavos": 4700, "cupom": "pedro"}
    assert app_mod._valor_de("mapa", pedido) == ""
    assert app_mod._valor_de("mapa", {"valor_centavos": 3000, "cupom": None}) == ""
    assert app_mod._valor_de("mapa", {"valor_centavos": 4700, "cupom": None}).startswith('<s class="preco-de">')


# ------------------------------------------------------------------ e-mails
def test_emails_que_ja_tinham_preco_mostram_de_97_por_47(ocidental):
    PES = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30", "lat": -23.55, "lon": -46.63, "cidade": "São Paulo"}
    amostra = marketing.email_amostra_html("mapa", rotas_ocidental.montar_amostra_email("mapa", PES), PES,
                                           "a@b.co", "Ana", "ocidental")
    assert "Quero o completo — de R$97 por R$47 →" in amostra
    for passo, texto in ((2, "Ver o completo — de R$97 por R$47 →"), (3, "Quero o completo — de R$97 por R$47 →")):
        assert texto in sequencias.email_boas_vindas(passo, "mapa", PES, "a@b.co")[1]
    # e-mail que não mostrava preço continua sem preço
    assert "R$" not in sequencias.email_boas_vindas(1, "mapa", PES, "a@b.co")[1]
    m = sequencias.email_pos_compra(1, "ocidental:mapa", "Ana", "a@b.co", ["ocidental:mapa"])
    assert m and "R$" not in m[1]
    # sem sr-only em e-mail (não há CSS para escondê-lo): o texto é corrido
    assert "sr-only" not in amostra


def test_emails_sem_preco_de_mostram_so_47(ocidental, sem_preco_de):
    PES = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30", "lat": -23.55, "lon": -46.63, "cidade": "São Paulo"}
    html = sequencias.email_boas_vindas(3, "mapa", PES, "a@b.co")[1]
    assert "Quero o completo — R$47 →" in html and "R$97" not in html


def test_email_da_vedica_nao_muda(monkeypatch):
    monkeypatch.setitem(ofertas.OFERTAS, "mapa", {**ofertas.OFERTAS["mapa"], "preco_de": 97})
    html = marketing.email_amostra_html("mapa", {}, {"nome": "Ana", "data": "1990-05-15", "hora": "14:30",
                                                     "lat": -23.55, "lon": -46.63}, "a@b.co", "Ana", "vedica")
    assert "R$97" not in html and f"R${ofertas.moeda(ofertas.OFERTAS['mapa']['preco'])}" in html

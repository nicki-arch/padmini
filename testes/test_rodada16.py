"""
Rodada 16 (16/out/2026), Fase 1: venda do mapa natal aberta, R$47 preço único.

Decisões do Nicolas: mapa a R$47 (sem preço de lançamento nem de fundador); a venda abre
com a revisão da Dona Valderez em andamento (o selo de revisado continua só nos textos com
`revisado: true`); "O seu ano" recebe R$47 e continua OCULTO. Estes testes usam o catálogo
DE VERDADE (sem a venda aberta à força do conftest).
"""
import re

import pytest

from test_app import app_mod, cliente  # primeiro: define os segredos de teste
import catalogo
import ofertas
import pendentes
import textos
from test_rodada11_fase2 import PESSOA, SessoesFalsas  # noqa: F401
import stripe_api

pytestmark = pytest.mark.catalogo_real
HTML = {"accept": "text/html"}


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    monkeypatch.delenv("PADMINI_VENDAS_TESTE", raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


@pytest.fixture
def stripe(monkeypatch, ocidental):
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_" + "a" * 20)
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_" + "b" * 20)
    sessoes = SessoesFalsas()
    from types import SimpleNamespace
    monkeypatch.setattr(stripe_api, "_cliente",
                        lambda: SimpleNamespace(v1=SimpleNamespace(checkout=SimpleNamespace(sessions=sessoes))))
    app_mod._paginas_prontas.clear()
    return sessoes


def test_precos_decididos():
    assert ofertas.oferta("mapa", "ocidental")["preco"] == 47
    assert ofertas.oferta("previsao", "ocidental")["preco"] == 47
    assert pendentes.valor_centavos("mapa") == 4700 and pendentes.valor_centavos("previsao") == 4700
    # preço único: nada de "de/por", lançamento ou fundador no YAML do mapa
    mapa = ofertas.oferta("mapa", "ocidental")
    assert mapa["preco_de"] is None and mapa["preco_cupom"] is None and not mapa["cupom_codigos"]


def test_venda_aberta_so_o_mapa_e_o_seu_ano_continua_oculto():
    assert catalogo.vendas_abertas()
    assert catalogo.vende("mapa")
    assert catalogo.estado("previsao") == "oculto" and not catalogo.vende("previsao")
    for chave in ("compat", "numerologia", "tarot"):
        assert catalogo.estado(chave) == "em_breve" and not catalogo.vende(chave), chave


def test_config_diz_venda_aberta(ocidental):
    assert cliente.get("/api/config").json()["vendas_abertas"] is True


@pytest.mark.parametrize("pagamento", ["cakto", "stripe"])
def test_amostra_do_mapa_vende_por_47_e_o_me_avise_do_mapa_some(request, pagamento, ocidental, monkeypatch):
    if pagamento == "stripe":
        request.getfixturevalue("stripe")
    else:
        monkeypatch.delenv("PADMINI_PAGAMENTO", raising=False)
    html = cliente.get("/mapa", headers=HTML).text
    assert 'data-me-avise="mapa"' not in html and "A leitura completa abre em breve" not in html
    # o botão da amostra: "Desbloquear por" (mapa.yaml) + o preço do ofertas.yaml
    assert textos.da_pagina("mapa", "ocidental")["amostra"]["botao_comprar"] == "Desbloquear por"
    assert "${esc(TA.botao_comprar)} R$47</a>" in html and "R$37" not in html
    if pagamento == "stripe":
        assert 'data-comprar="mapa"' in html and "pay.cakto" not in html


def test_em_breve_continua_com_o_me_avise_e_sem_preco(ocidental):
    for rota, chave in (("/compatibilidade", "compat"), ("/numerologia", "numerologia"), ("/tarot", "tarot")):
        html = cliente.get(rota, headers=HTML).text
        assert f'data-me-avise="{chave}"' in html, rota
        assert not re.search(r"R\$\s?\d", html), rota


def test_nenhuma_pagina_mostra_o_preco_antigo(ocidental):
    for rota in ("/", "/mapa", "/leituras", "/lista"):
        assert "R$37" not in cliente.get(rota, headers=HTML).text, rota


def test_faq_da_venda_aparece(ocidental):
    home = cliente.get("/").text
    assert "Como pago?" in home and "Quando abre a leitura completa?" not in home
    assert [i["pergunta"] for i in textos.faq(textos.da_pagina("home", "ocidental")["faq"]["itens"], True)
            if i.get("so_sem_venda")] == []


def test_checkout_da_stripe_cobra_47(stripe):
    r = cliente.post("/api/checkout", json={"produto": "mapa", "pessoa": PESSOA, "email": "ana@teste.com",
                                            "aceita_sequencia": False, "origem": {}})
    if r.status_code == 503:  # sem banco não há checkout (falha fechada); o valor sai do pendente
        assert pendentes.valor_centavos("mapa") == 4700
        return
    assert r.status_code == 200, r.text
    linha = stripe.criadas[-1]["params"]["line_items"][0]["price_data"]
    assert linha["unit_amount"] == 4700 and linha["currency"] == "brl"


def test_o_seu_ano_nao_e_vendido_mesmo_com_preco(stripe):
    r = cliente.post("/api/checkout", json={"produto": "previsao", "pessoa": PESSOA, "email": "ana@teste.com",
                                            "aceita_sequencia": False, "origem": {}})
    assert r.status_code == 404 and stripe.criadas == []
    assert cliente.get("/seu-ano", headers=HTML).status_code == 404


def test_selo_de_revisado_continua_honesto(ocidental):
    assert not textos.tudo_revisado()
    for rota in ("/", "/mapa", "/leituras"):
        assert "revisad" not in cliente.get(rota, headers=HTML).text.lower(), rota


def test_smoke_nao_confere_a_cakto_da_ocidental_com_a_stripe_no_ar(monkeypatch):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "smoke16", Path(__file__).resolve().parents[1] / "scripts" / "smoke_producao.py")
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    vistas = []
    monkeypatch.setattr(smoke, "conferir_precos_na_cakto", lambda o: vistas.append(o) or [])
    monkeypatch.setattr(smoke, "_ofertas_do_yaml", lambda v: v)
    monkeypatch.setattr(smoke, "_versao_no_ar", lambda: "ocidental")
    nome, f = next((n, f) for n, f in smoke.CHECAGENS if "bate com o que a Cakto" in n)
    monkeypatch.setattr(smoke, "_pagamento_no_ar", lambda: "stripe")
    assert f() and vistas == ["vedica"] and any("quem cobra é a Stripe" in a for a in smoke.AVISOS)
    vistas.clear()
    monkeypatch.setattr(smoke, "_pagamento_no_ar", lambda: "cakto")
    assert f() and vistas == ["vedica", "ocidental"]


def test_vitrine_dos_emails_abre_com_o_catalogo_de_verdade(ocidental, monkeypatch):
    """/estilo?previa= é onde o Nicolas aprova os e-mails. Com a sinastria em breve, o
    pós-compra passo 2 (oferecer a próxima leitura) não sai, e a página dava 500."""
    import sequencias
    monkeypatch.setenv("PADMINI_PREVIA_CHAVE", "previa-dos-testes")
    assert sequencias.email_pos_compra(2, "ocidental:mapa", "Ana", "a@b.co", ["ocidental:mapa"]) is None
    r = cliente.get("/estilo?previa=previa-dos-testes", headers=HTML)
    assert r.status_code == 200 and "Pós-compra 1/3" in r.text and "Pós-compra 3/3" in r.text
    assert "Pós-compra 2/3" not in r.text

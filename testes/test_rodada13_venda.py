"""
Rodada 13, Fase 4: a venda de "O seu ano" pronta e DESLIGADA. O produto existe no catálogo
(oculto) e no ofertas.yaml (sem preço); o checkout é o da Stripe, como o do mapa; o mapa
completo mostra o cartão "O seu ano" só com o produto ativo; o e-mail de aniversário (30 dias
antes, só com consentimento e descadastro) só sai com o produto à venda.
"""
import copy
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

import test_app as base  # configura o ambiente e o app
from test_rodada11_fase2 import banco, modo_stripe, precisa_banco, stripe_falsa  # noqa: F401  (fixtures)

import acesso  # noqa: E402
import app as app_mod  # noqa: E402
import catalogo  # noqa: E402
import db  # noqa: E402
import entrega  # noqa: E402
import marketing  # noqa: E402
import ofertas  # noqa: E402
import previsao  # noqa: E402
import sequencias  # noqa: E402

cliente = base.cliente
HTML = {"accept": "text/html"}
PESSOA = {"nome": "Ana Clara", "data": "1995-01-10", "hora": "21:40", "lat": -22.9068, "lon": -43.1729,
          "cidade": "Rio de Janeiro, RJ"}


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


@pytest.fixture
def previsao_ligada(monkeypatch):
    """Simula o Nicolas ligando o produto: ativo no catálogo, venda aberta e um preço."""
    dados = copy.deepcopy(catalogo.dados())
    dados["vendas_abertas"] = True
    for p in dados["produtos"]:
        if p["chave"] == "previsao":
            p["estado"] = "ativo"
    catalogo.usar(dados)
    original = ofertas.oferta
    monkeypatch.setattr(ofertas, "oferta", lambda chave, sistema="vedica": (
        {"nome": "O seu ano", "preco": 47} if chave == "previsao" and sistema == "ocidental" else original(chave, sistema)))
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


# ------------------------------------------------------------------ desligado em produção
@pytest.mark.catalogo_real
def test_em_producao_esta_desligado_com_o_preco_decidido():
    """Rodada 16: o preço (R$47) foi decidido, mas o produto continua OCULTO: ter preço não
    liga nada (a venda está aberta e mesmo assim o catálogo não vende "O seu ano")."""
    assert catalogo.vendas_abertas()
    assert catalogo.estado("previsao") == "oculto" and not catalogo.vende("previsao")
    oferta = ofertas.oferta("previsao", "ocidental")
    assert oferta and oferta["nome"] and oferta["preco"] == 47 and not oferta.get("checkout")


@pytest.mark.catalogo_real
def test_nao_liga_sem_preco():
    """A trava: ligar "O seu ano" no catalogo.yaml sem pôr o preço no ofertas.yaml derruba o CI
    (a página de venda mostraria R$ vazio e o checkout recusaria)."""
    if catalogo.estado("previsao") != "oculto":
        assert ofertas.oferta("previsao", "ocidental").get("preco"), "ponha o preço em ofertas.yaml"


def test_checkout_recusa_com_o_produto_oculto(ocidental, modo_stripe, stripe_falsa):
    r = cliente.post("/api/checkout", json={"produto": "previsao", "pessoa": PESSOA, "email": "ana@teste.com"})
    assert r.status_code == 404
    assert stripe_falsa.criadas == []


def test_sem_preco_o_checkout_recusa_mesmo_ligado(ocidental, modo_stripe, stripe_falsa):
    dados = copy.deepcopy(catalogo.dados())
    for p in dados["produtos"]:
        if p["chave"] == "previsao":
            p["estado"] = "ativo"
    catalogo.usar(dados)
    r = cliente.post("/api/checkout", json={"produto": "previsao", "pessoa": PESSOA, "email": "ana@teste.com"})
    assert r.status_code in (409, 422, 503) and stripe_falsa.criadas == []


@precisa_banco
def test_checkout_pela_stripe_quando_ligado(ocidental, modo_stripe, stripe_falsa, banco, previsao_ligada):
    r = cliente.post("/api/checkout", json={"produto": "previsao", "pessoa": PESSOA, "email": "ana@teste.com",
                                            "preco": 1})  # preço do navegador: ignorado
    assert r.status_code == 200, r.text
    params = stripe_falsa.criadas[0]["params"]
    item = params["line_items"][0]["price_data"]
    assert item["unit_amount"] == 4700 and item["product_data"]["name"] == "O seu ano"
    texto = repr(params)
    for dado in (PESSOA["data"], PESSOA["hora"], "Rio de Janeiro", "Ana Clara"):
        assert dado not in texto  # nenhum dado de nascimento na Stripe
    pendente = db.pendente(r.json()["url"].rsplit("/", 1)[1])
    dados = pendente["itens"][0]["dados"]
    assert dados["inicio"] == datetime.now(previsao.FUSO_DATAS).strftime("%Y-%m")  # o mês da compra


# ------------------------------------------------------------------ entrega
def test_link_de_entrega_abre_o_ano_comprado(ocidental):
    dados = {**PESSOA, "inicio": "2026-10"}
    link = entrega.link_completo("previsao", dados, "ocidental")
    u = urlparse(link)
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    # rodada 20.3: só o token (oc-ano-), com o ano comprado dentro
    assert u.path == "/seu-ano" and list(q) == ["token"] and q["token"].startswith("oc-ano-")
    assert acesso.abrir_token_cifrado("previsao", q["token"])["inicio"] == "2026-10"
    r = cliente.post("/api/ocidental/previsao", json={"nivel": "completo", "token": q["token"]})
    assert r.status_code == 200 and r.json()["inicio"] == "2026-10-01"
    assert cliente.get(f"/seu-ano?{u.query}", headers=HTML).status_code == 200  # abre mesmo oculto


def test_email_de_entrega_e_minhas_leituras():
    html = entrega.email_completo_html("previsao", "https://x/seu-ano?token=oc-1", "Ana", "", "ocidental")
    assert "o seu ano completo" in html.lower()
    assert entrega.nome_da_leitura("ocidental:previsao") == "O seu ano"


# ------------------------------------------------------------------ cartão no mapa completo
def test_cartao_o_seu_ano_so_com_o_produto_ativo(ocidental, previsao_ligada):
    assert 'id="cartao-seu-ano"' in cliente.get("/mapa", headers=HTML).text


@pytest.mark.catalogo_real
def test_sem_cartao_com_o_produto_oculto(ocidental):
    assert 'id="cartao-seu-ano"' not in cliente.get("/mapa", headers=HTML).text


# ------------------------------------------------------------------ e-mail de aniversário
def test_quem_faz_aniversario_daqui_a_30_dias():
    assert sequencias.aniversarios_alvo(date(2026, 10, 15)) == ["11-14"]
    assert sequencias.aniversarios_alvo(date(2027, 1, 30)) == ["03-01", "02-29"]  # 2027 não é bissexto
    assert sequencias.aniversarios_alvo(date(2028, 1, 30)) == ["02-29"]           # 2028 é


def test_email_de_aniversario_tom_e_descadastro():
    assunto, html = sequencias.email_aniversario(PESSOA, "ana@teste.com", date(2027, 1, 10))
    assert assunto == "O seu ano astrológico começa em 10 de janeiro"
    assert "Olá Ana" in html and "/seu-ano?" in html and "Descadastrar" in html
    assert "R$" not in html
    for proibido in (" vai ", "com certeza", "destino"):
        assert proibido not in html.lower()


def test_aniversario_desligado_com_o_produto_oculto(monkeypatch):
    chamado = []
    monkeypatch.setattr(db, "candidatos_aniversario", lambda *a, **k: chamado.append(1) or [])
    sequencias.rodar_aniversarios(date(2026, 10, 15), set(), {"enviado": 0})
    assert chamado == []  # nem consulta o banco


@precisa_banco
def test_aniversario_um_por_ano_e_so_com_consentimento(monkeypatch, previsao_ligada):
    monkeypatch.setenv("DATABASE_URL", base.os.environ.get("TEST_DATABASE_URL", ""))
    assert db.iniciar()
    with db._conectar() as c:
        c.execute("TRUNCATE amostras_email, envios_sequencia, email_optout")
    hoje = date(2026, 12, 11)  # aniversário em 10/01 → daqui a 30 dias
    nasc = {**PESSOA, "data": "1995-01-10"}
    db.registrar_amostra_email("sim@teste.com", "mapa", nasc, True, {}, "ocidental", aceita_sequencia=True)
    db.registrar_amostra_email("nao@teste.com", "mapa", nasc, False, {}, "ocidental", aceita_sequencia=False)
    db.registrar_amostra_email("outro@teste.com", "mapa", {**PESSOA, "data": "1995-03-10"}, True, {}, "ocidental",
                               aceita_sequencia=True)
    enviados = []
    monkeypatch.setattr(entrega, "enviar_email", lambda para, assunto, html, **k: enviados.append((para, assunto)) or True)
    contagem = {"enviado": 0, "pulado": 0, "falhou": 0, "repetido": 0}
    sequencias.rodar_aniversarios(hoje, set(), contagem)
    sequencias.rodar_aniversarios(hoje, set(), contagem)  # a tarefa roda de novo no mesmo dia
    assert enviados == [("sim@teste.com", "O seu ano astrológico começa em 10 de janeiro")]
    # descadastrado: nunca mais
    with db._conectar() as c:
        c.execute("TRUNCATE envios_sequencia")
        c.execute("INSERT INTO email_optout (email) VALUES ('sim@teste.com')")
    sequencias.rodar_aniversarios(hoje, set(), contagem)
    assert len(enviados) == 1


def test_boas_vindas_nao_empurra_produto_que_nao_esta_a_venda(monkeypatch):
    item = {"id": 1, "email": "a@b.c", "produto": "previsao", "dados": {}, "sistema": "ocidental",
            "criado_em": datetime.now(timezone.utc) - timedelta(days=3), "feitos": 0, "recebeu_hoje": False}
    monkeypatch.setattr(db, "ativo", lambda: True)
    monkeypatch.setattr(db, "candidatos_pos_compra", lambda: [])
    monkeypatch.setattr(db, "candidatos_boas_vindas", lambda: [item])
    monkeypatch.setattr(db, "candidatos_aniversario", lambda *a, **k: [])
    monkeypatch.setattr(sequencias, "_enviar", lambda *a, **k: pytest.fail("não devia enviar"))
    sequencias.rodar()

"""
Rodada 11, Fase 1 — checkout próprio com a Stripe: os interruptores e o pedido pendente.

  - PADMINI_PAGAMENTO=cakto|stripe (padrão cakto); valor desconhecido derruba a subida;
  - PADMINI_VENDAS_TESTE=1 abre a venda só com a Stripe em modo de teste; com chave de
    produção, sem chave ou com a Cakto, o site não sobe e diz por quê;
  - o pedido pendente: preço do ofertas.yaml (nunca do navegador), cupom aplicado no
    servidor, id opaco, dados de cada leitura; não pago sai em 7 dias.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

import test_app as base  # configura o ambiente e o app  # noqa: F401

import catalogo  # noqa: E402
import db  # noqa: E402
import pagamento  # noqa: E402
import pendentes  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
CHAVE_TESTE = "sk_test_" + "x" * 24     # montadas em partes: nada aqui parece chave de verdade
CHAVE_LIVE = "sk_live_" + "x" * 24


@pytest.fixture(autouse=True)
def _sem_stripe(monkeypatch):
    for v in ("PADMINI_PAGAMENTO", "PADMINI_VENDAS_TESTE", "STRIPE_SECRET_KEY"):
        monkeypatch.delenv(v, raising=False)


def _subir(**env) -> subprocess.CompletedProcess:
    ambiente = {k: v for k, v in os.environ.items()
                if k not in ("PADMINI_PAGAMENTO", "PADMINI_VENDAS_TESTE", "STRIPE_SECRET_KEY")}
    ambiente.update(env)
    return subprocess.run([sys.executable, "-c", "import app"], cwd=RAIZ, env=ambiente,
                          capture_output=True, text=True, timeout=120)


# ------------------------------------------------------------------ PADMINI_PAGAMENTO
def test_padrao_e_cakto(monkeypatch):
    assert pagamento.modo() == "cakto" and not pagamento.stripe()
    monkeypatch.setenv("PADMINI_PAGAMENTO", " Stripe ")
    assert pagamento.modo() == "stripe"


def test_pagamento_desconhecido_e_erro_claro(monkeypatch):
    monkeypatch.setenv("PADMINI_PAGAMENTO", "strype")
    with pytest.raises(pagamento.PagamentoInvalido, match="cakto.*stripe"):
        pagamento.validar_na_subida()


def test_app_nao_sobe_com_pagamento_desconhecido():
    r = _subir(PADMINI_PAGAMENTO="paypal")
    assert r.returncode != 0
    assert "PADMINI_PAGAMENTO='paypal' não existe" in r.stderr


def test_app_sobe_com_stripe_sem_venda_de_teste():
    assert _subir(PADMINI_PAGAMENTO="stripe").returncode == 0


# ------------------------------------------------------------------ PADMINI_VENDAS_TESTE
def test_venda_de_teste_com_chave_de_producao_nao_sobe(monkeypatch):
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    monkeypatch.setenv("PADMINI_VENDAS_TESTE", "1")
    monkeypatch.setenv("STRIPE_SECRET_KEY", CHAVE_LIVE)
    with pytest.raises(pagamento.PagamentoInvalido, match="sk_test_") as erro:
        pagamento.validar_na_subida()
    assert CHAVE_LIVE not in str(erro.value)  # a mensagem diz o prefixo, nunca a chave


def test_app_nao_sobe_com_venda_de_teste_e_chave_de_producao():
    r = _subir(PADMINI_PAGAMENTO="stripe", PADMINI_VENDAS_TESTE="1", STRIPE_SECRET_KEY=CHAVE_LIVE)
    assert r.returncode != 0
    assert "PADMINI_VENDAS_TESTE=1 exige STRIPE_SECRET_KEY de TESTE" in r.stderr
    assert CHAVE_LIVE not in r.stderr and CHAVE_LIVE not in r.stdout


def test_app_nao_sobe_com_venda_de_teste_na_cakto():
    r = _subir(PADMINI_VENDAS_TESTE="1", STRIPE_SECRET_KEY=CHAVE_TESTE)
    assert r.returncode != 0
    assert "só vale com PADMINI_PAGAMENTO=stripe" in r.stderr


@pytest.mark.parametrize("chave", ["", "pk_test_abc", "whsec_abc"])
def test_venda_de_teste_sem_chave_secreta_de_teste_nao_sobe(monkeypatch, chave):
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    monkeypatch.setenv("PADMINI_VENDAS_TESTE", "1")
    monkeypatch.setenv("STRIPE_SECRET_KEY", chave)
    with pytest.raises(pagamento.PagamentoInvalido):
        pagamento.vendas_teste()


def test_venda_de_teste_valor_desconhecido(monkeypatch):
    monkeypatch.setenv("PADMINI_VENDAS_TESTE", "sim")
    with pytest.raises(pagamento.PagamentoInvalido, match="Use 1"):
        pagamento.vendas_teste()


@pytest.mark.catalogo_real
def test_venda_de_teste_abre_a_venda_so_com_stripe_de_teste(monkeypatch):
    assert catalogo.dados()["vendas_abertas"] is False  # o YAML continua fechado
    assert not catalogo.vendas_abertas() and not catalogo.vende("mapa")
    monkeypatch.setenv("PADMINI_VENDAS_TESTE", "0")
    assert not catalogo.vendas_abertas()
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    monkeypatch.setenv("PADMINI_VENDAS_TESTE", "1")
    monkeypatch.setenv("STRIPE_SECRET_KEY", CHAVE_TESTE)
    assert catalogo.vendas_abertas() and catalogo.vende("mapa")
    assert not catalogo.vende("compat")  # em breve continua em breve
    assert catalogo.dados()["vendas_abertas"] is False


@pytest.mark.catalogo_real
def test_app_sobe_com_venda_de_teste_e_chave_de_teste():
    r = _subir(PADMINI_PAGAMENTO="stripe", PADMINI_VENDAS_TESTE="1", STRIPE_SECRET_KEY=CHAVE_TESTE)
    assert r.returncode == 0, r.stderr


# ------------------------------------------------------------------ o pedido pendente
PESSOA = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30", "lat": -30.03, "lon": -51.23,
          "cidade": "Porto Alegre, RS"}


def _pedido(**extra) -> pendentes.PedidoCheckout:
    corpo = {"produto": "mapa", "pessoa": PESSOA, "email": "Ana@Teste.com", "aceita_sequencia": True,
             "origem": {"ref": "PEDRO", "utm_source": "tiktok", "fbclid": "x" * 10}}
    corpo.update(extra)
    return pendentes.PedidoCheckout.model_validate(corpo)


def test_pendente_tem_preco_do_catalogo_e_dados_da_leitura():
    p = pendentes.montar(_pedido())
    assert p["valor_centavos"] == 3700  # ofertas.yaml (ocidental): mapa = 37
    assert p["itens"] == [{"chave": "mapa", "valor_centavos": 3700,
                           "dados": {"nome": "Ana", "data": "1990-05-15", "hora": "14:30",
                                     "lat": -30.03, "lon": -51.23, "cidade": "Porto Alegre, RS"}}]
    assert p["email"] == "ana@teste.com" and p["nome"] == "Ana" and p["moeda"] == "brl"
    assert p["consentimentos"] == {"aceita_sequencia": True}
    assert p["rastreio"] == {"ref": "PEDRO", "utm_source": "tiktok"}  # só o que conhecemos


@pytest.mark.parametrize("adulterado", [
    {"preco": 1}, {"valor": 0.5}, {"valor_centavos": 1}, {"amount": 100}, {"unit_amount": 100},
    {"price_data": {"unit_amount": 100}}, {"itens": [{"chave": "mapa", "valor_centavos": 1}]},
])
def test_pendente_nunca_grava_preco_vindo_do_navegador(adulterado):
    p = pendentes.montar(_pedido(**adulterado))
    assert p["valor_centavos"] == 3700 and p["itens"][0]["valor_centavos"] == 3700
    for chave in adulterado:
        assert chave not in p["itens"][0]["dados"]


def test_preco_adulterado_dentro_da_pessoa_e_ignorado():
    p = pendentes.montar(_pedido(pessoa={**PESSOA, "preco": 1, "valor_centavos": 1}))
    assert p["valor_centavos"] == 3700
    assert set(p["itens"][0]["dados"]) == {"nome", "data", "hora", "lat", "lon", "cidade"}


def test_cupom_aplicado_no_servidor_so_onde_vale():
    sinastria = {"produto": "compat", "pessoa": None, "a": PESSOA, "b": {**PESSOA, "nome": "Bia"}}
    com = pendentes.montar(_pedido(**sinastria, origem={"cupom": "PEDRO"}))
    assert com["cupom"] == "pedro" and com["valor_centavos"] == 9652  # 127 − 24%, calculado aqui
    assert com["nome"] == "Ana e Bia"
    sem = pendentes.montar(_pedido(**sinastria, origem={"cupom": "INVENTADO"}))
    assert sem["cupom"] is None and sem["valor_centavos"] == 12700
    mapa = pendentes.montar(_pedido(origem={"cupom": "pedro"}))  # o cupom é só da sinastria
    assert mapa["cupom"] is None and mapa["valor_centavos"] == 3700


def test_pendente_sem_taxa_da_plataforma():
    """Na Stripe a pessoa paga só o preço: os R$0,99 da Cakto não entram."""
    assert pendentes.valor_centavos("numerologia") == 2700 and pendentes.valor_centavos("tarot") == 1900


def test_id_opaco_e_unico():
    ids = {pendentes.novo_id() for _ in range(200)}
    assert len(ids) == 200
    p = pendentes.montar(_pedido())
    assert len(p["id"]) >= 22 and "ana" not in p["id"].lower() and "mapa" not in p["id"]


@pytest.mark.parametrize("extra,erro", [
    ({"email": "sem-arroba"}, "e-mail"),
    ({"pessoa": None}, "nascimento"),
    ({"produto": "compat", "a": PESSOA, "b": None}, "duas pessoas"),
    ({"produto": "numerologia", "nome": "", "data": "1990-05-15"}, "nome completo"),
    ({"produto": "tarot", "tiragem": " "}, "tiragem"),
])
def test_pedido_incompleto_e_recusado(extra, erro):
    with pytest.raises(pendentes.PedidoInvalido, match=erro):
        pendentes.montar(_pedido(**extra))


def test_produto_fora_da_lista_nao_valida():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        _pedido(produto="bump_mapas_casal")


# ------------------------------------------------------------------ no banco
TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
precisa_banco = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL não definida")


@pytest.fixture
def banco(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_URL)
    assert db.iniciar()
    with db._conectar() as c:
        c.execute("TRUNCATE pedidos_pendentes")
    yield


def _linhas(sql, *args):
    with db._conectar() as c:
        return c.execute(sql, args).fetchall()


def test_sem_banco_o_pendente_nao_e_criado(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert db.criar_pendente(pendentes.montar(_pedido())) is False
    assert db.pendente("qualquer") is None and db.limpar_pendentes() is None


@precisa_banco
def test_pendente_no_banco(banco):
    p = pendentes.montar(_pedido(preco=1))
    assert db.criar_pendente(p)
    lido = db.pendente(p["id"])
    assert lido["estado"] == "aberto" and lido["valor_centavos"] == 3700
    assert lido["itens"] == p["itens"] and lido["rastreio"] == {"ref": "PEDRO", "utm_source": "tiktok"}
    assert lido["stripe_session_id"] is None
    tudo = _linhas("SELECT row_to_json(pedidos_pendentes)::text FROM pedidos_pendentes")[0][0]
    assert '"preco"' not in tudo and "fbclid" not in tudo


@precisa_banco
def test_sessao_e_estados(banco):
    p = pendentes.montar(_pedido())
    db.criar_pendente(p)
    assert db.ligar_sessao(p["id"], "cs_test_1")
    assert not db.ligar_sessao(p["id"], "cs_test_2")  # uma sessão por pendente
    assert db.pendente_da_sessao("cs_test_1")["id"] == p["id"]
    assert db.marcar_pendente(p["id"], "pago")
    assert not db.marcar_pendente(p["id"], "expirado")  # pago é final
    assert db.pendente(p["id"])["estado"] == "pago"
    with pytest.raises(ValueError):
        db.marcar_pendente(p["id"], "cancelado")


@precisa_banco
def test_banco_recusa_estado_desconhecido_e_valor_zero(banco):
    import psycopg
    p = pendentes.montar(_pedido())
    with pytest.raises(psycopg.errors.CheckViolation), db._conectar() as c:
        c.execute("INSERT INTO pedidos_pendentes (id, itens, email, valor_centavos) VALUES ('x', '[]', 'a@b.c', 0)")
    db.criar_pendente(p)
    with pytest.raises(psycopg.errors.CheckViolation), db._conectar() as c:
        c.execute("UPDATE pedidos_pendentes SET estado = 'cancelado' WHERE id = %s", (p["id"],))


@precisa_banco
def test_limpeza_apaga_nao_pagos_com_mais_de_7_dias(banco):
    ids = {}
    for rotulo, estado, dias in (("novo", "aberto", 1), ("velho", "aberto", 8), ("expirado", "expirado", 8),
                                 ("falhou", "falhou", 30), ("pago", "pago", 400)):
        p = pendentes.montar(_pedido())
        db.criar_pendente(p)
        with db._conectar() as c:
            c.execute("UPDATE pedidos_pendentes SET estado = %s, criado_em = now() - make_interval(days => %s) "
                      "WHERE id = %s", (estado, dias, p["id"]))
        ids[rotulo] = p["id"]
    assert db.limpar_pendentes() == 3
    sobra = {r[0] for r in _linhas("SELECT id FROM pedidos_pendentes")}
    assert sobra == {ids["novo"], ids["pago"]}


@precisa_banco
def test_tarefa_diaria_limpa_os_pendentes(banco, monkeypatch):
    p = pendentes.montar(_pedido())
    db.criar_pendente(p)
    with db._conectar() as c:
        c.execute("UPDATE pedidos_pendentes SET criado_em = now() - interval '8 days'")
    monkeypatch.setenv("PADMINI_TAREFAS_CHAVE", "k")
    r = base.cliente.post("/api/tarefas/limpeza", headers={"Authorization": "Bearer k"})
    assert r.status_code == 200 and r.json()["apagadas"]["pedidos_pendentes"] == 1
    assert db.pendente(p["id"]) is None

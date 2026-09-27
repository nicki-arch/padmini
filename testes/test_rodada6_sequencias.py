"""
Rodada 6, Fase E: sequências de e-mail (boas-vindas e pós-compra) da ocidental.

- Ninguém recebe dois passos no mesmo dia nem o mesmo passo duas vezes.
- Comprou = para a boas-vindas e começa o pós-compra.
- Descadastrado não recebe nada; sem a caixa, nenhuma boas-vindas.
Os testes com banco precisam de TEST_DATABASE_URL (no CI rodam sempre).
"""
import json
import os

import pytest

import test_app as base
from test_app import app_mod, cliente

import db  # noqa: E402
import entrega  # noqa: E402
import marketing  # noqa: E402
import sequencias  # noqa: E402

TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
com_banco = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL não definida")

ANA = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30", "lat": -23.5505, "lon": -46.6333, "cidade": "SP"}


@pytest.fixture
def banco(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_URL)
    assert db.iniciar()
    with db._conectar() as c:
        c.execute("TRUNCATE pedidos, amostras_email, abandonos, email_optout, envios_sequencia")
    yield


@pytest.fixture
def emails(monkeypatch):
    enviados = []
    monkeypatch.setenv("RESEND_API_KEY", "teste")
    monkeypatch.setattr(entrega, "enviar_email",
                        lambda d, a, h, responder_para=None: enviados.append((d, a, h, responder_para)) or True)
    return enviados


def _sql(q, *args):
    with db._conectar() as c:
        cur = c.execute(q, args)
        return cur.fetchall() if cur.description else None


def _amostra(email="ana@x.com", dias=1, caixa=True, produto="mapa", dados=ANA, sistema="ocidental"):
    _sql("INSERT INTO amostras_email (email, produto, dados, aceita_lembrete, aceita_sequencia, sistema, criado_em) "
         "VALUES (%s,%s,%s,%s,%s,%s, now() - make_interval(days => %s))",
         email, produto, json.dumps(dados), caixa, caixa, sistema, dias)


def _pedido(email="ana@x.com", dias=2, produto="ocidental:mapa", cakto="p1"):
    _sql("INSERT INTO pedidos (cakto_id, produto, email, nome, link, criado_em) "
         "VALUES (%s,%s,%s,'Ana Souza','https://l', now() - make_interval(days => %s))", cakto, produto, email, dias)


def _ontem():
    """Empurra os envios de hoje para ontem (o "dia seguinte" do teste)."""
    _sql("UPDATE envios_sequencia SET enviado_em = enviado_em - interval '1 day'")


def _passos(sequencia="boas_vindas"):
    return [r[0] for r in _sql("SELECT passo FROM envios_sequencia WHERE sequencia = %s ORDER BY passo", sequencia)]


# ------------------------------------------------------------------ boas-vindas
@com_banco
def test_sem_a_caixa_nenhuma_boas_vindas(banco, emails):
    _amostra(caixa=False, dias=2)
    assert sequencias.rodar()["enviado"] == 0 and emails == []


@com_banco
def test_os_tres_passos_nos_dias_certos_e_um_por_dia(banco, emails):
    _amostra(dias=0)
    assert sequencias.rodar()["enviado"] == 0  # D+0: nada ainda
    _sql("UPDATE amostras_email SET criado_em = now() - interval '1 day 1 hour'")
    assert sequencias.rodar()["enviado"] == 1 and _passos() == [1]
    assert sequencias.rodar()["enviado"] == 0  # mesmo dia: nada de segundo passo
    _ontem()
    assert sequencias.rodar()["enviado"] == 0  # D+2: o passo 2 é no D+3
    _sql("UPDATE amostras_email SET criado_em = now() - interval '3 days 1 hour'")
    assert sequencias.rodar()["enviado"] == 1 and _passos() == [1, 2]
    _ontem()
    _sql("UPDATE amostras_email SET criado_em = now() - interval '6 days 1 hour'")
    assert sequencias.rodar()["enviado"] == 1 and _passos() == [1, 2, 3]
    _ontem()
    assert sequencias.rodar()["enviado"] == 0  # acabou
    assert [a for _, a, _, _ in emails][0].startswith("A sua Vênus em")
    assert all("Descadastrar" in h for _, _, h, _ in emails)


@com_banco
def test_atrasado_nao_manda_dois_no_mesmo_dia(banco, emails):
    _amostra(dias=10)  # a tarefa ficou parada: os 3 passos venceram
    assert sequencias.rodar()["enviado"] == 1 and _passos() == [1]
    assert sequencias.rodar()["enviado"] == 0


@com_banco
def test_mesmo_passo_nunca_duas_vezes(banco, emails):
    _amostra(dias=2)
    assert db.reservar_passo("ana@x.com", "boas_vindas", 1, None) is not None
    assert db.reservar_passo("ANA@x.com", "boas_vindas", 1, None) is None


@com_banco
def test_comprou_para_a_boas_vindas_e_comeca_o_pos_compra(banco, emails):
    _amostra(dias=4)
    _pedido(dias=2)
    r = sequencias.rodar()
    assert r["enviado"] == 1 and _passos("boas_vindas") == [] and _passos("pos_compra") == [1]
    destino, assunto, html, responder = emails[0]
    assert assunto == "Fez sentido?" and responder == sequencias.responder_para()
    assert "responda este e-mail" in html.lower()


@com_banco
def test_descadastrado_nao_recebe_nada(banco, emails):
    _amostra(dias=2)
    _pedido(email="rui@x.com", dias=3, cakto="p2")
    _sql("INSERT INTO email_optout (email) VALUES ('ana@x.com'), ('rui@x.com')")
    assert sequencias.rodar()["enviado"] == 0 and emails == []


@com_banco
def test_envio_que_falha_tenta_de_novo(banco, monkeypatch):
    _amostra(dias=2)
    monkeypatch.setattr(entrega, "enviar_email", lambda *a, **k: False)
    assert sequencias.rodar()["falhou"] == 1 and _passos() == []
    monkeypatch.setattr(entrega, "enviar_email", lambda *a, **k: True)
    assert sequencias.rodar()["enviado"] == 1 and _passos() == [1]


@com_banco
def test_vedica_fica_fora(banco, emails):
    _amostra(dias=2, sistema="vedica")
    _pedido(dias=3, produto="mapa")  # compra da védica
    assert sequencias.rodar()["enviado"] == 0


@com_banco
def test_pos_compra_segue_a_escada_e_pula_quem_ja_tem_tudo(banco, emails):
    _pedido(dias=8, cakto="p1")
    _sql("INSERT INTO envios_sequencia (email, sequencia, passo, enviado_em) "
         "VALUES ('ana@x.com', 'pos_compra', 1, now() - interval '5 days')")
    sequencias.rodar()
    assert "sinastria" in emails[-1][1].lower()  # comprou o mapa: a próxima é a sinastria
    # quem tem os 4: o passo 2 é pulado (sem e-mail)
    for i, p in enumerate(("compat", "numerologia", "tarot")):
        _pedido(email="tudo@x.com", dias=8, produto=f"ocidental:{p}", cakto=f"t{i}")
    _pedido(email="tudo@x.com", dias=8, produto="ocidental:mapa", cakto="t9")
    _sql("INSERT INTO envios_sequencia (email, sequencia, passo, enviado_em) "
         "VALUES ('tudo@x.com', 'pos_compra', 1, now() - interval '5 days')")
    antes = len(emails)
    r = sequencias.rodar()
    assert r["pulado"] == 1 and len(emails) == antes
    assert _sql("SELECT pulado FROM envios_sequencia WHERE email = 'tudo@x.com' AND passo = 2") == [(True,)]


@com_banco
def test_lembrete_antigo_nao_sai_para_quem_marcou_a_caixa_nova(banco):
    _amostra(email="nova@x.com", dias=2, caixa=True)
    _sql("INSERT INTO amostras_email (email, produto, dados, aceita_lembrete, sistema, criado_em) "
         "VALUES ('antiga@x.com', 'mapa', %s, true, 'ocidental', now() - interval '2 days')", json.dumps(ANA))
    assert [x["email"] for x in db.lembretes_pendentes()] == ["antiga@x.com"]


@com_banco
def test_limpeza_de_24_meses_leva_os_envios(banco):
    _sql("INSERT INTO email_optout (email) VALUES ('sai@x.com')")
    _sql("INSERT INTO envios_sequencia (email, sequencia, passo) VALUES ('sai@x.com', 'boas_vindas', 1)")
    assert db.limpar_marketing()["envios_sequencia"] == 1


# ------------------------------------------------------------------ sem banco
def test_sem_banco_nao_manda(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert sequencias.rodar() == {"enviado": 0, "pulado": 0, "falhou": 0, "repetido": 0}


def test_rota_da_tarefa_exige_a_chave(monkeypatch):
    monkeypatch.delenv("PADMINI_TAREFAS_CHAVE", raising=False)
    assert cliente.post("/api/tarefas/sequencias").status_code == 503
    monkeypatch.setenv("PADMINI_TAREFAS_CHAVE", "k")
    assert cliente.post("/api/tarefas/sequencias").status_code == 401
    monkeypatch.delenv("DATABASE_URL", raising=False)
    r = cliente.post("/api/tarefas/sequencias", headers={"Authorization": "Bearer k"})
    assert r.status_code == 200 and r.json()["enviado"] == 0


def test_workflow_chama_as_sequencias():
    wf = (base.RAIZ / ".github" / "workflows" / "tarefas.yml").read_text(encoding="utf-8")
    assert "/api/tarefas/sequencias" in wf


# ------------------------------------------------------------------ copy
@pytest.mark.parametrize("produto", ["mapa", "compat", "numerologia", "tarot"])
def test_boas_vindas_tem_descadastro_e_so_promete_o_que_o_completo_entrega(produto):
    import tarot
    dados = {"mapa": ANA, "compat": {"a": ANA, "b": {**ANA, "nome": "Rui", "data": "1988-02-03"}},
             "numerologia": {"nome": "Ana Maria Souza", "data": "1990-05-15"}, "tarot": {"tiragem": tarot.tirar()}}[produto]
    for passo in (1, 2, 3):
        assunto, html = sequencias.email_boas_vindas(passo, produto, dados, "a@b.c")
        assert assunto and "Descadastrar" in html and "descadastrar?" in html
        for proibido in ("garantimos", "vai acontecer", "com certeza você"):
            assert proibido not in html.lower()
    assert "Garantia de 7 dias" in sequencias.email_boas_vindas(3, produto, dados, "a@b.c")[1]


def test_pos_compra_depoimento_so_com_autorizacao():
    _, html = sequencias.email_pos_compra(3, "ocidental:mapa", "Ana", "a@b.c", ["ocidental:mapa"])
    assert "autorização por escrito" in html


def test_lembrete_da_numerologia_so_com_o_primeiro_nome():
    html = marketing.email_lembrete_html("numerologia", {"caminho_de_vida": {"valor": 3}},
                                         {"nome": "Ana Maria da Silva", "data": "1990-05-15"}, "a@b.c", "ocidental")
    assert "Olá Ana," in html and "Ana Maria" not in html


def test_estilo_mostra_as_sequencias(monkeypatch):
    monkeypatch.setenv("PADMINI_PREVIA_CHAVE", "k")
    html = cliente.get("/estilo?previa=k").text
    for passo in (1, 2, 3):
        assert f"Boas-vindas {passo}/3" in html and f"Pós-compra {passo}/3" in html


def test_privacidade_explica_os_emails_de_depois_da_compra(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    app_mod._paginas_prontas.clear()
    try:
        html = cliente.get("/privacidade").text
        assert "Até 3 e-mails depois de uma compra" in html and "Até 3 e-mails a mais" in html
    finally:
        app_mod._paginas_prontas.clear()

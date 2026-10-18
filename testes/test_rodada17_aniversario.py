"""
Rodada 17, Fase 3: o e-mail de aniversário de "O seu ano" liga e desliga pelo ESTADO DO SITE
(o /painel), sem deploy. Usa o consentimento de marketing que já existe (aceita_sequencia)
e tem descadastro (os dois cobertos também em test_rodada13_venda.py).
"""
import os
from datetime import date

import pytest

from test_app import app_mod  # noqa: F401  (define os segredos de teste)
import db
import entrega
import estado_site
import sequencias

TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
precisa_banco = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL não definida")
pytestmark = pytest.mark.catalogo_real  # no YAML, "O seu ano" está oculto e a venda aberta
NASC = {"nome": "Ana", "data": "1995-01-10", "hora": "14:30", "lat": -23.55, "lon": -46.63, "cidade": "São Paulo"}
HOJE = date(2026, 12, 11)  # aniversário em 10/01: daqui a 30 dias


@pytest.fixture
def banco(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_URL)
    for v in ("PADMINI_VENDAS_TESTE",):
        monkeypatch.delenv(v, raising=False)
    assert db.iniciar()
    with db._conectar() as c:
        c.execute("TRUNCATE amostras_email, envios_sequencia, email_optout, config_site, config_site_historico")
    estado_site.esquecer()
    db.registrar_amostra_email("sim@teste.com", "mapa", NASC, True, {}, "ocidental", aceita_sequencia=True)
    db.registrar_amostra_email("nao@teste.com", "mapa", NASC, False, {}, "ocidental", aceita_sequencia=False)
    yield
    with db._conectar() as c:
        c.execute("TRUNCATE amostras_email, envios_sequencia, config_site, config_site_historico")
    estado_site.esquecer()


@pytest.fixture
def enviados(monkeypatch):
    lista = []
    monkeypatch.setattr(entrega, "enviar_email", lambda para, assunto, html, **k: lista.append(para) or True)
    return lista


def _ciclo():
    contagem = {"enviado": 0, "pulado": 0, "falhou": 0, "repetido": 0}
    sequencias.rodar_aniversarios(HOJE, set(), contagem)
    return contagem


def _painel(**mudancas):
    db.gravar_config_site(mudancas, "Nicolas")
    estado_site.invalidar()  # o próximo ciclo da tarefa lê o banco de novo (cache de 15 s)


@precisa_banco
def test_oculto_no_painel_nenhum_email(banco, enviados):
    _painel(**{"produto:previsao": "oculto"})
    assert _ciclo()["enviado"] == 0 and enviados == []


@precisa_banco
def test_ligar_no_painel_liga_o_email_sem_deploy(banco, enviados):
    """Critério 3: oculto → nada; ligado no painel → o próximo ciclo envia (só a quem
    marcou a caixa); oculto de novo → para."""
    assert _ciclo()["enviado"] == 0  # nada salvo: vale o YAML (oculto)
    _painel(**{"produto:previsao": "ativo"})
    assert _ciclo()["enviado"] == 1 and enviados == ["sim@teste.com"]
    _painel(**{"produto:previsao": "oculto"})
    with db._conectar() as c:
        c.execute("TRUNCATE envios_sequencia")  # mesmo sem a trava de "um por ano"
    assert _ciclo()["enviado"] == 0 and enviados == ["sim@teste.com"]


@precisa_banco
def test_ativo_com_a_venda_fechada_no_painel_nao_envia(banco, enviados):
    """O e-mail leva à compra: com a venda fechada no painel, fica parado."""
    _painel(**{"produto:previsao": "ativo", "vendas_abertas": False})
    assert _ciclo()["enviado"] == 0


@precisa_banco
def test_modo_teste_do_painel_nao_liga_o_email(banco, enviados):
    """O "tudo liberado só para mim" é de um navegador: a tarefa diária não tem cookie e o
    estado PÚBLICO continua oculto."""
    tokens = estado_site.marcar_pedido(True, True)
    try:
        assert estado_site.liberado_para_mim()
        assert _ciclo()["enviado"] == 0
    finally:
        estado_site.desmarcar(tokens)


@precisa_banco
def test_descadastrado_nao_recebe_mesmo_ligado(banco, enviados):
    _painel(**{"produto:previsao": "ativo"})
    with db._conectar() as c:
        c.execute("INSERT INTO email_optout (email) VALUES ('sim@teste.com')")
    assert _ciclo()["enviado"] == 0

"""
Rodada 20.2 (21/out/2026): o smoke não dispara alerta por e-mail.

O smoke confere de propósito que /webhook/stripe e /webhook/cakto recusam evento sem
assinatura (401). Com os e-mails voltando a sair (rodada 20.1), cada rodada do smoke (de hora
em hora, pos-deploy.yml) mandava ~2 alertas falsos. Agora o smoke se identifica
(X-Padmini-Smoke: 1): a recusa é a mesma (401, e vai para o log), só o e-mail não sai. Sem o
cabeçalho, tudo como antes.
"""
import pytest

from test_app import app_mod, cliente  # primeiro: define os segredos de teste
from test_smoke import SEM_REDE, _local, smoke
import alertas
import estado_site

WEBHOOKS = {"/webhook/stripe": {"id": "evt_x", "type": "checkout.session.completed", "data": {"object": {}}},
            "/webhook/cakto": {"event": "purchase_approved", "data": {"id": "x"}}}


@pytest.fixture
def avisos(monkeypatch):
    lista = []
    monkeypatch.setattr(alertas, "alertar", lambda titulo, corpo="", *a, **k: lista.append(titulo))
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_" + "x" * 24)
    return lista


@pytest.mark.parametrize("rota", WEBHOOKS)
def test_recusa_do_smoke_401_sem_alerta(avisos, rota, caplog):
    r = cliente.post(rota, json=WEBHOOKS[rota], headers=smoke.SMOKE)
    assert r.status_code == 401 and avisos == []
    assert "smoke: sem alerta" in caplog.text  # a recusa continua no log


@pytest.mark.parametrize("rota", WEBHOOKS)
@pytest.mark.parametrize("cabecalho", [{}, {"X-Padmini-Smoke": "0"}, {"X-Padmini-Smoke": "sim"}])
def test_recusa_sem_o_cabecalho_alerta_como_antes(avisos, rota, cabecalho):
    r = cliente.post(rota, json=WEBHOOKS[rota], headers=cabecalho)
    assert r.status_code == 401 and len(avisos) == 1 and "recusado" in avisos[0]


@pytest.mark.parametrize("rota", WEBHOOKS)
def test_cabecalho_nao_muda_a_resposta(avisos, rota):
    com = cliente.post(rota, json=WEBHOOKS[rota], headers=smoke.SMOKE)
    sem = cliente.post(rota, json=WEBHOOKS[rota])
    assert (com.status_code, com.json()) == (sem.status_code, sem.json())


def test_smoke_manda_o_cabecalho_em_toda_chamada(monkeypatch):
    vistos = []

    class Abridor:
        def open(self, req, timeout=None):
            vistos.append(req)
            raise smoke.urllib.error.HTTPError(req.full_url, 401, "x", {}, None)
    monkeypatch.setattr(smoke.urllib.request, "build_opener", lambda *a: Abridor())
    monkeypatch.setattr(smoke.urllib.request, "urlopen", lambda req, timeout=None: Abridor().open(req))
    monkeypatch.setattr(smoke, "BASE", "https://padmini.com.br")
    smoke.req("/webhook/stripe", {})
    smoke._sem_seguir("https://padmini.com.br/webhook/cakto", {})
    assert len(vistos) == 2
    assert all(r.get_header("X-padmini-smoke") == "1" for r in vistos)


@pytest.mark.parametrize("pagamento", ["cakto", "stripe"])
def test_uma_rodada_do_smoke_nao_gera_alerta(avisos, monkeypatch, pagamento):
    """Critério 1: o smoke inteiro (o que roda sem rede) contra o app local: nenhum alerta."""
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    monkeypatch.setenv("PADMINI_PAGAMENTO", pagamento)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_" + "a" * 20)
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_" + "b" * 20)
    _local(monkeypatch)
    estado_site.esquecer()
    app_mod._paginas_prontas.clear()
    smoke.AVISOS.clear()
    checagens = [c for c in smoke.CHECAGENS if not any(t in c[0] for t in SEM_REDE)]
    checagens += smoke.CHECAGENS_STRIPE if pagamento == "stripe" else []
    # a checagem de webhooks da manutenção também (a de 503 abre o site direto, sem o req)
    checagens += [c for c in smoke.CHECAGENS_MANUTENCAO if "webhooks" in c[0]]
    resultados = {nome: f() for nome, f in checagens}
    app_mod._paginas_prontas.clear()
    assert all(resultados.values()), [n for n, ok in resultados.items() if not ok]
    assert any("webhook" in n for n in resultados)  # as recusas de webhook rodaram
    assert avisos == []

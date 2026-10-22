"""
Rodada 17, Fase 2: "O seu ano" no /live do Pedro.

A aba e a rota /api/live/ocidental/token/previsao só existem com o produto ATIVO no estado
do site (painel → catalogo.yaml) ou no "tudo liberado" (prévia: para todos; produção: só no
navegador logado no painel). Mesma sessão das outras abas; sem sessão, 401.
"""
import pytest

from test_app import app_mod, cliente  # primeiro: define os segredos de teste
import acesso
import db
import estado_site
import painel

ANA = {"nome": "Ana", "data": "1994-05-14", "hora": "15:40", "lat": -30.0346, "lon": -51.2177,
       "cidade": "Porto Alegre"}
SENHA_PAINEL = "uma-senha-bem-longa-de-teste"
pytestmark = pytest.mark.catalogo_real  # "O seu ano" está oculto no YAML


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    for v in ("PADMINI_CAPTURA", "PADMINI_VENDAS_TESTE", "DATABASE_URL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("PADMINI_PAINEL_SENHA", SENHA_PAINEL)
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_" + "a" * 20)
    monkeypatch.setattr(db, "registrar_live", lambda *a, **k: True)
    estado_site.esquecer()
    app_mod._paginas_prontas.clear()
    yield
    estado_site.esquecer()
    app_mod._paginas_prontas.clear()


def _painel(monkeypatch, **salvo):
    monkeypatch.setattr(estado_site, "salvo", lambda: dict(salvo))


LIVE = {"cookie": f"pad_live={acesso.emitir_sessao('live', 2_000_000_000)}"}


def _logado_no_painel():
    valor, _ = painel.emitir_sessao("Nicolas")
    return f"; {painel.COOKIE}={valor}"


def _token(cab=LIVE):
    return cliente.post("/api/live/ocidental/token/previsao", json=ANA, headers=cab)


# ------------------------------------------------------------------ oculto: nada
def test_oculto_nao_tem_aba_nem_token(base):
    assert 'id="aba-ano"' not in cliente.get("/live").text
    assert _token().status_code == 404


# ------------------------------------------------------------------ ativo pelo painel (critério 3)
def test_ativo_no_painel_liga_a_aba_e_o_token_sem_deploy(base, monkeypatch):
    _painel(monkeypatch, **{"produto:previsao": "ativo"})
    html = cliente.get("/live").text
    assert 'id="aba-ano"' in html and "/api/live/ocidental/token/previsao" in html
    r = _token()
    assert r.status_code == 200
    _painel(monkeypatch, **{"produto:previsao": "oculto"})
    assert 'id="aba-ano"' not in cliente.get("/live").text and _token().status_code == 404


def test_sem_sessao_recusa(base, monkeypatch):
    """Critério 2: sem sessão do live, 401 (mesmo com o produto ativo)."""
    _painel(monkeypatch, **{"produto:previsao": "ativo"})
    assert cliente.post("/api/live/ocidental/token/previsao", json=ANA).status_code == 401
    falso = {"cookie": "pad_live=2000000000.assinatura-falsa"}
    assert _token(falso).status_code == 401


def test_live_gera_o_seu_ano_completo(base, monkeypatch):
    """Critério 2: com sessão válida, o token abre o completo (temas, mês a mês, áreas)."""
    _painel(monkeypatch, **{"produto:previsao": "ativo"})
    t = _token().json()
    assert t["token"].startswith("oc-") and len(t["inicio"]) == 7
    r = cliente.post("/api/ocidental/previsao", json={**ANA, "nivel": "completo", "inicio": t["inicio"],
                                                      "token": t["token"]})
    assert r.status_code == 200
    d = r.json()
    assert d["nivel"] == "completo" and len(d["temas"]) == 3 and d["linha_do_tempo"] and d["areas"]
    # o token é o de "O seu ano" daquele ano: não abre o mapa natal
    r = cliente.post("/api/ocidental/mapa", json={**ANA, "nivel": "completo", "token": t["token"]})
    assert r.status_code == 402


def test_token_do_live_respeita_o_inicio_pedido(base, monkeypatch):
    _painel(monkeypatch, **{"produto:previsao": "ativo"})
    t = cliente.post("/api/live/ocidental/token/previsao", json={**ANA, "inicio": "2027-01"}, headers=LIVE).json()
    assert t["inicio"] == "2027-01"
    # rodada 20.3: o token novo leva o ano pedido dentro
    assert acesso.abrir_token_cifrado("previsao", t["token"])["inicio"] == "2027-01"
    assert t["link"] == "/seu-ano?token=" + t["token"]


# ------------------------------------------------------------------ tudo liberado
def test_tudo_liberado_na_producao_so_para_o_logado_no_painel(base, monkeypatch):
    _painel(monkeypatch, modo="tudo_liberado")
    assert 'id="aba-ano"' not in cliente.get("/live").text  # o Pedro sem o painel não vê
    assert _token().status_code == 404
    cab = {"cookie": LIVE["cookie"] + _logado_no_painel()}
    assert 'id="aba-ano"' in cliente.get("/live", headers=cab).text
    assert _token(cab).status_code == 200
    # e o cache de páginas não guardou a versão com a aba
    assert 'id="aba-ano"' not in cliente.get("/live").text


def test_tudo_liberado_na_previa_para_todos(base, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_" + "a" * 20)
    _painel(monkeypatch, modo="tudo_liberado")
    assert 'id="aba-ano"' in cliente.get("/live").text and _token().status_code == 200


# ------------------------------------------------------------------ as outras abas
def test_as_outras_abas_estao_sempre_no_live(base, monkeypatch):
    """Mapa, sinastria, numerologia e tarot são ferramentas do Pedro desde as rodadas 2–5:
    ficam no /live qualquer que seja o estado do produto (nem o YAML nem o painel as
    escondem). Só "O seu ano", ainda não lançado, depende do estado do site."""
    for salvo in ({}, {"produto:compat": "oculto", "produto:tarot": "oculto"}):
        _painel(monkeypatch, **salvo)
        html = cliente.get("/live").text
        for aba in ("aba-mapa", "aba-casal", "aba-num", "aba-tarot"):
            assert f'id="{aba}"' in html


def test_no_live_o_painel_vence_o_yaml(base, monkeypatch):
    """A aba pergunta ao estado_site, não ao catalogo.yaml: YAML dizendo ativo e o painel
    dizendo oculto = sem aba (e o contrário liga)."""
    import copy

    import catalogo
    dados = copy.deepcopy(catalogo.dados())
    for p in dados["produtos"]:
        if p["chave"] == "previsao":
            p["estado"] = "ativo"
    catalogo.usar(dados)
    _painel(monkeypatch, **{"produto:previsao": "oculto"})
    assert 'id="aba-ano"' not in cliente.get("/live").text and _token().status_code == 404
    _painel(monkeypatch)  # nada salvo no painel: vale o YAML (ativo)
    assert 'id="aba-ano"' in cliente.get("/live").text

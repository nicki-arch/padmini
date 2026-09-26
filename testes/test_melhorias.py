"""
Testes das melhorias de 25/set/2026 (docs/melhorias-2026-09.md):
  - preço de todas as páginas vindo do ofertas.yaml (a página do casal dizia R$127);
  - nota em formato brasileiro ("14", "14,5" — não "14.0");
  - amostra por e-mail, lembrete, descadastro, carrinho abandonado, venda cruzada;
  - alertas para a equipe (pedido pendente, e-mail que não saiu, erro 500);
  - /api/saude com a versão no ar (usada pelo workflow pos-deploy).
"""

import json
import re
import shutil
import subprocess
import time
import urllib.parse

import pytest
from fastapi.testclient import TestClient

from test_app import (  # noqa: E402
    PESSOA, PESSOA_B, RAIZ, SCK_CASAL, SCK_MAPA, _assinar, _evento, _postar_webhook, app_mod, cliente,
)

import alertas  # noqa: E402
import cakto  # noqa: E402
import db  # noqa: E402
import entrega  # noqa: E402
import marketing  # noqa: E402
import ofertas  # noqa: E402
from compatibilidade import nota_br  # noqa: E402


@pytest.fixture
def emails(monkeypatch):
    """Troca o envio real por uma lista: cada item é (destino, assunto, html)."""
    enviados = []
    monkeypatch.setenv("RESEND_API_KEY", "teste")
    monkeypatch.setattr(entrega, "enviar_email",
                        lambda d, a, h: enviados.append((d, a, h)) or True)
    return enviados


@pytest.fixture
def alertas_capturados(monkeypatch):
    lista = []
    monkeypatch.setattr(alertas, "alertar", lambda assunto, detalhes, **kw: lista.append((assunto, detalhes)) or True)
    return lista


# ============================================================ 1. preço e nota
@pytest.fixture
def precos_trocados(monkeypatch):
    """Muda os preços do YAML e limpa o cache das páginas montadas."""
    novas = json.loads(json.dumps(ofertas.OFERTAS))
    novas["mapa"]["preco"] = 55
    novas["compat"]["preco"] = 88
    novas["compat"]["preco_de"] = 111
    monkeypatch.setattr(ofertas, "OFERTAS", novas)
    monkeypatch.setattr(app_mod.ofertas, "OFERTAS", novas)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


@pytest.mark.parametrize("rota,esperados,proibidos", [
    ("/mapa", ["R$55"], ["R$47"]),
    ("/compatibilidade", ["completo por <b>R$88</b>", "R$88 <small>R$111</small>"], ["R$97", "R$127"]),
    ("/lista", ["R$88</span> <s>R$111</s>"], ["R$97", "R$127"]),
])
def test_precos_das_paginas_vem_do_yaml(precos_trocados, rota, esperados, proibidos):
    """O bug: a página do casal anunciava 'relatório completo por R$127' (preço
    riscado) e o mapa tinha R$47 escrito à mão — fora do ofertas.yaml."""
    html = cliente.get(rota).text
    for e in esperados:
        assert e in html, (rota, e)
    for p in proibidos:
        assert p not in html, (rota, p)


def test_nenhum_preco_escrito_a_mao_nos_html():
    for pagina in (RAIZ / "static").rglob("*.html"):  # inclui static/ocidental/
        texto = pagina.read_text(encoding="utf-8")
        assert not re.search(r"R\$\s?\d", texto), pagina.name


@pytest.mark.parametrize("valor,texto", [(14.0, "14"), (14.5, "14,5"), (28, "28"), (0.5, "0,5"), (36.0, "36")])
def test_nota_em_formato_brasileiro(valor, texto):
    assert nota_br(valor) == texto


def test_moldura_da_amostra_sem_ponto_zero():
    r = cliente.post("/api/compatibilidade", json={"a": PESSOA, "b": PESSOA_B, "nivel": "amostra"})
    moldura = r.json()["snippets"]["moldura"]
    assert not re.search(r"\d\.\d", moldura), moldura


# ============================================================ 2a. amostra por e-mail
def test_amostra_por_email_sem_resend_da_503(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    r = cliente.post("/api/amostra/email", json={"email": "a@b.com", "produto": "mapa", "pessoa": PESSOA})
    assert r.status_code == 503


def test_config_so_oferece_email_quando_configurado(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    assert cliente.get("/api/config").json()["amostra_email"] is False
    monkeypatch.setenv("RESEND_API_KEY", "x")
    assert cliente.get("/api/config").json()["amostra_email"] is True


def test_amostra_do_mapa_por_email(emails):
    r = cliente.post("/api/amostra/email", json={"email": "Ana@Teste.com ", "produto": "mapa",
                                                 "pessoa": PESSOA, "aceita_lembrete": True})
    assert r.status_code == 200, r.text
    destino, assunto, html = emails[0]
    assert destino == "ana@teste.com"
    assert "Ascendente" in html and "Lua" in html
    # botão de compra já com os dados de nascimento no sck, e o preço do YAML
    assert "pay.cakto.com.br" in html and "sck=m~1990-05-15" in html
    assert f"R${ofertas.preco('mapa')}" in html
    assert "/descadastrar?" in html


def test_amostra_do_casal_por_email(emails):
    r = cliente.post("/api/amostra/email", json={"email": "casal@teste.com", "produto": "compat",
                                                 "a": PESSOA, "b": PESSOA_B})
    assert r.status_code == 200, r.text
    html = emails[0][2]
    assert "ANA &amp; BRUNO" in html and "/ 36" in html
    assert "sck=c~1990-05-15" in html
    assert not re.search(r"\d\.0 de 36", html)


def test_amostra_por_email_escapa_o_nome(emails):
    p = {**PESSOA, "nome": '<img src=x onerror="alert(1)">'}
    assert cliente.post("/api/amostra/email", json={"email": "x@y.com", "produto": "mapa",
                                                    "pessoa": p}).status_code == 200
    assert "<img" not in emails[0][2]


@pytest.mark.parametrize("corpo,status", [
    ({"email": "nao-e-email", "produto": "mapa", "pessoa": PESSOA}, 422),
    ({"email": "a@b.com", "produto": "mapa"}, 422),
    ({"email": "a@b.com", "produto": "compat", "a": PESSOA}, 422),
    ({"email": "a@b.com", "produto": "outro", "pessoa": PESSOA}, 422),
])
def test_amostra_por_email_valida_a_entrada(emails, corpo, status):
    assert cliente.post("/api/amostra/email", json=corpo).status_code == status
    assert emails == []


def test_amostra_por_email_tem_limite_por_ip(emails):
    import limites
    c = TestClient(app_mod.app, headers={"CF-Connecting-IP": "203.0.113.77"})
    corpo = {"email": "a@b.com", "produto": "mapa", "pessoa": PESSOA}
    for _ in range(limites.AMOSTRA_EMAIL.maximo):
        assert c.post("/api/amostra/email", json=corpo).status_code == 200
    assert c.post("/api/amostra/email", json=corpo).status_code == 429


def test_amostra_por_email_limita_por_endereco(emails, monkeypatch):
    monkeypatch.setattr(db, "amostras_enviadas_hoje", lambda e: 3)
    r = cliente.post("/api/amostra/email", json={"email": "a@b.com", "produto": "mapa", "pessoa": PESSOA})
    assert r.status_code == 429 and emails == []


@pytest.mark.skipif(shutil.which("node") is None, reason="node não instalado")
@pytest.mark.parametrize("dados", [
    {"produto": "mapa", **PESSOA},
    {"produto": "compat", "a": PESSOA, "b": PESSOA_B},
    {"produto": "mapa", **PESSOA, "nome": "Nome~com~til e bem comprido demais", "cidade": "C" * 60},
])
def test_sck_do_email_igual_ao_do_site(dados):
    """O link do e-mail precisa gerar o mesmo sck que o botão do site (afiliado.js)."""
    js = ("global.location={search:'',origin:'https://padmini.teste'};"
          "global.sessionStorage={getItem(){return null},setItem(){}};global.window=global;"
          f"eval(require('fs').readFileSync({json.dumps(str(RAIZ / 'static' / 'afiliado.js'))},'utf8'));"
          f"process.stdout.write(window.padEmpacotar({json.dumps(dados)}));")
    do_site = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    assert marketing.empacotar_sck(dados["produto"], dados) == do_site


# ============================================================ 2b. lembrete e descadastro
def test_lembretes_sem_chave_configurada_recusa(monkeypatch):
    monkeypatch.delenv("PADMINI_TAREFAS_CHAVE", raising=False)
    assert cliente.post("/api/tarefas/lembretes").status_code == 503


def test_lembretes_com_chave_errada_recusa(monkeypatch):
    monkeypatch.setenv("PADMINI_TAREFAS_CHAVE", "chave-certa")
    r = cliente.post("/api/tarefas/lembretes", headers={"Authorization": "Bearer chave-errada"})
    assert r.status_code == 401


def test_lembretes_envia_e_marca(monkeypatch, emails):
    monkeypatch.setenv("PADMINI_TAREFAS_CHAVE", "chave-certa")
    dados_mapa = {**PESSOA}
    dados_casal = {"a": PESSOA, "b": PESSOA_B}
    monkeypatch.setattr(db, "lembretes_pendentes", lambda: [
        {"id": 1, "email": "m@t.com", "produto": "mapa", "dados": dados_mapa},
        {"id": 2, "email": "c@t.com", "produto": "compat", "dados": dados_casal}])
    marcados = []
    monkeypatch.setattr(db, "marcar_lembrete_enviado", marcados.append)
    r = cliente.post("/api/tarefas/lembretes", headers={"Authorization": "Bearer chave-certa"})
    assert r.json() == {"ok": True, "enviados": 2, "falhas": 0}
    assert marcados == [1, 2]
    assert "sck=m~" in emails[0][2] and "sck=c~" in emails[1][2]
    assert all("/descadastrar?" in h for _, _, h in emails)


def test_descadastro_com_link_valido_pede_confirmacao():
    link = marketing.link_descadastro("Ana@Teste.com")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(link).query))
    r = cliente.get("/descadastrar", params=q)
    assert r.status_code == 200 and "Sim, descadastrar" in r.text


def test_descadastro_com_link_falso_nao_faz_nada(monkeypatch):
    chamadas = []
    monkeypatch.setattr(db, "descadastrar", lambda e: chamadas.append(e) or True)
    r = cliente.post("/descadastrar", content="e=vitima%40x.com&t=chute",
                     headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert "inválido" in r.text and chamadas == []


def test_descadastro_confirmado(monkeypatch):
    chamadas = []
    monkeypatch.setattr(db, "descadastrar", lambda e: chamadas.append(e) or True)
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(marketing.link_descadastro("a@b.com")).query))
    r = cliente.post("/descadastrar", content=urllib.parse.urlencode(q),
                     headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert "Pronto" in r.text and chamadas == ["a@b.com"]


# ============================================================ 2c. carrinho abandonado
def _abandono(email="quase@teste.com", checkout=None, oferta=None):
    return {"event": "checkout_abandonment",
            "data": {"customerName": "Carla Souza", "customerEmail": email,
                     "customerCellphone": None, "createdAt": "2026-09-25T10:00:00-03:00",
                     "offer": {"id": oferta or ofertas.codigo("compat")},
                     "checkoutUrl": checkout or ofertas.checkout("compat")}}


@pytest.fixture
def banco_de_abandono(monkeypatch):
    registrados = []
    monkeypatch.setattr(db, "descadastrado", lambda e: False)
    monkeypatch.setattr(db, "abandono_ja_tratado", lambda e, o: False)
    monkeypatch.setattr(db, "registrar_abandono", lambda *a: registrados.append(a) or True)
    return registrados


def test_abandono_manda_recuperacao_para_o_site_sem_sck(emails, banco_de_abandono):
    r = _postar_webhook(_abandono())
    assert r.status_code == 200 and r.json()["abandono"] == "compat"
    destino, _, html = emails[0]
    assert destino == "quase@teste.com" and "Carla" in html
    assert "/compatibilidade?utm_source=email" in html  # sem sck: refaz a amostra no site
    assert "token=" not in html  # recuperação nunca libera o completo
    assert banco_de_abandono[0][0] == "quase@teste.com"


def test_abandono_com_sck_volta_para_o_mesmo_checkout(emails, banco_de_abandono):
    url = ofertas.checkout("compat") + "?sck=c~1990"
    _postar_webhook(_abandono(checkout=url))
    assert "sck=c~1990" in emails[0][2]


def test_abandono_nao_repete_nem_manda_para_descadastrado(emails, monkeypatch):
    monkeypatch.setattr(db, "descadastrado", lambda e: True)
    monkeypatch.setattr(db, "abandono_ja_tratado", lambda e, o: False)
    assert "ignorado" in _postar_webhook(_abandono()).json()
    monkeypatch.setattr(db, "descadastrado", lambda e: False)
    monkeypatch.setattr(db, "abandono_ja_tratado", lambda e, o: True)
    assert "ignorado" in _postar_webhook(_abandono()).json()
    assert emails == []


def test_abandono_sem_banco_nao_manda(emails):
    """Sem banco não há como saber se já mandou: não arrisca repetir."""
    assert "ignorado" in _postar_webhook(_abandono()).json() and emails == []


def test_abandono_precisa_de_assinatura(emails, banco_de_abandono):
    assert _postar_webhook(_abandono(), assinar=False).status_code == 401 and emails == []


def test_abandono_de_oferta_desconhecida_e_ignorado(emails, banco_de_abandono):
    ev = _abandono(oferta="xyz", checkout="https://pay.cakto.com.br/xyz_1")
    assert "ignorado" in _postar_webhook(ev).json() and emails == []


# ============================================================ 2d. venda cruzada
def test_entrega_do_casal_oferece_os_mapas_individuais(emails):
    r = _postar_webhook(_evento(SCK_CASAL))
    assert r.status_code == 200 and r.json()["email_enviado"] is True
    html = emails[0][2]
    assert "Mapa individual de Ana" in html and "Mapa individual de Bruno" in html
    assert f"{ofertas.codigo('mapa')}" in html and "utm_campaign=pos_compra" in html
    assert "sck=m~1990-05-15" in html


def test_entrega_do_mapa_oferece_a_compatibilidade(emails):
    _postar_webhook(_evento(SCK_MAPA))
    assert "/compatibilidade?utm_source=email" in emails[0][2]


def test_cupom_pos_compra_aparece_quando_configurado(emails, monkeypatch):
    novas = json.loads(json.dumps(ofertas.OFERTAS))
    novas["mapa"]["cupom_pos_compra"] = "CASAL10"
    monkeypatch.setattr(ofertas, "OFERTAS", novas)
    _postar_webhook(_evento(SCK_CASAL))
    assert "CASAL10" in emails[0][2]


# ============================================================ 5. alertas e versão
def test_pedido_pendente_gera_alerta(alertas_capturados):
    ev = _evento(SCK_CASAL, oferta={"offer": {"id": ofertas.codigo("mapa")}})
    _postar_webhook(ev)
    assert alertas_capturados and "sem entrega automática" in alertas_capturados[0][0]


def test_email_de_entrega_que_nao_saiu_gera_alerta_com_o_link(alertas_capturados, monkeypatch):
    monkeypatch.setattr(entrega, "enviar_email", lambda *a: False)
    _postar_webhook(_evento(SCK_MAPA))
    assunto, detalhes = alertas_capturados[0]
    assert "NÃO saiu" in assunto and "token=" in detalhes


def test_webhook_recusado_gera_alerta(alertas_capturados):
    _postar_webhook(_evento(SCK_MAPA), assinar=False)
    assert "recusado" in alertas_capturados[0][0]


def test_erro_500_gera_alerta(alertas_capturados, monkeypatch):
    def quebra(q):
        raise RuntimeError("falha de teste")
    monkeypatch.setattr(app_mod.busca, "buscar", quebra)
    r = TestClient(app_mod.app, raise_server_exceptions=False).get("/api/cidades?q=Porto")
    assert r.status_code == 500
    assert alertas_capturados and "500" in alertas_capturados[0][0]


def test_alerta_nao_vira_enxurrada(monkeypatch):
    enviados = []
    monkeypatch.setenv("PADMINI_ALERTA_EMAIL", "equipe@padmini.teste")
    monkeypatch.setattr(entrega, "enviar_email", lambda d, a, h: enviados.append(d) or True)
    alertas.limpar()
    for _ in range(5):
        alertas.alertar("x", "y", chave="k", intervalo=60)
    assert enviados == ["equipe@padmini.teste"]
    alertas.limpar()


def test_alerta_sem_destinatario_so_loga(monkeypatch):
    monkeypatch.delenv("PADMINI_ALERTA_EMAIL", raising=False)
    assert alertas.alertar("x", "y") is False


def test_saude_mostra_a_versao_no_ar(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "3c496d1d699b36987d557ae5d285357f61f2f8dc")
    assert cliente.get("/api/saude").json()["versao"] == "3c496d1"

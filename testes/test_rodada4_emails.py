"""
Rodada 4, Fase A: os e-mails de marketing (amostra por e-mail, lembrete, carrinho
abandonado) existem nas duas versões, cada um na copy, na paleta e nos links da
versão EM QUE A PESSOA ESTAVA — nunca da que está no ar na hora do envio.

Nenhum e-mail real sai nos testes (o envio é trocado por uma lista).
"""
import json
import re
import shutil
import subprocess
import urllib.parse

import pytest

from test_app import RAIZ, _postar_webhook, app_mod, cliente

import db  # noqa: E402
import entrega  # noqa: E402
import marketing  # noqa: E402
import ofertas  # noqa: E402
import paleta  # noqa: E402
import tarot  # noqa: E402

ANA = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30", "lat": -23.5505, "lon": -46.6333,
       "cidade": "São Paulo, SP"}
RAFA = {"nome": "Rafael", "data": "1988-11-02", "hora": "", "lat": -22.9068, "lon": -43.1729,
        "cidade": "Rio de Janeiro, RJ"}
PERGUNTA = "Devo aceitar a proposta do meu chefe?"


def _sem_nada_antigo(html: str, onde: str):
    baixo = html.lower()
    for antiga in paleta.ANTIGAS:
        assert antiga.lower() not in baixo, f"{onde}: usa {antiga!r}"
    assert not re.search(r"[ऀ-ॿ]", html), f"{onde}: devanágari"


@pytest.fixture
def emails(monkeypatch):
    enviados = []
    monkeypatch.setenv("RESEND_API_KEY", "teste")
    monkeypatch.setattr(entrega, "enviar_email", lambda d, a, h: enviados.append((d, a, h)) or True)
    return enviados


@pytest.fixture
def banco(monkeypatch):
    """Banco falso: guarda o que seria gravado."""
    gravado = {"amostras": [], "abandonos": []}
    monkeypatch.setattr(db, "amostras_enviadas_hoje", lambda e: 0)
    monkeypatch.setattr(db, "registrar_amostra_email",
                        lambda *a, **k: gravado["amostras"].append((a, k)) or True)
    monkeypatch.setattr(db, "descadastrado", lambda e: False)
    monkeypatch.setattr(db, "abandono_ja_tratado", lambda e, o: False)
    monkeypatch.setattr(db, "registrar_abandono", lambda *a, **k: gravado["abandonos"].append((a, k)) or True)
    return gravado


@pytest.fixture
def no_ar(monkeypatch):
    def ligar(v):
        monkeypatch.setenv("PADMINI_SISTEMA", v)
        app_mod._paginas_prontas.clear()
    yield ligar
    app_mod._paginas_prontas.clear()


def _pedidos_ocidentais():
    return {
        "mapa": {"produto": "mapa", "pessoa": ANA},
        "compat": {"produto": "compat", "a": ANA, "b": RAFA},
        "numerologia": {"produto": "numerologia", "nome": "Ana Maria da Conceição", "data": "1990-05-15"},
        "tarot": {"produto": "tarot", "tiragem": tarot.tirar()},
    }


# ------------------------------------------------------------------ amostra por e-mail
@pytest.mark.parametrize("produto", ["mapa", "compat", "numerologia", "tarot"])
def test_amostra_por_email_na_ocidental(produto, emails, banco, no_ar):
    no_ar("ocidental")
    corpo = {"email": "Ana@Teste.com", "aceita_lembrete": True, **_pedidos_ocidentais()[produto]}
    r = cliente.post("/api/amostra/email", json=corpo)
    assert r.status_code == 200, r.text
    destino, assunto, html = emails[0]
    assert destino == "ana@teste.com" and assunto == marketing.TEXTOS["ocidental"]["assunto_amostra"][produto]
    _sem_nada_antigo(html, f"amostra {produto}")
    assert paleta.EMAIL["ocidental"]["fundo"] in html and "/descadastrar?" in html
    # botão de compra = o do site: checkout da ocidental com o sck no formato do afiliado.js
    gravado = _args_amostra(banco)
    assert gravado["produto"] == produto and gravado["aceita_lembrete"] is True and gravado["sistema"] == "ocidental"
    assert ofertas.checkout(produto, "ocidental") in html
    assert urllib.parse.urlencode({"sck": marketing.empacotar_sck(produto, gravado["dados"])}) in html


def _args_amostra(banco):
    a, k = banco["amostras"][0]
    return dict(zip(["email", "produto", "dados", "aceita_lembrete", "origem", "sistema"], a), **k)


def test_amostra_grava_a_versao_do_servidor_nao_a_do_navegador(emails, banco, no_ar):
    no_ar("ocidental")
    corpo = {"email": "a@teste.com", "produto": "mapa", "pessoa": ANA, "sistema": "vedica"}
    assert cliente.post("/api/amostra/email", json=corpo).status_code == 200
    assert _args_amostra(banco)["sistema"] == "ocidental"
    _sem_nada_antigo(emails[0][2], "amostra com sistema forjado")


def test_amostra_do_tarot_nunca_leva_a_pergunta(emails, banco, no_ar):
    """A pergunta do tarot não vai para o banco nem para o e-mail — só o número da tiragem."""
    no_ar("ocidental")
    t = tarot.tirar()
    corpo = {"email": "a@teste.com", "produto": "tarot", "tiragem": t, "pergunta": PERGUNTA}
    assert cliente.post("/api/amostra/email", json=corpo).status_code == 200
    gravado = _args_amostra(banco)
    assert gravado["dados"] == {"tiragem": t}
    assert PERGUNTA not in json.dumps(banco, ensure_ascii=False) and PERGUNTA not in emails[0][2]
    assert "Devo aceitar" not in emails[0][1]


def test_amostra_do_tarot_com_tiragem_forjada(emails, banco, no_ar):
    no_ar("ocidental")
    r = cliente.post("/api/amostra/email", json={"email": "a@teste.com", "produto": "tarot",
                                                 "tiragem": "AAAAAAAAAAAAAAAA"})
    assert r.status_code == 422 and not emails and not banco["amostras"]


def test_numerologia_e_tarot_nao_existem_na_vedica(emails, banco, no_ar):
    no_ar("vedica")
    for produto, corpo in _pedidos_ocidentais().items():
        if produto in ("numerologia", "tarot"):
            r = cliente.post("/api/amostra/email", json={"email": "a@teste.com", **corpo})
            assert r.status_code == 422, produto
    assert not emails


def test_amostra_da_vedica_continua_igual(emails, banco, no_ar):
    no_ar("vedica")
    pessoa = {**ANA, "hora": "14:30"}
    r = cliente.post("/api/amostra/email", json={"email": "a@teste.com", "produto": "mapa", "pessoa": pessoa})
    assert r.status_code == 200
    assert emails[0][1] == "Sua amostra da Padmini" and "background:#241522" in emails[0][2]
    assert _args_amostra(banco)["sistema"] == "vedica"


def test_amostra_ocidental_respeita_o_limite_por_email(emails, banco, no_ar, monkeypatch):
    no_ar("ocidental")
    monkeypatch.setattr(db, "amostras_enviadas_hoje", lambda e: 3)
    r = cliente.post("/api/amostra/email", json={"email": "a@teste.com", **_pedidos_ocidentais()["numerologia"]})
    assert r.status_code == 429 and not emails


@pytest.mark.skipif(shutil.which("node") is None, reason="node não instalado")
@pytest.mark.parametrize("dados", [
    {"produto": "numerologia", "nome": "Maria da Conceição Araújo dos Santos~com til", "data": "1990-05-15"},
    {"produto": "tarot", "tiragem": "abcDEF-_123456789"},
])
def test_sck_do_email_igual_ao_do_site(dados):
    js = ("global.location={search:'',origin:'https://padmini.teste'};"
          "global.sessionStorage={getItem(){return null},setItem(){}};global.window=global;"
          f"eval(require('fs').readFileSync({json.dumps(str(RAIZ / 'static' / 'afiliado.js'))},'utf8'));"
          f"process.stdout.write(window.padEmpacotar({json.dumps(dados)}));")
    do_site = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    assert marketing.empacotar_sck(dados["produto"], dados) == do_site


@pytest.mark.parametrize("pagina,produto", [("mapa", "mapa"), ("compatibilidade", "compat"),
                                            ("numerologia", "numerologia"), ("tarot", "tarot")])
def test_as_4_paginas_ocidentais_tem_a_caixa(pagina, produto, no_ar):
    no_ar("ocidental")
    html = cliente.get(f"/{pagina}").text
    assert "/static/amostra-email.js" in html and 'id="amostra-email"' in html
    assert f'padAmostraEmail("#amostra-email", "{produto}"' in html
    if produto == "tarot":  # só o número da tiragem vai para o e-mail
        chamada = html[html.index('padAmostraEmail("#amostra-email", "tarot"'):][:120]
        assert "pergunta" not in chamada.lower()


# ------------------------------------------------------------------ lembrete
def test_lembrete_sai_na_versao_do_registro(emails, monkeypatch, no_ar):
    """Com a védica no ar, o registro da ocidental recebe o lembrete da ocidental (e vice-versa)."""
    no_ar("vedica")
    monkeypatch.setenv("PADMINI_TAREFAS_CHAVE", "chave")
    pedidos = _pedidos_ocidentais()
    itens = [{"id": 1, "email": "o@t.com", "produto": "numerologia", "sistema": "ocidental",
              "dados": {"nome": pedidos["numerologia"]["nome"], "data": pedidos["numerologia"]["data"]}},
             {"id": 2, "email": "t@t.com", "produto": "tarot", "sistema": "ocidental",
              "dados": {"tiragem": pedidos["tarot"]["tiragem"]}},
             {"id": 3, "email": "c@t.com", "produto": "compat", "sistema": "ocidental", "dados": {"a": ANA, "b": RAFA}},
             {"id": 4, "email": "m@t.com", "produto": "mapa", "sistema": "ocidental", "dados": ANA},
             {"id": 5, "email": "v@t.com", "produto": "mapa", "sistema": "vedica", "dados": ANA}]
    marcados = []
    monkeypatch.setattr(db, "lembretes_pendentes", lambda: itens)
    monkeypatch.setattr(db, "marcar_lembrete_enviado", marcados.append)
    r = cliente.post("/api/tarefas/lembretes", headers={"Authorization": "Bearer chave"})
    assert r.json() == {"ok": True, "enviados": 5, "falhas": 0} and marcados == [1, 2, 3, 4, 5]
    por_email = {d: (a, h) for d, a, h in emails}
    for e, produto in (("o@t.com", "numerologia"), ("t@t.com", "tarot"), ("c@t.com", "compat"), ("m@t.com", "mapa")):
        assunto, html = por_email[e]
        assert assunto == marketing.TEXTOS["ocidental"]["assunto_lembrete"][produto]
        _sem_nada_antigo(html, f"lembrete {produto}")
        assert ofertas.checkout(produto, "ocidental").split("?")[0] in html
        assert "9 planetas" not in html and "/36" not in html and "fases da vida" not in html
    assunto, html = por_email["v@t.com"]
    assert assunto == "Faltou uma parte do seu mapa" and "background:#241522" in html


# ------------------------------------------------------------------ carrinho abandonado
def _abandono(oferta: str, checkout: str, email="quase@teste.com"):
    return {"event": "checkout_abandonment",
            "data": {"customerName": "Carla Souza", "customerEmail": email,
                     "offer": {"id": oferta}, "checkoutUrl": checkout}}


@pytest.mark.parametrize("produto", ["mapa", "compat", "numerologia", "tarot"])
def test_abandono_ocidental(produto, emails, banco, no_ar):
    no_ar("ocidental")
    r = _postar_webhook(_abandono(ofertas.codigo(produto, "ocidental"), ofertas.checkout(produto, "ocidental")))
    assert r.status_code == 200 and r.json() == {"ok": True, "abandono": produto, "email_enviado": True}
    _, assunto, html = emails[0]
    _sem_nada_antigo(html, f"abandono {produto}")
    assert marketing.TEXTOS["ocidental"]["abandono_titulo"][produto] in html
    assert "compatibilidade" not in html.split("/descadastrar")[0].replace("/compatibilidade?", "")
    assert f"/{marketing.PAGINA_DO_PRODUTO[produto]}?utm_source=email" in html  # sem sck: volta à página
    args, _ = banco["abandonos"][0]
    assert args[4] is True and args[5] == "ocidental"


def test_abandono_da_sinastria_fala_sinastria(emails, banco, no_ar):
    no_ar("ocidental")
    _postar_webhook(_abandono(ofertas.codigo("compat", "ocidental"), ofertas.checkout("compat", "ocidental")))
    corpo = emails[0][2]
    assert "a sinastria de vocês" in corpo and "compatibilidade de vocês" not in corpo


def test_abandono_com_sck_volta_para_o_mesmo_checkout(emails, banco, no_ar):
    no_ar("ocidental")
    checkout = ofertas.checkout("numerologia", "ocidental") + "?sck=n~1990-05-15~Ana"
    _postar_webhook(_abandono(ofertas.codigo("numerologia", "ocidental"), checkout))
    assert checkout.replace("&", "&amp;") in emails[0][2]


def test_bump_do_combo_sozinho_nao_e_abandono(emails, banco, no_ar):
    no_ar("ocidental")
    r = _postar_webhook(_abandono(ofertas.codigo("bump_mapas_casal", "ocidental"),
                                  ofertas.checkout("compat", "ocidental")))
    assert "bump" in r.json()["ignorado"] and not emails and not banco["abandonos"]


def test_abandono_de_oferta_vedica_com_a_ocidental_no_ar_nao_manda(emails, banco, no_ar):
    """Mandar para uma página que vende outra coisa é pior que silêncio: só registra."""
    no_ar("ocidental")
    r = _postar_webhook(_abandono(ofertas.codigo("mapa", "vedica"), ofertas.checkout("mapa", "vedica") + "?sck=m~x"))
    assert r.json()["email_enviado"] is False and not emails
    args, _ = banco["abandonos"][0]
    assert args[4] is False and args[5] == "vedica"


def test_abandono_de_oferta_ocidental_com_a_vedica_no_ar_nao_manda(emails, banco, no_ar):
    no_ar("vedica")
    r = _postar_webhook(_abandono(ofertas.codigo("tarot", "ocidental"), ofertas.checkout("tarot", "ocidental")))
    assert r.json()["email_enviado"] is False and not emails
    assert banco["abandonos"][0][0][5] == "ocidental"


# ------------------------------------------------------------------ descadastro e privacidade
def test_descadastrar_com_o_tema_da_versao_no_ar(no_ar):
    link = marketing.link_descadastro("ana@teste.com")
    caminho = link.split(entrega.SITE_URL, 1)[1]
    no_ar("ocidental")
    html = cliente.get(caminho).text
    assert "/static/ocidental/tema.css" in html and "Sim, descadastrar" in html
    _sem_nada_antigo(html, "/descadastrar")
    no_ar("vedica")
    html = cliente.get(caminho).text
    assert "tema.css" not in html and "Sim, descadastrar" in html


@pytest.mark.parametrize("versao", ["vedica", "ocidental"])
def test_privacidade_diz_a_verdade_sobre_os_emails(versao, no_ar):
    no_ar(versao)
    html = cliente.get("/privacidade").text
    for trecho in ("Enviar a amostra por e-mail", "art. 7º, V", "Um único lembrete", "vem desmarcada",
                   "art. 7º, I", "Um e-mail de recuperação", "art. 7º, IX", "descadastrar",
                   "Amostra por e-mail, lembrete e recuperação de carrinho", "24 meses"):
        assert trecho in html, (versao, trecho)
    if versao == "ocidental":
        assert "nunca a sua pergunta" in html and "nome completo de registro e a data" in html


# ------------------------------------------------------------------ /estilo
def test_estilo_mostra_os_emails_de_marketing(monkeypatch):
    monkeypatch.setenv("PADMINI_PREVIA_CHAVE", "k")
    html = cliente.get("/estilo?previa=k").text
    for produto in ("mapa", "compat", "numerologia", "tarot"):
        for tipo in ("Amostra por e-mail", "Lembrete", "Carrinho abandonado"):
            assert f"{tipo} · {produto}" in html
    _sem_nada_antigo(html, "/estilo")

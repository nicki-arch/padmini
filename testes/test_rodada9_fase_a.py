"""
Rodada 9, Fase A: catálogo por estados, venda desligada e "me avise".

Estes testes usam o catálogo DE VERDADE (conteudo/ocidental/catalogo.yaml:
venda fechada, só o mapa natal ativo) — o conftest abre a venda para os testes
anteriores, que protegem o "com vendas_abertas: true, tudo como antes".
"""
import copy
import re

import pytest

from test_app import RAIZ, _postar_webhook, app_mod, cliente  # primeiro: define os segredos de teste
import catalogo
import entrega
import marketing
import ofertas
import rotas_ocidental
import sequencias
import textos
from test_api_ocidental import _evento as _evento_oc

pytestmark = pytest.mark.catalogo_real

OCULTOS = ("/comunidade", "/cursos", "/cursos/astrologia-do-zero", "/consulta")
EM_BREVE = ("/compatibilidade", "/numerologia", "/tarot")
PESSOA = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30", "lat": -23.5505, "lon": -46.6333,
          "cidade": "São Paulo, SP"}
HTML = {"accept": "text/html"}


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


def _mudar(**estados):
    """Troca estados (e/ou vendas_abertas) no catálogo, como quem edita o YAML."""
    d = copy.deepcopy(catalogo.carregar())
    for chave, valor in estados.items():
        if chave == "vendas_abertas":
            d["vendas_abertas"] = valor
        else:
            next(p for p in d["produtos"] if p["chave"] == chave)["estado"] = valor
    catalogo.usar(d)
    app_mod._paginas_prontas.clear()


def _menu(html: str) -> list[str]:
    """Páginas de produto no cabeçalho (menu do desktop + painel do celular, rodada 9:
    os em breve ficam em "Chegando em breve" no painel), sem âncoras nem repetição."""
    cab = html[html.index('<header class="cab">'):html.index("</header>")]
    cab = re.sub(r'<a class="(cab-bt|rod-bt)"[^>]*>.*?</a>', "", cab)
    vistos = []
    for h in re.findall(r'href="(/[a-z/-]*)"', cab):
        if h not in vistos and h not in ("/", "/minhas-leituras", "/blog"):
            vistos.append(h)
    return vistos


def _sitemap() -> list[str]:
    return re.findall(r"<loc>[^<]*padmini[^/]*(/[^<]*)</loc>", cliente.get("/sitemap.xml").text)


# ------------------------------------------------------------------ o YAML
def test_catalogo_de_producao():
    assert catalogo.vendas_abertas() is False
    assert [(p["chave"], p["estado"]) for p in catalogo.produtos()] == [
        ("mapa", "ativo"), ("compat", "em_breve"), ("numerologia", "em_breve"), ("tarot", "em_breve"),
        ("comunidade", "oculto"), ("cursos", "oculto"), ("astrologia-do-zero", "oculto"), ("consulta", "oculto")]
    dims = {d["nome"]: d["estado"] for d in catalogo.dimensoes_mapa()}
    assert [n for n, e in dims.items() if e == "ativo"] == ["Essência", "Emoções", "Como você chega", "Mente",
                                                           "Amor", "Ação"]
    assert [n for n, e in dims.items() if e == "em_breve"] == ["Carreira", "Dinheiro", "Família", "Propósito"]


def test_catalogo_invalido_falha_na_subida():
    d = copy.deepcopy(catalogo.carregar())
    d["produtos"][0]["estado"] = "ligado"
    with pytest.raises(catalogo.CatalogoInvalido):
        catalogo.validar(d)
    d = copy.deepcopy(catalogo.carregar())
    d["vendas_abertas"] = "não"
    with pytest.raises(catalogo.CatalogoInvalido):
        catalogo.validar(d)


def test_a_vedica_nao_tem_catalogo():
    assert catalogo.vendas_abertas("vedica") is True and catalogo.vende("compat", "vedica") is True


# ------------------------------------------------------------------ estados
@pytest.mark.parametrize("rota", OCULTOS)
def test_oculto_responde_404(ocidental, rota):
    assert cliente.get(rota, headers=HTML).status_code == 404
    assert cliente.get(rota).status_code == 404


def test_oculto_e_404_mesmo_com_a_captura(ocidental, monkeypatch):
    monkeypatch.setenv("PADMINI_CAPTURA", "1")
    assert cliente.get("/comunidade", follow_redirects=False).status_code == 404


def test_oculto_nao_aparece_em_lugar_nenhum(ocidental):
    for rota in ("/", "/mapa", "/leituras", "/lista", "/compatibilidade"):
        html = cliente.get(rota).text
        for oculto in OCULTOS:
            assert f'href="{oculto}' not in html, (rota, oculto)
        assert "Comunidade" not in html and "Consulta" not in html
    assert not set(OCULTOS) & set(_sitemap())


def test_em_breve_mostra_o_me_avise_sem_o_formulario_do_produto(ocidental):
    for rota in EM_BREVE:
        r = cliente.get(rota)
        assert r.status_code == 200
        assert "Em breve" in r.text and 'data-me-avise="' in r.text, rota
        assert "/api/ocidental/" not in r.text, rota  # nada do fluxo de amostra/compra
    assert 'data-me-avise="compat"' in cliente.get("/compatibilidade").text


def test_menu_home_rodape_e_leituras_vem_do_catalogo(ocidental):
    home = cliente.get("/").text
    assert _menu(home) == ["/mapa", "/leituras", "/compatibilidade", "/numerologia", "/tarot"]
    assert home.count("em breve") >= 3  # os três produtos em breve no menu
    rodape = home.split('<footer', 1)[1]
    assert all(f'href="{r}"' in rodape for r in ("/mapa", "/compatibilidade", "/leituras"))
    leituras = cliente.get("/leituras").text
    assert re.findall(r'<h2 class="t3">([^<]+)</h2>', leituras) == ["Mapa natal", "Sinastria do casal", "Numerologia", "Tarot"]
    assert _sitemap() == ["/", "/mapa", "/compatibilidade", "/numerologia", "/tarot", "/leituras"]


def test_trocar_um_estado_no_yaml_muda_o_que_aparece(ocidental):
    # sinastria ativa: a página volta a ter o formulário do casal; o menu tira o "em breve"
    _mudar(compat="ativo")
    html = cliente.get("/compatibilidade").text
    assert "/api/ocidental/sinastria" in html
    assert re.search(r'<nav class="nav".*href="/compatibilidade"', html, re.S)  # vai para o menu do desktop
    assert 'href="/compatibilidade#me-avise"' not in cliente.get("/").text  # sai de "Chegando em breve"
    # tarot oculto: 404, some do menu, da home, de "Todas as leituras" e do sitemap
    _mudar(tarot="oculto")
    assert cliente.get("/tarot", headers=HTML).status_code == 404
    assert "/tarot" not in _menu(cliente.get("/").text)
    assert 'href="/tarot' not in cliente.get("/leituras").text
    assert "/tarot" not in _sitemap()
    # comunidade em breve: a rota abre com o "me avise" e entra no menu
    _mudar(comunidade="em_breve")
    r = cliente.get("/comunidade")
    assert r.status_code == 200 and 'data-me-avise="comunidade"' in r.text
    assert "/comunidade" in _menu(cliente.get("/").text) and "/comunidade" in _sitemap()


def test_link_com_token_abre_o_produto_em_breve(ocidental):
    """Quem comprou antes continua lendo: o token abre a página de verdade."""
    html = cliente.get("/compatibilidade?token=oc-qualquer").text
    assert "/api/ocidental/sinastria" in html and 'data-me-avise="compat"' not in html.split("<script>")[0]
    assert "/api/ocidental/numerologia" in cliente.get("/numerologia?token=oc-x").text
    assert "/api/ocidental/tarot" in cliente.get("/tarot?token=oc-x").text


def test_minhas_leituras_e_live_continuam(ocidental):
    assert cliente.get("/minhas-leituras").status_code == 200
    assert cliente.get("/live").status_code == 200


def test_em_breve_vai_para_a_lista_com_a_captura(ocidental, monkeypatch):
    monkeypatch.setenv("PADMINI_CAPTURA", "1")
    r = cliente.get("/compatibilidade", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].startswith("/lista")
    assert cliente.get("/leituras", follow_redirects=False).status_code == 302


# ------------------------------------------------------------------ venda desligada: páginas
PUBLICAS = ("/", "/mapa", "/compatibilidade", "/numerologia", "/tarot", "/leituras", "/lista", "/minhas-leituras",
            "/privacidade", "/termos", "/live", "/nao-existe")


def _sem_venda(html: str, onde: str):
    assert "R$" not in html, onde
    assert "pay.cakto" not in html, onde
    assert "checkout_click" not in html, onde


def test_venda_fechada_sem_preco_nem_cakto_nas_paginas(ocidental):
    for rota in PUBLICAS:
        _sem_venda(cliente.get(rota, headers=HTML).text, rota)


def test_venda_fechada_vale_ate_para_produto_ativo(ocidental):
    """Ligar os produtos sem abrir a venda: páginas sem preço, com o "me avise"."""
    _mudar(compat="ativo", numerologia="ativo", tarot="ativo")
    for rota in PUBLICAS + ("/compatibilidade?token=oc-x",):
        _sem_venda(cliente.get(rota, headers=HTML).text, rota)
    for rota in ("/mapa", "/compatibilidade", "/numerologia", "/tarot"):
        html = cliente.get(rota).text
        assert "data-me-avise=" in html and "A leitura completa abre em breve" in html, rota


def test_venda_aberta_volta_a_mostrar_preco_e_cakto(ocidental):
    _mudar(vendas_abertas=True)
    mapa = cliente.get("/mapa").text
    assert f"R${ofertas.moeda(ofertas.oferta('mapa', 'ocidental')['preco'])}" in mapa
    assert ofertas.checkout("mapa", "ocidental") in mapa and "data-me-avise" not in mapa
    # a sinastria continua em breve: sem preço, mesmo com a venda aberta
    _sem_venda(cliente.get("/compatibilidade").text, "/compatibilidade")


def test_amostra_do_mapa_traz_o_me_avise_no_lugar_da_compra(ocidental):
    html = cliente.get("/mapa").text
    js = html.split("function desenharAmostra", 1)[1].split("\n}\n", 1)[0]
    assert 'data-me-avise="mapa"' in js and "price-card" not in js
    assert "A leitura completa abre em breve" in js
    # o pedaço vai dentro de template string: nada de crase nem ${ vindo do partial
    partial = (RAIZ / "static" / "ocidental" / "_me_avise.html").read_text(encoding="utf-8")
    sem_comentario = re.sub(r"\{#.*?#\}", "", partial, flags=re.S)
    assert "`" not in sem_comentario and "${" not in sem_comentario
    assert 'src="/static/ocidental/me-avise.js"' in html


def test_me_avise_tem_nome_email_e_whatsapp_obrigatorios(ocidental):
    html = cliente.get("/numerologia").text
    form = re.search(r'<form class="form stack" data-me-avise="numerologia".*?</form>', html, re.S).group(0)
    for campo in ("nome", "email", "whatsapp", "aceita_email"):
        assert re.search(rf'name="{campo}"[^>]*required', form), campo
    assert re.search(r'name="aceita_whatsapp"(?![^>]*(required|checked))', form)


def test_config_diz_que_a_venda_esta_fechada(ocidental):
    assert cliente.get("/api/config").json()["vendas_abertas"] is False


# ------------------------------------------------------------------ me avise / lista (API)
@pytest.fixture
def gravados(monkeypatch, ocidental):
    lista = []
    monkeypatch.setattr(app_mod.db, "registrar_lead", lambda *a: lista.append(a) or True)
    return lista


OK = {"nome": "Ana Souza", "email": "ana@teste.com", "whatsapp": "(51) 99999-8888", "aceita_email": True,
      "interesse": "compat"}


def test_me_avise_grava_o_interesse_do_produto(gravados):
    assert cliente.post("/api/lista", json=OK).status_code == 200
    nome, email, zap, aceita_email, aceita_zap, interesse, _ = gravados[0]
    assert (nome, email, zap, aceita_email, aceita_zap, interesse) == \
        ("Ana Souza", "ana@teste.com", "5551999998888", True, False, "compat")


@pytest.mark.parametrize("campo,valor", [("nome", ""), ("nome", "  "), ("whatsapp", ""), ("whatsapp", "123"),
                                         ("email", "ana"), ("aceita_email", False)])
def test_me_avise_recusa_campo_obrigatorio_vazio(gravados, campo, valor):
    r = cliente.post("/api/lista", json={**OK, campo: valor})
    assert r.status_code == 422 and not gravados


def test_whatsapp_so_recebe_mensagem_com_a_caixa(gravados):
    cliente.post("/api/lista", json={**OK, "aceita_whatsapp": True})
    assert gravados[0][4] is True


def test_interesse_de_produto_oculto_nao_e_gravado(gravados):
    assert cliente.post("/api/lista", json={**OK, "interesse": "comunidade"}).status_code == 200
    assert gravados[0][5] == ""


def test_me_avise_usa_os_limites_da_lista(gravados):
    import limites
    codigos = [cliente.post("/api/lista", json=OK).status_code for _ in range(limites.LISTA.maximo + 1)]
    assert codigos[-1] == 429


def test_lista_pede_nome_e_whatsapp(ocidental):
    html = cliente.get("/lista").text
    assert re.search(r'id="nome"[^>]*required', html) and re.search(r'id="whatsapp"[^>]*required', html)
    assert 'id="aceita-whatsapp" disabled' in html  # a caixa do WhatsApp continua separada e desmarcada


def test_amostra_do_mapa_exige_nome(ocidental):
    r = cliente.post("/api/ocidental/mapa", json={**PESSOA, "nome": " ", "nivel": "amostra", "email": "a@b.co"})
    assert r.status_code == 422 and "nome" in r.json()["detail"]
    html = cliente.get("/mapa").text
    assert re.search(r'id="nome"[^>]*required', html) and "(opcional)" not in html.split('id="nome"')[0][-200:]


# ------------------------------------------------------------------ venda desligada: e-mails
def _emails_ocidental() -> dict:
    import tarot
    dados = {"mapa": PESSOA, "compat": {"a": PESSOA, "b": {**PESSOA, "nome": "Bruno", "data": "1992-03-10"}},
             "numerologia": {"nome": "Ana Maria da Silva", "data": "1990-05-15"}}
    try:
        dados["tarot"] = {"tiragem": tarot.tirar()}
    except tarot.SemSegredo:
        pass
    saida = {}
    for produto, d in dados.items():
        amostra = rotas_ocidental.montar_amostra_email(produto, d)
        saida[f"amostra {produto}"] = marketing.email_amostra_html(produto, amostra, d, "a@b.co", "Ana", "ocidental")
        saida[f"lembrete {produto}"] = marketing.email_lembrete_html(produto, amostra, d, "a@b.co", "ocidental")
        saida[f"abandono {produto}"] = marketing.email_abandono_html(produto, "Ana", marketing.link_site(produto, "x"),
                                                                     "a@b.co", "ocidental")
        for passo in (1, 2, 3):
            saida[f"boas-vindas {passo} {produto}"] = sequencias.email_boas_vindas(passo, produto, d, "a@b.co")[1]
        extra = marketing.bloco_venda_cruzada(produto, d, "ocidental")
        saida[f"entrega {produto}"] = entrega.email_completo_html(produto, "https://x/?token=oc-1", "Ana", extra,
                                                                  "ocidental")
    for passo in (1, 2, 3):
        m = sequencias.email_pos_compra(passo, "ocidental:mapa", "Ana", "a@b.co", ["ocidental:mapa"])
        if m:
            saida[f"pós-compra {passo}"] = m[1]
    saida["mapas do casal"] = entrega.email_mapas_do_casal_html([("Ana", "https://x/?token=oc-1")], "Ana", "ocidental")
    return saida


def test_venda_fechada_sem_preco_nem_cakto_nos_emails(ocidental):
    emails = _emails_ocidental()
    assert len(emails) >= 20
    for nome, html in emails.items():
        _sem_venda(html, nome)
    assert "abre em breve" in emails["amostra mapa"]
    assert sequencias.email_pos_compra(2, "ocidental:mapa", "Ana", "a@b.co", ["ocidental:mapa"]) is None


def test_venda_aberta_volta_a_vender_nos_emails(ocidental):
    _mudar(vendas_abertas=True)
    html = marketing.email_amostra_html("mapa", rotas_ocidental.montar_amostra_email("mapa", PESSOA), PESSOA,
                                        "a@b.co", "Ana", "ocidental")
    assert "pay.cakto" in html and "R$" in html


def test_sequencias_de_venda_ficam_paradas(ocidental, monkeypatch):
    monkeypatch.setattr(sequencias.db, "ativo", lambda: True)
    monkeypatch.setattr(sequencias.db, "candidatos_pos_compra", lambda: [])
    chamou = []
    monkeypatch.setattr(sequencias.db, "candidatos_boas_vindas", lambda: chamou.append(1) or [])
    sequencias.rodar()
    assert not chamou  # boas-vindas nem é consultada com a venda fechada


def test_lembrete_fica_parado(ocidental, monkeypatch):
    monkeypatch.setenv("PADMINI_TAREFAS_CHAVE", "k")
    item = {"id": 1, "produto": "mapa", "dados": PESSOA, "email": "a@b.co", "sistema": "ocidental"}
    monkeypatch.setattr(app_mod.db, "lembretes_pendentes", lambda: [item])
    marcados, enviados = [], []
    monkeypatch.setattr(app_mod.db, "marcar_lembrete_enviado", marcados.append)
    monkeypatch.setattr(app_mod.entrega, "enviar_email", lambda *a, **k: enviados.append(a) or True)
    r = cliente.post("/api/tarefas/lembretes", headers={"Authorization": "Bearer k"}).json()
    assert r["enviados"] == 0 and not enviados and not marcados


def test_carrinho_abandonado_nao_manda_email(ocidental, monkeypatch):
    enviados = []
    monkeypatch.setattr(app_mod.entrega, "enviar_email", lambda *a, **k: enviados.append(a) or True)
    monkeypatch.setattr(app_mod.db, "descadastrado", lambda e: False)
    monkeypatch.setattr(app_mod.db, "abandono_ja_tratado", lambda e, o: False)
    monkeypatch.setattr(app_mod.db, "registrar_abandono", lambda *a: True)
    codigo = ofertas.codigo("mapa", "ocidental")
    r = app_mod._tratar_abandono({"event": "checkout_abandonment",
                                  "data": {"customerEmail": "a@b.co", "customerName": "Ana",
                                           "offer": {"id": f"{codigo}_1"}}})
    assert r["email_enviado"] is False and not enviados


# ------------------------------------------------------------------ webhook continua
def test_webhook_da_cakto_entrega_com_a_venda_fechada(ocidental, monkeypatch):
    novas = copy.deepcopy(ofertas.POR_SISTEMA["ocidental"])
    novas["mapa"].update(checkout="https://pay.cakto.com.br/ocmapa9_1", codigo="ocmapa9")
    monkeypatch.setitem(ofertas.POR_SISTEMA, "ocidental", novas)
    c = _postar_webhook(_evento_oc("m~1990-05-15~14:30~-23.5505~-46.6333~Ana~Sao Paulo", "oc-fechada")).json()
    assert c["produto"] == "mapa" and "token=oc-" in c["link"]
    tok = c["link"].split("token=")[1]
    r = cliente.post("/api/ocidental/mapa", json={**PESSOA, "nome": "", "nivel": "completo", "token": tok})
    assert r.status_code == 200  # link entregue abre (e o completo não exige nome)


# ------------------------------------------------------------------ regra de honestidade
def test_honestidade_nenhum_revisado_enquanto_os_textos_nao_forem(ocidental):
    assert not textos.tudo_revisado()  # hoje: os lotes ainda não foram gravados
    for rota in PUBLICAS + ("/compatibilidade?token=oc-x",):
        assert "revisad" not in cliente.get(rota, headers=HTML).text.lower(), rota
    for nome, html in _emails_ocidental().items():
        assert "revisad" not in html.lower(), nome


def test_honestidade_frase_muda_quando_tudo_for_revisado(ocidental, monkeypatch):
    monkeypatch.setattr(textos, "tudo_revisado", lambda: True)
    assert "revisados pela Dona Valderez" in cliente.get("/").text
    assert "revisad" in textos.frase_revisao("lista_titulo").lower()


def test_frases_de_revisao_nao_ficam_escritas_nos_templates():
    for arq in (RAIZ / "static" / "ocidental").glob("*.html"):
        if arq.name == "estilo.html":
            continue
        texto = re.sub(r"\{#.*?#\}", "", arq.read_text(encoding="utf-8"), flags=re.S).lower()
        assert "revisados pela" not in texto and "revisado pela" not in texto, arq.name

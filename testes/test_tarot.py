"""
Tarot da versão ocidental (Fase D da rodada 2): tiragem de 3 cartas
(Situação · Desafio · Conselho), 78 cartas, só na posição normal.

O ponto central: o completo mostra EXATAMENTE as cartas da amostra — o ID da
tiragem carrega as cartas com selo do servidor e o link pago assina esse ID.
"""
import base64
import json
import urllib.parse

import pytest

from test_app import _postar_webhook, app_mod, cliente

import acesso  # noqa: E402
import cakto  # noqa: E402
import db  # noqa: E402
import entrega  # noqa: E402
import montar_texto_ocidental as mt  # noqa: E402
import ofertas  # noqa: E402
import revisao  # noqa: E402
import tarot  # noqa: E402


def _token(tiragem, versao="ocidental"):
    return acesso.emitir_token("tarot", acesso.chave_tarot(tiragem), versao)


def _id(corpo: bytes, selo: bytes | None = None) -> str:
    selo = tarot._selo(corpo) if selo is None else selo
    return base64.urlsafe_b64encode(corpo + selo).decode().rstrip("=")


# ------------------------------------------------------------------ baralho e sorteio
def test_baralho_de_78():
    assert len(tarot.CARTAS) == 78
    assert len({c["chave"] for c in tarot.CARTAS}) == 78
    assert sum(c["arcano"] == "maior" for c in tarot.CARTAS) == 22
    for naipe, _ in tarot.NAIPES:
        assert sum(c["naipe"] == naipe for c in tarot.CARTAS) == 14


def test_tiragem_tem_3_cartas_diferentes_nas_3_posicoes():
    t = tarot.tirar()
    cartas = tarot.cartas_da_tiragem(t)
    assert [c["posicao"] for c in cartas] == ["situacao", "desafio", "conselho"]
    assert len({c["indice"] for c in cartas}) == 3
    assert tarot.cartas_da_tiragem(t) == cartas  # o mesmo ID dá sempre as mesmas cartas


def test_sorteio_alcanca_o_baralho_inteiro():
    vistas = set()
    for _ in range(2000):
        vistas.update(c["indice"] for c in tarot.cartas_da_tiragem(tarot.tirar()))
    assert vistas == set(range(78))


def test_ids_nao_se_repetem():
    assert len({tarot.tirar() for _ in range(500)}) == 500


def test_id_forjado_ou_alterado_e_recusado():
    valido = tarot.tirar()
    bruto = bytearray(base64.urlsafe_b64decode(valido + "=" * (-len(valido) % 4)))
    bruto[0] = (bruto[0] + 1) % 78  # troca a carta da Situação, mantendo o selo
    invalidos = [
        base64.urlsafe_b64encode(bytes(bruto)).decode().rstrip("="),
        _id(bytes([0, 1, 2]) + b"\0" * 5, selo=b"\0\0\0\0"),  # selo inventado
        _id(bytes([5, 5, 9]) + b"\0" * 5),                     # carta repetida (mesmo com selo certo)
        _id(bytes([5, 78, 9]) + b"\0" * 5),                    # carta que não existe
        valido[:-2], "", "!!!!", "a" * 40,
    ]
    for t in invalidos:
        with pytest.raises(ValueError):
            tarot.cartas_da_tiragem(t)


# ------------------------------------------------------------------ textos
def test_textos_das_78_cartas():
    b = mt.base("tarot")
    assert set(b["cartas"]) == {c["chave"] for c in tarot.CARTAS}
    for chave, t in b["cartas"].items():
        assert t["frase"]["texto"].strip(), chave
        n = len(t["leitura"]["texto"].split())
        assert 40 <= n <= 90, f"{chave}: {n} palavras (tarot: 40 a 90)"
    assert set(b["posicoes"]) == set(tarot.POSICOES)
    assert set(b["conjunto"]["maiores"]) == {0, 1, 2, 3}
    assert set(b["conjunto"]["naipe"]) == {n for n, _ in tarot.NAIPES}


def test_textos_passam_nas_regras_de_tom():
    itens = [i for i in revisao.itens() if i["arquivo"] == "tarot"]
    assert len(itens) == 78 * 2 + 3 + 4 + 4 + 1
    for i in itens:
        assert revisao.problemas(i["texto"], "tarot", i["caminho"]) == [], i["id"]
    # só a leitura tem o limite de 40 a 90; frase e peças não
    assert revisao.limites("tarot", ("cartas", "o_louco", "leitura")) == (40, 90)
    assert revisao.limites("tarot", ("cartas", "o_louco", "frase")) is None


def test_leitura_de_conjunto_escolhe_as_pecas():
    cartas = lambda *ch: [next(c for c in tarot.CARTAS if c["chave"] == k) for k in ch]  # noqa: E731
    b = mt.base("tarot")["conjunto"]
    tres_maiores = mt.conjunto_tarot(cartas("o_louco", "o_mago", "a_lua"))
    assert tres_maiores == [b["maiores"][3]["texto"], b["fecho"]["texto"]]
    duas_copas = mt.conjunto_tarot(cartas("as_de_copas", "o_sol", "rei_de_copas"))
    assert duas_copas == [b["maiores"][1]["texto"], b["naipe"]["copas"]["texto"], b["fecho"]["texto"]]
    sem_naipe = mt.conjunto_tarot(cartas("as_de_copas", "dois_de_paus", "tres_de_ouros"))
    assert sem_naipe == [b["maiores"][0]["texto"], b["fecho"]["texto"]]


# ------------------------------------------------------------------ API
def test_amostra_tem_nome_e_frase_sem_a_leitura():
    r = cliente.post("/api/ocidental/tarot/tirar")
    assert r.status_code == 200
    c = r.json()
    assert len(c["cartas"]) == 3 and all(x["frase"] and x["nome"] for x in c["cartas"])
    assert all("leitura" not in x for x in c["cartas"]) and "conjunto" not in c
    # reabrir a mesma tiragem (recarregar a página) mostra as mesmas cartas
    de_novo = cliente.post("/api/ocidental/tarot", json={"tiragem": c["tiragem"]}).json()
    assert de_novo["cartas"] == c["cartas"]


def test_completo_mostra_exatamente_as_cartas_da_amostra():
    """Amostra → pagamento (link de entrega) → completo: as mesmas 3 cartas, nas mesmas posições."""
    for _ in range(20):
        amostra = cliente.post("/api/ocidental/tarot/tirar").json()
        link = entrega.link_completo("tarot", {"tiragem": amostra["tiragem"]}, "ocidental")
        q = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
        assert q["t"] == [amostra["tiragem"]] and q["token"][0].startswith("oc-")
        completo = cliente.post("/api/ocidental/tarot",
                                json={"tiragem": q["t"][0], "nivel": "completo", "token": q["token"][0]}).json()
        assert [(x["chave"], x["posicao"]) for x in completo["cartas"]] == \
               [(x["chave"], x["posicao"]) for x in amostra["cartas"]]
        assert all(x["leitura"] and x["moldura"] for x in completo["cartas"]) and completo["conjunto"]


def test_completo_trancado():
    t, outra = tarot.tirar(), tarot.tirar()
    pedido = {"tiragem": t, "nivel": "completo"}
    assert cliente.post("/api/ocidental/tarot", json=pedido).status_code == 402
    # token de outra tiragem não abre esta
    assert cliente.post("/api/ocidental/tarot", json={**pedido, "token": _token(outra)}).status_code == 402
    # token da védica (mesma chave) não abre o da ocidental
    assert cliente.post("/api/ocidental/tarot", json={**pedido, "token": _token(t, "vedica")}).status_code == 402
    assert cliente.post("/api/ocidental/tarot", json={**pedido, "token": _token(t)}).status_code == 200


def test_tiragem_forjada_na_api():
    r = cliente.post("/api/ocidental/tarot", json={"tiragem": _id(bytes([0, 1, 2]) + b"\0" * 5, b"\0" * 4)})
    assert r.status_code == 422


def test_pdf():
    t = tarot.tirar()
    assert cliente.post("/api/ocidental/tarot/pdf", json={"tiragem": t}).status_code == 402
    r = cliente.post("/api/ocidental/tarot/pdf", json={"tiragem": t, "token": _token(t)})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


def test_ia_nao_sai_na_amostra():
    assert cliente.post("/api/ocidental/tarot", json={"tiragem": tarot.tirar(), "texto_ia": True}).status_code == 402


def test_pergunta_tem_no_maximo_140_caracteres():
    t = tarot.tirar()
    r = cliente.post("/api/ocidental/tarot", json={"tiragem": t, "nivel": "completo", "token": _token(t),
                                                   "pergunta": "x" * 141})
    assert r.status_code == 422


@pytest.fixture
def ia_falsa(monkeypatch):
    import montar_texto
    chamadas = {"prompts": [], "guardados": []}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste")
    monkeypatch.setattr(montar_texto, "gerar_com_claude", lambda p: chamadas["prompts"].append(p) or "## Texto\n\nOk.")
    monkeypatch.setattr(db, "texto_ia", lambda chave: None)
    monkeypatch.setattr(db, "guardar_texto_ia", lambda *a, **k: chamadas["guardados"].append(a))
    return chamadas


def test_pergunta_vai_so_para_a_ia_e_nao_e_guardada(ia_falsa):
    t = tarot.tirar()
    pedido = {"tiragem": t, "nivel": "completo", "token": _token(t), "texto_ia": True}
    pergunta = "O que preciso entender sobre o meu trabalho?"
    r = cliente.post("/api/ocidental/tarot", json={**pedido, "pergunta": pergunta})
    assert r.status_code == 200 and r.json()["texto_ia"]
    assert pergunta in ia_falsa["prompts"][-1]
    assert ia_falsa["guardados"] == []          # com pergunta: não vai para o cache/banco
    assert pergunta not in json.dumps(r.json())  # nem volta na resposta
    cliente.post("/api/ocidental/tarot", json=pedido)
    assert len(ia_falsa["guardados"]) == 1      # sem pergunta: texto em cache, como os outros produtos
    assert "PERGUNTA da pessoa (texto dela" not in ia_falsa["prompts"][-1]


# ------------------------------------------------------------------ página
@pytest.fixture
def versao(monkeypatch):
    def ligar(v):
        monkeypatch.setenv("PADMINI_SISTEMA", v)
        app_mod._paginas_prontas.clear()
    yield ligar
    app_mod._paginas_prontas.clear()


def test_pagina_so_na_versao_ocidental(versao):
    versao("vedica")
    assert cliente.get("/tarot").status_code == 404
    versao("ocidental")
    html = cliente.get("/tarot").text
    assert "/api/ocidental/tarot/tirar" in html and 'maxlength="140"' in html
    assert f"R${ofertas.preco('tarot', 'ocidental')}" in html and "védic" not in html.lower()
    assert "<img" not in html  # cartas só tipográficas


def test_link_pago_abre_mesmo_com_a_vedica_no_ar(versao):
    versao("vedica")
    t = tarot.tirar()
    r = cliente.get("/tarot?" + urllib.parse.urlencode({"t": t, "token": _token(t)}))
    assert r.status_code == 200 and "/api/ocidental/tarot" in r.text


# ------------------------------------------------------------------ webhook
@pytest.fixture
def oferta_tarot(monkeypatch):
    novas = json.loads(json.dumps(ofertas.POR_SISTEMA["ocidental"]))
    novas["tarot"].update(checkout="https://pay.cakto.com.br/octar1_1", codigo="octar1")
    monkeypatch.setitem(ofertas.POR_SISTEMA, "ocidental", novas)


def test_webhook_entrega_as_mesmas_cartas(oferta_tarot):
    amostra = cliente.post("/api/ocidental/tarot/tirar").json()
    ev = {"event": "purchase_approved", "secret": "segredo-de-teste-webhook",
          "data": {"id": "tar-1", "status": "paid", "offer": {"id": "octar1"},
                   "sck": "t~" + amostra["tiragem"], "customer": {"email": "t@teste.com", "name": "Ana"}}}
    assert cakto.oferta_paga(ev) == ("ocidental", "tarot")
    c = _postar_webhook(ev).json()
    assert c["produto"] == "tarot" and "/tarot?" in c["link"]
    q = urllib.parse.parse_qs(urllib.parse.urlparse(c["link"]).query)
    completo = cliente.post("/api/ocidental/tarot",
                            json={"tiragem": q["t"][0], "nivel": "completo", "token": q["token"][0]}).json()
    assert [x["chave"] for x in completo["cartas"]] == [x["chave"] for x in amostra["cartas"]]


def test_sck_de_tarot_nao_escolhe_o_produto(oferta_tarot):
    """Regra 11: pagou o mapa com sck de tarot → não entrega tarot."""
    ev = {"event": "purchase_approved", "secret": "segredo-de-teste-webhook",
          "data": {"id": "tar-2", "status": "paid", "offer": {"id": ofertas.codigo("mapa")},
                   "sck": "t~" + tarot.tirar(), "customer": {"email": "t@teste.com"}}}
    assert "pendente" in _postar_webhook(ev).json()


def test_live_tarot_exige_sessao():
    t = tarot.tirar()
    assert cliente.post("/api/live/ocidental/token/tarot", json={"tiragem": t}).status_code == 401
    cookie = acesso.emitir_sessao("live", 2_000_000_000)
    r = cliente.post("/api/live/ocidental/token/tarot", json={"tiragem": t}, cookies={"pad_live": cookie})
    assert r.json()["token"] == _token(t)


def test_live_tem_a_aba_de_tarot(versao):
    versao("ocidental")
    html = cliente.get("/live").text
    assert 'id="aba-tarot"' in html and "/api/live/ocidental/token/tarot" in html and "linha laranja" in html


@pytest.mark.skipif(__import__("shutil").which("node") is None, reason="node não instalado")
def test_sck_do_front_e_lido_pelo_back():
    import subprocess
    from test_app import RAIZ
    dados = {"produto": "tarot", "tiragem": tarot.tirar()}
    js = ("global.location={search:'',origin:'https://padmini.teste'};"
          "global.sessionStorage={getItem(){return null},setItem(){}};global.window=global;"
          f"eval(require('fs').readFileSync({json.dumps(str(RAIZ / 'static' / 'afiliado.js'))},'utf8'));"
          f"process.stdout.write(window.padEmpacotar({json.dumps(dados)}));")
    sck = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    pd = cakto.coletar_pd({"data": {"sck": sck}})
    assert cakto.dados_nascimento(pd, "tarot") == {"tiragem": dados["tiragem"]}

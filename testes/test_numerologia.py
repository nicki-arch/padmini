"""
Numerologia pitagórica da versão ocidental (Fase C da rodada 2).

Os exemplos foram conferidos à mão (a conta está no comentário de cada um).
"""
import json
import urllib.parse
from datetime import date

import pytest

from test_app import _postar_webhook, app_mod, cliente

import acesso  # noqa: E402
import cakto  # noqa: E402
import montar_texto_ocidental as mt  # noqa: E402
import numerologia as nu  # noqa: E402
import ofertas  # noqa: E402


# ------------------------------------------------------------------ regras
def test_tabela_pitagorica():
    # A=1 … I=9, J=1 … R=9, S=1 … Z=9
    assert [nu.valor(c) for c in "AIJRSZ"] == [1, 9, 1, 9, 1, 8]
    assert nu.valor("W") == 5 and nu.valor("Y") == 7


def test_acento_e_cedilha():
    assert nu.normalizar_nome("João da Conceição-Araújo D'Ávila") == "JOAODACONCEICAOARAUJODAVILA"


def test_nome_com_acento_e_cedilha_conferido_a_mao():
    # MARIA DA CONCEIÇÃO ARAÚJO → MARIADACONCEICAOARAUJO
    # M4 A1 R9 I9 A1 D4 A1 = 29 · C3 O6 N5 C3 E5 I9 C3 A1 O6 = 41 · A1 R9 A1 U3 J1 O6 = 21
    # Expressão: 29+41+21 = 91 → 10 → 1
    # Alma (vogais A I A A O E I A O A A U O): 1+9+1+1+6+5+9+1+6+1+1+3+6 = 50 → 5
    # Personalidade (M R D C N C C R J): 4+9+4+3+5+3+3+9+1 = 41 → 5
    r = nu.calcular_numerologia("Maria da Conceição Araújo", date(1990, 5, 15), 2026)
    assert r["numeros"]["expressao"] == 1
    assert r["numeros"]["alma"] == 5
    assert r["numeros"]["personalidade"] == 5


def test_y_vogal_e_w_consoante():
    # WAGNER YURI: vogais A E Y U I = 1+5+7+3+9 = 25 → 7; consoantes W G N R R = 5+7+5+9+9 = 35 → 8
    r = nu.calcular_numerologia("Wagner Yuri", date(1990, 1, 1), 2026)["numeros"]
    assert r["alma"] == 7 and r["personalidade"] == 8


def test_caminho_de_vida_usa_a_variante_documentada():
    """04/01/1950. Reduzindo dia, mês e ano separadamente (a regra documentada):
    4 + 1 + (1+9+5+0=15→6) = 11, mestre, não reduz. Somando todos os algarismos
    de uma vez (a outra variante): 0+4+0+1+1+9+5+0 = 20 → 2."""
    assert nu.caminho_de_vida(date(1950, 1, 4)) == 11


@pytest.mark.parametrize("d,esperado", [
    (date(1990, 5, 15), 3),    # 15→6 · 5 · 1990→19→10→1 → 12 → 3
    (date(1985, 11, 29), 9),   # 29→11 · 11 · 1985→23→5 → 27 → 9
    (date(1977, 2, 29 - 1), 9),  # 28→10→1 · 2 · 1977→24→6 → 9
])
def test_caminho_de_vida_exemplos(d, esperado):
    assert nu.caminho_de_vida(d) == esperado


@pytest.mark.parametrize("n,esperado", [(11, 11), (22, 22), (33, 33), (29, 11), (38, 11), (44, 8), (99, 9)])
def test_mestres_nao_reduzem(n, esperado):
    assert nu.reduzir(n) == esperado


def test_dia_e_ano_pessoal():
    # dia 29 → 11 (mestre). Ano Pessoal 2026 de 29/11: 11 + 11 + (2026→10→1) = 23 → 5
    r = nu.calcular_numerologia("Ana Souza", date(1985, 11, 29), 2026)["numeros"]
    assert r["dia"] == 11 and r["ano_pessoal"] == 5


def test_nome_sem_letras_e_recusado():
    with pytest.raises(ValueError):
        nu.calcular_numerologia("123 ---", date(1990, 1, 1))


# ------------------------------------------------------------------ textos
def test_base_de_numerologia_completa():
    b = mt.base("numerologia")
    for numero in nu.NUMEROS:
        assert set(b[numero]) == set(nu.VALORES), numero
        assert b["descricao"][numero]["texto"]


# ------------------------------------------------------------------ API e páginas
PEDIDO = {"nome": "Maria da Conceição Araújo", "data": "1950-01-04"}


def _token(nome=PEDIDO["nome"], data=PEDIDO["data"], versao="ocidental"):
    return acesso.emitir_token("numerologia", acesso.chave_numerologia(nu.normalizar_nome(nome), data), versao)


def test_amostra_so_o_caminho_de_vida():
    r = cliente.post("/api/ocidental/numerologia", json=PEDIDO)
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["caminho_de_vida"]["valor"] == 11 and c["caminho_de_vida"]["mestre"]
    assert "numeros" not in c


def test_completo_trancado_e_com_token():
    assert cliente.post("/api/ocidental/numerologia", json={**PEDIDO, "nivel": "completo"}).status_code == 402
    assert cliente.post("/api/ocidental/numerologia",
                        json={**PEDIDO, "nivel": "completo", "token": _token(versao="vedica")}).status_code == 402
    # o token é do nome exato: trocar uma letra não abre
    outro = {**PEDIDO, "nome": "Maria da Conceicao Araujo X"}
    assert cliente.post("/api/ocidental/numerologia",
                        json={**outro, "nivel": "completo", "token": _token()}).status_code == 402
    r = cliente.post("/api/ocidental/numerologia", json={**PEDIDO, "nivel": "completo", "token": _token()})
    assert r.status_code == 200
    assert [x["chave"] for x in r.json()["numeros"]] == list(nu.NUMEROS)


def test_acento_nao_muda_a_chave():
    """"Conceição" e "Conceicao" são o mesmo nome para a numerologia."""
    sem_acento = {**PEDIDO, "nome": "MARIA DA CONCEICAO ARAUJO"}
    r = cliente.post("/api/ocidental/numerologia", json={**sem_acento, "nivel": "completo", "token": _token()})
    assert r.status_code == 200


def test_pdf():
    assert cliente.post("/api/ocidental/numerologia/pdf", json={**PEDIDO, "nivel": "completo"}).status_code == 402
    r = cliente.post("/api/ocidental/numerologia/pdf", json={**PEDIDO, "nivel": "completo", "token": _token()})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


def test_ia_nao_sai_na_amostra():
    assert cliente.post("/api/ocidental/numerologia", json={**PEDIDO, "texto_ia": True}).status_code == 402


@pytest.fixture
def versao(monkeypatch):
    def ligar(v):
        monkeypatch.setenv("PADMINI_SISTEMA", v)
        app_mod._paginas_prontas.clear()
    yield ligar
    app_mod._paginas_prontas.clear()


def test_pagina_so_na_versao_ocidental(versao):
    versao("vedica")
    assert cliente.get("/numerologia").status_code == 404
    versao("ocidental")
    html = cliente.get("/numerologia").text
    assert "certidão" in html and "/api/ocidental/numerologia" in html
    assert f"R${ofertas.preco('numerologia', 'ocidental')}" in html and "védic" not in html.lower()


def test_link_pago_abre_mesmo_com_a_vedica_no_ar(versao):
    versao("vedica")
    r = cliente.get("/numerologia?" + urllib.parse.urlencode({**PEDIDO, "token": _token()}))
    assert r.status_code == 200 and "/api/ocidental/numerologia" in r.text


# ------------------------------------------------------------------ webhook
@pytest.fixture
def oferta_numerologia(monkeypatch):
    novas = json.loads(json.dumps(ofertas.POR_SISTEMA["ocidental"]))
    novas["numerologia"].update(checkout="https://pay.cakto.com.br/ocnum1_1", codigo="ocnum1")
    monkeypatch.setitem(ofertas.POR_SISTEMA, "ocidental", novas)


def test_webhook_entrega_numerologia(oferta_numerologia):
    ev = {"event": "purchase_approved", "secret": "segredo-de-teste-webhook",
          "data": {"id": "num-1", "status": "paid", "offer": {"id": "ocnum1"},
                   "sck": "n~1950-01-04~Maria da Conceição Araújo",
                   "customer": {"email": "m@teste.com", "name": "Maria"}}}
    assert cakto.oferta_paga(ev) == ("ocidental", "numerologia")
    c = _postar_webhook(ev).json()
    assert c["produto"] == "numerologia" and "/numerologia?" in c["link"]
    q = urllib.parse.parse_qs(urllib.parse.urlparse(c["link"]).query)
    r = cliente.post("/api/ocidental/numerologia",
                     json={"nome": q["nome"][0], "data": q["data"][0], "nivel": "completo", "token": q["token"][0]})
    assert r.status_code == 200


def test_sck_de_numerologia_nao_escolhe_o_produto(oferta_numerologia):
    """Regra 11: pagou o tarot/mapa com sck de numerologia → não entrega numerologia."""
    ev = {"event": "purchase_approved", "secret": "segredo-de-teste-webhook",
          "data": {"id": "num-2", "status": "paid", "offer": {"id": ofertas.codigo("mapa")},
                   "sck": "n~1950-01-04~Maria da Conceição Araújo",
                   "customer": {"email": "m@teste.com"}}}
    assert "pendente" in _postar_webhook(ev).json()


def test_live_numerologia_exige_sessao():
    assert cliente.post("/api/live/ocidental/token/numerologia", json=PEDIDO).status_code == 401
    cookie = acesso.emitir_sessao("live", 2_000_000_000)
    r = cliente.post("/api/live/ocidental/token/numerologia", json=PEDIDO, cookies={"pad_live": cookie})
    assert r.json()["token"] == _token()


@pytest.mark.skipif(__import__("shutil").which("node") is None, reason="node não instalado")
def test_sck_do_front_e_lido_pelo_back():
    import subprocess
    from test_app import RAIZ
    dados = {"produto": "numerologia", "nome": "Maria da Conceição Araújo dos Santos", "data": "1950-01-04"}
    js = ("global.location={search:'',origin:'https://padmini.teste'};"
          "global.sessionStorage={getItem(){return null},setItem(){}};global.window=global;"
          f"eval(require('fs').readFileSync({json.dumps(str(RAIZ / 'static' / 'afiliado.js'))},'utf8'));"
          f"process.stdout.write(window.padEmpacotar({json.dumps(dados)}));")
    sck = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    pd = cakto.coletar_pd({"data": {"sck": sck}})
    assert cakto.dados_nascimento(pd, "numerologia") == {"nome": dados["nome"], "data": dados["data"]}

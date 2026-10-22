"""
Rodada 20.3, Parte B (NIC-31): links pagos sem dado de nascimento.

O link do mapa natal e o de "O seu ano" levavam nome, data, hora, cidade e coordenadas na URL
(`/mapa?data=…&nome=…&token=oc-…`), que iam parar no log de acesso da Render, no histórico do
navegador e em qualquer pixel. Agora o link leva SÓ um token cifrado (AES-GCM, como o do
calendário): `/mapa?token=oc-mapa-…`, `/seu-ano?token=oc-ano-…`. Os links antigos continuam
abrindo e a página troca a barra para o formato novo; o log de acesso sai sem a query.
"""
import base64
import logging
from urllib.parse import parse_qs, urlparse

import pytest

import test_app as base  # configura o ambiente e o app
from test_app import cliente

import acesso  # noqa: E402
import app as app_mod  # noqa: E402
import entrega  # noqa: E402

PESSOA = {"nome": "Ana Clara", "data": "1990-05-15", "hora": "14:30", "lat": -30.0331, "lon": -51.23,
          "cidade": "Porto Alegre, RS"}
ANO = {**PESSOA, "inicio": "2026-10"}
DADOS_NA_URL = {"data", "hora", "lat", "lon", "nome", "cidade", "inicio"}


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


def _query(link: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(link).query, keep_blank_values=True).items()}


def _link_antigo(produto: str, dados: dict) -> str:
    """O formato de antes desta rodada (token HMAC + os dados na URL), como os e-mails já enviados."""
    from urllib.parse import urlencode
    if produto == "mapa":
        chave = acesso.chave_mapa(dados["data"], dados["hora"], dados["lat"], dados["lon"])
        q = {k: dados[k] for k in ("data", "hora", "lat", "lon", "cidade", "nome")}
        return "/mapa?" + urlencode({**q, "token": acesso.emitir_token("mapa", chave, "ocidental")})
    chave = acesso.chave_previsao(dados["data"], dados["hora"], dados["lat"], dados["lon"], dados["inicio"])
    q = {k: dados[k] for k in ("data", "hora", "lat", "lon", "cidade", "nome", "inicio")}
    return "/seu-ano?" + urlencode({**q, "token": acesso.emitir_token("previsao", chave, "ocidental")})


# ------------------------------------------------------------------ links emitidos
@pytest.mark.parametrize("produto, dados, pagina, prefixo", [
    ("mapa", PESSOA, "/mapa", "oc-mapa-"), ("previsao", ANO, "/seu-ano", "oc-ano-"),
    ("calendario", ANO, "/calendario-lunar", "oc-cal-")])
def test_link_emitido_so_tem_o_token(produto, dados, pagina, prefixo):
    link = entrega.link_completo(produto, dados, "ocidental")
    assert urlparse(link).path == pagina
    q = _query(link)
    assert list(q) == ["token"] and q["token"].startswith(prefixo)
    assert not DADOS_NA_URL & set(q)
    for dado in ("Ana", "1990", "14%3A30", "Porto", "-30.0331"):
        assert dado not in link


def test_kit_e_mapas_do_casal_so_com_token():
    for l in entrega.link_completo("kit", ANO, "ocidental").split("\n"):
        assert list(_query(l)) == ["token"]
    assert list(_query(entrega.link_completo("mapa", {**PESSOA, "hora": ""}, "ocidental"))) == ["token"]


def test_vedica_nao_muda():
    """A védica continua com o link de sempre (a foto da védica confere o resto)."""
    q = _query(entrega.link_completo("mapa", PESSOA, "vedica"))
    assert {"data", "hora", "lat", "lon", "token"} <= set(q) and not q["token"].startswith("oc-")


def test_token_cabe_em_400_caracteres_com_nome_e_cidade_longos():
    longo = {**ANO, "nome": "Maria " * 30 + "ção", "cidade": "São João do Rio Vermelho " * 10}
    for produto in ("mapa", "previsao"):
        token = acesso.emitir_token_cifrado(produto, longo)
        assert len(token) <= 400
        d = acesso.abrir_token_cifrado(produto, token)
        assert len(d["nome"]) <= acesso.LIMITE_NOME and len(d["cidade"]) <= acesso.LIMITE_CIDADE
        assert (d["data"], d["hora"], d["lat"], d["lon"]) == (ANO["data"], ANO["hora"], ANO["lat"], ANO["lon"])


def test_token_nao_deixa_ler_os_dados():
    token = acesso.emitir_token_cifrado("mapa", PESSOA)
    bruto = base64.urlsafe_b64decode(token[len("oc-mapa-"):] + "==")
    assert b"1990" not in bruto and b"Ana" not in bruto
    assert token != acesso.emitir_token_cifrado("mapa", PESSOA)  # nonce novo a cada emissão


# ------------------------------------------------------------------ as APIs com o token sozinho
def test_completo_e_pdf_abrem_so_com_o_token(ocidental):
    t = _query(entrega.link_completo("mapa", PESSOA, "ocidental"))["token"]
    r = cliente.post("/api/ocidental/mapa", json={"token": t, "nivel": "completo"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["nome"], d["data"], d["hora"], d["cidade"]) == ("Ana Clara", "1990-05-15", "14:30", "Porto Alegre, RS")
    assert "link_novo" not in d
    pdf = cliente.post("/api/ocidental/pdf", json={"token": t, "nivel": "completo"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_ano_e_pdf_abrem_so_com_o_token(ocidental):
    t = _query(entrega.link_completo("previsao", ANO, "ocidental"))["token"]
    r = cliente.post("/api/ocidental/previsao", json={"token": t, "nivel": "completo"})
    assert r.status_code == 200, r.text
    assert r.json()["inicio"] == "2026-10-01" and r.json()["data"] == "1990-05-15"
    pdf = cliente.post("/api/ocidental/previsao/pdf", json={"token": t, "nivel": "completo"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_o_servidor_ignora_dados_mandados_junto_com_o_token(ocidental):
    """O pedido sai de dentro do token: trocar a data no corpo não muda (nem abre) outro mapa."""
    t = acesso.emitir_token_cifrado("mapa", PESSOA)
    r = cliente.post("/api/ocidental/mapa", json={**PESSOA, "data": "2001-01-01", "token": t, "nivel": "completo"})
    assert r.status_code == 200 and r.json()["data"] == "1990-05-15"


def _adulterado(token: str) -> str:
    i = len(token) - 10
    return token[:i] + ("A" if token[i] != "A" else "B") + token[i + 1:]


@pytest.mark.parametrize("rota, produto", [("/api/ocidental/mapa", "mapa"), ("/api/ocidental/pdf", "mapa"),
                                           ("/api/ocidental/previsao", "previsao"),
                                           ("/api/ocidental/previsao/pdf", "previsao")])
def test_token_ruim_e_402(rota, produto, ocidental, monkeypatch):
    bom = acesso.emitir_token_cifrado(produto, ANO)
    prefixo = acesso.CIFRADOS[produto][0]
    ruins = [_adulterado(bom), prefixo + "A" * 80, prefixo, prefixo + "!!!", prefixo + "A" * 600]
    monkeypatch.setattr(acesso, "SEGREDO", "outro-segredo")
    ruins.append(acesso.emitir_token_cifrado(produto, ANO))  # de outro segredo
    monkeypatch.setattr(acesso, "SEGREDO", "segredo-de-teste-tokens")
    for ruim in ruins:
        r = cliente.post(rota, json={"token": ruim, "nivel": "completo"})
        assert r.status_code == 402, (ruim[:30], r.status_code, r.text)


def test_token_de_um_produto_nao_abre_o_outro(ocidental):
    ano = acesso.emitir_token_cifrado("previsao", ANO)
    mapa = acesso.emitir_token_cifrado("mapa", PESSOA)
    assert acesso.abrir_token_cifrado("mapa", ano) is None and acesso.abrir_token_cifrado("previsao", mapa) is None
    assert cliente.post("/api/ocidental/mapa", json={"token": ano, "nivel": "completo"}).status_code == 402
    assert cliente.post("/api/ocidental/pdf", json={"token": ano, "nivel": "completo"}).status_code == 402
    corpo = {"token": mapa, "nivel": "completo", "inicio": "2026-10"}
    assert cliente.post("/api/ocidental/previsao", json=corpo).status_code == 402
    # nem trocando o prefixo (a chave e o dado associado são do produto)
    trocado = "oc-ano-" + mapa[len("oc-mapa-"):]
    assert cliente.post("/api/ocidental/previsao", json={**corpo, "token": trocado}).status_code == 402
    # nem o do calendário
    cal = acesso.emitir_token_calendario(ANO["data"], ANO["hora"], ANO["lat"], ANO["lon"], "2026-10")
    assert cliente.post("/api/ocidental/mapa", json={**PESSOA, "token": cal, "nivel": "completo"}).status_code == 402


def test_token_novo_nao_abre_a_vedica():
    t = acesso.emitir_token_cifrado("mapa", PESSOA)
    chave = acesso.chave_mapa(PESSOA["data"], PESSOA["hora"], PESSOA["lat"], PESSOA["lon"])
    assert acesso.completo_liberado("mapa", chave, t, "ocidental")
    assert not acesso.completo_liberado("mapa", chave, t, "vedica")


# ------------------------------------------------------------------ links antigos
@pytest.mark.parametrize("produto, api", [("mapa", "/api/ocidental/mapa"), ("previsao", "/api/ocidental/previsao")])
def test_link_antigo_abre_e_recebe_o_link_novo(produto, api, ocidental):
    antigo = _link_antigo(produto, ANO)
    q = _query(antigo)
    assert {"data", "nome", "token"} <= set(q)  # o formato dos e-mails já enviados
    r = cliente.post(api, json={**{k: v for k, v in q.items()}, "lat": float(q["lat"]), "lon": float(q["lon"]),
                                "nivel": "completo"})
    assert r.status_code == 200, r.text
    novo = r.json()["link_novo"]
    pagina = "/mapa" if produto == "mapa" else "/seu-ano"
    assert urlparse(novo).path == pagina and list(_query(novo)) == ["token"]
    r2 = cliente.post(api, json={"token": _query(novo)["token"], "nivel": "completo"})
    assert r2.status_code == 200 and "link_novo" not in r2.json()
    assert r2.json()["data"] == ANO["data"]


def test_link_antigo_adulterado_continua_402(ocidental):
    q = _query(_link_antigo("mapa", PESSOA))
    corpo = {**q, "lat": float(q["lat"]), "lon": float(q["lon"]), "nivel": "completo", "data": "1991-05-15"}
    assert cliente.post("/api/ocidental/mapa", json=corpo).status_code == 402


@pytest.mark.parametrize("pagina, produto", [("/mapa", "mapa"), ("/seu-ano", "previsao")])
def test_paginas_trocam_a_barra_para_o_formato_novo(pagina, produto, ocidental):
    html = cliente.get(pagina + "?token=" + acesso.emitir_token_cifrado(produto, ANO),
                       headers={"accept": "text/html"}).text
    assert "history.replaceState(null, \"\", d.link_novo)" in html
    assert 'token.startsWith("' + acesso.CIFRADOS[produto][0] + '")' in html


def test_pagina_com_token_novo_abre_mesmo_com_o_produto_oculto(ocidental, monkeypatch):
    import catalogo
    import copy
    dados = copy.deepcopy(catalogo.dados())
    for p in dados["produtos"]:
        p["estado"] = "oculto"
    catalogo.usar(dados)
    assert cliente.get("/seu-ano").status_code == 404
    t = acesso.emitir_token_cifrado("previsao", ANO)
    assert cliente.get("/seu-ano?token=" + t).status_code == 200


# ------------------------------------------------------------------ o calendário não muda
def test_calendario_continua_igual():
    """Formato e chave do token do calendário iguais aos da rodada 14: um token montado aqui
    com a especificação de lá (HKDF info "padmini|calendario-lunar|v1", AAD = "oc-cal-",
    "data|hora|lat|lon|inicio") abre, e o emitido continua sendo assim."""
    import os
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    chave = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                 info=b"padmini|calendario-lunar|v1").derive(b"segredo-de-teste-tokens")
    nonce = os.urandom(12)
    claro = b"1990-05-15|14:30|-30.0331|-51.2300|2026-10"
    token = "oc-cal-" + base64.urlsafe_b64encode(nonce + AESGCM(chave).encrypt(nonce, claro, b"oc-cal-")).decode().rstrip("=")
    assert acesso.abrir_token_calendario(token) == {"data": "1990-05-15", "hora": "14:30", "lat": -30.0331,
                                                    "lon": -51.23, "inicio": "2026-10"}
    emitido = acesso.emitir_token_calendario("1990-05-15", "14:30", -30.0331, -51.23, "2026-10")
    bruto = base64.urlsafe_b64decode(emitido[len("oc-cal-"):] + "==")
    assert AESGCM(chave).decrypt(bruto[:12], bruto[12:], b"oc-cal-") == claro


# ------------------------------------------------------------------ o /live
def test_live_devolve_link_so_com_token(ocidental):
    cookie = {"pad_live": acesso.emitir_sessao("live", 2_000_000_000)}
    cliente.cookies.update(cookie)
    try:
        t = cliente.post("/api/live/ocidental/token/mapa", json=PESSOA).json()
    finally:
        cliente.cookies.clear()
    assert t["link"] == "/mapa?token=" + t["token"] and t["token"].startswith("oc-mapa-")


# ------------------------------------------------------------------ o log de acesso
def _linha_de_acesso(caminho: str) -> str:
    """A linha que o uvicorn escreve para um pedido (o mesmo formato e argumentos dele)."""
    from uvicorn.logging import AccessFormatter
    registro = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 0,
                                 '%s - "%s %s HTTP/%s" %d', ("10.0.0.1:5555", "GET", caminho, "1.1", 200), None)
    for filtro in logging.getLogger("uvicorn.access").filters:
        filtro.filter(registro)
    return AccessFormatter('%(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False).format(registro)


def test_log_de_acesso_sem_query():
    linha = _linha_de_acesso("/mapa?token=oc-mapa-AAAA")
    assert linha == '10.0.0.1:5555 - "GET /mapa HTTP/1.1" 200 OK'
    antigo = _linha_de_acesso("/mapa?data=1990-05-15&hora=14%3A30&nome=Ana&token=oc-1")
    assert "?" not in antigo and "1990" not in antigo and "Ana" not in antigo
    assert _linha_de_acesso("/api/saude") == '10.0.0.1:5555 - "GET /api/saude HTTP/1.1" 200 OK'


def test_filtro_esta_no_logger_do_uvicorn():
    assert any(isinstance(f, app_mod.SemQueryNoLog) for f in logging.getLogger("uvicorn.access").filters)


def test_uvicorn_de_verdade_registra_sem_query():
    """O uvicorn de verdade, num socket local: a linha de acesso sai sem a query."""
    import socket
    import threading
    import time
    import urllib.request

    import uvicorn

    async def mini(scope, receive, send):
        if scope["type"] != "http":
            return
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    class Lista(logging.Handler):
        def __init__(self):
            super().__init__()
            self.linhas = []

        def emit(self, record):
            self.linhas.append(record.getMessage())

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    # o Config configura os loggers do uvicorn (como na Render, antes de importar o app)
    servidor = uvicorn.Server(uvicorn.Config(mini, host="127.0.0.1", port=porta, log_level="info", lifespan="off"))
    acesso_log = logging.getLogger("uvicorn.access")
    filtro, lista = app_mod.SemQueryNoLog(), Lista()
    acesso_log.addFilter(filtro)  # o que o import do app.py faz
    acesso_log.addHandler(lista)
    th = threading.Thread(target=servidor.run, daemon=True)
    try:
        th.start()
        for _ in range(100):
            if servidor.started:
                break
            time.sleep(0.05)
        urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
            f"http://127.0.0.1:{porta}/mapa?data=1990-05-15&nome=Ana&token=oc-1", timeout=5).read()
        time.sleep(0.2)
    finally:
        servidor.should_exit = True
        th.join(5)
        acesso_log.removeHandler(lista)
        acesso_log.removeFilter(filtro)
    assert lista.linhas and all("?" not in l and "Ana" not in l for l in lista.linhas), lista.linhas
    assert any('"GET /mapa HTTP/1.1" 200' in l for l in lista.linhas), lista.linhas

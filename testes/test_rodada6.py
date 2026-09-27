"""
Rodada 6, Fase A: e-mail obrigatório antes de qualquer amostra grátis (ocidental).

- Sem e-mail válido: 422, e nada é calculado.
- A resposta da API leva só a parte da tela; o resto sai no e-mail (teste por produto,
  procurando o texto do e-mail no JSON inteiro).
- E-mail que não sai (Resend fora, sem chave): a tela mostra tudo e a equipe é avisada.
- Completo com token e /live não pedem e-mail.
- Tarot: a pergunta nunca vai para o banco nem para o e-mail.
"""
import html
import json
import subprocess
import shutil

import pytest

from test_app import RAIZ, app_mod, cliente

import acesso  # noqa: E402
import alertas  # noqa: E402
import db  # noqa: E402
import entrega  # noqa: E402
import tarot  # noqa: E402

ANA = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30", "lat": -23.5505, "lon": -46.6333, "cidade": "São Paulo"}
RUI = {"nome": "Rui", "data": "1988-11-02", "hora": "09:10", "lat": -22.9068, "lon": -43.1729, "cidade": "Rio"}
NUM = {"nome": "Ana Maria da Silva", "data": "1990-05-15"}
EMAIL = "ana@exemplo.com"
PERGUNTA = "Devo aceitar a proposta do meu chefe?"


@pytest.fixture
def emails(monkeypatch):
    enviados = []
    monkeypatch.setenv("RESEND_API_KEY", "teste")
    monkeypatch.setattr(entrega, "enviar_email", lambda d, a, h: enviados.append((d, a, h)) or True)
    return enviados


@pytest.fixture
def banco(monkeypatch):
    gravado = []
    monkeypatch.setattr(db, "amostras_enviadas_hoje", lambda e: 0)
    monkeypatch.setattr(db, "registrar_amostra_email", lambda *a, **k: gravado.append((a, k)) or True)
    return gravado


@pytest.fixture
def avisos(monkeypatch):
    lista = []
    monkeypatch.setattr(alertas, "alertar", lambda *a, **k: lista.append(a))
    return lista


def _amostra(produto, extra=None):
    extra = {"email": EMAIL, **(extra or {})}
    if produto == "mapa":
        return cliente.post("/api/ocidental/mapa", json={**ANA, "nivel": "amostra", **extra})
    if produto == "compat":
        return cliente.post("/api/ocidental/sinastria", json={"a": ANA, "b": RUI, **extra})
    if produto == "numerologia":
        return cliente.post("/api/ocidental/numerologia", json={**NUM, **extra})
    return cliente.post("/api/ocidental/tarot/tirar", json=extra)


PRODUTOS = ["mapa", "compat", "numerologia", "tarot"]


# ------------------------------------------------------------------ o portão
@pytest.mark.parametrize("produto", PRODUTOS)
@pytest.mark.parametrize("email", [None, "", "sem-arroba", "a@b"])
def test_amostra_sem_email_valido_e_422(produto, email, banco, emails):
    extra = {} if email is None else {"email": email}
    corpo = {"mapa": {**ANA, "nivel": "amostra"}, "compat": {"a": ANA, "b": RUI},
             "numerologia": NUM, "tarot": {}}[produto]
    rota = {"mapa": "/api/ocidental/mapa", "compat": "/api/ocidental/sinastria",
            "numerologia": "/api/ocidental/numerologia", "tarot": "/api/ocidental/tarot/tirar"}[produto]
    r = cliente.post(rota, json={**corpo, **extra})
    assert r.status_code == 422, (produto, email, r.text)
    assert banco == [] and emails == []


def test_reabrir_tiragem_sem_email_e_422(banco):
    assert cliente.post("/api/ocidental/tarot", json={"tiragem": tarot.tirar()}).status_code == 422


def test_limite_por_email(monkeypatch, emails):
    monkeypatch.setattr(db, "amostras_enviadas_hoje", lambda e: 3)
    assert _amostra("mapa").status_code == 429 and emails == []


# ------------------------------------------------------------------ tela × e-mail
def _so_no_email(produto, inteira):
    """Os textos que a tela NÃO pode ter (e o e-mail tem)."""
    if produto == "mapa":
        a = inteira["amostra"]
        return [i["texto"] for i in a["triade"] if i["ponto"] != "sol"] + [a["aspecto"]["texto"]]
    if produto == "compat":
        return [inteira["ponto_forte"]["texto"], inteira["ponto_atencao"]["texto"], inteira["ponto_atencao"]["titulo"]]
    if produto == "numerologia":
        return [inteira["caminho_de_vida"]["texto"]]
    return [c["frase"] for c in inteira["cartas"]]


@pytest.mark.parametrize("produto", PRODUTOS)
def test_api_nao_traz_a_parte_do_email(produto, emails, banco, monkeypatch):
    if produto == "tarot":  # a mesma tiragem nas duas chamadas
        fixa = tarot.tirar()
        monkeypatch.setattr(tarot, "tirar", lambda: fixa)
    tela = _amostra(produto)
    assert tela.status_code == 200, tela.text
    t = tela.json()
    assert t["email"] == {"enviado": True, "para": EMAIL} and t["parcial"] is True
    # a versão inteira (como sairia se o e-mail falhasse), para saber o que procurar
    monkeypatch.setattr(entrega, "enviar_email", lambda *a: False)
    inteira = _amostra(produto).json()
    assert "parcial" not in inteira
    bruto = json.dumps(t, ensure_ascii=False)
    for texto in _so_no_email(produto, inteira):
        assert texto and texto not in bruto, (produto, texto[:60])
        assert any(texto in html.unescape(h) for _, _, h in emails), (produto, texto[:60])
    assert len(emails) == 1 and emails[0][0] == EMAIL


def test_o_que_fica_na_tela_tem_valor_sozinho(emails, banco):
    mapa = _amostra("mapa").json()["amostra"]
    sol = next(i for i in mapa["triade"] if i["ponto"] == "sol")
    assert sol["texto"] and sol["signo"] and sol["grau"]
    assert {i["ponto"] for i in mapa["triade"]} == {"sol", "lua", "ascendente"}  # nomes de Lua e Asc
    casal = _amostra("compat").json()
    assert 0 <= casal["indice"] <= 100 and casal["ponto_forte"]["titulo"] and casal["indice_texto"]
    num = _amostra("numerologia").json()
    assert isinstance(num["caminho_de_vida"]["valor"], int) and num["caminho_de_vida"]["descricao"]
    cartas = _amostra("tarot").json()["cartas"]
    assert len(cartas) == 3 and all(c["nome"] and c["posicao_pt"] for c in cartas)


def test_email_da_amostra_tem_as_frases_do_tarot(emails, banco, monkeypatch):
    fixa = tarot.tirar()
    monkeypatch.setattr(tarot, "tirar", lambda: fixa)
    _amostra("tarot")
    import montar_texto_ocidental as mt
    frases = [c["frase"] for c in mt.montar_tarot(tarot.cartas_da_tiragem(fixa), "amostra")["cartas"]]
    corpo = html.unescape(emails[0][2])
    assert all(f in corpo for f in frases)


# ------------------------------------------------------------------ falha do e-mail
@pytest.mark.parametrize("produto", PRODUTOS)
def test_email_que_nao_sai_mostra_tudo_e_avisa(produto, monkeypatch, banco, avisos):
    monkeypatch.setenv("RESEND_API_KEY", "teste")
    monkeypatch.setattr(entrega, "enviar_email", lambda *a: False)
    r = _amostra(produto)
    assert r.status_code == 200
    c = r.json()
    assert c["email"]["enviado"] is False and "parcial" not in c
    for texto in _so_no_email(produto, c):
        assert texto  # tudo na tela
    assert avisos and len(banco) == 1  # a equipe sabe; o registro existe


def test_sem_chave_do_resend_mostra_tudo(monkeypatch, banco, avisos):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    c = _amostra("mapa").json()
    assert c["email"]["enviado"] is False and all(i["texto"] for i in c["amostra"]["triade"])


# ------------------------------------------------------------------ registro
def test_registra_com_a_caixa_e_a_versao(emails, banco):
    _amostra("mapa", {"aceita_sequencia": True, "origem": {"utm_source": "tiktok", "lixo": "x"}})
    (email, produto, dados, aceita_lembrete, origem, versao), k = banco[0]
    assert (email, produto, versao) == (EMAIL, "mapa", "ocidental")
    assert k["aceita_sequencia"] is True and aceita_lembrete is True
    assert origem == {"utm_source": "tiktok"} and dados["data"] == ANA["data"]
    _amostra("numerologia")
    assert banco[1][1]["aceita_sequencia"] is False  # caixa desmarcada por padrão


def test_pergunta_do_tarot_nao_vai_para_o_banco_nem_para_o_email(emails, banco):
    r = _amostra("tarot", {"pergunta": PERGUNTA})
    assert r.status_code == 200
    (_, produto, dados, *_), _ = banco[0]
    assert produto == "tarot" and set(dados) == {"tiragem"}
    assert PERGUNTA not in json.dumps(banco, ensure_ascii=False, default=str)
    assert all(PERGUNTA not in h and "chefe" not in h for _, _, h in emails)


# ------------------------------------------------------------------ o que NÃO pede e-mail
def test_completo_com_token_nao_pede_email(banco, emails):
    chave = acesso.chave_mapa(ANA["data"], ANA["hora"], ANA["lat"], ANA["lon"])
    r = cliente.post("/api/ocidental/mapa", json={**ANA, "nivel": "completo",
                                                  "token": acesso.emitir_token("mapa", chave, "ocidental")})
    assert r.status_code == 200 and "secoes" in r.json()
    t = tarot.tirar()
    r = cliente.post("/api/ocidental/tarot", json={"tiragem": t, "nivel": "completo",
                                                   "token": acesso.emitir_token("tarot", acesso.chave_tarot(t), "ocidental")})
    assert r.status_code == 200 and banco == [] and emails == []


def test_live_nao_pede_email(banco, emails):
    cookie = {"pad_live": acesso.emitir_sessao("live", 2_000_000_000)}
    tir = cliente.post("/api/ocidental/tarot/tirar", json={}, cookies=cookie)
    assert tir.status_code == 200 and all(c["frase"] for c in tir.json()["cartas"])
    assert cliente.post("/api/live/ocidental/token/tarot", json={"tiragem": tir.json()["tiragem"]},
                        cookies=cookie).status_code == 200
    assert cliente.post("/api/live/ocidental/token/mapa", json=ANA, cookies=cookie).status_code == 200
    assert cliente.post("/api/live/ocidental/token/numerologia", json=NUM, cookies=cookie).status_code == 200
    assert cliente.post("/api/live/ocidental/token/sinastria", json={"a": ANA, "b": RUI},
                        cookies=cookie).status_code == 200
    assert banco == [] and emails == []


def test_sessao_live_falsa_nao_libera_o_sorteio(banco):
    assert cliente.post("/api/ocidental/tarot/tirar", json={}, cookies={"pad_live": "falso"}).status_code == 422


# ------------------------------------------------------------------ páginas
@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


@pytest.mark.parametrize("rota", ["/mapa", "/compatibilidade", "/numerologia", "/tarot"])
def test_formulario_tem_email_antes_do_botao_e_caixa_desmarcada(rota, ocidental):
    html = cliente.get(rota).text
    form = html[html.index('<form id="form"'):html.index("</form>")]
    assert form.index('id="email"') < form.index('id="enviar"')
    assert 'type="email"' in form and "required" in form[form.index('id="email"') - 20:form.index('id="email"') + 200]
    caixa = form[form.index('id="aceita-sequencia"') - 40:form.index('id="aceita-sequencia"') + 60]
    assert "checked" not in caixa
    assert "até 3 e-mails" in form
    assert "/static/ocidental/amostra-email.js" in html and "/static/amostra-email.js" not in html


def test_vedica_nao_pede_email_na_amostra(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    app_mod._paginas_prontas.clear()
    try:
        for rota in ("/mapa", "/compatibilidade"):
            html = cliente.get(rota).text
            assert 'id="aceita-sequencia"' not in html and "/static/ocidental/amostra-email.js" not in html
    finally:
        app_mod._paginas_prontas.clear()


def test_privacidade_ocidental_explica_o_email_da_amostra(ocidental):
    html = cliente.get("/privacidade").text
    for trecho in ("o e-mail é a condição para recebê-la", "art. 7º, V", "Até 3 e-mails a mais",
                   "vem desmarcada", "art. 7º, I", "24 meses", "nunca a sua pergunta"):
        assert trecho in html, trecho


# ------------------------------------------------------------------ checkout pré-preenchido
@pytest.mark.skipif(not shutil.which("node"), reason="node não instalado")
def test_link_do_checkout_leva_o_email_so_quando_pedido():
    js = (f"global.window=global;global.location={{search:'',origin:'https://padmini.com.br'}};"
          f"global.sessionStorage={{getItem(){{return null}},setItem(){{}}}};"
          f"eval(require('fs').readFileSync({json.dumps(str(RAIZ / 'static' / 'afiliado.js'))},'utf8'));"
          "const d={produto:'mapa',data:'1990-05-15',hora:'14:30',lat:-23.5,lon:-46.6,nome:'Ana',cidade:'SP'};"
          "console.log(JSON.stringify(["
          "linkCheckout('https://pay.cakto.com.br/x',d,{email:'ana@exemplo.com'}),"
          "linkCheckout('https://pay.cakto.com.br/x',d),"
          "linkCheckout('https://pay.cakto.com.br/x',d,{email:'nao-e-email'})]))")
    com, sem, ruim = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
    assert "email=ana%40exemplo.com" in com and "confirmEmail=ana%40exemplo.com" in com
    assert "name=" not in com and "sck=m" in com  # nome não; nascimento só no sck
    assert "email" not in sem and "email" not in ruim

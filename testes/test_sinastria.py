"""
Sinastria da versão ocidental (Fase 2): motor (sinastria.py), Índice Padmini,
API /api/ocidental/sinastria, página, cupom e entrega.

O índice é método próprio: não existe fonte externa para validá-lo. Os testes
são de PROPRIEDADE — determinismo, simetria (A,B = B,A) e casos extremos
construídos à mão.
"""
import json
import random
import shutil
import subprocess
from datetime import datetime

import pytest

from test_app import PESSOA, PESSOA_B, RAIZ, _postar_webhook, app_mod, cliente

import acesso  # noqa: E402
import mapa_ocidental as mo  # noqa: E402
import montar_texto_ocidental as mt  # noqa: E402
import ofertas  # noqa: E402
import sinastria as si  # noqa: E402


def _mapa(dt, lat=-23.55, lon=-46.63):
    return mo.calcular_mapa_ocidental(dt, lat, lon)


def _falso(longitudes: dict, asc=None) -> dict:
    """Mapa construído à mão: só as longitudes que importam."""
    pontos = {k: mo._ponto(v, 1.0) for k, v in longitudes.items()}
    casas = None
    if asc is not None:
        pontos["ascendente"] = mo._ponto(asc)
        casas = {"sistema": "placidus", "cuspides": [(asc + 30 * i) % 360 for i in range(12)]}
    return {"pontos": pontos, "casas": casas, "tem_hora": asc is not None}


# ------------------------------------------------------------------ propriedades
def test_deterministico():
    a, b = _mapa(datetime(1990, 5, 15, 14, 30)), _mapa(datetime(1992, 3, 10, 8, 0))
    assert si.calcular_sinastria(a, b) == si.calcular_sinastria(a, b)


def test_simetrico_em_300_casais_sorteados():
    rnd = random.Random(26092026)
    for _ in range(300):
        dts = [datetime(rnd.randint(1950, 2006), rnd.randint(1, 12), rnd.randint(1, 28), rnd.randint(0, 23)) for _ in range(2)]
        a, b = _mapa(dts[0]), _mapa(dts[1])
        if rnd.random() < 0.3:  # às vezes sem hora
            a = mo.calcular_mapa_ocidental(None, -23.55, -46.63, data=dts[0].date())
        ab, ba = si.calcular_sinastria(a, b), si.calcular_sinastria(b, a)
        assert ab["indice"] == ba["indice"]
        assert {k: d["nota"] for k, d in ab["dimensoes"].items()} == {k: d["nota"] for k, d in ba["dimensoes"].items()}
        assert 0 <= ab["indice"] <= 100


PESSOAIS_7 = ("sol", "lua", "mercurio", "venus", "marte", "jupiter", "saturno")


def test_extremo_todos_em_trigono_da_indice_alto():
    a = _falso({p: 10.0 for p in PESSOAIS_7})
    b = _falso({p: 130.0 for p in PESSOAIS_7})  # 120° de tudo
    s = si.calcular_sinastria(a, b)
    assert s["indice"] >= 85
    assert all(d["nota"] >= 70 for k, d in s["dimensoes"].items() if d["nota"] is not None)


def test_extremo_todos_em_quadratura_da_indice_baixo():
    a = _falso({p: 10.0 for p in PESSOAIS_7})
    b = _falso({p: 100.0 for p in PESSOAIS_7})  # 90° de tudo
    s = si.calcular_sinastria(a, b)
    assert s["indice"] <= 20


def test_sem_aspecto_nenhum_fica_neutro_em_50():
    a = _falso({p: 10.0 for p in PESSOAIS_7})
    b = _falso({p: 40.0 for p in PESSOAIS_7})  # 30°: nenhum aspecto maior
    s = si.calcular_sinastria(a, b)
    assert s["aspectos"] == [] and s["indice"] == 50


def test_venus_marte_em_oposicao_conta_como_quimica():
    """Ajuste documentado: oposição Vênus–Marte não derruba a Atração."""
    a = _falso({"venus": 10.0, "marte": 200.0})
    b = _falso({"venus": 250.0, "marte": 190.0})  # Vênus A × Marte B a 180°
    s = si.calcular_sinastria(a, b)
    assert s["dimensoes"]["atracao"]["nota"] >= 50


def test_saturno_tenso_pesa_mais_que_quadratura_comum():
    assert si.peso("saturno", "lua", "quadratura") < si.peso("venus", "lua", "quadratura")


def test_dia_a_dia_sem_hora_de_ninguem_fica_de_fora_do_indice():
    a = mo.calcular_mapa_ocidental(None, -23.55, -46.63, data=datetime(1990, 5, 15).date())
    b = mo.calcular_mapa_ocidental(None, -22.9, -43.17, data=datetime(1992, 3, 10).date())
    s = si.calcular_sinastria(a, b)
    assert s["dimensoes"]["dia_a_dia"]["nota"] is None
    assert s["casas_a_em_b"] == [] and s["casas_b_em_a"] == []


def test_casa_6_ou_7_do_outro_soma_no_dia_a_dia():
    a = _falso({"venus": 5.0}, asc=0.0)      # casas iguais de 30° a partir de 0°
    b_longe = _falso({"venus": 95.0})        # casa 4 de A
    b_perto = _falso({"venus": 185.0})       # casa 7 de A
    assert (si.calcular_sinastria(a, b_perto)["dimensoes"]["dia_a_dia"]["soma"]
            > si.calcular_sinastria(a, b_longe)["dimensoes"]["dia_a_dia"]["soma"])


def test_oito_dimensoes_da_grade():
    assert list(si.DIMENSOES) == ["atracao", "emocoes", "comunicacao", "afeto", "identidade",
                                  "crescimento", "compromisso", "dia_a_dia"]


# ------------------------------------------------------------------ textos
def test_textos_da_sinastria_completos_e_no_tamanho():
    sb = mt.base("sinastria")
    for k in si.DIMENSOES:
        for faixa in ("alta", "media", "baixa"):
            n = len(mt.texto_dimensao(k, {"alta": 80, "media": 50, "baixa": 20}[faixa], "Ana", "Bruno").split())
            assert 60 <= n <= 120, (k, faixa, n)
    for c in range(1, 13):
        assert 55 <= len(mt.texto_casa_sinastria(c, "Ana", "Bruno").split()) <= 120
    for pa in si.PONTOS:
        for pb in si.PONTOS:
            for tipo in mo.ASPECTOS:
                t = mt.texto_aspecto_cruzado({"a": pa, "b": pb, "tipo": tipo}, "Ana", "Bruno")
                assert "{" not in t and t[0].isupper()
    assert "método próprio" in sb["metodo"]["texto"]


# ------------------------------------------------------------------ API
def test_amostra_gratis_so_com_indice_e_dois_pontos():
    r = cliente.post("/api/ocidental/sinastria", json={"a": PESSOA, "b": PESSOA_B})
    assert r.status_code == 200, r.text
    c = r.json()
    assert 0 <= c["indice"] <= 100 and c["maximo"] == 100
    assert c["ponto_forte"]["texto"] and c["ponto_atencao"]["texto"]
    assert "dimensoes" not in c and "aspectos" not in c  # o detalhe é pago


def test_completo_trancado_e_token_de_outra_versao_nao_abre():
    corpo = {"a": PESSOA, "b": PESSOA_B, "nivel": "completo"}
    assert cliente.post("/api/ocidental/sinastria", json=corpo).status_code == 402
    chave = acesso.chave_compat((PESSOA["data"], PESSOA["hora"], PESSOA["lat"], PESSOA["lon"]),
                                (PESSOA_B["data"], PESSOA_B["hora"], PESSOA_B["lat"], PESSOA_B["lon"]))
    vedico = acesso.emitir_token("compat", chave)
    assert cliente.post("/api/ocidental/sinastria", json={**corpo, "token": vedico}).status_code == 402
    ok = cliente.post("/api/ocidental/sinastria", json={**corpo, "token": acesso.emitir_token("compat", chave, "ocidental")})
    assert ok.status_code == 200
    c = ok.json()
    assert len(c["dimensoes"]) == 8 and c["aspectos"] and c["casas"]


def test_ia_nao_sai_na_amostra():
    r = cliente.post("/api/ocidental/sinastria", json={"a": PESSOA, "b": PESSOA_B, "texto_ia": True})
    assert r.status_code == 402


def test_sem_hora_de_um_funciona_e_avisa():
    r = cliente.post("/api/ocidental/sinastria", json={"a": {**PESSOA, "hora": ""}, "b": PESSOA_B})
    assert r.status_code == 200
    assert any("sem hora" in a for a in r.json()["avisos"])


# ------------------------------------------------------------------ página e preço
@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


def test_pagina_do_casal_ocidental(ocidental):
    html = cliente.get("/compatibilidade").text
    assert "/api/ocidental/sinastria" in html and "Índice Padmini" in html and "método próprio" in html
    assert "védic" not in html.lower() and "Guna" not in html and "पद्मिनी" not in html
    assert ".cardc::after{content:none}" in html  # base.css desenha "पद्मिनी" no card
    # R$127 por padrão; R$97 só existe como preço com cupom (do YAML)
    assert f"relatório completo por <b id=\"preco-nota\">R${ofertas.preco('compat', 'ocidental')}</b>" in html
    assert f'const PRECO_CUPOM = "{ofertas.oferta("compat", "ocidental")["preco_cupom"]}";' in html


def test_precos_do_casal_ocidental_no_yaml():
    o = ofertas.oferta("compat", "ocidental")
    assert o["preco"] == 127 and o["preco_cupom"] == 97


def test_home_e_lista_ocidentais(ocidental):
    home = cliente.get("/").text
    assert "Sinastria" in home and "védic" not in home.lower() and "पद्मिनी" not in home
    assert f"R${ofertas.preco('compat', 'ocidental')}" in home
    lista = cliente.get("/lista").text
    assert "védic" not in lista.lower() and "पद्मिनी" not in lista


@pytest.mark.skipif(shutil.which("node") is None, reason="node não instalado")
@pytest.mark.parametrize("opcoes,esperado", [("undefined", None), ("{aplicarCupom:true}", "PEDRO30")])
def test_cupom_so_vai_para_a_cakto_quando_a_pagina_pede(opcoes, esperado):
    """A védica (sem opção) continua igual: o cupom vai só como utm_term. A
    ocidental passa `coupon=`, que a Cakto aplica no checkout."""
    js = (
        "global.location={search:'?cupom=PEDRO30',origin:'https://padmini.teste'};"
        "const st={};global.sessionStorage={getItem(k){return st[k]??null},setItem(k,v){st[k]=v}};global.window=global;"
        f"eval(require('fs').readFileSync({json.dumps(str(RAIZ / 'static' / 'afiliado.js'))},'utf8'));"
        f"const u=new URL(window.linkCheckout('https://pay.cakto.com.br/x',null,{opcoes}));"
        "process.stdout.write(JSON.stringify([u.searchParams.get('coupon'),u.searchParams.get('utm_term')]));"
    )
    coupon, utm_term = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
    assert coupon == esperado and utm_term == "PEDRO30"


# ------------------------------------------------------------------ entrega
@pytest.fixture
def oferta_casal_ocidental(monkeypatch):
    novas = json.loads(json.dumps(ofertas.POR_SISTEMA["ocidental"]))
    novas["compat"].update(checkout="https://pay.cakto.com.br/occasal7_1", codigo="occasal7")
    monkeypatch.setitem(ofertas.POR_SISTEMA, "ocidental", novas)


def test_webhook_entrega_sinastria_mesmo_sem_hora(oferta_casal_ocidental):
    sck = "c~1990-05-15~~-23.5505~-46.6333~Ana~SP~1992-03-10~08:00~-22.9068~-43.1729~Bruno~RJ"
    ev = {"event": "purchase_approved", "secret": "segredo-de-teste-webhook",
          "data": {"id": "oc-casal-1", "status": "paid", "sck": sck, "offer": {"id": "occasal7"},
                   "customer": {"email": "c@teste.com", "name": "Ana"}}}
    c = _postar_webhook(ev).json()
    assert c["produto"] == "compat" and "token=oc-" in c["link"] and "/compatibilidade?" in c["link"]
    import urllib.parse
    tok = urllib.parse.parse_qs(urllib.parse.urlparse(c["link"]).query)["token"][0]
    corpo = {"a": {**PESSOA, "hora": "", "lat": -23.5505, "lon": -46.6333},
             "b": {**PESSOA_B, "lat": -22.9068, "lon": -43.1729}, "nivel": "completo", "token": tok}
    assert cliente.post("/api/ocidental/sinastria", json=corpo).status_code == 200


def test_live_sinastria_exige_sessao():
    corpo = {"a": PESSOA, "b": PESSOA_B}
    assert cliente.post("/api/live/ocidental/token/sinastria", json=corpo).status_code == 401

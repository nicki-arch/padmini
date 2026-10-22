"""
Testes da lógica do smoke de produção (scripts/smoke_producao.py) que não
precisam de rede: a checagem "preço do ofertas.yaml = preço da Cakto".

O bug que ela pega (26/set/2026): o site anunciava o casal por R$97, com R$127
riscado, e a oferta na Cakto cobrava R$127.
"""
import importlib.util

from test_app import RAIZ

_spec = importlib.util.spec_from_file_location("smoke_producao", RAIZ / "scripts" / "smoke_producao.py")
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)

# Trecho no formato do HTML real do checkout (conferido em 26/set/2026).
CHECKOUT_127 = ('<p class="tabular-nums">R$&nbsp;127,00<!-- --> à vista</p>'
                '<span>6x de R$&nbsp;9,99</span><span>R$&nbsp;0,99</span>')


def test_extrai_valores_ignorando_um_digito():
    assert smoke.valores_do_checkout(CHECKOUT_127) == {127}
    assert smoke.valores_do_checkout("R$ 1.297,00 e R$ 47,00") == {1297, 47}


def test_reprova_quando_o_site_anuncia_outro_preco():
    ofertas = {"compat": {"preco": 97, "checkout": "https://pay.cakto.com.br/x_1"}}
    falhas = smoke.conferir_precos_na_cakto(ofertas, baixar=lambda url: CHECKOUT_127)
    assert len(falhas) == 1 and "R$97" in falhas[0] and "R$127" in falhas[0]


def test_aprova_quando_bate_e_ignora_oferta_sem_checkout():
    ofertas = {"compat": {"preco": 127, "checkout": "https://pay.cakto.com.br/x_1"},
               "bump": {"preco": 167, "checkout": ""}}
    assert smoke.conferir_precos_na_cakto(ofertas, baixar=lambda url: CHECKOUT_127) == []


def test_cakto_fora_do_ar_avisa_sem_reprovar():
    def fora(url):
        raise OSError("timeout")
    smoke.AVISOS.clear()
    ofertas = {"compat": {"preco": 127, "checkout": "https://pay.cakto.com.br/x_1"}}
    assert smoke.conferir_precos_na_cakto(ofertas, baixar=fora) == []
    assert smoke.AVISOS and "não respondeu" in smoke.AVISOS[0]


# ---------------------------------------------------------------------------
# O smoke inteiro contra o app local, nas duas versões (sem rede: a conferência
# com a Cakto e os cabeçalhos HTTPS ficam de fora).
# ---------------------------------------------------------------------------
import json  # noqa: E402

import pytest  # noqa: E402

from test_app import app_mod, cliente  # noqa: E402
import catalogo  # noqa: E402

SEM_REDE = ("preço do ofertas.yaml bate", "cabeçalhos de segurança")


def _req_local(caminho, corpo=None, timeout=90):
    # com o cabeçalho do smoke, como o req de verdade (rodada 20.2: sem alerta por e-mail)
    r = (cliente.post(caminho, json=corpo, headers=smoke.SMOKE) if corpo is not None
         else cliente.get(caminho, headers=smoke.SMOKE))
    return r.status_code, r.content


def _destino_local(caminho, timeout=90):
    r = cliente.get(caminho, follow_redirects=False)
    return r.status_code, r.headers.get("location", "")


def _local(monkeypatch):
    monkeypatch.setattr(smoke, "req", _req_local)
    monkeypatch.setattr(smoke, "destino", _destino_local)


@pytest.mark.parametrize("versao", ["vedica", "ocidental"])
def test_smoke_passa_no_app_local(versao, monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", versao)
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    _local(monkeypatch)
    smoke.AVISOS.clear()
    app_mod._paginas_prontas.clear()
    falhas = []
    try:
        for nome, f in smoke.CHECAGENS:
            if any(t in nome for t in SEM_REDE):
                continue
            if not f():
                falhas.append(nome)
    finally:
        app_mod._paginas_prontas.clear()
    assert falhas == []
    assert not any("captura" in a for a in smoke.AVISOS)


@pytest.mark.catalogo_real
@pytest.mark.parametrize("captura", [True, False])
def test_smoke_com_o_catalogo_de_verdade(captura, monkeypatch):
    """Rodada 9: os dois cenários do brief — captura ligada e captura desligada. Desde a
    rodada 16 o YAML está com a venda aberta: sem captura, as checagens de preço e de
    botão de compra voltam a valer (e o aviso de "venda fechada" some)."""
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    if captura:
        monkeypatch.setenv("PADMINI_CAPTURA", "1")
    else:
        monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    _local(monkeypatch)
    smoke.AVISOS.clear()
    app_mod._paginas_prontas.clear()
    falhas = [nome for nome, f in smoke.CHECAGENS if not any(t in nome for t in SEM_REDE) and not f()]
    app_mod._paginas_prontas.clear()
    assert falhas == []
    assert any("captura" in a for a in smoke.AVISOS) == captura
    assert any("venda fechada" in a for a in smoke.AVISOS) == (not captura and not catalogo.vendas_abertas())


def test_smoke_cobre_os_4_produtos():
    nomes = " ".join(n for n, _ in smoke.CHECAGENS)
    # rodada 6: as amostras pedem e-mail (o smoke confere o 422); o tarot completo
    # sai do 402 do smoke (sem sorteio não há tiragem) e fica em test_tarot
    # rodada 20.3: as páginas (numerologia e tarot inclusive) seguem o estado no painel
    for trecho in ("amostras dos 4 produtos pedem o e-mail", "completos e PDFs trancados",
                   "páginas de produto seguem o painel"):
        assert trecho in nomes


# ---------------------------------------------------------------------------
# Rodada 3: cupom em % (a Cakto só aceita % inteiro) e o combo como order bump.
# Trechos no formato do checkout real da sinastria (conferido em 26/set/2026).
# ---------------------------------------------------------------------------
SINASTRIA = ("<p>R$&nbsp;127,00 à vista</p><h2>SIM, QUERO O MAPA DE CADA UM</h2><p>R$&nbsp;40,00</p>"
             "<p>Taxa de serviço R$&nbsp;0,99</p>")
SINASTRIA_CUPOM = ("<p>R$&nbsp;127,00</p><p>R$&nbsp;96,52à vista</p><p>R$&nbsp;40,00</p>"
                   "<p>pedro</p><p>Desconto (24%)-R$&nbsp;30,48</p>")
OFERTAS_R3 = {
    "compat": {"preco": 127, "cupom_percentual": 24, "cupom_codigos": ["pedro"],
               "checkout": "https://pay.cakto.com.br/hrf7qtu_1141270"},
    "bump_mapas_casal": {"preco": 167, "bump_de": "compat", "checkout": "https://pay.cakto.com.br/32vnvwx_1144252"},
}


def _cakto(com_cupom, sem_cupom=SINASTRIA):
    def baixar(url):
        assert "32vnvwx" not in url  # o bump não tem checkout próprio: nunca é aberto
        return com_cupom if "coupon=pedro" in url else sem_cupom
    return baixar


def test_cupom_e_bump_conferem_com_a_cakto():
    smoke.AVISOS.clear()
    assert smoke.conferir_precos_na_cakto(OFERTAS_R3, baixar=_cakto(SINASTRIA_CUPOM)) == []
    assert smoke.AVISOS == []


def test_cupom_com_outro_percentual_reprova():
    outro = SINASTRIA_CUPOM.replace("96,52", "101,60").replace("24%", "20%")
    falhas = smoke.conferir_precos_na_cakto(OFERTAS_R3, baixar=_cakto(outro))
    assert len(falhas) == 1 and "R$96,52" in falhas[0] and "20%" in falhas[0]


def test_cupom_que_so_aparece_no_navegador_e_aviso():
    smoke.AVISOS.clear()
    assert smoke.conferir_precos_na_cakto(OFERTAS_R3, baixar=_cakto(SINASTRIA)) == []
    aviso = next(a for a in smoke.AVISOS if "cupom 'pedro'" in a)
    assert "não dá para conferir sem navegador" in aviso and "confira à mão" in aviso.lower()
    assert "?coupon=pedro" in aviso and "R$96,52" in aviso


def test_bump_com_outro_valor_reprova():
    falhas = smoke.conferir_precos_na_cakto(
        OFERTAS_R3, baixar=_cakto(SINASTRIA_CUPOM.replace("40,00", "50,00"), SINASTRIA.replace("40,00", "50,00")))
    assert any("bump_mapas_casal" in f and "R$40" in f for f in falhas)


# ---------------------------------------------------------------------------
# 28/set/2026: com PADMINI_CAPTURA=1 no ar, as páginas vão para /lista e o smoke
# reprovava de hora em hora ("botões de compra", "preço do casal") sem nada
# quebrado. Agora ele reconhece a captura (302 de / para /lista), confere o
# redirecionamento com utm/ref, a /lista e a recusa da inscrição sem autorização.
# ---------------------------------------------------------------------------
@pytest.fixture
def captura(monkeypatch):
    monkeypatch.setenv("PADMINI_CAPTURA", "1")
    _local(monkeypatch)
    app_mod._paginas_prontas.clear()
    smoke.AVISOS.clear()
    yield
    app_mod._paginas_prontas.clear()


def _checagem(trecho):
    return next(f for n, f in smoke.CHECAGENS if trecho in n)


@pytest.mark.parametrize("versao", ["vedica", "ocidental"])
def test_smoke_passa_com_a_captura_ligada_e_avisa(versao, captura, monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", versao)
    falhas = [n for n, f in smoke.CHECAGENS if not any(t in n for t in SEM_REDE) and not f()]
    assert falhas == []
    assert sum("captura ligada" in a for a in smoke.AVISOS) == 1


def test_captura_confere_os_5_redirecionamentos_com_utm_e_ref(captura, monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    vistos = []

    def destino(caminho, timeout=90):
        vistos.append(caminho.split("?")[0])
        return _destino_local(caminho)
    monkeypatch.setattr(smoke, "destino", destino)
    assert _checagem("redirecionam para /lista")() is True
    assert {"/", "/mapa", "/compatibilidade", "/numerologia", "/tarot"} <= set(vistos)


def test_captura_que_perde_o_ref_reprova(captura, monkeypatch):
    def destino(caminho, timeout=90):
        st, onde = _destino_local(caminho)
        return (st, "/lista") if caminho.startswith("/mapa") else (st, onde)
    monkeypatch.setattr(smoke, "destino", destino)
    assert _checagem("redirecionam para /lista")() is False


def test_captura_com_a_lista_fora_do_ar_reprova(captura, monkeypatch):
    def req(caminho, corpo=None, timeout=90):
        return (500, b"erro") if caminho == "/lista" else _req_local(caminho, corpo, timeout)
    monkeypatch.setattr(smoke, "req", req)
    assert _checagem("/lista responde")() is False


def test_captura_com_a_lista_aceitando_sem_autorizacao_reprova(captura, monkeypatch):
    def req(caminho, corpo=None, timeout=90):
        return (200, b'{"ok": true}') if caminho == "/api/lista" else _req_local(caminho, corpo, timeout)
    monkeypatch.setattr(smoke, "req", req)
    assert _checagem("/lista responde")() is False


def test_captura_nao_inscreve_ninguem(captura, monkeypatch):
    gravados = []
    monkeypatch.setattr(app_mod.db, "registrar_lead", lambda *a, **k: gravados.append(a) or True)
    assert _checagem("/lista responde")() is True and gravados == []


def test_sem_captura_nao_avisa(monkeypatch):
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    _local(monkeypatch)
    smoke.AVISOS.clear()
    assert smoke._captura_no_ar() is False and smoke.AVISOS == []


def test_valor_solto_no_yaml_nao_derruba_a_conferencia():
    """30/set/2026: `taxa_plataforma: 0.99` entrou no topo do ofertas.yaml da
    ocidental e a checagem caía com "'float' object has no attribute 'get'"."""
    ofertas = {"taxa_plataforma": 0.99,
               "compat": {"preco": 127, "checkout": "https://pay.cakto.com.br/x_1"}}
    assert smoke.conferir_precos_na_cakto(ofertas, baixar=lambda url: CHECKOUT_127) == []


@pytest.mark.parametrize("versao", ["vedica", "ocidental"])
def test_conferencia_roda_com_o_yaml_de_verdade(versao):
    smoke.AVISOS.clear()
    smoke.conferir_precos_na_cakto(smoke._ofertas_do_yaml(versao), baixar=lambda url: "")


# ---------------------------------------------------------------------------
# Rodada 20.3: o smoke segue o estado do painel. Em 22/out o Nicolas deixou só o mapa à
# venda (sinastria, numerologia, tarot e comunidade Ocultos) e o smoke caiu para 41/44:
# "/compatibilidade responde 200", "numerologia e tarot: 200" e "/comunidade 404" tinham
# o produto fixo. Agora: ativo ou em breve → 200, oculto → 404, conforme o /api/config.
# ---------------------------------------------------------------------------
TODAS = [p["chave"] for p in catalogo.carregar()["produtos"]]
ESTADOS = {
    # 22/out/2026: só o mapa (e a home); o resto Oculto no painel
    "hoje": {"mapa": "ativo"},
    "tudo_ativo": {c: "ativo" for c in TODAS},
    "tudo_oculto_menos_o_mapa": {"mapa": "ativo"},
    "misturado": {"mapa": "ativo", "compat": "em_breve", "numerologia": "ativo", "comunidade": "ativo",
                  "previsao": "em_breve"},
}


def _no_painel(monkeypatch, estados: dict, vendas=True):
    """O estado do painel (o que o público vê) só com `estados`; o resto oculto."""
    import copy
    dados = copy.deepcopy(catalogo.carregar())
    dados["vendas_abertas"] = vendas
    for p in dados["produtos"]:
        p["estado"] = estados.get(p["chave"], "oculto")
    catalogo.usar(dados)
    app_mod._paginas_prontas.clear()


@pytest.mark.parametrize("cenario", list(ESTADOS))
def test_smoke_segue_o_painel(cenario, monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    _local(monkeypatch)
    _no_painel(monkeypatch, ESTADOS[cenario])
    smoke.AVISOS.clear()
    falhas = [n for n, f in smoke.CHECAGENS if not any(t in n for t in SEM_REDE) and not f()]
    app_mod._paginas_prontas.clear()
    assert falhas == []
    estados = smoke.estados_no_ar()
    assert {r for r, e in estados.items() if e == "ativo"} >= {"/mapa"}
    # "nenhum oculto" só aparece quando de fato não há oculto
    assert any("nenhum oculto" in a for a in smoke.AVISOS) == ("oculto" not in estados.values())


def test_config_informa_em_breve_e_nunca_oculto(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    _no_painel(monkeypatch, ESTADOS["misturado"])
    cfg = cliente.get("/api/config").json()
    assert set(cfg["produtos_ativos"]) == {"/mapa", "/numerologia", "/comunidade"}
    assert set(cfg["produtos_em_breve"]) == {"/compatibilidade", "/seu-ano"}
    assert "/tarot" not in cfg["produtos_ativos"] + cfg["produtos_em_breve"]


def test_config_da_vedica_sem_catalogo(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    cfg = cliente.get("/api/config").json()
    assert cfg["produtos_ativos"] == [] and cfg["produtos_em_breve"] == []


@pytest.mark.parametrize("cenario", list(ESTADOS))
def test_smoke_reprova_pagina_fora_do_estado(cenario, monkeypatch):
    """O smoke continua pegando defeito de verdade: oculto que abre (200) ou ativo que some (404)."""
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    _local(monkeypatch)
    _no_painel(monkeypatch, ESTADOS[cenario])
    estados = smoke.estados_no_ar()
    errada = next(r for r, e in estados.items() if e != "ativo") if "oculto" in estados.values() else "/mapa"

    def req(caminho, corpo=None, timeout=90):
        if caminho == errada:
            return (200 if estados[errada] == "oculto" else 404), b""
        return _req_local(caminho, corpo, timeout)
    monkeypatch.setattr(smoke, "req", req)
    assert _checagem("páginas de produto seguem o painel")() is False


# Os três estados do brief simulados só no /api/config (sem app): o que o smoke espera.
CONFIG_HOJE = {"sistema": "ocidental", "produtos_ativos": ["/mapa"], "produtos_em_breve": []}
CONFIG_TUDO = {"sistema": "ocidental", "produtos_em_breve": [],
               "produtos_ativos": [p["rota"] for p in catalogo.carregar()["produtos"] if p.get("rota")]}


@pytest.mark.parametrize("config, esperado", [
    (CONFIG_HOJE, {"/mapa": 200, "/compatibilidade": 404, "/numerologia": 404, "/tarot": 404,
                   "/comunidade": 404, "/seu-ano": 404, "/calendario-lunar": 404}),
    (CONFIG_TUDO, {"/mapa": 200, "/compatibilidade": 200, "/numerologia": 200, "/tarot": 200,
                   "/comunidade": 200, "/seu-ano": 200, "/calendario-lunar": 200}),
    ({"sistema": "ocidental", "produtos_ativos": ["/mapa"], "produtos_em_breve": ["/tarot"]},
     {"/mapa": 200, "/tarot": 200, "/compatibilidade": 404, "/comunidade": 404}),
    ({"sistema": "vedica", "produtos_ativos": []},
     {"/mapa": 200, "/compatibilidade": 200, "/numerologia": 404, "/tarot": 404, "/comunidade": 404}),
])
def test_status_esperado_pelo_config(config, esperado):
    estados = smoke.estados_no_ar(config)
    assert {r: smoke.status_esperado(estados[r]) for r in esperado} == {r: (st,) for r, st in esperado.items()}


def test_site_sem_produtos_em_breve_aceita_200_ou_404():
    """Site anterior à rodada 20.3 (sem o campo): em breve e oculto não se distinguem; fora os
    ativos, a página passa com 200 ou 404 e o smoke avisa (o YAML não é o estado no ar)."""
    smoke.AVISOS.clear()
    estados = smoke.estados_no_ar({"sistema": "ocidental", "produtos_ativos": ["/mapa"]})
    assert estados["/mapa"] == "ativo" and smoke.status_esperado(estados["/mapa"]) == (200,)
    assert all(smoke.status_esperado(e) == (200, 404) for r, e in estados.items() if r != "/mapa")
    assert any("produtos_em_breve" in a for a in smoke.AVISOS)


def test_site_sem_produtos_em_breve_passa_com_o_estado_de_hoje(monkeypatch):
    """O smoke desta rodada contra a produção ANTES do deploy dela (22/out: só o mapa ativo,
    sinastria, numerologia, tarot e comunidade ocultos, e o /api/config sem o campo novo)."""
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    _local(monkeypatch)
    _no_painel(monkeypatch, ESTADOS["hoje"])

    def req(caminho, corpo=None, timeout=90):
        st, corpo_r = _req_local(caminho, corpo, timeout)
        if caminho == "/api/config":
            cfg = json.loads(corpo_r)
            cfg.pop("produtos_em_breve")
            return st, json.dumps(cfg).encode()
        return st, corpo_r
    monkeypatch.setattr(smoke, "req", req)
    smoke.AVISOS.clear()
    for trecho in ("páginas de produto seguem o painel", "um produto oculto", "em breve\" mostram"):
        assert _checagem(trecho)() is True, trecho

"""
Rodada 6, Fase D: aviso de cookies e pixels de anúncio (só na versão ocidental).

- Sem consentimento, nenhum script de terceiro (Meta, TikTok, Google, PostHog).
- Com as variáveis vazias, a página e a CSP saem iguais às de hoje.
- Nenhum evento leva dado pessoal; em URL com dado pessoal, os pixels nem carregam.
- A CSP libera só os domínios de cada plataforma configurada.
- O teste com navegador de verdade roda onde houver Chromium (pulado no CI).
"""
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time

import pytest

from test_app import RAIZ, app_mod, cliente

import seguranca  # noqa: E402

PAGINAS_OC = ["/", "/mapa", "/compatibilidade", "/numerologia", "/tarot", "/privacidade", "/termos"]
TERCEIROS = re.compile(r"connect\.facebook\.net|facebook\.com/tr|analytics\.tiktok\.com|googletagmanager\.com|"
                       r"google-analytics\.com|googleadservices\.com|doubleclick\.net|posthog\.com")
IDS = {"PADMINI_META_PIXEL": "123456789012345", "PADMINI_TIKTOK_PIXEL": "C1ABCDEFGHIJ",
       "PADMINI_GOOGLE_TAG": "G-TESTE123,AW-987654321", "PADMINI_GOOGLE_ADS_LEAD": "AW-987654321/lead"}


@pytest.fixture
def no_ar(monkeypatch):
    def ligar(v):
        monkeypatch.setenv("PADMINI_SISTEMA", v)
        app_mod._paginas_prontas.clear()
    yield ligar
    app_mod._paginas_prontas.clear()


@pytest.fixture
def sem_pixels(monkeypatch):
    for v in IDS:
        monkeypatch.delenv(v, raising=False)


@pytest.fixture
def com_pixels(monkeypatch):
    for k, v in IDS.items():
        monkeypatch.setenv(k, v)


# ------------------------------------------------------------------ páginas
@pytest.mark.parametrize("rota", PAGINAS_OC)
def test_pagina_ocidental_tem_o_aviso_e_nenhum_script_de_terceiro(rota, no_ar, com_pixels):
    no_ar("ocidental")
    html = cliente.get(rota).text
    assert '<meta name="pad-consentimento" content="exigido">' in html
    assert "/static/ocidental/consentimento.js" in html
    assert not TERCEIROS.search(html), rota  # nada de terceiro no HTML: só o JS carrega, e só depois do "Aceitar"


def test_vedica_sem_aviso_nem_pixel(no_ar, com_pixels):
    no_ar("vedica")
    for rota in ("/", "/mapa", "/compatibilidade", "/privacidade"):
        html = cliente.get(rota).text
        assert "consentimento.js" not in html and "pad-consentimento" not in html
    c = cliente.get("/api/config").json()
    assert all(c[k] == "" for k in seguranca.PIXELS)  # com a védica no ar, nenhum ID sai


# ------------------------------------------------------------------ config e CSP
CSP_DE_HOJE = ("default-src 'self'; script-src 'self' 'unsafe-inline' {ph}; style-src 'self' 'unsafe-inline' "
               "https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; "
               "connect-src 'self' {ph}; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; "
               "form-action 'self'; frame-ancestors 'none'")


def test_variaveis_vazias_deixam_config_e_csp_como_antes(no_ar, sem_pixels):
    for versao in ("ocidental", "vedica"):
        no_ar(versao)
        c = cliente.get("/api/config").json()
        assert all(c[k] == "" for k in seguranca.PIXELS)
        esperado = CSP_DE_HOJE.format(ph=" ".join(seguranca.origens_posthog()))
        if versao == "ocidental":  # rodada visual (fase B): a ocidental serve as próprias fontes
            esperado = esperado.replace(" https://fonts.googleapis.com", "").replace(" https://fonts.gstatic.com", "")
        assert cliente.get("/").headers["content-security-policy"] == esperado


def test_com_ids_a_csp_libera_so_o_que_cada_plataforma_pede(no_ar, com_pixels):
    no_ar("ocidental")
    c = cliente.get("/api/config").json()
    assert c["meta_pixel"] == IDS["PADMINI_META_PIXEL"] and c["google_ads_lead"] == IDS["PADMINI_GOOGLE_ADS_LEAD"]
    csp = cliente.get("/").headers["content-security-policy"]
    d = {x.split()[0]: x.split()[1:] for x in csp.split("; ")}
    assert "https://connect.facebook.net" in d["script-src"] and "https://www.facebook.com" in d["img-src"]
    assert "https://analytics.tiktok.com" in d["connect-src"] and "bytedance:" in d["frame-src"]
    assert "https://www.googletagmanager.com" in d["script-src"] and "https://*.google-analytics.com" in d["connect-src"]
    assert "'unsafe-eval'" not in csp and "*" not in d["script-src"]
    assert d["frame-ancestors"] == ["'none'"] and d["object-src"] == ["'none'"]


def test_so_meta_configurado_so_libera_meta(no_ar, sem_pixels, monkeypatch):
    no_ar("ocidental")
    monkeypatch.setenv("PADMINI_META_PIXEL", "1")
    csp = cliente.get("/").headers["content-security-policy"]
    assert "facebook" in csp and "tiktok" not in csp and "google-analytics" not in csp and "frame-src" not in csp


# ------------------------------------------------------------------ o código
def _js(nome):
    return (RAIZ / "static" / nome).read_text(encoding="utf-8")


def test_pixels_so_carregam_dentro_do_aceite():
    js = _js("ocidental/consentimento.js")
    # os carregadores só são chamados em carregar(), e carregar() só no "aceito"
    corpo = js[js.index("function carregar()"):js.index("// evento padrão")]
    assert "carregarMeta(" in corpo and "carregarTikTok(" in corpo and "carregarGoogle(" in corpo
    chamadas = [m.start() for m in re.finditer(r"(?<!function )\bcarregar\(\)", js)]
    for pos in chamadas:
        antes = js[max(0, pos - 160):pos]
        assert '"aceito"' in antes, js[pos - 160:pos + 12]
    assert 'data-cookies="recusado"' in js and 'data-cookies="aceito"' in js
    assert "checked" not in js  # nenhuma caixa pré-marcada
    assert "365 * 24 * 60 * 60 * 1000" in js  # a escolha vale 12 meses


def test_botoes_com_o_mesmo_destaque():
    js = _js("ocidental/consentimento.js")
    botoes = re.findall(r'<button type="button" class="([^"]+)" data-cookies="(\w+)"', js)
    assert {b for _, b in botoes} == {"aceito", "recusado"} and len({c for c, _ in botoes}) == 1


def test_eventos_sem_dado_pessoal():
    js = _js("ocidental/consentimento.js")
    ev = js[js.index("function evento("):js.index("window.padPixel")]
    assert re.search(r"props = \{ content_name: produto, content_category: \"leitura\" \}", ev)
    for proibido in ("email", "nome", "data", "hora", "cidade", "pergunta", "lat", "lon"):
        assert not re.search(rf"\b{proibido}\b", ev), proibido
    assert 'fbq("set", "autoConfig", false' in js  # o Meta não lê botões nem campos
    assert re.search(r'fbq\("init", id\)', js)       # init sem dados do usuário (sem advanced matching)
    assert "URL_SENSIVEL.test(location.search)" in js
    for p in ("token", "data", "hora", "nome", "cidade", "email", "sck"):
        assert p in js[js.index("URL_SENSIVEL = "):js.index("URL_SENSIVEL = ") + 120]


def test_nomes_padrao_de_evento():
    js = _js("ocidental/consentimento.js")
    for trecho in ('"PageView"', '"ViewContent"', '"Lead"', '"SubmitForm"', '"generate_lead"', "eventID: id", "event_id: id"):
        assert trecho in js, trecho
    # checkout e compra são dos pixels da Cakto: o site não dispara (não conta em dobro)
    assert "InitiateCheckout" not in js and "Purchase" not in js and "CompletePayment" not in js


def test_posthog_espera_o_consentimento_na_ocidental():
    js = _js("analytics.js")
    assert "meta[name=\"pad-consentimento\"]" in js.replace("'", '"')
    assert "pad:consentimento" in js


@pytest.mark.skipif(not shutil.which("node"), reason="node não instalado")
@pytest.mark.parametrize("ocidental", [True, False])
def test_link_do_checkout_leva_os_ids_de_clique_so_na_ocidental(ocidental):
    doc = ("{querySelector(){return {}}}" if ocidental else "{querySelector(){return null}}")
    js = (f"global.window=global;global.document={doc};"
          "global.location={search:'?fbclid=FB1&ttclid=TT1&gclid=G1&utm_source=tiktok',origin:'https://padmini.com.br'};"
          "const _s={};global.sessionStorage={getItem(k){return _s[k]||null},setItem(k,v){_s[k]=v}};"
          f"eval(require('fs').readFileSync({json.dumps(str(RAIZ / 'static' / 'afiliado.js'))},'utf8'));"
          "console.log(linkCheckout('https://pay.cakto.com.br/x',{produto:'tarot',tiragem:'abc'}));"
          "console.log(JSON.stringify(padAtribuicao()));")
    link, attr = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout.split("\n")[:2]
    for k, v in (("fbclid", "FB1"), ("ttclid", "TT1"), ("gclid", "G1")):
        assert (f"{k}={v}" in link) is ocidental
        assert k not in attr  # nunca no PostHog
    assert "utm_source=tiktok" in link


def test_privacidade_ocidental_explica_os_cookies(no_ar):
    no_ar("ocidental")
    html = cliente.get("/privacidade").text
    for trecho in ('id="cookies"', "Pixel da Meta", "Pixel do TikTok", "Google Analytics e Google Ads", "PostHog",
                   "só com a sua permissão", "12 meses", "Preferências de cookies", "art. 7º, I"):
        assert trecho in html, trecho


# ------------------------------------------------------------------ navegador de verdade
def _chromium():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        return None
    for c in ("/opt/pw-browsers/chromium-1194/chrome-linux/chrome",):
        if os.path.exists(c):
            return c
    return None


@pytest.fixture
def servidor(monkeypatch):
    import uvicorn
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    for k, v in IDS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("PADMINI_POSTHOG_KEY", "phc_teste")
    app_mod._paginas_prontas.clear()
    s = socket.socket(); s.bind(("127.0.0.1", 0)); porta = s.getsockname()[1]; s.close()
    srv = uvicorn.Server(uvicorn.Config(app_mod.app, port=porta, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True); t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{porta}"
    srv.should_exit = True; t.join(5)
    app_mod._paginas_prontas.clear()


@pytest.mark.skipif(not _chromium(), reason="sem Chromium (roda localmente, não no CI)")
def test_no_navegador_nada_de_terceiro_antes_do_aceite(servidor):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=_chromium())
        for escolha in ("recusado", "aceito"):
            ctx = b.new_context()
            pedidos = []
            ctx.route(TERCEIROS, lambda rota: (pedidos.append(rota.request.url), rota.abort()))
            pg = ctx.new_page()
            pg.goto(servidor + "/mapa")
            pg.wait_for_selector("#aviso-cookies")
            pg.wait_for_timeout(500)
            assert pedidos == [], pedidos  # o aviso está na tela e nada de terceiro saiu
            assert pg.is_visible("#preferencias-cookies")
            pg.click(f'[data-cookies="{escolha}"]')
            pg.wait_for_timeout(800)
            if escolha == "recusado":
                assert pedidos == []
                pg.reload(); pg.wait_for_timeout(600)
                assert pedidos == [] and not pg.query_selector("#aviso-cookies")  # lembrou a escolha
            else:
                vistos = " ".join(pedidos)
                for dominio in ("connect.facebook.net", "analytics.tiktok.com", "googletagmanager.com", "posthog.com"):
                    assert dominio in vistos, (dominio, pedidos)
                eventos = pg.evaluate("() => (window.fbq && window.fbq.queue || []).map(x => Array.from(x))")
                assert ["track", "ViewContent"] == eventos[-1][:2] or any(e[:2] == ["track", "ViewContent"] for e in eventos)
                assert all(set(e[2].keys()) <= {"content_name", "content_category"}
                           for e in eventos if e[0] == "track" and len(e) > 2 and isinstance(e[2], dict))
            ctx.close()
        # link de entrega com dados de nascimento na URL: mesmo aceito, os pixels não carregam
        ctx = b.new_context()
        pedidos = []
        ctx.route(TERCEIROS, lambda rota: (pedidos.append(rota.request.url), rota.abort()))
        pg = ctx.new_page()
        pg.goto(servidor + "/mapa")
        pg.wait_for_selector("#aviso-cookies")  # a página terminou de ler a escolha (nenhuma)
        pg.evaluate("() => localStorage.setItem('pad_consentimento', JSON.stringify({escolha:'aceito', em: Date.now(), v:1}))")
        pedidos.clear()
        pg.goto(servidor + "/mapa?data=1990-05-15&hora=14:30&lat=-23.5&lon=-46.6&nome=Ana&token=oc-x")
        pg.wait_for_timeout(800)
        assert not any(d in " ".join(pedidos) for d in ("facebook", "tiktok", "googletagmanager")), pedidos
        b.close()

"""
Rodada 9, Fase B: visual 2.0 (pacote valderez-design-2.0), marca (a roda),
ilustrações trocáveis e a amostra do mapa natal por dimensões.
"""
import re

import pytest

from test_app import RAIZ, app_mod, cliente  # primeiro: define os segredos de teste

import catalogo
import ilustracoes
import montar_texto_ocidental as mt
import paleta

pytestmark = pytest.mark.catalogo_real
HTML = {"accept": "text/html"}
PESSOA = {"nome": "Ana", "data": "1994-05-14", "hora": "15:40", "lat": -30.0331, "lon": -51.23,
          "cidade": "Porto Alegre, RS", "email": "ana@teste.com", "nivel": "amostra"}
V2 = ("/", "/mapa", "/lista", "/leituras", "/compatibilidade", "/nao-existe")


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


# ------------------------------------------------------------------ marca e fontes
def test_svgs_servidos_tem_menos_de_30_kb():
    svgs = list((RAIZ / "static").rglob("*.svg"))
    assert svgs and all(s.stat().st_size < 30_000 for s in svgs), [s.name for s in svgs if s.stat().st_size >= 30_000]


def test_a_roda_e_o_simbolo_no_cabecalho_rodape_e_favicon(ocidental):
    html = cliente.get("/").text
    cab = html[html.index('<header class="cab">'):html.index("</header>")]
    assert 'src="/static/valderez/roda.svg" width="48" height="48"' in cab and "<b>Valderez</b><i>Astrologia</i>" in cab
    assert "roda-claro.svg" in html[html.index('<footer class="rod">'):]
    for png in ("favicon-32.png", "favicon-192.png", "favicon-512.png"):
        assert (RAIZ / "static" / "valderez" / png).read_bytes()[:4] == b"\x89PNG", png
    assert 'href="/static/valderez/favicon-32.png"' in html and 'href="/static/valderez/favicon-192.png"' in html


def test_fontes_novas_servidas_pelo_site(ocidental):
    tema = (RAIZ / "static" / "ocidental" / "tema.css").read_text(encoding="utf-8")
    for familia in ("Fraunces", "Figtree", "Noto Sans Symbols 2"):
        assert f"font-family: '{familia}'" in tema
    html = cliente.get("/").text
    assert "fonts.googleapis" not in html and "fonts.gstatic" not in html


def test_pares_de_cor_do_visual_2_passam_no_contraste():
    assert all(c["passa"] for c in paleta.contrastes_vz())


def test_cabecalho_tem_menu_do_celular_com_details(ocidental):
    html = cliente.get("/mapa").text
    assert '<details class="menu-cel">' in html and 'class="menu-painel"' in html
    painel = html[html.index('class="menu-painel"'):html.index("</details>")]
    assert "Chegando em breve" in painel and 'href="/compatibilidade"' in painel and "/minhas-leituras" in painel


# ------------------------------------------------------------------ ilustrações
def test_conjunto_ativo_passa_na_conferencia():
    import importlib.util
    spec = importlib.util.spec_from_file_location("checar", RAIZ / "scripts" / "checar_ilustracoes.py")
    checar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checar)
    assert checar.conferir(ilustracoes._dados["conjunto_ativo"]) == []


def test_template_pede_a_vaga_nunca_o_arquivo():
    for f in (RAIZ / "static" / "ocidental").glob("*.html"):
        texto = f.read_text(encoding="utf-8")
        assert "ilustracoes/" not in texto, f.name
        for vaga in re.findall(r'ilustracao(?:_url)?\(\s*["\']([a-z0-9-]+)["\']', texto):
            assert vaga in ilustracoes.VAGAS, (f.name, vaga)
    for d in catalogo.dimensoes_mapa() + catalogo.produtos():
        assert not d["vaga"] or d["vaga"] in ilustracoes.VAGAS, d["vaga"]


def test_vaga_que_falta_cai_na_reserva_e_depois_no_fundo_liso(monkeypatch):
    monkeypatch.setitem(ilustracoes._dados, "conjunto_ativo", "nao-existe")
    assert ilustracoes.url("dim-sol").endswith("/aquarela-2026/dim-sol.webp")  # a reserva
    monkeypatch.setitem(ilustracoes._dados, "conjunto_reserva", "tambem-nao")
    assert ilustracoes.url("dim-sol") == ""
    assert "background:#F5EAE2" in ilustracoes.tag("dim-sol") and "<img" not in ilustracoes.tag("dim-sol")
    with pytest.raises(KeyError):
        ilustracoes.url("vaga-inventada")


# ------------------------------------------------------------------ amostra por dimensões
def test_amostra_traz_cada_dimensao_ativa_so_com_o_comeco_do_texto(ocidental):
    r = cliente.post("/api/ocidental/mapa", json=PESSOA)
    assert r.status_code == 200, r.text
    dims = {d["chave"]: d for d in r.json()["dimensoes"]}
    assert list(dims) == [d["chave"] for d in catalogo.dimensoes_mapa()]
    for d in catalogo.dimensoes_mapa():
        item = dims[d["chave"]]
        if d["estado"] == "em_breve":
            assert item["estado"] == "em_breve" and "trecho" not in item
            continue
        completo = mt.texto_signo(d["ponto"], item["signo"])
        assert item["trecho"] and completo.startswith(item["trecho"]) and len(item["trecho"]) < len(completo)
        assert item["img"].startswith("/static/ilustracoes/") and item["vaga"] == f"signo-{item['signo']}"
    # o texto pago de Mercúrio, Vênus e Marte nunca vai para o navegador
    corpo = r.text
    for ponto in ("mercurio", "venus", "marte"):
        item = next(x for x in dims.values() if x.get("ponto") == ponto)
        resto = mt.texto_signo(ponto, item["signo"])[len(item["trecho"]):].strip()
        assert resto[:60] not in corpo, ponto


def test_sem_hora_a_dimensao_do_ascendente_avisa(ocidental):
    r = cliente.post("/api/ocidental/mapa", json={**PESSOA, "hora": ""})
    dims = {d["chave"]: d for d in r.json()["dimensoes"]}
    assert dims["como-voce-chega"]["estado"] == "sem_hora" and "trecho" not in dims["como-voce-chega"]


def test_trecho_tem_uma_ou_duas_frases():
    assert mt.trecho("Primeira frase. Segunda frase. Terceira.") == "Primeira frase. Segunda frase."
    longa = "A" * 250 + ". Segunda frase."
    assert mt.trecho(longa) == "A" * 250 + "."


def test_selo_so_com_texto_revisado(ocidental, monkeypatch):
    r = cliente.post("/api/ocidental/mapa", json=PESSOA)
    assert all("selo" not in d for d in r.json()["dimensoes"])  # hoje nada está revisado
    monkeypatch.setattr(mt, "revisado_signo", lambda ponto, signo: ponto == "sol")
    r = cliente.post("/api/ocidental/mapa", json={**PESSOA, "email": "outra@teste.com"})
    com_selo = [d["chave"] for d in r.json()["dimensoes"] if d.get("selo")]
    assert com_selo == ["essencia"]


def test_pagina_do_mapa_tem_os_estados_e_o_me_avise(ocidental):
    html = cliente.get("/mapa").text
    for trecho in ('id="estado-form"', 'id="estado-carregando"', 'id="resultado"', 'class="roda-gira"',
                   'class="vela"', 'aria-hidden="true">${esc(TA.fumo)}', 'data-me-avise="mapa"'):
        assert trecho in html, trecho
    assert re.search(r'id="nome"[^>]*required', html)
    assert "/static/ilustracoes/" not in html[:html.index('<form id="form"')].split('id="estado-form"')[1]


def test_data_da_home_nao_vai_na_url(ocidental):
    html = cliente.get("/").text
    form = html[html.index('<form class="hero-form"'):html.index("</form>")]
    assert 'action="/mapa"' in form and "name=" not in form  # nada vai na URL
    assert 'sessionStorage.setItem("pad_data_nasc"' in html
    assert 'sessionStorage.getItem("pad_data_nasc")' in cliente.get("/mapa").text


# ------------------------------------------------------------------ páginas
@pytest.mark.parametrize("rota", V2)
def test_paginas_no_visual_2_nao_carregam_nada_de_fora(ocidental, rota):
    r = cliente.get(rota, headers=HTML)
    assert '<body class="vz">' in r.text and "/static/valderez/v2.css" in r.text, rota
    for url in re.findall(r'<(?:link|script|img)\b[^>]*?\s(?:href|src)="([^"$]+)"', r.text):
        if "canonical" in url:
            continue
        assert url.startswith("/") and not url.startswith("//") or url.startswith("https://padmini.com.br"), (rota, url)


def test_404_e_500_tem_status_certo(ocidental, monkeypatch):
    r = cliente.get("/nao-existe", headers=HTML)
    assert r.status_code == 404 and "não foi encontrada" in r.text
    from fastapi.testclient import TestClient

    def quebra():
        raise RuntimeError("teste")
    app_mod.app.add_api_route("/_quebra_teste", quebra)
    rota = app_mod.app.router.routes[-1]
    c = TestClient(app_mod.app, raise_server_exceptions=False)
    monkeypatch.setattr(app_mod.alertas, "alertar", lambda *a, **k: None)
    r = c.get("/_quebra_teste", headers=HTML)
    assert r.status_code == 500 and "Algo deu errado" in r.text and '<body class="vz">' in r.text
    r = c.get("/_quebra_teste")  # sem pedir HTML (fetch, robô): texto simples
    assert r.status_code == 500 and "<html" not in r.text
    app_mod.app.router.routes.remove(rota)


def test_lista_nao_redireciona_e_pede_nome_e_whatsapp(ocidental):
    r = cliente.get("/lista", follow_redirects=False)
    assert r.status_code == 200
    assert re.search(r'id="nome"[^>]*required', r.text) and re.search(r'id="whatsapp"[^>]*required', r.text)
    assert r.text.index("lista-form") < r.text.index("lista-mais")  # no celular, o formulário vem antes


def test_aviso_de_cookies_botoes_do_mesmo_tamanho():
    css = (RAIZ / "static" / "valderez" / "casca.css").read_text(encoding="utf-8")
    regra = re.search(r"\.cookie button\.button \{([^}]*)\}", css).group(1)
    assert "min-height: 46px" in regra and "width: 100%" in regra  # a mesma regra para os dois
    assert "grid-template-columns: 1fr 1fr" in css


def test_atributo_hidden_vence_as_classes():
    """Bug do print da Fase B: o bloco "Pronto" da /lista aparecia antes da inscrição
    porque o display:flex da classe vencia o atributo hidden."""
    css = (RAIZ / "static" / "valderez" / "v2.css").read_text(encoding="utf-8")
    assert ".vz [hidden] { display: none !important; }" in css

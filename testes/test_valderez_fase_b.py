"""
Rodada visual (Valderez Astrologia), Fase B: fluxo do mapa natal e o que sai por
e-mail e PDF.

- A 404 da ocidental é a tela do pacote e responde HTTP 404; API e védica, como antes.
- /mapa: formulário, carregando e resultado são estados da mesma página; no celular
  o formulário vem antes da ilustração; a taxa da plataforma vem do ofertas.yaml;
  o aviso "foi para o seu e-mail" só com o envio confirmado; o completo só com a
  resposta autorizada do servidor.
- Home, /mapa, textos legais, /minhas-leituras e 404 já não carregam o base.css.
- E-mails, remetente e PDF com o nome e as cores da Valderez; a védica igual.
- A CSP da ocidental não libera o Google Fonts (a da védica, sim).
- Nada de nome de variável de ambiente (PADMINI_…) no HTML público.
"""
import re
from datetime import datetime

import pytest

from test_app import RAIZ, app_mod, cliente

import entrega  # noqa: E402
import marketing  # noqa: E402
import ofertas  # noqa: E402
import paleta  # noqa: E402
import seguranca  # noqa: E402
import sistema  # noqa: E402

HTML = {"accept": "text/html,application/xhtml+xml"}
VESTIDAS = ["/", "/mapa", "/privacidade", "/termos", "/minhas-leituras", "/lista"]


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


# ------------------------------------------------------------------ 404
def test_404_da_ocidental_e_a_tela_do_pacote_com_status_404(ocidental):
    r = cliente.get("/uma-pagina-que-nao-existe", headers=HTML)
    assert r.status_code == 404 and r.headers["content-type"].startswith("text/html")
    assert "Esta página não foi encontrada" in r.text and 'href="/"' in r.text
    assert '<header class="header"' in r.text and "Valderez Astrologia" in r.text
    # rota que existe mas diz 404 (estilo sem chave) também
    assert cliente.get("/estilo", headers=HTML).status_code == 404


def test_404_com_a_captura_ligada_leva_para_a_lista(ocidental, monkeypatch):
    monkeypatch.setenv("PADMINI_CAPTURA", "1")
    r = cliente.get("/nao-existe", headers=HTML)
    assert r.status_code == 404 and 'href="/lista"' in r.text
    cabecalho = r.text[r.text.index("<header"):r.text.index("</header>")]
    assert "/mapa" not in cabecalho


def test_404_da_api_e_da_vedica_continuam_json(ocidental, monkeypatch):
    for rota in ("/api/nao-existe", "/static/nao-existe.css", "/webhook/nada"):
        r = cliente.get(rota, headers=HTML)
        assert r.status_code == 404 and r.json() == {"detail": "Not Found"}, rota
    assert cliente.get("/nao-existe").json() == {"detail": "Not Found"}  # sem pedir HTML (fetch, robô)
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    r = cliente.get("/nao-existe", headers=HTML)
    assert r.status_code == 404 and r.json() == {"detail": "Not Found"}


# ------------------------------------------------------------------ páginas vestidas
@pytest.mark.parametrize("rota", VESTIDAS)
def test_paginas_vestidas_nao_carregam_o_base_css(rota, ocidental):
    html = cliente.get(rota).text
    assert "/static/base.css" not in html and "/static/valderez/componentes.css" in html, rota
    assert '<html lang="pt-BR" data-theme="light">' in html, rota


def test_home_mantem_as_secoes(ocidental):
    html = cliente.get("/").text
    for trecho in ('class="produtos"', "As oito dimensões do casal", 'class="galeria"', "Como funciona",
                   "Uma tradição de família", "Perguntas", "/static/valderez/celeste.svg",
                   '<section class="hero" data-theme="dark">'):
        assert trecho in html, trecho
    assert html.count('class="cardc exemplo"') == 3


# ------------------------------------------------------------------ /mapa
def test_mapa_tem_os_tres_estados_na_mesma_pagina(ocidental):
    html = cliente.get("/mapa").text
    for estado in ('id="estado-form"', 'id="estado-carregando"', 'id="resultado"'):
        assert estado in html, estado
    assert '<ol class="stepbar" id="etapas"' in html
    # no celular, o formulário vem antes da ilustração (ordem no HTML)
    assert html.index('class="card mapa-form"') < html.index('class="mapa-arte"')
    # os campos e contratos de sempre
    for trecho in ('id="form"', 'id="data"', 'id="hora"', 'id="sem-hora"', 'id="cidade" name="cidade" role="combobox"',
                   'id="cidades" role="listbox"', 'id="email"', 'id="aceita-sequencia"', "/api/ocidental/mapa",
                   "/static/ocidental/amostra-email.js", "/static/afiliado.js", "linkCheckout("):
        assert trecho in html, trecho


def test_mapa_foca_o_erro_e_o_titulo_do_resultado(ocidental):
    html = cliente.get("/mapa").text
    assert 'mostrarErro("Preencha a data de nascimento no formato dd/mm/aaaa.", $("#data"))' in html
    assert 'campo.setAttribute("aria-invalid", "true"); campo.focus();' in html
    assert 'focar($("#titulo-resultado"))' in html and 'id="titulo-resultado" tabindex="-1"' in html


def test_taxa_da_plataforma_vem_do_ofertas_yaml(ocidental):
    taxa = ofertas.do_sistema("ocidental")["mapa"]["taxa_plataforma"]
    assert taxa == 0.99
    assert all(o["taxa_plataforma"] == taxa for o in ofertas.do_sistema("ocidental").values())
    html = cliente.get("/mapa").text
    assert f'const TAXA = "{ofertas.moeda(taxa)}";' in html
    assert "de taxa da plataforma" in html
    # e não virou "oferta": o webhook e o pronto_para_virar só veem ofertas
    assert "taxa_plataforma" not in ofertas.do_sistema("ocidental")
    assert ofertas.do_sistema("vedica")["mapa"]["taxa_plataforma"] is None


def test_aviso_de_email_so_com_o_envio_confirmado():
    js = (RAIZ / "static" / "ocidental" / "amostra-email.js").read_text(encoding="utf-8")
    corpo = js[js.index("function aviso(d)"):js.index("function ligar(")]
    assert 'if (!d.email || !d.email.enviado) return "";' in corpo


def test_completo_so_com_a_resposta_do_servidor(ocidental):
    html = cliente.get("/mapa?data=1990-05-15&hora=14:30&lat=-23.5&lon=-46.6&token=oc-falso").text
    # a página não traz nada do completo: ele é desenhado com a resposta da API
    assert 'pedir("/api/ocidental/mapa", { ...ultimoPedido, nivel: "completo" }).then(desenharResultado)' in html
    assert "Elementos e modalidades</h2>" not in html.split("<script>")[0]
    r = cliente.post("/api/ocidental/mapa", json={"data": "1990-05-15", "hora": "14:30", "lat": -23.5, "lon": -46.6,
                                                   "nivel": "completo", "token": "oc-falso"})
    assert r.status_code in (401, 402, 403)


# ------------------------------------------------------------------ e-mails e PDF
def _sem_padmini(html: str) -> list:
    html = re.sub(r"https?://[^\s\"'<>)]+", "", html).replace("Índice Padmini", "")
    return re.findall(r".{0,30}\bPadmini\b.{0,30}", html)


def test_emails_da_ocidental_com_a_marca_nova():
    import tarot
    import rotas_ocidental
    import sequencias
    ana = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30", "lat": -23.55, "lon": -46.63, "cidade": "SP"}
    htmls = [entrega.email_completo_html("mapa", "https://padmini.com.br/x", "Ana", "", "ocidental"),
             entrega.email_mapas_do_casal_html([("Ana", "https://x")], "Ana", "ocidental"),
             entrega.email_minhas_leituras_html([{"produto": "ocidental:mapa", "criado_em": datetime(2026, 9, 30),
                                                  "link": "https://x"}]),
             marketing.email_abandono_html("mapa", "Ana", "https://x", "a@b.c", "ocidental")]
    for produto, dados in {"mapa": ana, "tarot": {"tiragem": tarot.tirar()}}.items():
        amostra = rotas_ocidental.montar_amostra_email(produto, dados)
        htmls.append(marketing.email_amostra_html(produto, amostra, dados, "a@b.c", "Ana", "ocidental"))
        htmls.append(marketing.email_lembrete_html(produto, amostra, dados, "a@b.c", "ocidental"))
    htmls += [sequencias.email_boas_vindas(1, "mapa", ana, "a@b.c")[1],
              sequencias.email_pos_compra(1, "ocidental:mapa", "Ana", "a@b.c", ["ocidental:mapa"])[1]]
    for html in htmls:
        assert "Valderez Astrologia" in html and paleta.EMAIL["ocidental"]["fundo"] in html
        assert _sem_padmini(html) == [], _sem_padmini(html)
        assert entrega.remetente_do_email(html).startswith("Valderez Astrologia <")
    assert "Padmini" not in marketing.assunto("abandono", "mapa", "ocidental")


def test_remetente_muda_so_o_nome(monkeypatch):
    monkeypatch.setenv("PADMINI_EMAIL_FROM", "Padmini <nao-responda@padmini.com.br>")
    oc = entrega.email_completo_html("mapa", "https://x", "Ana", "", "ocidental")
    ve = entrega.email_completo_html("mapa", "https://x", "Ana", "", "vedica")
    assert entrega.remetente_do_email(oc) == "Valderez Astrologia <nao-responda@padmini.com.br>"
    assert entrega.remetente_do_email(ve) == "Padmini <nao-responda@padmini.com.br>"
    assert "<!-- versao:" not in ve  # a védica sai byte a byte como antes
    assert entrega.remetente_do_email("") == "Padmini <nao-responda@padmini.com.br>"


def test_email_da_ocidental_so_usa_pares_aprovados():
    """Texto do e-mail no fundo claro: só cores do tema claro que passam no fundo."""
    c, claro = paleta.EMAIL["ocidental"], paleta.VALDEREZ["light"]
    assert c["fundo"] == claro["background"] and c["texto"] == claro["text"]
    for chave in ("texto", "suave", "fraco", "acento", "acento2"):
        assert paleta.contraste(c[chave], c["fundo"]) >= 4.5, chave
    assert paleta.contraste(c["sobre_acento"], c["acento"]) >= 4.5


def test_pdf_com_a_marca_nova(monkeypatch):
    from reportlab import rl_config
    import gerar_pdf_ocidental as g
    import mapa_ocidental as mo
    import montar_texto_ocidental as mt
    monkeypatch.setattr(rl_config, "pageCompression", 0)
    nasc = datetime(1990, 5, 15, 14, 30)
    m = mo.calcular_mapa_ocidental(nasc, -23.5505, -46.6333)
    pdf = g.gerar_pdf_ocidental(mapa=m, secoes=mt.montar_secoes(m), nome="Ana", cidade="SP",
                                data_nascimento=nasc.date(), hora="14:30").decode("latin-1")
    assert "Valderez Astrologia" in pdf and "/Author (Valderez Astrologia)" in pdf
    assert "Young" not in pdf and "Almanaque" not in pdf


# ------------------------------------------------------------------ CSP e HTML público
def test_csp_da_ocidental_sem_google_fonts(ocidental):
    csp = cliente.get("/mapa").headers["content-security-policy"]
    assert "fonts.googleapis.com" not in csp and "fonts.gstatic.com" not in csp
    assert "font-src 'self'" in csp and "style-src 'self' 'unsafe-inline'" in csp


def test_link_da_vedica_com_a_ocidental_no_ar_ainda_carrega_as_fontes_dela(ocidental):
    # link de entrega da védica (token sem prefixo): a página é a védica, que usa o Google Fonts
    csp = cliente.get("/mapa?token=" + "a" * 32).headers["content-security-policy"]
    assert "https://fonts.googleapis.com" in csp and "https://fonts.gstatic.com" in csp
    csp_oc = cliente.get("/mapa?token=oc-abc").headers["content-security-policy"]
    assert "fonts.googleapis.com" not in csp_oc


def test_csp_da_vedica_como_sempre(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    csp = cliente.get("/").headers["content-security-policy"]
    assert "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com" in csp
    assert "font-src 'self' https://fonts.gstatic.com" in csp


@pytest.mark.parametrize("rota", list(sistema.PAGINAS["ocidental"]) + ["/privacidade", "/termos", "/minhas-leituras",
                                                                       "/live", "/nao-existe"])
def test_html_publico_sem_nome_de_variavel_de_ambiente(rota, ocidental):
    html = cliente.get(rota, headers=HTML).text
    assert not re.search(r"PADMINI_[A-Z_]+", html), (rota, re.findall(r"PADMINI_[A-Z_]+", html))


def test_js_publico_sem_nome_de_variavel_de_ambiente():
    for js in [*(RAIZ / "static").glob("*.js"), *(RAIZ / "static" / "ocidental").glob("*.js")]:
        assert not re.search(r"PADMINI_[A-Z_]+", js.read_text(encoding="utf-8")), js.name

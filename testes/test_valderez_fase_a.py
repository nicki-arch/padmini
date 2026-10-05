"""
Rodada visual (29/set/2026), Fase A: a marca Valderez Astrologia na versão ocidental.

- Nenhuma página pública da ocidental carrega fonte ou recurso de fora do site.
- Os tokens e os pares de cor da ocidental batem com o tokens.json do pacote.
- "Padmini" não aparece como marca nas páginas públicas da ocidental (exceções:
  o Índice Padmini, que o Nicolas ainda vai renomear, e o domínio). Desde a fase B,
  também nos textos legais.
- Nada do pacote de referência (barra "REFERÊNCIA", noindex, colchetes) vai ao ar.
- Fontes WOFF2 com as licenças OFL; SVGs servidos leves e sem texto embutido.
- Com a captura ligada, a /lista é a porta: sem menu para páginas trancadas.
"""
import json
import re

import pytest

from test_app import RAIZ, app_mod, cliente

import marca  # noqa: E402
import paleta  # noqa: E402
import sistema  # noqa: E402

PACOTE = RAIZ / "docs" / "design" / "valderez-1.0"
TOKENS = json.loads((PACOTE / "tokens" / "tokens.json").read_text(encoding="utf-8"))
VALDEREZ = RAIZ / "static" / "valderez"

# Páginas públicas da ocidental (as do buscador e as do rodapé).
PUBLICAS = (list(sistema.PAGINAS["ocidental"]) + list(sistema.LEGAIS["ocidental"])
            + ["/minhas-leituras", "/blog"])
# Textos legais: a marca troca; o responsável pelos dados e o CNPJ, não.
LEGAIS = set(sistema.LEGAIS["ocidental"])


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


def _pagina(rota):
    r = cliente.get(rota)
    if rota == "/blog" and r.status_code == 404:  # sem artigo revisado o blog não abre
        pytest.skip("blog sem artigo publicado")
    assert r.status_code == 200, rota
    return r.text


# ------------------------------------------------------------------ nada de fora
_RECURSO = re.compile(r'<(?:link|script|img|source|iframe)\b[^>]*?\s(?:href|src)="([^"]+)"', re.I)


def _recursos(html):
    """Endereços que o navegador BAIXA ao abrir a página (não os links <a>, nem og:*)."""
    for m in _RECURSO.finditer(html):
        tag = m.group(0)
        if tag.lower().startswith("<link") and re.search(r'rel="(canonical|alternate)"', tag):
            continue
        if "${" in m.group(1):
            continue  # marcador de template string do JavaScript (o endereço vem da API: ver test_rodada9_fase_b)
        yield m.group(1)


@pytest.mark.parametrize("rota", PUBLICAS + ["/live"])
def test_pagina_publica_so_carrega_recurso_do_proprio_site(rota, ocidental):
    html = _pagina(rota)
    for url in _recursos(html):
        assert url.startswith("/") and not url.startswith("//") or url.startswith("data:"), (rota, url)
    assert "fonts.googleapis" not in html and "fonts.gstatic" not in html, rota
    assert "@import" not in html and "url(http" not in html.replace(" ", ""), rota


def test_css_da_ocidental_nao_chama_nada_de_fora():
    for css in [RAIZ / "static" / "ocidental" / "tema.css", *VALDEREZ.glob("*.css")]:
        texto = css.read_text(encoding="utf-8")
        assert "@import" not in texto, css.name
        for url in re.findall(r"url\(\s*['\"]?([^'\")]+)", texto):
            assert url.startswith("/static/") or url.startswith("data:"), (css.name, url)


def test_fontes_sao_woff2_do_site_com_as_licencas():
    # rodada 9: Fraunces, Figtree e Noto Sans Symbols 2 (visual 2.0); Inter e Cormorant
    # continuam enquanto a fase C não vestir as páginas restantes
    usadas = paleta.FONTES["ocidental"]["arquivos"]
    assert {f for f, _, _ in usadas} == {"Inter", "Cormorant Garamond"}
    novas = paleta.FONTES_VZ["arquivos"]
    assert {f for f, _, _, _ in novas} == {"Fraunces", "Figtree", "Noto Sans Symbols", "Noto Sans Symbols 2"}
    for arquivo in [a for _, _, a in usadas] + [a for _, _, _, a in novas]:
        assert (VALDEREZ / "fontes" / arquivo).read_bytes()[:4] == b"wOF2", arquivo
    for licenca in ("Inter", "CormorantGaramond", "Fraunces", "Figtree", "NotoSansSymbols", "NotoSansSymbols2"):
        assert (VALDEREZ / "fontes" / f"OFL-{licenca}.txt").exists(), licenca
    tema = (RAIZ / "static" / "ocidental" / "tema.css").read_text(encoding="utf-8")
    assert tema.count("@font-face") == 9 and "format('woff2')" in tema


def test_svgs_servidos_leves_e_sem_fonte_embutida():
    # rodada 9: todo SVG servido tem menos de 30 KB (a roda tem ~22 KB)
    for svg in (RAIZ / "static").rglob("*.svg"):
        texto = svg.read_text(encoding="utf-8")
        assert svg.stat().st_size < 30_000, svg.name
        assert "<text" not in texto and "@font-face" not in texto and "http" not in texto.replace(
            "http://www.w3.org/2000/svg", ""), svg.name
        assert "[" not in texto, svg.name  # nada das marcações entre colchetes do pacote


def test_arquivos_de_marca_sao_os_de_marca_py():
    assert (VALDEREZ / "favicon.svg").read_text(encoding="utf-8") == marca.favicon_svg()
    assert (VALDEREZ / "simbolo-claro.svg").read_text(encoding="utf-8") == marca.svg_arquivo(
        paleta.VALDEREZ["light"]["text"])
    assert (VALDEREZ / "simbolo-escuro.svg").read_text(encoding="utf-8") == marca.svg_arquivo(
        paleta.VALDEREZ["dark"]["rose"])


def test_cores_das_ilustracoes_sao_da_paleta():
    todas = {v.lower() for tema in paleta.VALDEREZ.values() for v in tema.values()} | {v.lower() for v in paleta.VZ.values()}
    for svg in VALDEREZ.glob("*.svg"):
        for cor in re.findall(r"#[0-9a-fA-F]{6}\b", svg.read_text(encoding="utf-8")):
            assert cor.lower() in todas, (svg.name, cor)


# ------------------------------------------------------------------ tokens e contraste
def test_tokens_batem_com_o_pacote():
    for tema in ("light", "dark"):
        pacote = {k: v["value"].lower() for k, v in TOKENS["themes"][tema].items()}
        assert {k: v.lower() for k, v in paleta.VALDEREZ[tema].items()} == pacote, tema
    for k, v in TOKENS["typography"].items():
        assert paleta.TIPOGRAFIA[k] == ((v["mobile"]["size"], v["mobile"]["lineHeight"]),
                                        (v["desktop"]["size"], v["desktop"]["lineHeight"])), k
    assert paleta.ESPACOS == TOKENS["spacing"] and paleta.RAIOS == TOKENS["radii"]


def test_pares_de_cor_da_ocidental_sao_os_aprovados():
    aprovados = {(p["theme"], p["foreground"], p["background"]): p for p in TOKENS["contrast"]["pairs"]}
    usados = paleta.contrastes("ocidental")
    assert {(c["tema"], c["texto"], c["fundo"]) for c in usados} == set(aprovados)
    for c in usados:
        p = aprovados[(c["tema"], c["texto"], c["fundo"])]
        assert abs(c["razao"] - p["ratio"]) <= 0.01 and c["razao"] >= p["minimum"] and p["AA"], c


def test_tema_css_so_usa_cores_da_paleta():
    tema = (RAIZ / "static" / "ocidental" / "tema.css").read_text(encoding="utf-8")
    corpo = tema[tema.index("*/") + 2:]  # o comentário do topo lista os pares
    todas = {v.lower() for t in paleta.VALDEREZ.values() for v in t.values()} | {v.lower() for v in paleta.VZ.values()}
    for cor in re.findall(r"#[0-9a-fA-F]{6}\b", corpo):
        assert cor.lower() in todas, cor


def test_css_das_paginas_novas_nao_escreve_cor():
    """Cor só por token (var(--…)): nada de hexadecimal no casca.css e no componentes.css
    (a impressão, que força preto no branco, é a exceção)."""
    for nome in ("casca.css", "componentes.css", "v2.css"):
        texto = (VALDEREZ / nome).read_text(encoding="utf-8")
        texto = re.sub(r"@media print\{.*?\}\}", "", texto, flags=re.S)
        assert not re.findall(r"#[0-9a-fA-F]{3,6}\b", texto), nome


# ------------------------------------------------------------------ marca
def _sem_excecoes(html):
    html = re.sub(r"https?://[^\s\"'<>)]+", "", html)   # domínio e endereços (padmini.com.br, GitHub)
    html = html.replace("Índice Padmini", "")          # nome de produto: o Nicolas decide (fase C)
    return html


@pytest.mark.parametrize("rota", PUBLICAS)
def test_padmini_nao_aparece_como_marca(rota, ocidental):
    html = _pagina(rota)
    assert "Valderez Astrologia" in html, rota
    achados = re.findall(r".{0,40}\bPadmini\b.{0,40}", _sem_excecoes(html))
    assert achados == [], (rota, achados)


def test_textos_legais_trocam_a_marca_mas_nao_o_responsavel(ocidental):
    """Termos e privacidade (decisão do Nicolas, fase B): onde "Padmini" era nome de
    marca, agora é Valderez Astrologia; o responsável pelos dados e o CNPJ não mudam."""
    for rota in LEGAIS:
        html = _pagina(rota)
        assert "<title>Valderez Astrologia — " in html and 'class="marca"' in html, rota
        assert "Pedro Sperb Monteiro LTDA" in html and "55.428.936/0001-00" in html, rota
        assert "Valderez Astrologia (padmini.com.br)" in html, rota


# ------------------------------------------------------------------ nada do pacote vai ao ar
@pytest.mark.parametrize("rota", PUBLICAS + ["/live"])
def test_nada_da_referencia_do_pacote(rota, ocidental):
    html = _pagina(rota)
    assert "REFERÊNCIA" not in html and "prototype-note" not in html, rota
    assert not re.search(r"\[(Título|Texto|Ação|Nome|Digite|Orientação|Créditos|Privacidade|Termos|Contato)", html), rota
    # o noindex do pacote ("noindex,nofollow", sem espaço). As páginas que já eram fora do
    # buscador antes da rodada (legais, minhas-leituras, /live) continuam com o delas.
    assert 'content="noindex,nofollow"' not in html, rota
    if rota in sistema.PAGINAS["ocidental"]:
        assert "noindex" not in html, rota


def test_nenhum_template_tem_a_barra_de_referencia():
    for f in (RAIZ / "static").rglob("*.html"):
        texto = f.read_text(encoding="utf-8")
        assert "REFERÊNCIA DE DESIGN" not in texto and "prototype-note" not in texto, f.name


# ------------------------------------------------------------------ casca
@pytest.mark.parametrize("rota", PUBLICAS)
def test_cabecalho_e_rodape_da_valderez(rota, ocidental):
    html = _pagina(rota)
    # rodada 9: cabeçalho claro com a roda; rodapé noite com a roda clara
    assert '<header class="cab">' in html and '<footer class="rod">' in html
    assert 'src="/static/valderez/roda.svg" width="48" height="48"' in html
    assert 'src="/static/valderez/roda-claro.svg"' in html.split('<footer class="rod">')[1]
    assert 'href="#conteudo"' in html and 'id="conteudo"' in html
    assert 'href="/static/valderez/favicon.svg"' in html
    rodape = html[html.index('<footer class="rod"'):]
    for destino in ("/privacidade", "/termos", "mailto:", "/minhas-leituras", "github.com/nicki-arch/padmini",
                    'id="preferencias-cookies"'):
        assert destino in rodape, (rota, destino)


def test_lista_com_a_captura_ligada(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.setenv("PADMINI_CAPTURA", "1")
    app_mod._paginas_prontas.clear()
    try:
        assert cliente.get("/", follow_redirects=False).headers["location"].startswith("/lista")
        html = cliente.get("/lista").text
        assert "/static/valderez/v2.css" in html  # rodada 9: visual 2.0
        assert "/static/base.css" not in html  # a lista já é toda do pacote novo
        cabecalho = html[html.index("<header"):html.index("</header>")]
        assert 'href="/lista"' in cabecalho and "/mapa" not in cabecalho  # sem menu para páginas trancadas
        assert 'og:site_name" content="Valderez Astrologia"' in html
        # formulário e contrato com /api/lista e os scripts de sempre
        for trecho in ('id="form"', 'id="email"', 'id="aceita-email"', 'id="aceita-whatsapp"', 'id="site"',
                       '"/api/lista"', "/static/afiliado.js", "/static/ocidental/consentimento.js",
                       '<meta name="pad-consentimento" content="exigido">'):
            assert trecho in html, trecho
        assert not re.search(r'<input type="checkbox" id="aceita-email"[^>]*checked', html)  # nunca pré-marcado
        # no celular o formulário vem antes das vantagens e da ilustração
        assert html.index('lista-form"') < html.index('lista-mais"')
    finally:
        app_mod._paginas_prontas.clear()


def test_aviso_de_cookies_com_botoes_iguais():
    js = (RAIZ / "static" / "ocidental" / "consentimento.js").read_text(encoding="utf-8")
    botoes = re.findall(r'<button type="button" class="([^"]+)" data-cookies="(\w+)">', js)
    assert sorted(b[1] for b in botoes) == ["aceito", "recusado"]
    assert len({b[0] for b in botoes}) == 1  # a mesma classe: mesmo tamanho e mesmo destaque
    assert 'className = "cookie"' in js and "cookie-actions" in js


def test_descadastro_na_marca_nova(ocidental):
    html = cliente.get("/descadastrar?e=a@b.c&t=x").text
    assert "Valderez Astrologia" in html and "Padmini" not in _sem_excecoes(html)
    assert "/static/valderez/casca.css" in html and "fonts.googleapis" not in html


def test_vedica_nao_carrega_nada_da_valderez(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    app_mod._paginas_prontas.clear()
    try:
        for rota in list(sistema.PAGINAS["vedica"]) + ["/termos", "/privacidade", "/descadastrar?e=a@b.c&t=x"]:
            html = cliente.get(rota).text
            assert "valderez" not in html.lower(), rota
    finally:
        app_mod._paginas_prontas.clear()

"""
Rodada visual (Valderez Astrologia), Fase C: sinastria, numerologia, tarot, blog e
/live com os componentes do pacote, sem fluxo novo; o nome do índice da sinastria
numa chave só (conteudo/ocidental/marca.yaml).
"""
import re
from pathlib import Path

import pytest

from test_app import RAIZ, app_mod, cliente

import blog  # noqa: E402
import marketing  # noqa: E402
import montar_texto_ocidental as mt  # noqa: E402
import textos  # noqa: E402

FASE_C = ["/compatibilidade", "/numerologia", "/tarot", "/live"]


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


# ------------------------------------------------------------------ páginas
@pytest.mark.parametrize("rota", FASE_C)
def test_paginas_da_fase_c_no_pacote(rota, ocidental):
    html = cliente.get(rota).text
    assert "/static/base.css" not in html and "/static/valderez/componentes.css" in html, rota
    assert "/static/ocidental/componentes.css" not in html, rota
    tema = "dark" if rota == "/live" else "light"  # /live: tela de transmissão, tema escuro inteiro
    assert f'<html lang="pt-BR" data-theme="{tema}">' in html, rota


def test_nenhum_template_da_ocidental_usa_o_base_css():
    for f in (RAIZ / "static" / "ocidental").glob("*.html"):
        codigo = re.sub(r"\{#.*?#\}", "", f.read_text(encoding="utf-8"), flags=re.S)
        assert "/static/base.css" not in codigo and "/static/ocidental/componentes.css" not in codigo, f.name


def test_contratos_de_sempre(ocidental):
    """Mesmos ids, APIs e scripts: o visual mudou, o funcionamento não."""
    esperado = {
        "/compatibilidade": ['id="data-a"', 'id="data-b"', 'id="cidade-a" name="cidade-a" role="combobox"', 'id="lista-b"',
                             'id="cidade-a-status" aria-live="polite"', 'id="email"', 'id="aceita-sequencia"',
                             "/api/ocidental/sinastria", "linkCheckout(", "const CUPONS", "PRECO_BUMP_MAPAS"],
        "/numerologia": ['id="nome"', 'id="data"', 'id="email"', "/api/ocidental/numerologia", "linkCheckout("],
        "/tarot": ['id="pergunta"', 'maxlength="140"', 'id="email"', "/api/ocidental/tarot/tirar", "pad_tarot_pergunta",
                   "linkCheckout("],
        "/live": ['id="senha"', "/api/live/ocidental/token/mapa", 'id="aba-tarot"', 'class="faixa pago"'],
    }
    for rota, trechos in esperado.items():
        html = cliente.get(rota).text
        for t in trechos:
            assert t in html, (rota, t)


@pytest.mark.parametrize("rota", ["/compatibilidade", "/numerologia", "/tarot"])
def test_taxa_e_foco_nas_paginas_de_produto(rota, ocidental):
    html = cliente.get(rota).text
    assert 'const TAXA = "0,99";' in html and "de taxa da plataforma" in html
    assert 'campo.setAttribute("aria-invalid", "true"); campo.focus();' in html
    assert 'focar($("#titulo-resultado"))' in html and 'id="titulo-resultado" tabindex="-1"' in html


def test_cartas_e_rosa_em_bloco_escuro(ocidental):
    """A rosa, as cartas e o card desenham com as cores do tema escuro: ficam em blocos escuros."""
    compat = cliente.get("/compatibilidade").text
    assert '<figure class="rosa-bloco" data-theme="dark">' in compat
    assert '<div class="cardc" data-theme="dark">' in compat
    assert 'class="mesa" data-theme="dark"' in cliente.get("/tarot").text


def test_blog_no_pacote(ocidental, monkeypatch):
    monkeypatch.setenv("PADMINI_PREVIA_CHAVE", "chave-teste")
    lista = cliente.get("/blog?previa=chave-teste")
    assert lista.status_code == 200 and "/static/base.css" not in lista.text and 'class="card artigo-card"' in lista.text
    a = blog.todos()[0]
    art = cliente.get(f"/blog/{a['slug']}?previa=chave-teste").text
    assert '<article class="article"' in art and a["titulo"] in art


# ------------------------------------------------------------------ o nome do índice
ARQUIVO_DO_NOME = RAIZ / "conteudo" / "ocidental" / "marca.yaml"


def test_nome_do_indice_mora_so_numa_chave():
    """Nenhum código, template, CSS/JS ou texto escreve o nome do índice: só a marca.yaml."""
    nome = textos.NOME_INDICE
    assert nome == "Índice Padmini"  # o de hoje; o Nicolas decide o novo
    achados = []
    for pasta, padroes in ((RAIZ, ["*.py", "scripts/*.py"]), (RAIZ / "static", ["**/*.html", "**/*.js", "**/*.css"]),
                           (RAIZ / "conteudo", ["**/*.yaml", "**/*.md"])):
        for padrao in padroes:
            for f in pasta.glob(padrao):
                if f == ARQUIVO_DO_NOME:
                    continue
                if nome.lower() in f.read_text(encoding="utf-8").lower():
                    achados.append(str(f.relative_to(RAIZ)))
    assert achados == [], achados


def test_trocar_o_nome_e_uma_linha(ocidental, monkeypatch):
    novo = "Índice Valderez"
    monkeypatch.setattr(textos, "NOME_INDICE", novo)
    monkeypatch.setitem(app_mod._jinja.globals, "indice", novo)
    textos._lidos.clear(); blog.todos.cache_clear()
    try:
        for rota in ("/compatibilidade",):  # rodada 9: a home não fala mais do índice (sinastria em breve)
            html = cliente.get(rota).text
            assert novo in html and "Índice Padmini" not in html, rota
        artigo = next(a for a in blog.todos() if a["slug"] == "como-ler-o-indice-padmini")
        assert novo in artigo["titulo"]  # o endereço do artigo não muda
        assert novo in mt.texto_metodo() and "{indice}" not in mt.texto_metodo()
        import rotas_ocidental
        ana = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30", "lat": -23.55, "lon": -46.63, "cidade": "SP"}
        dados = {"a": ana, "b": {**ana, "nome": "Rui", "data": "1988-11-02"}}
        html = marketing.email_amostra_html("compat", rotas_ocidental.montar_amostra_email("compat", dados), dados,
                                            "a@b.c", "Ana", "ocidental")
        sem_links = re.sub(r"https?://[^\s\"'<>)]+", "", html)
        assert (novo in html or novo.upper() in html) and "PADMINI" not in sem_links.upper()
    finally:
        textos._lidos.clear(); blog.todos.cache_clear(); app_mod._paginas_prontas.clear()


def test_marcador_nunca_vaza(ocidental):
    for rota in ("/", "/compatibilidade", "/live"):
        assert "{indice}" not in cliente.get(rota).text, rota
    for a in blog.todos():
        assert "{indice}" not in str(a), a["slug"]
    assert "{indice}" not in mt.texto_metodo()


def test_card_do_casal_usa_a_chave_e_a_marca(ocidental):
    html = cliente.get("/compatibilidade").text
    assert '(NOME_INDICE + " · método próprio").toUpperCase()' in html
    assert '"valderez-" + _slug' in html and "padmini-" not in html
    assert "Young Serif" not in html and "Source Sans" not in html  # o canvas usa as fontes do site

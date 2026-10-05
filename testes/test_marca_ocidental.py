"""
Rodada 3, Fase B: a identidade "Almanaque" da versão ocidental — desde 29/set/2026
a marca Valderez Astrologia (rodada visual; ver também test_valderez_fase_a.py).

- Nada da ocidental (páginas, e-mails, PDFs, imagens) usa as cores ou as fontes
  antigas, nem devanágari.
- Uma fonte de verdade: paleta.py. O tema.css é gerado dele; os tokens da védica
  no base.css batem com ele; os contrastes seguem a regra do base.css.
- Nada servido pela védica muda (a foto de testes/test_sistema.py continua valendo).
"""
import importlib.util
import re
from datetime import date, datetime
from io import BytesIO

import pytest

from test_app import RAIZ, app_mod, cliente

import entrega  # noqa: E402
import marca  # noqa: E402
import marketing  # noqa: E402
import paleta  # noqa: E402
import sistema  # noqa: E402

_spec = importlib.util.spec_from_file_location("gerar_tema_css", RAIZ / "scripts" / "gerar_tema_css.py")
gerar_tema_css = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gerar_tema_css)


def _sem_nada_antigo(texto: str, onde: str):
    baixo = texto.lower()
    for antiga in paleta.ANTIGAS:
        assert antiga.lower() not in baixo, f"{onde}: ainda usa {antiga!r}"
    assert not re.search(r"[ऀ-ॿ]", texto), f"{onde}: tem devanágari"


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


# ------------------------------------------------------------------ fonte única
def test_tema_css_esta_em_dia_com_a_paleta():
    assert (RAIZ / "static" / "ocidental" / "tema.css").read_text(encoding="utf-8") == gerar_tema_css.gerar(), \
        "rode python scripts/gerar_tema_css.py"


def _numeros(v: str):
    return [float(x) for x in re.findall(r"\d*\.?\d+", v)] if "(" in v else v.strip().lower()


def test_tokens_da_vedica_no_base_css_batem_com_a_paleta():
    css = (RAIZ / "static" / "base.css").read_text(encoding="utf-8")
    raiz = css[css.index(":root"):css.index("}", css.index(":root"))]
    declarados = dict(re.findall(r"--([\w-]+):\s*([^;]+);", raiz))
    for token, valor in paleta.tela("vedica").items():
        assert _numeros(declarados[token]) == _numeros(valor), token


def test_contrastes_da_ocidental_seguem_a_regra():
    """Valderez: os 44 pares aprovados do pacote passam (texto ≥ 4,5; contorno ≥ 3)."""
    linhas = paleta.contrastes("ocidental")
    ruins = [f"{c['texto']} sobre {c['fundo']}: {c['razao']}" for c in linhas if not c["passa"]]
    assert ruins == [] and len(linhas) == 44


def test_nomes_antigos_da_ocidental_sao_cores_do_tema_escuro():
    """As páginas ainda no base.css usam --ground, --ink…: só cores do tema escuro da Valderez."""
    escuro = {v.lower() for v in paleta.VALDEREZ["dark"].values()}
    for k, v in paleta.TELA["ocidental"].items():
        if isinstance(v, str) and v.startswith("#"):
            assert v.lower() in escuro, k


def test_nada_de_roxo_na_tinta_da_ocidental():
    """Fundo azul-tinta, não ameixa/roxo: o azul domina o vermelho em todas as superfícies."""
    for k in ("ground", "ground-2", "ground-3"):
        r, g, b = paleta._rgb(paleta.TELA["ocidental"][k])
        assert b > r + 15 and b > g, k


# ------------------------------------------------------------------ páginas
def test_paginas_da_ocidental_sem_cor_fonte_nem_devanagari_antigos(ocidental):
    rotas = list(sistema.PAGINAS["ocidental"]) + list(sistema.LEGAIS["ocidental"]) + ["/live"]
    for rota in rotas:
        html = cliente.get(rota).text
        _sem_nada_antigo(html, rota)
        assert "/static/ocidental/tema.css" in html and "/static/valderez/casca.css" in html, rota
    for arquivo in ("tema.css", "_carta.html"):
        _sem_nada_antigo((RAIZ / "static" / "ocidental" / arquivo).read_text(encoding="utf-8"), arquivo)


def test_paginas_da_vedica_nao_carregam_o_tema(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    app_mod._paginas_prontas.clear()
    try:
        for rota in list(sistema.PAGINAS["vedica"]) + ["/termos", "/privacidade"]:
            assert "tema.css" not in cliente.get(rota).text, rota
    finally:
        app_mod._paginas_prontas.clear()


def test_simbolo_da_valderez():
    """Círculo, oito raios e a estrela de quatro pontas (docs/design/valderez-1.0/marca/simbolo-claro.svg)."""
    svg = marca.svg(30)
    assert 'fill="none"' in svg and "<circle" in svg and svg.count("<path") == 2 and "currentColor" in svg
    ref = (RAIZ / "docs" / "design" / "valderez-1.0" / "marca" / "simbolo-claro.svg").read_text(encoding="utf-8")
    assert "M32 5v54M5 32h54M13 13l38 38M13 51l38-38" in ref and 'r="24"' in ref  # o mesmo desenho
    # rodada 9: o favicon é a roda dos 12 signos (pacote valderez-design-2.0)
    uri = marca.favicon_uri()
    assert uri.startswith("data:image/svg+xml,") and paleta.VZ["ouro"][1:] in uri
    assert (RAIZ / "static" / "valderez" / "favicon.svg").read_text(encoding="utf-8") == marca.favicon_svg()


# ------------------------------------------------------------------ e-mails
def test_emails_da_ocidental(monkeypatch):
    for produto in ("mapa", "compat", "numerologia", "tarot"):
        extra = marketing.bloco_venda_cruzada(produto, {"nome": "Ana", "a": {"nome": "A"}, "b": {"nome": "B"}},
                                              "ocidental")
        html = entrega.email_completo_html(produto, "https://padmini.com.br/x", "Ana", extra, "ocidental")
        _sem_nada_antigo(html, f"e-mail {produto}")
        assert paleta.EMAIL["ocidental"]["fundo"] in html and "Fraunces" in html  # rodada 9: fontes do visual 2.0
    _sem_nada_antigo(entrega.email_mapas_do_casal_html([("Ana", "https://x")], "Ana", "ocidental"), "mapas do casal")


def test_emails_de_marketing_da_ocidental():
    """Rodada 4: amostra por e-mail, lembrete e carrinho abandonado na paleta nova."""
    import rotas_ocidental
    import tarot
    ana = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30", "lat": -23.55, "lon": -46.63, "cidade": "SP"}
    exemplos = {"mapa": ana, "compat": {"a": ana, "b": {**ana, "nome": "Rui", "hora": ""}},
                "numerologia": {"nome": "Ana Souza", "data": "1990-05-15"}, "tarot": {"tiragem": tarot.tirar()}}
    for produto, dados in exemplos.items():
        amostra = rotas_ocidental.montar_amostra_email(produto, dados)
        for nome, html in (
                ("amostra", marketing.email_amostra_html(produto, amostra, dados, "a@b.c", "Ana", "ocidental")),
                ("lembrete", marketing.email_lembrete_html(produto, amostra, dados, "a@b.c", "ocidental")),
                ("abandono", marketing.email_abandono_html(produto, "Ana", "https://x", "a@b.c", "ocidental"))):
            _sem_nada_antigo(html, f"{nome} {produto}")
            assert paleta.EMAIL["ocidental"]["fundo"] in html and "Fraunces" in html, f"{nome} {produto}"


def test_emails_da_vedica_continuam_com_as_cores_de_sempre():
    html = entrega.email_completo_html("mapa", "https://padmini.com.br/x", "Ana", "", "vedica")
    assert "background:#241522" in html and "background:#e7a24a;color:#2a1608" in html


# ------------------------------------------------------------------ PDFs
def _pdf_sem_compressao(monkeypatch, gerar):
    from reportlab import rl_config
    monkeypatch.setattr(rl_config, "pageCompression", 0)
    return gerar().decode("latin-1")


def _cor_pdf(hexa: str) -> tuple:
    return tuple(round(c / 255, 3) for c in paleta._rgb(hexa))


def test_pdfs_da_ocidental(monkeypatch):
    import gerar_pdf_ocidental as g
    import mapa_ocidental as mo
    import montar_texto_ocidental as mt
    import numerologia as nu
    import tarot
    nasc = datetime(1990, 5, 15, 14, 30)
    m = mo.calcular_mapa_ocidental(nasc, -23.5505, -46.6333)
    pdfs = {
        "mapa": lambda: g.gerar_pdf_ocidental(mapa=m, secoes=mt.montar_secoes(m), nome="Ana", cidade="SP",
                                              data_nascimento=nasc.date(), hora="14:30"),
        "numerologia": lambda: g.gerar_pdf_numerologia(
            rel=mt.montar_numerologia(nu.calcular_numerologia("Ana Souza", date(1990, 5, 15), 2026), "completo"),
            nome="Ana Souza", data_nascimento=date(1990, 5, 15)),
        "tarot": lambda: g.gerar_pdf_tarot(rel=mt.montar_tarot(tarot.cartas_da_tiragem(tarot.tirar()), "completo")),
    }
    antigas = {_cor_pdf(v) for k, v in paleta.PAPEL["vedica"].items() if isinstance(v, str) and v.startswith("#")}
    novas = {_cor_pdf(paleta.PAPEL["ocidental"][k]) for k in ("tinta", "acento")}
    for nome, gerar in pdfs.items():
        conteudo = _pdf_sem_compressao(monkeypatch, gerar)
        # rodada 9: Fraunces + Figtree, como o site (visual 2.0); nada da rodada 3
        assert "Fraunces" in conteudo and "Figtree" in conteudo, nome
        assert "YoungSerif" not in conteudo and "SourceSans3" not in conteudo, nome
        assert "Valderez Astrologia" in conteudo or "Valderez" in conteudo, nome
        usadas = {tuple(round(float(x), 3) for x in trio.split())
                  for trio in re.findall(r"(\d*\.?\d+ \d*\.?\d+ \d*\.?\d+) (?:rg|RG)", conteudo)}
        assert not (usadas & antigas), f"{nome}: cor antiga {usadas & antigas}"
        assert usadas & novas, nome


# ------------------------------------------------------------------ imagens
@pytest.mark.parametrize("nome", ["home", "mapa", "compatibilidade", "numerologia", "tarot"])
def test_og_images_da_ocidental(nome):
    from PIL import Image
    img = Image.open(RAIZ / "static" / f"og-oc-{nome}.png").convert("RGB")
    assert img.size == (1200, 630)
    cores = dict((c, n) for n, c in img.getcolors(1200 * 630))
    fundo = max(cores, key=cores.get)
    # rodada 9: a imagem da home (scripts/gerar_marca.py) é a roda no creme; as outras, até a fase C, no azul
    esperado = paleta.VZ["creme"] if nome == "home" else paleta.VALDEREZ["dark"]["background"]
    assert fundo == paleta._rgb(esperado)
    for antiga in ("#241522", "#e7a24a", "#e2a89d", "#2b1a29"):
        assert paleta._rgb(antiga) not in cores, f"og-oc-{nome}.png tem {antiga}"


# ------------------------------------------------------------------ /estilo
def test_estilo_so_com_a_chave_de_previa(monkeypatch):
    monkeypatch.setenv("PADMINI_PREVIA_CHAVE", "chave-teste")
    assert cliente.get("/estilo").status_code == 404
    assert cliente.get("/estilo?previa=errada").status_code == 404
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")  # sempre a ocidental, qualquer que seja a do ar
    r = cliente.get("/estilo?previa=chave-teste")
    assert r.status_code == 200 and "noindex" in r.headers.get("x-robots-tag", "")
    html = r.text
    assert '<meta name="robots" content="noindex, nofollow">' in html
    for trecho in ("Paleta e contrastes", "Cormorant Garamond", "Inter", 'class="button"', "<input",
                   "Cidade", "Consentimento", "Cartão de resultado", "Preço", "Aviso de cookies", "Menu",
                   "Perguntas frequentes", "Artigo", "Seu pagamento foi confirmado", "14.55:1"):
        assert trecho in html, trecho
    _sem_nada_antigo(html, "/estilo")


def test_estilo_sem_chave_configurada_nao_abre(monkeypatch):
    monkeypatch.delenv("PADMINI_PREVIA_CHAVE", raising=False)
    assert cliente.get("/estilo?previa=").status_code == 404

"""
Rodada 19 (17/out/2026): a página /links, o link da bio do TikTok, do Instagram e do YouTube.

O mais importante é a ORIGEM: /links?utm_source=tiktok repassa utm_source=tiktok (mais
utm_medium=bio e utm_campaign=links) a todos os botões internos, no HTML montado no
servidor; a amostra feita a partir daí fica gravada com essa origem, e o
scripts/relatorio_origem.py conta por utm_source.
"""
import copy
import html as html_mod
import json
import os
import re
import shutil
import subprocess
from datetime import date

import pytest

from test_app import RAIZ, app_mod, cliente  # primeiro: define os segredos de teste
import catalogo
import db
import enderecos
import entrega
import pagina_links
import stripe_api

HTML = {"accept": "text/html"}
TEST_URL = os.environ.get("TEST_DATABASE_URL", "")
precisa_banco = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL não definida")
ANA = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30", "lat": -23.5505, "lon": -46.6333, "cidade": "São Paulo"}


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    for v in ("PADMINI_CAPTURA", "PADMINI_VENDAS_TESTE", "PADMINI_DOMINIO_PRINCIPAL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("PADMINI_PAGAMENTO", "stripe")  # como a produção desde 11/out
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_" + "a" * 20)
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_" + "b" * 20)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


def _links(query=""):
    r = cliente.get("/links" + query, headers=HTML)
    assert r.status_code == 200, r.text
    return r.text


def _hrefs_internos(html):
    """Os links do corpo da página que levam a outra página nossa (não arquivos estáticos)."""
    corpo = html[html.index("<main"):html.index("</main>")]
    return [html_mod.unescape(h) for h in re.findall(r'href="(/[^"]*)"', corpo) if not h.startswith("/static/")]


# ------------------------------------------------------------------ a página
def test_so_na_ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    assert cliente.get("/links", headers=HTML).status_code == 404


def test_origem_vai_para_todos_os_botoes(ocidental):
    hrefs = _hrefs_internos(_links("?utm_source=tiktok"))
    assert {h.split("?")[0] for h in hrefs} >= {"/mapa", "/minhas-leituras", "/privacidade"}
    for h in hrefs:
        assert "?utm_source=tiktok&utm_medium=bio&utm_campaign=links" in h, h


def test_sem_utm_source_vira_links_e_o_que_vier_e_mantido(ocidental):
    for h in _hrefs_internos(_links()):
        assert h.endswith("?utm_source=links&utm_medium=bio&utm_campaign=links"), h
    hrefs = _hrefs_internos(_links("?utm_source=instagram&utm_medium=story&utm_content=v12&ref=PEDRO&cupom=PEDRO"
                                   "&fbclid=abc&email=ana%40x.com"))
    for h in hrefs:
        assert h.endswith("?utm_source=instagram&utm_medium=story&utm_campaign=links&ref=PEDRO&cupom=PEDRO"
                          "&utm_content=v12"), h  # fora da lista (fbclid, email) não segue


def test_origem_maliciosa_sai_escapada(ocidental):
    html = _links('?utm_source="><script>alert(1)</script>')
    assert "<script>alert(1)" not in html and '"><script' not in html


def test_botoes_do_catalogo_de_verdade(ocidental):
    catalogo.usar(catalogo.carregar())  # o YAML como está: mapa ativo, 3 em breve
    app_mod._paginas_prontas.clear()
    html = _links("?utm_source=tiktok")
    botoes = re.findall(r'<a class="links-bt[^"]*" href="([^"?]+)\?[^"]*" data-destino="([^"]+)"', html)
    assert botoes == [("/mapa", "mapa_gratis"), ("/mapa", "mapa"), ("/compatibilidade", "compat"),
                      ("/numerologia", "numerologia")]  # em breve: no máximo 2
    assert "Faça o seu mapa natal grátis" in html and "O começo das 10 dimensões do seu mapa, na hora" in html
    assert ('<s class="preco-de"><span class="sr-only">de </span>R$97</s><span class="sr-only">, por</span> R$47'
            " · relatório inteiro, roda e PDF") in html
    assert html.count('<span class="chip chip-breve">Em breve</span>') == 2
    assert "Recuperar minhas leituras" in html


def test_ligar_o_seu_ano_faz_o_botao_aparecer(ocidental):
    dados = copy.deepcopy(catalogo.carregar())
    for p in dados["produtos"]:
        if p["chave"] == "previsao":
            p["estado"] = "ativo"
    catalogo.usar(dados)
    html = _links("?utm_source=youtube")
    assert re.search(r'href="/seu-ano\?utm_source=youtube&amp;utm_medium=bio[^"]*" data-destino="previsao">\s*'
                     r'<b>O seu ano</b>\s*<span><s class="preco-de">.*?R\$47 ·', html, re.S)


def test_venda_fechada_sem_preco(ocidental):
    catalogo.usar(dict(catalogo.carregar(), vendas_abertas=False))
    html = _links()
    assert "R$" not in html[html.index("<main"):] and 'data-destino="mapa_gratis"' in html


def test_lista_de_espera_ligada_abre_e_o_principal_vai_para_a_lista(ocidental, monkeypatch):
    monkeypatch.setenv("PADMINI_CAPTURA", "1")
    r = cliente.get("/links?utm_source=tiktok", headers=HTML, follow_redirects=False)
    assert r.status_code == 200
    assert 'href="/lista?utm_source=tiktok&amp;utm_medium=bio&amp;utm_campaign=links" data-destino="lista"' in r.text
    assert "R$" not in r.text[r.text.index("<main"):]  # nada à venda com a lista ligada


def test_canonical_og_sitemap(ocidental):
    html = _links("?utm_source=tiktok")
    assert f'<link rel="canonical" href="{enderecos.SITE_URL}/links">' in html
    assert f'<meta property="og:image" content="{enderecos.SITE_URL}/static/og-oc-home.png">' in html
    assert f"<loc>{enderecos.SITE_URL}/links</loc>" in cliente.get("/sitemap.xml").text


def test_sitemap_da_vedica_sem_links(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    assert "/links<" not in cliente.get("/sitemap.xml").text


def test_redes_contato_e_rodape_minimo(ocidental):
    html = _links()
    for r in enderecos.REDES:
        assert f'<a href="{r["url"]}" rel="noopener" aria-label="{r["nome"]} da Dona Valderez"' in html
    assert "@astrologiavalderez" in html and f'href="mailto:{enderecos.CONTATO}"' in html
    assert "Não é previsão nem substitui orientação profissional." in html
    assert '<header class="cab">' not in html and '<footer class="rod">' not in html  # sem menu nem rodapé grande


def test_nada_de_terceiros_nem_imagem_grande(ocidental):
    html = _links()
    for tag in re.findall(r"<(?:script|iframe|img|link|embed)\b[^>]*>", html):
        assert not re.search(r'(?:src|href)="(?:https?:)?//', tag) or 'rel="canonical"' in tag, tag
    assert "linktr.ee" not in html and "beacons" not in html
    assert '<meta name="pad-consentimento" content="exigido">' in html  # PostHog só depois do aceite
    assert 'padTrack("links_clique", { destino:' in html


def test_template_sem_preco_nem_endereco_a_mao():
    texto = (RAIZ / "static" / "ocidental" / "links.html").read_text(encoding="utf-8")
    assert not re.search(r"R\$\s*\d", texto) and "padmini.com.br" not in texto and "@astrologia" not in texto


@pytest.mark.skipif(not shutil.which("node"), reason="node não instalado")
def test_afiliado_js_guarda_a_origem_do_botao(ocidental):
    """O /mapa aberto pelo botão guarda a origem na sessão (afiliado.js): é dela que a
    amostra e o checkout tiram o `origem`."""
    href = _hrefs_internos(_links("?utm_source=tiktok"))[0]
    assert "/static/afiliado.js" in cliente.get("/mapa", headers=HTML).text
    js = (f"global.window=global;global.document={{querySelector(){{return null}}}};"
          f"global.location={{search:{json.dumps(href[href.index('?'):])},origin:'https://x'}};"
          "const s={};global.sessionStorage={getItem(k){return k in s?s[k]:null},setItem(k,v){s[k]=v}};"
          f"eval(require('fs').readFileSync({json.dumps(str(RAIZ / 'static' / 'afiliado.js'))},'utf8'));"
          "console.log(JSON.stringify(window.padAtribuicao()))")
    attr = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
    assert attr["utm_source"] == "tiktok" and attr["utm_medium"] == "bio" and attr["utm_campaign"] == "links"


# ------------------------------------------------------------------ Stripe
def test_metadata_da_stripe_leva_o_canal_e_nada_pessoal():
    pend = {"id": "p" * 24, "email": "ana@x.com", "itens": [{"chave": "mapa", "valor_centavos": 4700}],
            "rastreio": {"utm_source": "tiktok", "utm_medium": "bio", "utm_campaign": "links",
                         "ref": "PEDRO", "cupom": "PEDRO"}}
    p = stripe_api.parametros_da_sessao(pend, "https://x")
    esperado = {"pedido": "p" * 24, "utm_source": "tiktok", "utm_medium": "bio", "utm_campaign": "links"}
    assert p["metadata"] == esperado and p["payment_intent_data"] == {"metadata": esperado}
    assert stripe_api.metadata({**pend, "rastreio": {}}) == {"pedido": "p" * 24}


# ------------------------------------------------------------------ relatório
def test_relatorio_monta_a_tabela_sem_banco(monkeypatch, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("relatorio_origem", RAIZ / "scripts" / "relatorio_origem.py")
    rel = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rel)
    linhas = rel.linhas({"tiktok": {"amostras": 3, "me_avise": 1, "pedidos_pagos": 1},
                         "(sem origem)": {"amostras": 5, "me_avise": 0, "pedidos_pagos": 0}})
    assert linhas[0][0] == "(sem origem)" and linhas[-1] == ("total", 8, 1, 1)
    assert rel.csv(linhas).splitlines()[0] == "utm_source;amostras;me_avise;pedidos_pagos"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert rel.main(["--desde", "2026-10-14"]) == 2 and rel.main(["--desde", "14/10"]) == 2


@precisa_banco
def test_da_bio_ate_o_relatorio(ocidental, monkeypatch, capsys):
    """Critério 2: chegada por /links?utm_source=tiktok → amostra gravada com
    utm_source=tiktok → o relatório mostra 1 amostra do TikTok (e o "me avise" e o pedido)."""
    monkeypatch.setenv("DATABASE_URL", TEST_URL)
    assert db.iniciar()
    with db._conectar() as c:
        c.execute("TRUNCATE amostras_email, leads, pedidos")
    monkeypatch.setenv("RESEND_API_KEY", "teste")
    monkeypatch.setattr(entrega, "enviar_email", lambda *a, **k: True)

    href = _hrefs_internos(_links("?utm_source=tiktok"))[0]
    origem = dict(p.split("=") for p in href.split("?")[1].split("&"))  # o que o afiliado.js guarda
    r = cliente.post("/api/ocidental/mapa", json={**ANA, "nivel": "amostra", "email": "ana@exemplo.com",
                                                  "origem": origem})
    assert r.status_code == 200, r.text
    with db._conectar() as c:
        (gravada,) = c.execute("SELECT origem FROM amostras_email").fetchone()
    assert gravada == {"utm_source": "tiktok", "utm_medium": "bio", "utm_campaign": "links"}

    assert cliente.post("/api/lista", json={"nome": "Ana Souza", "email": "ana@teste.com",
                                            "whatsapp": "(51) 99999-8888", "aceita_email": True,
                                            "interesse": "compat", "origem": origem}).status_code == 200
    pend = {"id": "x" * 24, "email": "bia@x.com", "itens": [{"chave": "mapa", "valor_centavos": 4700}],
            "rastreio": origem}
    assert db.registrar_pedido_stripe({"id": "cs_1", "payment_intent": "pi_1", "amount_total": 4700}, pend,
                                      "ocidental:mapa", ANA, "https://x/mapa?token=oc-1", True,
                                      "checkout.session.completed", "card")

    import importlib.util
    spec = importlib.util.spec_from_file_location("relatorio_origem", RAIZ / "scripts" / "relatorio_origem.py")
    rel = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rel)
    assert db.contagem_por_origem(date(2026, 10, 14)) == {"tiktok": {"amostras": 1, "me_avise": 1, "pedidos_pagos": 1}}
    assert rel.main(["--desde", "2026-10-14"]) == 0
    saida = capsys.readouterr().out
    assert re.search(r"tiktok\s+1\s+1\s+1", saida) and "ana@" not in saida and "Ana" not in saida

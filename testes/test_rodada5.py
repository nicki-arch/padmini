"""
Round 5 (melhorias do site ocidental). Fase A: exemplos, rosa das oito
dimensões, "como fica o completo" e movimento.

- Os exemplos saem do motor (nada de número escrito à mão) e a página diz que
  os nascimentos são fictícios.
- A amostra não ganha as notas por dimensão (isso é do completo).
- Movimento só com prefers-reduced-motion: no-preference, e sem JS a página
  aparece inteira.
"""
import re

import pytest

from test_app import PESSOA, PESSOA_B, RAIZ, app_mod, cliente

import acesso  # noqa: E402
import exemplos_ocidental as ex  # noqa: E402
import sinastria as si  # noqa: E402

PAGINAS_OC = ("/", "/compatibilidade", "/mapa", "/numerologia", "/tarot")


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


# ------------------------------------------------------------------ exemplos
def test_exemplos_saem_do_motor():
    import rotas_ocidental as ro
    from datetime import date
    for base, calc in zip(ex.CASAIS, ex.casais()):
        mapas = [ro.calcular(ro.PedidoMapaOcidental(**{**base[x], "data": date.fromisoformat(base[x]["data"])}))[0]
                 for x in "ab"]
        sin = si.calcular_sinastria(*mapas)
        assert calc["indice"] == sin["indice"]
        assert calc["notas"] == {k: d["nota"] for k, d in sin["dimensoes"].items()}


def test_exemplos_variados():
    cs = ex.casais()
    assert len(cs) >= 3
    assert len({c["indice"] for c in cs}) == len(cs)
    assert len({c["ponto_forte"] for c in cs}) == len(cs)


def test_home_mostra_os_exemplos_calculados_e_diz_que_sao_ficticios(ocidental):
    html = cliente.get("/").text
    for c in ex.casais():
        assert f'{c["nomes"]["a"]} &amp; {c["nomes"]["b"]}' in html
        assert f'<div class="score">{c["indice"]}<span>' in html
        assert c["ponto_forte"].lower() in html
    assert html.count('class="rosa"') == len(ex.casais())
    assert "nascimentos fictícios" in html
    assert "/compatibilidade#como-fica" in html


def test_pagina_do_casal_mostra_como_fica_o_completo(ocidental):
    html = cliente.get("/compatibilidade").text
    assert 'id="como-fica"' in html and "Amostra grátis" in html
    c = ex.casais()[0]
    assert "nascimentos fictícios" in html and c["nomes"]["a"] in html
    forte = c["relatorio"]["ponto_forte"]
    assert f'{forte["titulo"]} — {forte["nota"]}/100' in html
    # o preço da tabela vem das ofertas (regra 12)
    import ofertas
    assert f'Completo · R${ofertas.moeda(ofertas.do_sistema("ocidental")["compat"]["preco"])}' in html


# ------------------------------------------------------------------ rosa
def test_rosa_tem_oito_petalas_e_rotulo_acessivel():
    notas = {k: 10 * i + 5 for i, k in enumerate(si.DIMENSOES)}
    svg = ex.rosa_svg(notas, "afeto")
    assert svg.count('class="petala"') == 8
    assert 'role="img"' in svg and "Atração 5" in svg and "Dia a dia 75" in svg
    assert svg == ex.rosa_svg(notas, "afeto")  # determinística
    assert "var(--blush)" in svg  # o ponto forte na segunda tinta


def test_rosa_sem_dados_vira_petala_tracejada():
    notas = {k: 60 for k in si.DIMENSOES}
    notas["dia_a_dia"] = None
    svg = ex.rosa_svg(notas)
    assert "stroke-dasharray:3 3" in svg and "Dia a dia sem dados" in svg


def test_petala_cresce_com_a_nota():
    def comprimento(nota):
        svg = ex.rosa_svg({k: nota for k in si.DIMENSOES}, rotulos=False)
        # ponta da primeira pétala (para cima): o y do primeiro Q
        d = re.search(r'class="petala"[^>]* d="M[\d.]+ [\d.]+Q[\d.]+ [\d.]+ [\d.]+ ([\d.]+)', svg).group(1)
        return 100 - float(d)
    assert comprimento(20) < comprimento(50) < comprimento(90)


# ------------------------------------------------------------------ API
def _chave():
    return acesso.chave_compat((PESSOA["data"], PESSOA["hora"], PESSOA["lat"], PESSOA["lon"]),
                               (PESSOA_B["data"], PESSOA_B["hora"], PESSOA_B["lat"], PESSOA_B["lon"]))


def test_rosa_so_no_completo():
    amostra = cliente.post("/api/ocidental/sinastria", json={"a": PESSOA, "b": PESSOA_B}).json()
    assert "rosa" not in amostra and "dimensoes" not in amostra
    corpo = {"a": PESSOA, "b": PESSOA_B, "nivel": "completo",
             "token": acesso.emitir_token("compat", _chave(), "ocidental")}
    c = cliente.post("/api/ocidental/sinastria", json=corpo).json()
    assert c["rosa"].count('class="petala"') == 8
    for d in c["dimensoes"]:
        if d["nota"] is not None:
            assert f'{ex.ROTULO_CURTO[d["chave"]]} {d["nota"]}' in c["rosa"]


# ------------------------------------------------------------------ movimento
def test_movimento_respeita_reduzir_movimento():
    css = (RAIZ / "static" / "ocidental" / "movimento.css").read_text(encoding="utf-8")
    corpo = re.sub(r"/\*.*?\*/", "", css, flags=re.S).strip()
    assert corpo.startswith("@media (prefers-reduced-motion: no-preference)") and corpo.endswith("}")
    # o que começa escondido só se esconde com .mov (posta pelo JS)
    for regra in re.findall(r"([^{}]+)\{[^{}]*opacity:\s*0", corpo):
        assert ".mov" in regra, regra
    js = (RAIZ / "static" / "ocidental" / "movimento.js").read_text(encoding="utf-8")
    assert "prefers-reduced-motion: reduce" in js and "IntersectionObserver" in js


def test_paginas_ocidentais_carregam_o_movimento(ocidental):
    for rota in PAGINAS_OC:
        html = cliente.get(rota).text
        assert "/static/ocidental/movimento.css" in html and "/static/ocidental/movimento.js" in html, rota


def test_vedica_nao_carrega_movimento_nem_exemplos(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    app_mod._paginas_prontas.clear()
    try:
        for rota in ("/", "/compatibilidade", "/mapa"):
            html = cliente.get(rota).text
            assert "movimento" not in html and 'id="como-fica"' not in html and 'class="rosa"' not in html
    finally:
        app_mod._paginas_prontas.clear()


# ================================================================== Fase B
def test_todo_campo_dos_formularios_tem_name(ocidental):
    for rota in ("/compatibilidade", "/mapa", "/numerologia", "/tarot"):
        html = cliente.get(rota).text
        for tag in re.findall(r"<(?:input|textarea)\b[^>]*>", html):
            assert " name=" in tag, f"{rota}: {tag}"


def test_menu_com_os_quatro_produtos_em_todas_as_paginas(ocidental):
    for rota in PAGINAS_OC:
        html = cliente.get(rota).text
        menu = re.search(r'<nav class="menu-produtos".*?</nav>', html, re.S).group(0)
        for destino in ("/compatibilidade", "/mapa", "/numerologia", "/tarot"):
            assert f'href="{destino}"' in menu, (rota, destino)
        atual = re.findall(r'href="([^"]+)" aria-current="page"', menu)
        assert atual == ([] if rota == "/" else [rota]), rota
        assert "/static/ocidental/componentes.css" in html


def test_busca_de_cidade_diz_o_que_aconteceu(ocidental):
    for rota, ids in (("/mapa", ["cidade-status"]), ("/compatibilidade", ["cidade-a-status", "cidade-b-status"])):
        html = cliente.get(rota).text
        for i in ids:
            assert f'id="{i}" aria-live="polite"' in html, (rota, i)
        assert "Nenhuma cidade encontrada" in html and "Cidade escolhida" in html


def test_json_ld_da_home_bate_com_a_pagina(ocidental):
    import json
    import textos
    html = cliente.get("/").text
    bloco = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
    dados = json.loads(bloco)
    tipos = {g["@type"] for g in dados["@graph"]}
    assert tipos == {"Organization", "WebSite", "FAQPage"}
    faq = next(g for g in dados["@graph"] if g["@type"] == "FAQPage")["mainEntity"]
    t = textos.da_pagina("home", "ocidental")
    assert [q["name"] for q in faq] == [i["pergunta"] for i in t["faq"]["itens"]]
    assert "aggregateRating" not in bloco and "review" not in bloco.lower()  # não temos avaliações


def test_json_ld_nao_fecha_o_script_antes_da_hora():
    import dados_estruturados
    t = {"seo": {"descricao": "x"}, "faq": {"itens": [{"pergunta": "a</script><b>", "resposta": "r"}]}}
    saida = dados_estruturados.home(t)
    assert saida.count("</script>") == 1


def test_vedica_sem_menu_novo_nem_json_ld(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    app_mod._paginas_prontas.clear()
    try:
        for rota in ("/", "/compatibilidade", "/mapa"):
            html = cliente.get(rota).text
            assert "menu-produtos" not in html and "application/ld+json" not in html
    finally:
        app_mod._paginas_prontas.clear()


def test_tarefa_diaria_chama_a_limpeza():
    wf = (RAIZ / ".github" / "workflows" / "tarefas.yml").read_text(encoding="utf-8")
    assert "/api/tarefas/limpeza" in wf


def test_limpeza_sem_chave_recusa(monkeypatch):
    monkeypatch.delenv("PADMINI_TAREFAS_CHAVE", raising=False)
    assert cliente.post("/api/tarefas/limpeza").status_code == 503
    monkeypatch.setenv("PADMINI_TAREFAS_CHAVE", "certa")
    assert cliente.post("/api/tarefas/limpeza", headers={"Authorization": "Bearer errada"}).status_code == 401

"""
Rodada 6.1 (29/set): a /lista da ocidental, única página aberta com a captura ligada.

- Mapa natal na frente (título e primeira opção de interesse, marcada); a sinastria em segundo.
- Nada de "o valor que aparece aqui é o que se paga": a Cakto soma R$0,99 de taxa.
- Condição de quem está na lista sem valor nem percentual prometido.
- Copy no YAML (conteudo/ocidental/lista.yaml).
"""
import re

import pytest

from test_app import RAIZ, app_mod, cliente

import textos  # noqa: E402


@pytest.fixture
def lista(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    app_mod._paginas_prontas.clear()
    yield cliente.get("/lista").text
    app_mod._paginas_prontas.clear()


def test_mapa_natal_e_a_porta_de_entrada(lista):
    h1 = re.search(r"<h1>(.*?)</h1>", lista, re.S).group(1)
    assert "nasceu" in h1 and "dois" not in h1
    lede = re.search(r'<p class="lede">(.*?)</p>', lista, re.S).group(1)
    assert lede.index("mapa natal") < lede.index("sinastria")
    assert "O seu mapa natal — Valderez Astrologia" in lista and "A sinastria de vocês dois" not in lista


def test_interesse_mapa_primeiro_e_marcado(lista):
    radios = re.findall(r'<input type="radio" name="interesse" value="(\w+)"( checked)?>', lista)
    assert radios == [("mapa", " checked"), ("compat", ""), ("ambos", "")]
    assert "Meu mapa natal" in lista and "Sinastria do casal" in lista


def test_sem_promessa_de_preco(lista):
    assert "o que se paga" not in lista
    assert not re.search(r"R\$\s?\d", lista)  # nem preço nem valor de fundador na lista
    assert not re.search(r"\d+\s?%", re.sub(r"<[^>]*>", " ", lista.split("<main", 1)[1].split("</main>")[0]))  # nem percentual de desconto
    assert "Condição especial para quem está na lista" in lista


def test_revisao_da_dona_valderez(lista):
    assert "Dona Valderez" in lista and "mais de 40 anos" in lista


def test_copy_vem_do_yaml(lista):
    t = textos.da_pagina("lista", "ocidental")
    for trecho in (t["seo"]["titulo"], t["hero"]["eyebrow"], t["revisao"]["titulo"], t["formulario"]["botao"],
                   t["pronto"]["titulo"], *(b["titulo"] for b in t["beneficios"])):
        assert trecho in lista
    html = (RAIZ / "static" / "ocidental" / "lista.html").read_text(encoding="utf-8")
    assert "Sinastria do casal" not in html and "Entrar na lista</button>" not in html


def test_valores_gravados_continuam_os_mesmos(monkeypatch):
    gravados = []
    monkeypatch.setattr(app_mod.db, "registrar_lead", lambda *a: gravados.append(a[5]) or True)
    for v in ("mapa", "compat", "ambos"):
        assert cliente.post("/api/lista", json={"email": "a@b.co", "aceita_email": True, "interesse": v}).status_code == 200
    assert gravados == ["mapa", "compat", "ambos"]

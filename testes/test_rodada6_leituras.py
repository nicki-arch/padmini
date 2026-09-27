"""
Rodada 6, Fase C: "Recuperar minhas leituras" (ocidental), sem login.

- A resposta é sempre a mesma, exista compra ou não; sem compra, nenhum e-mail sai.
- Com compra, sai UM e-mail com todos os links (link da védica continua o da védica).
- Nada de outra pessoa vaza; limites por IP (429) e por e-mail (silencioso).
"""
from datetime import datetime

import pytest

from test_app import app_mod, cliente

import alertas  # noqa: E402
import db  # noqa: E402
import entrega  # noqa: E402
import limites  # noqa: E402

COMPRAS = {
    "ana@exemplo.com": [
        {"produto": "compat", "criado_em": datetime(2026, 9, 20), "link": "https://padmini.com.br/compatibilidade?token=VEDICO1"},
        {"produto": "ocidental:mapa", "criado_em": datetime(2026, 9, 26), "link": "https://padmini.com.br/mapa?token=oc-MAPA1"},
        {"produto": "ocidental:mapas_casal", "criado_em": datetime(2026, 9, 26),
         "link": "https://padmini.com.br/mapa?token=oc-A\nhttps://padmini.com.br/mapa?token=oc-B"},
    ],
    "rui@exemplo.com": [
        {"produto": "ocidental:tarot", "criado_em": datetime(2026, 9, 27), "link": "https://padmini.com.br/tarot?t=x&token=oc-RUI"},
    ],
}


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


@pytest.fixture
def emails(monkeypatch):
    enviados = []
    monkeypatch.setenv("RESEND_API_KEY", "teste")
    monkeypatch.setattr(entrega, "enviar_email", lambda d, a, h: enviados.append((d, a, h)) or True)
    monkeypatch.setattr(db, "leituras_do_email", lambda e: [dict(x) for x in COMPRAS.get(e.lower(), [])])
    return enviados


def _pedir(email):
    return cliente.post("/api/minhas-leituras", json={"email": email})


def test_pagina_so_na_ocidental(ocidental, monkeypatch):
    r = cliente.get("/minhas-leituras")
    assert r.status_code == 200 and 'id="email"' in r.text and "noindex" in r.text
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    assert cliente.get("/minhas-leituras").status_code == 404
    assert _pedir("ana@exemplo.com").status_code == 404


def test_resposta_igual_com_e_sem_compra(ocidental, emails):
    com, sem = _pedir("ana@exemplo.com"), _pedir("ninguem@exemplo.com")
    assert com.status_code == sem.status_code == 200
    assert com.json() == sem.json()
    assert [d for d, _, _ in emails] == ["ana@exemplo.com"]  # sem compra, nada sai


def test_um_email_com_todos_os_links(ocidental, emails):
    _pedir("ANA@exemplo.com")
    assert len(emails) == 1
    destino, assunto, html = emails[0]
    assert destino == "ana@exemplo.com" and "leituras" in assunto.lower()
    for token in ("VEDICO1", "oc-MAPA1", "oc-A", "oc-B"):
        assert token in html, token
    assert "Compatibilidade do casal" in html and "Mapa natal" in html and "Mapas natais do casal" in html
    assert "20/09/2026" in html and "Abrir o 2 de 2" in html
    assert "oc-RUI" not in html  # nada de outra pessoa


def test_links_da_vedica_continuam_os_da_vedica(ocidental, emails):
    _pedir("ana@exemplo.com")
    assert "https://padmini.com.br/compatibilidade?token=VEDICO1" in emails[0][2]


def test_limite_por_email_e_silencioso(ocidental, emails):
    respostas = [_pedir("ana@exemplo.com").json() for _ in range(5)]
    assert all(r == respostas[0] for r in respostas)
    assert len(emails) == limites.MINHAS_LEITURAS_EMAIL.maximo


def test_limite_por_ip(ocidental, emails):
    for i in range(limites.MINHAS_LEITURAS.maximo):
        assert _pedir(f"x{i}@exemplo.com").status_code == 200
    assert _pedir("mais@exemplo.com").status_code == 429


@pytest.mark.parametrize("email", ["", "sem-arroba", "a@b"])
def test_email_invalido(ocidental, emails, email):
    assert _pedir(email).status_code == 422 and emails == []


def test_falha_do_envio_avisa_a_equipe_e_nao_muda_a_resposta(ocidental, emails, monkeypatch):
    avisos = []
    monkeypatch.setattr(entrega, "enviar_email", lambda *a: False)
    monkeypatch.setattr(alertas, "alertar", lambda *a, **k: avisos.append(a))
    r = _pedir("ana@exemplo.com")
    assert r.status_code == 200 and avisos and "ana@exemplo.com" not in str(avisos)


def test_sem_banco_nada_sai(ocidental, monkeypatch):
    enviados = []
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(entrega, "enviar_email", lambda *a: enviados.append(a) or True)
    assert _pedir("ana@exemplo.com").status_code == 200 and enviados == []


# ------------------------------------------------------------------ onde o link aparece
def test_link_no_rodape_e_na_falha_do_completo(ocidental):
    for rota in ("/", "/mapa", "/compatibilidade", "/numerologia", "/tarot", "/privacidade"):
        assert 'href="/minhas-leituras">Minhas leituras</a>' in cliente.get(rota).text, rota
    for rota in ("/mapa", "/compatibilidade", "/numerologia", "/tarot"):
        assert 'Se você já pagou, <a href="/minhas-leituras">' in cliente.get(rota).text, rota


def test_link_no_email_de_entrega_so_na_ocidental():
    oc = entrega.email_completo_html("mapa", "https://x", "Ana", "", "ocidental")
    ve = entrega.email_completo_html("mapa", "https://x", "Ana", "", "vedica")
    assert "/minhas-leituras" in oc and "/minhas-leituras" not in ve
    assert "/minhas-leituras" in entrega.email_mapas_do_casal_html([("Ana", "https://x")], "Ana", "ocidental")
    assert "/minhas-leituras" not in entrega.email_mapas_do_casal_html([("Ana", "https://x")], "Ana", "vedica")


def test_vedica_sem_link_nas_paginas(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "vedica")
    app_mod._paginas_prontas.clear()
    try:
        for rota in ("/", "/mapa", "/compatibilidade"):
            assert "minhas-leituras" not in cliente.get(rota).text
    finally:
        app_mod._paginas_prontas.clear()

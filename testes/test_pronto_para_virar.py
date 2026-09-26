"""
scripts/pronto_para_virar.py: a lista do que impede trocar PADMINI_SISTEMA
para `ocidental`.
"""
import importlib.util
import json
import os

from test_app import RAIZ

import entrega  # noqa: E402
import ofertas  # noqa: E402

_spec = importlib.util.spec_from_file_location("pronto_para_virar", RAIZ / "scripts" / "pronto_para_virar.py")
pronto = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pronto)


def test_lista_as_ofertas_sem_link():
    bloqueios, avisos = pronto.ofertas_sem_link()
    sem_link = {k for k, o in ofertas.do_sistema("ocidental").items() if not o.get("checkout")}
    assert {b.split(" ")[0] for b in bloqueios} == sem_link - set(pronto.OPCIONAIS)
    assert {a.split(" ")[0] for a in avisos} == sem_link & set(pronto.OPCIONAIS)


def test_com_todos_os_links_as_ofertas_nao_bloqueiam(monkeypatch):
    novas = json.loads(json.dumps(ofertas.POR_SISTEMA["ocidental"]))
    for o in novas.values():
        o["checkout"] = "https://pay.cakto.com.br/x_1"
    monkeypatch.setitem(ofertas.POR_SISTEMA, "ocidental", novas)
    assert pronto.ofertas_sem_link() == ([], [])


def test_conta_os_textos_nao_revisados():
    import revisao
    _, por_produto = pronto.textos()
    assert sum(t for _, t in por_produto.values()) == len(revisao.itens())
    assert set(por_produto) == {"Mapa natal", "Sinastria", "Numerologia", "Tarot"}


def test_nenhuma_pagina_da_ocidental_fala_da_vedica():
    antes = os.environ.get("PADMINI_SISTEMA")
    assert pronto.paginas_com_vedica() == []
    assert os.environ.get("PADMINI_SISTEMA") == antes  # não deixa a versão trocada


def test_acha_a_copy_da_vedica_quando_ela_vaza(monkeypatch):
    monkeypatch.setattr(entrega, "email_completo_html", lambda *a, **k: "Padmini — astrologia védica")
    achados = pronto.paginas_com_vedica()
    assert achados and all("e-mail de entrega" in a and "védic" in a for a in achados)

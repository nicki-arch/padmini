"""
Base de textos da versão ocidental (conteudo/ocidental/textos/*.yaml).

  - está completa: 10 planetas × 12 signos, 10 × 12 casas, 12 Ascendentes,
    e todo aspecto que o motor pode achar entre pessoais tem texto próprio;
  - todo texto tem `revisado` (é o contador de trabalho da família);
  - tom: 60 a 120 palavras, sem previsão de saúde, morte ou dinheiro, sem
    "você vai" (tendência, não sentença), sem HTML/script.
"""
import itertools
import random
import re
from datetime import datetime

import pytest

import mapa_ocidental as mo  # noqa: E402
import montar_texto_ocidental as mt  # noqa: E402

from revisao import PROIBIDOS  # noqa: E402  (uma lista só: testes e importação da planilha)
LONGOS = ("planetas_signos", "planetas_casas", "ascendente", "aspectos_pessoais", "numerologia")


def test_base_completa():
    signos, casas = mt.base("planetas_signos"), mt.base("planetas_casas")
    for p in mo.PLANETAS:
        assert set(signos[p]) == set(mo.SIGNOS), p
        assert set(casas[p]) == set(range(1, 13)), p
    assert set(mt.base("ascendente")) == set(mo.SIGNOS)
    pecas = mt.base("pecas")
    assert set(pecas["temas"]) >= set(mo.PONTOS_COM_ASPECTO)
    assert set(pecas["dinamica"]) == set(pecas["conselho"]) == set(mo.ASPECTOS)
    assert set(pecas["regente_ascendente"]) == set(mo.PLANETAS)


def test_todo_texto_tem_revisado():
    for arquivo, caminho, no in mt.cada_texto():
        assert isinstance(no.get("revisado"), bool), (arquivo, caminho)
        assert str(no.get("texto") or "").strip(), (arquivo, caminho)


@pytest.mark.parametrize("arquivo", LONGOS)
def test_tamanho_60_a_120_palavras(arquivo):
    for a, caminho, no in mt.cada_texto():
        if a == arquivo and caminho[0] != "descricao":  # descrições da numerologia são peças curtas
            n = len(no["texto"].split())
            assert 60 <= n <= 120, (arquivo, caminho, n)


def test_aspectos_compostos_tambem_tem_tamanho_certo():
    for a, b in itertools.combinations(mo.PONTOS_COM_ASPECTO, 2):
        for tipo in mo.ASPECTOS:
            n = len(mt.texto_aspecto(a, b, tipo).split())
            assert 55 <= n <= 120, (a, b, tipo, n)
            assert "{" not in mt.texto_aspecto(a, b, tipo)


def test_tom_sem_previsao_de_saude_morte_ou_dinheiro():
    for arquivo, caminho, no in mt.cada_texto():
        baixo = no["texto"].lower()
        for p in PROIBIDOS:
            assert p not in baixo, (arquivo, caminho, p)
        assert not re.search(r"<\s*script|javascript:|on\w+=", baixo), (arquivo, caminho)


def test_todo_aspecto_entre_pessoais_que_o_ceu_permite_tem_texto_proprio():
    """Sorteia 3000 datas (1900–2025) e confere que cada aspecto que o motor acha
    entre Sol, Lua, Mercúrio, Vênus e Marte tem texto em aspectos_pessoais.yaml."""
    proprios = mt.base("aspectos_pessoais")
    rnd = random.Random(20260926)
    for _ in range(3000):
        dt = datetime(rnd.randint(1900, 2025), rnd.randint(1, 12), rnd.randint(1, 28), rnd.randint(0, 23))
        mapa = mo.calcular_mapa_ocidental(dt, -23.55, -46.63)
        for a in mapa["aspectos"]:
            if a["a"] in mo.PESSOAIS and a["b"] in mo.PESSOAIS:
                assert a["tipo"] in proprios.get(f"{a['a']}-{a['b']}", {}), a


def test_contagem_de_revisao():
    c = mt.contagem_de_revisao()
    revisados, total = c["_total"]
    assert total == sum(t for k, (_, t) in c.items() if k != "_total") >= 330
    assert 0 <= revisados <= total

"""
Rodada 13, Fase 2: os textos de "O seu ano" (repositório privado, conteudo/ocidental/textos/
previsao/) entram na planilha de revisão, numa aba "Previsão", com as regras de tom mais
rigorosas da previsão (nada de "vai", "destino", saúde, acidente, herança...).
"""
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

import mapa_ocidental as mo
import montar_texto_ocidental as mt
import revisao

LENTOS = ("jupiter", "saturno", "urano", "netuno", "plutao")
PONTOS_NATAIS = ("sol", "lua", "mercurio", "venus", "marte", "jupiter", "saturno", "ascendente", "meio_do_ceu")


def _da_previsao():
    return [i for i in revisao.itens() if i["arquivo"].startswith("previsao/")]


def test_os_254_textos_existem_com_as_chaves_certas():
    contagem = Counter(i["arquivo"] for i in _da_previsao())
    assert contagem == {"previsao/transitos": 135, "previsao/casas": 60, "previsao/eclipses": 24,
                        "previsao/revolucao": 24, "previsao/pecas": 11}
    t = mt.base("previsao/transitos")
    assert list(t) == list(LENTOS)
    for planeta in LENTOS:
        assert list(t[planeta]) == list(PONTOS_NATAIS)
        for ponto in PONTOS_NATAIS:
            assert list(t[planeta][ponto]) == ["conjuncao", "harmonico", "tenso"]
    c = mt.base("previsao/casas")
    assert all(list(c[p]) == list(range(1, 13)) for p in LENTOS)
    e = mt.base("previsao/eclipses")
    assert list(e) == ["solar", "lunar"] and all(list(e[x]) == list(range(1, 13)) for x in e)
    r = mt.base("previsao/revolucao")
    assert list(r["ascendente"]) == mo.SIGNOS and list(r["sol_casa"]) == list(range(1, 13))
    pecas = mt.base("previsao/pecas")
    for k in ("abertura", "como_ler", "temas", "linha_do_tempo", "areas", "eclipses", "revolucao", "fechamento"):
        assert pecas[k]["texto"]
    assert set(pecas["avisos"]) == {"sem_hora", "retrogradacao", "sem_revolucao"}


def test_nada_novo_nasce_revisado_e_tudo_passa_nas_regras():
    for i in _da_previsao():
        assert i["revisado"] is False, i["id"]
        assert i["produto"] == "Previsão" and i["onde"].startswith("Previsão · "), i["id"]
        assert revisao.problemas(i["texto"], i["arquivo"], i["caminho"]) == [], i["id"]


def test_tamanhos_da_previsao():
    assert revisao.limites("previsao/transitos", ("jupiter", "sol", "tenso")) == (60, 120)
    assert revisao.limites("previsao/casas", ("saturno", "4")) == (60, 120)
    for arq in ("previsao/eclipses", "previsao/revolucao", "previsao/pecas"):
        assert revisao.limites(arq, ("x",)) == (40, 80)


@pytest.mark.parametrize("frase", [
    "Neste período você vai conhecer alguém especial.",
    "É o seu destino mudar de cidade.",
    "Um tempo que pede atenção à saúde do coração.",
    "A herança da família chega neste ano.",
    "Uma demissão pode abrir portas.",
    "A separação acontecerá no fim do ano.",
    "Os planetas vão trazer novidades.",
])
def test_regras_mais_duras_na_previsao(frase):
    """O que o mapa natal tolera às vezes (ex.: "vão", "separação"), a previsão não."""
    texto = (frase + " ") + "Um tempo de tema e janela, com calma e exemplo concreto. " * 7
    assert revisao.problemas(texto, "previsao/casas", ("jupiter", "1")), frase


def test_vai_dentro_de_outra_palavra_nao_e_barrado():
    texto = "Um tempo de vaidade bem cuidada e de ir avante com calma, em vários planos da vida. " * 4
    assert revisao.problemas(texto, "previsao/casas", ("jupiter", "1")) == []


def test_aba_previsao_na_planilha(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    saida = tmp_path / "revisao.xlsx"
    subprocess.run([sys.executable, "scripts/exportar_revisao.py", str(saida)], check=True,
                   cwd=Path(__file__).resolve().parents[1], env=dict(os.environ), capture_output=True)
    wb = openpyxl.load_workbook(saida)
    assert "Previsão" in wb.sheetnames
    ids = [r[0].value for r in wb["Previsão"].iter_rows(min_row=2) if r[0].value]
    assert len(ids) == 254 and all(x.startswith("previsao/") for x in ids)


def test_importar_grava_na_subpasta(tmp_path, monkeypatch):
    """A gravação da revisão acha o arquivo dentro de previsao/ e mexe só no bloco aprovado."""
    pasta = tmp_path / "textos"
    shutil.copytree(mt.PASTA, pasta)
    monkeypatch.setattr(mt, "PASTA", pasta)
    mt.base.cache_clear()
    try:
        alvo = next(i for i in _da_previsao() if i["id"] == "previsao/eclipses:solar/10")
        antes = (pasta / "previsao" / "eclipses.yaml").read_text(encoding="utf-8")
        assert revisao.gravar([{"arquivo": alvo["arquivo"], "caminho": alvo["caminho"],
                                "texto": None, "revisado": True}]) == ["previsao/eclipses"]
        depois = (pasta / "previsao" / "eclipses.yaml").read_text(encoding="utf-8")
        assert mt.base("previsao/eclipses")["solar"][10]["revisado"] is True
        assert mt.base("previsao/eclipses")["solar"][9]["revisado"] is False
        # só o bloco aprovado muda (a quebra de linha dele pode mudar); o resto, byte a byte
        assert antes[antes.index("\nlunar:"):] == depois[depois.index("\nlunar:"):]
        assert antes[:antes.index("\n  10:")] == depois[:depois.index("\n  10:")]
    finally:
        monkeypatch.undo()
        mt.base.cache_clear()

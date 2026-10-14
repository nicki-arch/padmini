"""
Rodada 12: o mapa natal fecha as 10 dimensões. Carreira, Dinheiro, Família e Propósito
deixam de ser "em breve" e se leem pelas casas (cúspide, planetas na casa, regente) e
pelo Nodo Norte; sem hora de nascimento, cada uma mostra o que vale para o dia inteiro e
um aviso. Textos novos no repositório privado (meio_do_ceu, cuspides, nodo_norte,
regentes, aspectos_sociais), todos `revisado: false` até a Dona Valderez revisar.
"""
from datetime import date, datetime, timedelta

import pytest

from test_app import app_mod, cliente  # primeiro: define os segredos de teste

import acesso
import catalogo
import mapa_ocidental as mo
import montar_texto_ocidental as mt
import revisao

pytestmark = pytest.mark.catalogo_real
HTML = {"accept": "text/html"}
PESSOA = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30", "lat": -30.03, "lon": -51.23,
          "cidade": "Porto Alegre, RS"}
NOVOS = ("meio_do_ceu", "cuspides", "nodo_norte", "regentes", "aspectos_sociais")
NOVAS = ("carreira", "dinheiro", "familia", "proposito")


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


def _completo(p=PESSOA):
    token = acesso.emitir_token("mapa", acesso.chave_mapa(p["data"], p["hora"], p["lat"], p["lon"]), "ocidental")
    r = cliente.post("/api/ocidental/mapa", json={**p, "nivel": "completo", "token": token})
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ os textos novos
def test_os_146_textos_novos_existem_e_seguem_as_regras():
    contagem = {a: 0 for a in NOVOS}
    for it in revisao.itens():
        if it["arquivo"] in NOVOS:
            contagem[it["arquivo"]] += 1
            no = mt._no(it["arquivo"], *[int(c) if c.isdigit() else c for c in it["caminho"]])
            assert no["revisado"] is False, it["id"]  # nada novo nasce revisado
            assert revisao.problemas(it["texto"], it["arquivo"], it["caminho"]) == [], it["id"]
            assert it["onde"].startswith("Mapa natal · ") and it["produto"] == "Mapa natal"
    assert contagem == {"meio_do_ceu": 12, "cuspides": 24, "nodo_norte": 24, "regentes": 36,
                        "aspectos_sociais": 50}


def test_todas_as_chaves_tem_texto():
    for s in mo.SIGNOS:
        assert mt.texto_meio_do_ceu(s) and mt.texto_cuspide(2, s) and mt.texto_cuspide(4, s)
        assert mt.texto_nodo(signo=s)
    for casa in range(1, 13):
        assert mt.texto_nodo(casa=casa)
        assert all(mt.texto_regente(x, casa) for x in (10, 2, 4))
    for d in ("sem_hora_carreira", "sem_hora_dinheiro", "sem_hora_familia", "sem_hora_proposito"):
        assert mt.aviso(d)


# ------------------------------------------------------------------ as dimensões
def test_catalogo_tem_as_10_dimensoes_ativas():
    assert [d["estado"] for d in catalogo.dimensoes_mapa()] == ["ativo"] * 10


@pytest.mark.parametrize("data,hora,lat,lon", [
    ("1990-05-15", "14:30", -30.03, -51.23), ("1985-11-02", "06:10", -23.55, -46.63),
    ("2001-02-28", "23:45", -3.73, -38.52), ("1972-08-09", "12:00", 51.5, -0.12)])
def test_com_hora_as_compostas_tem_texto_regente_e_casa(data, hora, lat, lon):
    m = mo.calcular_mapa_ocidental(datetime.fromisoformat(f"{data}T{hora}"), lat, lon)
    c = mt.compostas_ativas(m)
    assert list(c) == list(NOVAS)
    for chave, d in c.items():
        assert d["texto"] and not d["aviso"], chave
        assert all(b["titulo"] and b["texto"] for b in d["blocos"]), chave
    assert c["carreira"]["titulo"].startswith("Meio do Céu em ")
    assert c["dinheiro"]["titulo"].startswith("Casa 2 em ")
    assert c["familia"]["titulo"].startswith("Fundo do Céu em ")
    for chave, casa in (("carreira", 10), ("dinheiro", 2), ("familia", 4)):
        regente = mo.REGENTE[mt.signo_da_cuspide(m, casa)]
        assert any(b["titulo"] == f"O regente da casa {casa}: {mo.PONTO_PT[regente]} na casa {m['pontos'][regente]['casa']}"
                   for b in c[chave]["blocos"]), chave
        # todo planeta na casa aparece (texto inteiro ou referência)
        for p in mo.PLANETAS:
            if m["pontos"][p]["casa"] == casa:
                assert any(b["titulo"] == f"{mo.PONTO_PT[p]} na casa {casa}" for b in c[chave]["blocos"]), (chave, p)
    assert any(b["titulo"].startswith("Nodo Norte na casa") for b in c["proposito"]["blocos"])
    assert any(b["titulo"].startswith("A sua Lua em") and b.get("referencia") for b in c["familia"]["blocos"])


def test_sem_hora_as_compostas_mostram_o_que_vale_para_o_dia_e_avisam():
    m = mo.calcular_mapa_ocidental(None, -30.03, -51.23, data=date(1990, 5, 15))
    c = mt.compostas_ativas(m)
    assert c["carreira"]["titulo"].startswith("Saturno em ") and c["carreira"]["texto"]
    assert c["dinheiro"]["titulo"].startswith("Júpiter em ") and c["dinheiro"]["texto"]
    assert c["familia"]["titulo"].startswith("Lua em ")
    assert c["proposito"]["titulo"].startswith("Nodo Norte em ") and c["proposito"]["texto"]
    for chave in NOVAS:
        assert c[chave]["aviso"] == mt.aviso(f"sem_hora_{chave}"), chave
        assert not any("casa" in b["titulo"] for b in c[chave]["blocos"]), chave  # sem hora, sem casas


def test_planeta_com_dimensao_propria_entra_so_como_referencia():
    """Não repetir texto: o planeta que já tem dimensão (ou que outra composta já mostrou)
    aparece com o título e uma frase; o texto inteiro de cada casa sai uma vez só."""
    for data, hora in (("1990-05-15", "14:30"), ("1985-11-02", "06:10"), ("2001-02-28", "23:45")):
        m = mo.calcular_mapa_ocidental(datetime.fromisoformat(f"{data}T{hora}"), -23.55, -46.63)
        vistos = set()
        for chave, d in mt.compostas_ativas(m).items():
            for b in d["blocos"]:
                ponto = next((p for p in mo.PLANETAS if b["titulo"].startswith(f"{mo.PONTO_PT[p]} na casa")), None)
                if ponto is None:
                    continue
                if ponto in mo.PESSOAIS or ponto in vistos:
                    assert b.get("referencia") and b["texto"].endswith("."), (chave, b["titulo"])
                    assert len(b["texto"]) < len(mt.texto_casa(ponto, m["pontos"][ponto]["casa"])) + 30
                else:
                    assert not b.get("referencia")
                    vistos.add(ponto)


def test_completo_traz_as_10_dimensoes_sem_em_breve(ocidental):
    d = _completo()
    assert [x["chave"] for x in d["dimensoes"]] == [x["chave"] for x in catalogo.dimensoes_mapa()]
    assert all(x["estado"] == "ativo" for x in d["dimensoes"])
    novas = {x["chave"]: x for x in d["dimensoes"] if x["chave"] in NOVAS}
    assert all(x["texto"] and x["blocos"] and x["titulo"] for x in novas.values())
    # o texto inteiro de um planeta usado numa composta não se repete no resto do mapa
    corpo = str(d["resto"])
    for x in novas.values():
        for b in x["blocos"]:
            if not b.get("referencia") and " na casa " in b["titulo"] and not b["titulo"].startswith(("O regente", "Nodo")):
                assert b["texto"] not in corpo, b["titulo"]
    assert "em breve" not in str(d).lower()


def test_completo_sem_hora(ocidental):
    d = _completo({**PESSOA, "hora": ""})
    novas = {x["chave"]: x for x in d["dimensoes"] if x["chave"] in NOVAS}
    assert all(x["estado"] == "ativo" and x["aviso"] for x in novas.values())
    assert "em breve" not in str(d).lower()


def test_token_entregue_antes_da_rodada_abre_as_10(ocidental):
    """O token não muda: um link já entregue abre o que estiver ativo (a promessa do
    "chega em breve no seu mapa")."""
    token = acesso.emitir_token("mapa", acesso.chave_mapa(PESSOA["data"], PESSOA["hora"], PESSOA["lat"],
                                                          PESSOA["lon"]), "ocidental")
    r = cliente.post("/api/ocidental/mapa", json={**PESSOA, "nivel": "completo", "token": token})
    assert sum(x["estado"] == "ativo" for x in r.json()["dimensoes"]) == 10


def test_amostra_mostra_so_o_comeco_das_novas(ocidental):
    r = cliente.post("/api/ocidental/mapa", json={**PESSOA, "email": "ana@teste.com", "nivel": "amostra"})
    assert r.status_code == 200, r.text
    dims = {x["chave"]: x for x in r.json()["dimensoes"]}
    m = mo.calcular_mapa_ocidental(datetime(1990, 5, 15, 14, 30), -30.03, -51.23)
    c = mt.compostas_ativas(m)
    for chave in NOVAS:
        item, texto = dims[chave], c[chave]["texto"]
        assert item["estado"] == "ativo" and item["titulo"] == c[chave]["titulo"]
        assert item["trecho"] and texto.startswith(item["trecho"]) and len(item["trecho"]) < len(texto)
        resto = texto[len(item["trecho"]):].strip()
        assert resto[:60] not in r.text, chave  # o texto pago nunca vai para o navegador
        for b in c[chave]["blocos"]:
            if b.get("referencia"):  # a referência é o começo de um texto que outra dimensão já mostra
                continue
            assert b["texto"][:60] not in r.text, (chave, b["titulo"])
        assert "blocos" not in item and "texto" not in item


def test_pdf_e_live_tem_as_dimensoes_novas():
    m = mo.calcular_mapa_ocidental(datetime(1990, 5, 15, 14, 30), -30.03, -51.23)
    secoes = mt.montar_secoes(m)  # o PDF, o /live e o prompt da IA leem estas seções
    for nome in ("Carreira", "Dinheiro", "Família", "Propósito"):
        assert nome in secoes and secoes[nome], nome
    assert "em breve" not in str(secoes).lower()
    assert "Carreira" not in mt.montar_secoes(m, dimensoes=False)  # a página já as mostra nas dimensões
    from gerar_pdf_ocidental import gerar_pdf_ocidental
    pdf = gerar_pdf_ocidental(mapa=m, secoes=secoes, nome="Ana", cidade="Porto Alegre, RS",
                              data_nascimento=date(1990, 5, 15), hora="14:30")
    assert pdf[:4] == b"%PDF" and len(pdf) > 10_000


def test_pagina_do_mapa_desenha_titulo_blocos_e_aviso(ocidental):
    html = cliente.get("/mapa", headers=HTML).text
    assert "const tituloDim" in html and "x.blocos" in html and "x.aviso" in html


def test_selo_so_com_texto_revisado_tambem_nas_novas(monkeypatch):
    m = mo.calcular_mapa_ocidental(datetime(1990, 5, 15, 14, 30), -30.03, -51.23)
    dims = {x["chave"]: x for x in mt.dimensoes_amostra(m)}
    assert all("selo" not in dims[c] for c in NOVAS)  # os textos novos nascem não revisados


# ------------------------------------------------------------------ Fase 3: aspectos de Júpiter e Saturno
def test_saturno_e_jupiter_com_pessoais_tem_texto_proprio():
    """Saturno em quadratura com a Lua usa o texto de aspectos_sociais (nos dois sentidos
    do par), não o montado com as peças."""
    proprio = mt._no("aspectos_sociais", "saturno-lua", "quadratura")["texto"].strip()
    assert mt.texto_aspecto("saturno", "lua", "quadratura") == proprio
    assert mt.texto_aspecto("lua", "saturno", "quadratura") == proprio
    for social in ("jupiter", "saturno"):
        for pessoal in ("sol", "lua", "mercurio", "venus", "marte"):
            for tipo in mo.ASPECTOS:
                assert mt.texto_aspecto(pessoal, social, tipo) == \
                    mt._no("aspectos_sociais", f"{social}-{pessoal}", tipo)["texto"].strip()


def test_urano_netuno_plutao_continuam_montados():
    p = mt.base("pecas")
    montado = (mt._t(p["dinamica"]["trigono"]).format(a=mt._t(p["temas"]["urano"]), b=mt._t(p["temas"]["venus"]))
               + " " + mt._t(p["conselho"]["trigono"])).strip()
    assert mt.texto_aspecto("urano", "venus", "trigono") == montado
    assert mt.texto_aspecto("jupiter", "saturno", "quadratura") != ""  # social × social: montado
    assert "jupiter-saturno" not in mt.base("aspectos_sociais")


def test_mapa_com_saturno_quadratura_lua_mostra_o_texto_proprio():
    for dia in range(0, 4000, 7):  # procura um mapa real com o aspecto
        m = mo.calcular_mapa_ocidental(datetime(1980, 1, 1, 12, 0) + timedelta(days=dia),
                                       -23.55, -46.63)
        asp = [a for a in mt.aspectos_principais(m) if {a["a"], a["b"]} == {"saturno", "lua"}
               and a["tipo"] == "quadratura"]
        if asp:
            break
    assert asp
    secoes = mt.montar_secoes(m)
    proprio = mt._no("aspectos_sociais", "saturno-lua", "quadratura")["texto"].strip()
    assert proprio in str(secoes)

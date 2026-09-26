"""
Testes do interruptor de versão (PADMINI_SISTEMA = vedica | ocidental), Fase 0.5.

  - a védica sai IDÊNTICA à foto tirada antes do interruptor
    (testes/dados/vedica_html, ver scripts/foto_vedica.py);
  - valor desconhecido = erro claro na subida, não site meio montado;
  - link já entregue abre na versão comprada, qualquer que seja a do ar;
  - token de uma versão não abre o completo da outra;
  - o webhook reconhece as ofertas das duas versões, qualquer que seja a ativa.
"""
import importlib.util
import json
import os
import subprocess
import sys

import pytest

from test_app import PESSOA, PESSOA_B, RAIZ, _postar_webhook, app_mod, cliente

import acesso  # noqa: E402
import cakto  # noqa: E402
import entrega  # noqa: E402
import ofertas  # noqa: E402
import sistema  # noqa: E402

_spec = importlib.util.spec_from_file_location("foto_vedica", RAIZ / "scripts" / "foto_vedica.py")
foto_vedica = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(foto_vedica)


@pytest.fixture
def versao(monkeypatch):
    """versao("ocidental") liga a versão no ar e limpa o cache das páginas."""
    def ligar(valor):
        if valor is None:
            monkeypatch.delenv("PADMINI_SISTEMA", raising=False)
        else:
            monkeypatch.setenv("PADMINI_SISTEMA", valor)
        app_mod._paginas_prontas.clear()
    yield ligar
    app_mod._paginas_prontas.clear()


# ============================================================ a védica não mudou
@pytest.mark.parametrize("valor", [None, "vedica", " Vedica "])
def test_vedica_identica_a_foto_de_antes_do_interruptor(versao, valor):
    versao(valor)
    atual = foto_vedica.gerar(cliente)
    for nome, conteudo in atual.items():
        esperado = (foto_vedica.PASTA / nome).read_bytes()
        assert conteudo == esperado, f"{nome} mudou em relação à foto da védica"


# ============================================================ valor inválido
def test_valor_desconhecido_e_erro_claro(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "vedico")
    with pytest.raises(sistema.SistemaInvalido, match="vedica.*ocidental"):
        sistema.ativo()


def test_app_nao_sobe_com_valor_desconhecido():
    env = {**os.environ, "PADMINI_SISTEMA": "ocidentau"}
    r = subprocess.run([sys.executable, "-c", "import app"], cwd=RAIZ, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode != 0
    assert "PADMINI_SISTEMA='ocidentau' não existe" in r.stderr


def test_vazio_ou_ausente_e_vedica(monkeypatch):
    monkeypatch.delenv("PADMINI_SISTEMA", raising=False)
    assert sistema.ativo() == "vedica"
    monkeypatch.setenv("PADMINI_SISTEMA", "  ")
    assert sistema.ativo() == "vedica"


def test_config_diz_a_versao_no_ar(versao):
    versao("ocidental")
    assert cliente.get("/api/config").json()["sistema"] == "ocidental"
    versao(None)
    assert cliente.get("/api/config").json()["sistema"] == "vedica"


# ============================================================ troca das páginas
def test_ocidental_troca_as_paginas(versao):
    versao("ocidental")
    for rota in ("/", "/mapa", "/compatibilidade", "/lista"):
        html = cliente.get(rota).text
        assert "Padmini" in html
        assert "védica" not in html.lower() and "पद्मिनी" not in html, rota


# ============================================================ tokens e links
def _chave(p):
    return acesso.chave_mapa(p["data"], p["hora"], p["lat"], p["lon"])


def test_token_diz_a_versao():
    tv = acesso.emitir_token("mapa", _chave(PESSOA), "vedica")
    to = acesso.emitir_token("mapa", _chave(PESSOA), "ocidental")
    assert acesso.sistema_do_token(tv) == "vedica" and acesso.sistema_do_token(to) == "ocidental"
    assert to.startswith("oc-") and len(tv) == 32
    # o token védico continua o de sempre (links já entregues valem)
    assert tv == acesso.emitir_token("mapa", _chave(PESSOA))


def test_token_de_uma_versao_nao_abre_a_outra():
    chave = _chave(PESSOA)
    to = acesso.emitir_token("mapa", chave, "ocidental")
    tv = acesso.emitir_token("mapa", chave, "vedica")
    assert not acesso.completo_liberado("mapa", chave, to, "vedica")
    assert not acesso.completo_liberado("mapa", chave, tv, "ocidental")
    assert acesso.completo_liberado("mapa", chave, to, "ocidental")
    # nem trocando o prefixo à mão
    assert not acesso.completo_liberado("mapa", chave, "oc-" + tv, "ocidental")
    r = cliente.post("/api/mapa", json={**PESSOA, "nivel": "completo", "token": to})
    assert r.status_code == 402


def test_link_vedico_entregue_abre_a_vedica_com_a_ocidental_no_ar(versao):
    dm = {k: str(v) for k, v in PESSOA.items()}
    link = entrega.link_completo("mapa", dm)  # como os links já entregues
    versao("ocidental")
    caminho = link.replace(entrega.SITE_URL, "")
    html = cliente.get(caminho).text
    assert html == (foto_vedica.PASTA / "mapa.html").read_text(encoding="utf-8")


def test_link_ocidental_abre_a_ocidental_com_a_vedica_no_ar(versao):
    dm = {k: str(v) for k, v in PESSOA.items()}
    link = entrega.link_completo("mapa", dm, "ocidental")
    assert "token=oc-" in link
    versao("vedica")
    html = cliente.get(link.replace(entrega.SITE_URL, "")).text
    assert "védica" not in html.lower()


# ============================================================ webhook
@pytest.fixture
def ofertas_ocidentais(monkeypatch):
    """Simula as ofertas ocidentais já criadas na Cakto."""
    novas = json.loads(json.dumps(ofertas.POR_SISTEMA["ocidental"]))
    novas["mapa"].update(checkout="https://pay.cakto.com.br/ocmapa1_999", codigo="ocmapa1")
    novas["compat"].update(checkout="https://pay.cakto.com.br/occasal_998", codigo="occasal")
    monkeypatch.setitem(ofertas.POR_SISTEMA, "ocidental", novas)
    return novas


def _evento(sck, oferta_id, pid="pedido-sistema-1"):
    return {"event": "purchase_approved", "secret": "segredo-de-teste-webhook",
            "data": {"id": pid, "status": "paid", "sck": sck, "offer": {"id": oferta_id},
                     "customer": {"email": "comprador@teste.com", "name": "Ana"}}}


SCK_MAPA = "m~1990-05-15~14:30~-23.5505~-46.6333~Ana~Sao Paulo"


@pytest.mark.parametrize("no_ar", ["vedica", "ocidental"])
def test_webhook_reconhece_as_duas_versoes(versao, ofertas_ocidentais, no_ar):
    versao(no_ar)
    assert cakto.oferta_paga(_evento(SCK_MAPA, "ocmapa1")) == ("ocidental", "mapa")
    assert cakto.oferta_paga(_evento(SCK_MAPA, ofertas.codigo("mapa"))) == ("vedica", "mapa")
    assert cakto.oferta_paga(_evento(SCK_MAPA, "desconhecida")) == ("", "")


@pytest.mark.parametrize("no_ar", ["vedica", "ocidental"])
def test_compra_ocidental_entrega_link_ocidental(versao, ofertas_ocidentais, no_ar):
    versao(no_ar)
    r = _postar_webhook(_evento(SCK_MAPA, "ocmapa1", f"p-oc-{no_ar}"))
    corpo = r.json()
    assert corpo["produto"] == "mapa" and "token=oc-" in corpo["link"]
    tok = corpo["link"].split("token=")[1]
    assert acesso.completo_liberado("mapa", _chave(PESSOA), tok, "ocidental")


@pytest.mark.parametrize("no_ar", ["vedica", "ocidental"])
def test_compra_vedica_entrega_link_vedico(versao, ofertas_ocidentais, no_ar):
    versao(no_ar)
    corpo = _postar_webhook(_evento(SCK_MAPA, ofertas.codigo("mapa"), f"p-ve-{no_ar}")).json()
    tok = corpo["link"].split("token=")[1]
    assert not tok.startswith("oc-") and acesso.completo_liberado("mapa", _chave(PESSOA), tok)


def test_email_ocidental_sem_vedica():
    html = entrega.email_completo_html("mapa", "https://x/mapa?token=oc-1", "Ana", "", "ocidental")
    assert "védica" not in html and "mapa natal" in html

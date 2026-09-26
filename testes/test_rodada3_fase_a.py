"""
Rodada 3, Fase A: os links reais da Cakto, o cupom do Pedro em % (a Cakto só
aceita % inteiro: 24% → R$96,52, não R$97) e o preço sempre em formato brasileiro.
"""
import json
import re
import shutil
import subprocess

import pytest

from test_app import RAIZ, _postar_webhook, app_mod, cliente

import cakto  # noqa: E402
import ofertas  # noqa: E402
import sistema  # noqa: E402

LINKS = {"mapa": "39vm3n6", "compat": "hrf7qtu", "numerologia": "3by9kh8", "tarot": "hzxu8hh",
         "bump_mapas_casal": "32vnvwx"}


# ------------------------------------------------------------------ moeda
@pytest.mark.parametrize("valor,texto", [(127, "127"), (96.52, "96,52"), (40, "40"), (19.0, "19"),
                                         (0.5, "0,50"), (1297, "1.297"), (1297.9, "1.297,90"), (None, "")])
def test_moeda_em_formato_brasileiro(valor, texto):
    assert ofertas.moeda(valor) == texto


def test_preco_com_cupom_sai_do_percentual():
    o = ofertas.oferta("compat", "ocidental")
    assert o["cupom_percentual"] == 24 and o["cupom_codigos"] == ["pedro"]
    assert o["preco_cupom"] == 96.52 == ofertas.com_desconto(127, 24)
    assert ofertas.com_desconto(37, 15) == 31.45 and ofertas.com_desconto(19, 33) == 12.73


def test_nenhuma_pagina_ocidental_escreve_preco_com_ponto(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    app_mod._paginas_prontas.clear()
    try:
        for rota in sistema.PAGINAS["ocidental"]:
            html = cliente.get(rota).text
            assert not re.search(r"R\$\s?\d+\.\d{2}(?!\d)", html), rota
            assert not re.search(r'"\d+\.\d{2}"', html), rota  # nem nas constantes do JS
    finally:
        app_mod._paginas_prontas.clear()


# ------------------------------------------------------------------ links reais
def test_links_de_checkout_da_ocidental():
    for chave, codigo in LINKS.items():
        o = ofertas.oferta(chave, "ocidental")
        assert o["checkout"].startswith(f"https://pay.cakto.com.br/{codigo}_") and o["codigo"] == codigo


@pytest.mark.parametrize("produto", ["mapa", "compat", "numerologia", "tarot"])
def test_webhook_reconhece_cada_oferta_real(produto):
    ev = {"data": {"offer": {"id": LINKS[produto]},
                   "checkoutUrl": ofertas.checkout(produto, "ocidental") + "?sck=x"}}
    assert cakto.oferta_paga(ev) == ("ocidental", produto)


SCK = "c~1990-05-15~~-23.5505~-46.6333~Ana~SP~1992-03-10~08:00~-22.9068~-43.1729~Bruno~RJ"


def _bump():
    """O order bump chega como pedido próprio: offer.id do bump, checkoutUrl da sinastria."""
    return {"event": "purchase_approved", "secret": "segredo-de-teste-webhook",
            "data": {"id": "bump-r3", "status": "paid", "offer_type": "orderbump", "sck": SCK,
                     "offer": {"id": "32vnvwx"},
                     "checkoutUrl": "https://pay.cakto.com.br/hrf7qtu_1141270?sck=" + SCK,
                     "customer": {"email": "c@teste.com", "name": "Ana"}}}


def test_bump_real_e_reconhecido_como_combo_da_ocidental():
    assert cakto.versao_do_bump_mapas(_bump()) == "ocidental"
    r = _postar_webhook(_bump()).json()
    assert r["produto"] == "ocidental:mapas_casal" and len(r["links"]) == 2
    assert all("/mapa?" in link and "token=oc-" in link for link in r["links"])


def test_sinastria_paga_sem_o_bump_nao_vira_combo():
    ev = _bump()
    ev["data"].update(offer_type="main", offer={"id": "hrf7qtu"})
    assert cakto.versao_do_bump_mapas(ev) == ""
    assert cakto.oferta_paga(ev) == ("ocidental", "compat")


# ------------------------------------------------------------------ cupom
def test_pagina_anuncia_o_cupom_em_percentual(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    app_mod._paginas_prontas.clear()
    html = cliente.get("/compatibilidade").text
    app_mod._paginas_prontas.clear()
    assert 'const PRECO_CUPOM = "96,52";' in html and 'const CUPOM_PERCENTUAL = "24";' in html
    assert "% de desconto" in html and "R$30" not in html
    assert 'const PRECO_BUMP_MAPAS = "R$40";' in html


@pytest.mark.skipif(shutil.which("node") is None, reason="node não instalado")
@pytest.mark.parametrize("digitado", ["PEDRO", "pedro", "Pedro"])
def test_cupom_sem_diferenca_de_maiusculas(digitado):
    """?cupom=PEDRO e ?cupom=pedro dão o mesmo checkout: coupon=pedro (a Cakto grava
    em minúsculas; conferimos no checkout real que as duas formas dão R$96,52)."""
    js = (
        f"global.location={{search:'?cupom={digitado}',origin:'https://padmini.teste'}};"
        "const st={};global.sessionStorage={getItem(k){return st[k]??null},setItem(k,v){st[k]=v}};global.window=global;"
        f"eval(require('fs').readFileSync({json.dumps(str(RAIZ / 'static' / 'afiliado.js'))},'utf8'));"
        "const u=new URL(window.linkCheckout('https://pay.cakto.com.br/hrf7qtu_1141270',null,{aplicarCupom:true}));"
        "process.stdout.write(u.searchParams.get('coupon'));"
    )
    assert subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout == "pedro"


def test_link_do_pedro_documentado():
    doc = (RAIZ / "docs" / "ocidental.md").read_text(encoding="utf-8")
    assert "https://padmini.com.br/compatibilidade?cupom=PEDRO&utm_source=pedro&utm_medium=tiktok" in doc

"""
Testes da lógica do smoke de produção (scripts/smoke_producao.py) que não
precisam de rede: a checagem "preço do ofertas.yaml = preço da Cakto".

O bug que ela pega (26/set/2026): o site anunciava o casal por R$97, com R$127
riscado, e a oferta na Cakto cobrava R$127.
"""
import importlib.util

from test_app import RAIZ

_spec = importlib.util.spec_from_file_location("smoke_producao", RAIZ / "scripts" / "smoke_producao.py")
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)

# Trecho no formato do HTML real do checkout (conferido em 26/set/2026).
CHECKOUT_127 = ('<p class="tabular-nums">R$&nbsp;127,00<!-- --> à vista</p>'
                '<span>6x de R$&nbsp;9,99</span><span>R$&nbsp;0,99</span>')


def test_extrai_valores_ignorando_um_digito():
    assert smoke.valores_do_checkout(CHECKOUT_127) == {127}
    assert smoke.valores_do_checkout("R$ 1.297,00 e R$ 47,00") == {1297, 47}


def test_reprova_quando_o_site_anuncia_outro_preco():
    ofertas = {"compat": {"preco": 97, "checkout": "https://pay.cakto.com.br/x_1"}}
    falhas = smoke.conferir_precos_na_cakto(ofertas, baixar=lambda url: CHECKOUT_127)
    assert len(falhas) == 1 and "R$97" in falhas[0] and "R$127" in falhas[0]


def test_aprova_quando_bate_e_ignora_oferta_sem_checkout():
    ofertas = {"compat": {"preco": 127, "checkout": "https://pay.cakto.com.br/x_1"},
               "bump": {"preco": 167, "checkout": ""}}
    assert smoke.conferir_precos_na_cakto(ofertas, baixar=lambda url: CHECKOUT_127) == []


def test_cakto_fora_do_ar_avisa_sem_reprovar():
    def fora(url):
        raise OSError("timeout")
    smoke.AVISOS.clear()
    ofertas = {"compat": {"preco": 127, "checkout": "https://pay.cakto.com.br/x_1"}}
    assert smoke.conferir_precos_na_cakto(ofertas, baixar=fora) == []
    assert smoke.AVISOS and "não respondeu" in smoke.AVISOS[0]

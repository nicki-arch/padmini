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


# ---------------------------------------------------------------------------
# O smoke inteiro contra o app local, nas duas versões (sem rede: a conferência
# com a Cakto e os cabeçalhos HTTPS ficam de fora).
# ---------------------------------------------------------------------------
import pytest  # noqa: E402

from test_app import app_mod, cliente  # noqa: E402

SEM_REDE = ("preço do ofertas.yaml bate", "cabeçalhos de segurança")
# Com a ocidental no ar e sem links de checkout (hoje), os botões ficam "em breve":
# o smoke acusa — é exatamente o bloqueio que precisa sumir antes da virada.
SO_COM_LINKS = ("botões de compra",)


def _req_local(caminho, corpo=None, timeout=90):
    r = cliente.post(caminho, json=corpo) if corpo is not None else cliente.get(caminho)
    return r.status_code, r.content


@pytest.mark.parametrize("versao", ["vedica", "ocidental"])
def test_smoke_passa_no_app_local(versao, monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", versao)
    monkeypatch.setattr(smoke, "req", _req_local)
    app_mod._paginas_prontas.clear()
    falhas = []
    try:
        for nome, f in smoke.CHECAGENS:
            if any(t in nome for t in SEM_REDE):
                continue
            if versao == "ocidental" and any(t in nome for t in SO_COM_LINKS):
                assert not f(), f"{nome}: deveria acusar a falta de link de checkout"
                continue
            if not f():
                falhas.append(nome)
    finally:
        app_mod._paginas_prontas.clear()
    assert falhas == []


def test_smoke_cobre_os_4_produtos():
    nomes = " ".join(n for n, _ in smoke.CHECAGENS)
    for trecho in ("amostras dos 4 produtos", "completos e PDFs dos 4 produtos", "numerologia e tarot"):
        assert trecho in nomes

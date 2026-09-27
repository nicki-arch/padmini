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
            if not f():
                falhas.append(nome)
    finally:
        app_mod._paginas_prontas.clear()
    assert falhas == []


def test_smoke_cobre_os_4_produtos():
    nomes = " ".join(n for n, _ in smoke.CHECAGENS)
    # rodada 6: as amostras pedem e-mail (o smoke confere o 422); o tarot completo
    # sai do 402 do smoke (sem sorteio não há tiragem) e fica em test_tarot
    for trecho in ("amostras dos 4 produtos pedem o e-mail", "completos e PDFs trancados", "numerologia e tarot"):
        assert trecho in nomes


# ---------------------------------------------------------------------------
# Rodada 3: cupom em % (a Cakto só aceita % inteiro) e o combo como order bump.
# Trechos no formato do checkout real da sinastria (conferido em 26/set/2026).
# ---------------------------------------------------------------------------
SINASTRIA = ("<p>R$&nbsp;127,00 à vista</p><h2>SIM, QUERO O MAPA DE CADA UM</h2><p>R$&nbsp;40,00</p>"
             "<p>Taxa de serviço R$&nbsp;0,99</p>")
SINASTRIA_CUPOM = ("<p>R$&nbsp;127,00</p><p>R$&nbsp;96,52à vista</p><p>R$&nbsp;40,00</p>"
                   "<p>pedro</p><p>Desconto (24%)-R$&nbsp;30,48</p>")
OFERTAS_R3 = {
    "compat": {"preco": 127, "cupom_percentual": 24, "cupom_codigos": ["pedro"],
               "checkout": "https://pay.cakto.com.br/hrf7qtu_1141270"},
    "bump_mapas_casal": {"preco": 167, "bump_de": "compat", "checkout": "https://pay.cakto.com.br/32vnvwx_1144252"},
}


def _cakto(com_cupom, sem_cupom=SINASTRIA):
    def baixar(url):
        assert "32vnvwx" not in url  # o bump não tem checkout próprio: nunca é aberto
        return com_cupom if "coupon=pedro" in url else sem_cupom
    return baixar


def test_cupom_e_bump_conferem_com_a_cakto():
    smoke.AVISOS.clear()
    assert smoke.conferir_precos_na_cakto(OFERTAS_R3, baixar=_cakto(SINASTRIA_CUPOM)) == []
    assert smoke.AVISOS == []


def test_cupom_com_outro_percentual_reprova():
    outro = SINASTRIA_CUPOM.replace("96,52", "101,60").replace("24%", "20%")
    falhas = smoke.conferir_precos_na_cakto(OFERTAS_R3, baixar=_cakto(outro))
    assert len(falhas) == 1 and "R$96,52" in falhas[0] and "20%" in falhas[0]


def test_cupom_que_so_aparece_no_navegador_e_aviso():
    smoke.AVISOS.clear()
    assert smoke.conferir_precos_na_cakto(OFERTAS_R3, baixar=_cakto(SINASTRIA)) == []
    aviso = next(a for a in smoke.AVISOS if "cupom 'pedro'" in a)
    assert "não dá para conferir sem navegador" in aviso and "confira à mão" in aviso.lower()
    assert "?coupon=pedro" in aviso and "R$96,52" in aviso


def test_bump_com_outro_valor_reprova():
    falhas = smoke.conferir_precos_na_cakto(
        OFERTAS_R3, baixar=_cakto(SINASTRIA_CUPOM.replace("40,00", "50,00"), SINASTRIA.replace("40,00", "50,00")))
    assert any("bump_mapas_casal" in f and "R$40" in f for f in falhas)

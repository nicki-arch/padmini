"""
Rodada 20.1 (21/out/2026): os e-mails do site voltam a sair e o Instagram certo volta ao site.

Parte A: nenhum e-mail saía desde pelo menos 13/out. O `enviar_email` usava o User-Agent
padrão do Python ("Python-urllib/3.x"), barrado pela proteção na frente da API do Resend
(403, "error code: 1010") antes de chegar à conta, e o erro era engolido sem log. Agora o
pedido leva o nosso User-Agent e a falha vai para o log com o status (sem a chave, sem o
destinatário completo, sem o conteúdo do e-mail).

Parte B: o Instagram é `astrologiavalderez_` (com o sublinhado no fim), ativo de novo.
"""
import io
import json
import logging
import re
import urllib.error

import pytest

from test_app import cliente  # primeiro: define os segredos de teste
import app as app_mod
import entrega
import enderecos

HTML = {"accept": "text/html"}
CHAVE = "re_chave_secreta_de_teste_123"
DESTINO = "maria.da.silva@exemplo.com.br"
INSTA = "https://www.instagram.com/astrologiavalderez_/"


# ====================================================================== Parte A: o envio
class Resposta:
    def __init__(self, status=200, corpo=b'{"id":"abc"}'):
        self.status, self._corpo = status, corpo

    def read(self):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def resend(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", CHAVE)
    chamadas = []

    def urlopen(req, timeout=None):
        chamadas.append(req)
        resposta = chamadas_resposta[0]
        if isinstance(resposta, Exception):
            raise resposta
        return resposta
    chamadas_resposta = [Resposta()]
    monkeypatch.setattr(entrega.urllib.request, "urlopen", urlopen)
    return {"chamadas": chamadas, "resposta": chamadas_resposta}


def _enviar():
    return entrega.enviar_email(DESTINO, "Assunto", "<p>Corpo com 1990-05-15</p>")


def test_user_agent_proprio_e_nao_o_do_python(resend):
    assert _enviar() is True
    req = resend["chamadas"][0]
    ua = req.get_header("User-agent")
    assert ua == enderecos.USER_AGENT and ua.startswith("ValderezAstrologia/")
    assert enderecos.SITE_URL in ua and "Python-urllib" not in ua
    assert req.full_url == "https://api.resend.com/emails" and req.get_method() == "POST"
    assert req.get_header("Authorization") == f"Bearer {CHAVE}"
    corpo = json.loads(req.data)
    assert corpo["to"] == [DESTINO] and corpo["subject"] == "Assunto"


def test_pedido_resend_leva_o_user_agent():
    req = entrega.pedido_resend("re_x", {"to": ["a@b.c"]})
    assert req.get_header("User-agent") == enderecos.USER_AGENT


def _http_erro(status, corpo):
    return urllib.error.HTTPError(entrega.URL_RESEND, status, "erro", {}, io.BytesIO(corpo))


def test_403_vai_para_o_log_com_o_status(resend, caplog):
    resend["resposta"][0] = _http_erro(403, b"error code: 1010")
    with caplog.at_level(logging.WARNING, logger="padmini.entrega"):
        assert _enviar() is False
    linha = "\n".join(r.getMessage() for r in caplog.records)
    assert "403" in linha and "error code: 1010" in linha and "@exemplo.com.br" in linha
    for segredo in (CHAVE, DESTINO, "maria.da.silva", "1990-05-15", "Corpo"):
        assert segredo not in linha


def test_resposta_com_e_mail_dentro_nao_vaza_no_log(resend, caplog):
    corpo = json.dumps({"statusCode": 422, "message": f"Invalid `to` field: {DESTINO} " + "x" * 400}).encode()
    resend["resposta"][0] = _http_erro(422, corpo)
    with caplog.at_level(logging.WARNING, logger="padmini.entrega"):
        assert _enviar() is False
    linha = "\n".join(r.getMessage() for r in caplog.records)
    assert "422" in linha and "[e-mail]" in linha and DESTINO not in linha and "maria" not in linha
    trecho = re.search(r"\((.*)\) para", linha).group(1)
    assert len(trecho) <= 200


def test_falha_de_rede_vai_para_o_log(resend, caplog):
    resend["resposta"][0] = urllib.error.URLError("timed out")
    with caplog.at_level(logging.WARNING, logger="padmini.entrega"):
        assert _enviar() is False
    assert "URLError" in caplog.text and DESTINO not in caplog.text


def test_sem_chave_nao_chama_nada(resend, monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY")
    assert _enviar() is False and resend["chamadas"] == []


def test_nenhuma_chamada_para_fora_sem_user_agent():
    """O único outro urlopen do código do site (baixar_dados.py, GeoNames) também manda o
    nosso. (O smoke, em scripts/, só chama o próprio site e manda o dele para a Cakto.)"""
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[1]
    for arquivo in raiz.glob("*.py"):
        texto = arquivo.read_text(encoding="utf-8")
        for m in re.finditer(r"urlopen\(([^,)]+)", texto):
            arg = m.group(1).strip()
            assert not arg.startswith(("\"", "'", "BASE +", "f\"")), f"{arquivo.name}: urlopen({arg}) sem Request"


# ====================================================================== Parte B: o Instagram
@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    app_mod._paginas_prontas.clear()
    yield
    app_mod._paginas_prontas.clear()


def test_instagram_no_marca_yaml():
    insta = next(r for r in enderecos.REDES if r["nome"] == "Instagram")
    assert insta["url"] == INSTA and insta["arroba"] == "@astrologiavalderez_" and insta.get("ativa") is True


@pytest.mark.parametrize("rota", ["/", "/mapa", "/leituras", "/termos"])
def test_instagram_no_rodape(ocidental, rota):
    html = cliente.get(rota, headers=HTML).text
    rod = html[html.index('<footer class="rod">'):]
    assert f'<a href="{INSTA}" rel="noopener" aria-label="Instagram da Dona Valderez">' in rod, rota


def test_instagram_no_quem_revisa(ocidental):
    html = cliente.get("/", headers=HTML).text
    quem = html[html.index('id="quem-revisa"'):]
    quem = quem[:quem.index("</section>")]
    assert f'<a href="{INSTA}" rel="noopener">' in quem and "<span>Instagram</span>" in quem


def test_instagram_na_links_e_o_arroba_certo(ocidental):
    html = cliente.get("/links", headers=HTML).text
    assert f'href="{INSTA}"' in html
    # a linha do @ vale para "as redes": o do TikTok e do YouTube, não o do Instagram
    assert '<p class="links-arroba">@astrologiavalderez</p>' in html


def test_instagram_no_same_as(ocidental):
    html = cliente.get("/", headers=HTML).text
    bloco = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
    org = next(g for g in json.loads(bloco)["@graph"] if g["@type"] == "Organization")
    assert INSTA in org["sameAs"]
    assert "https://www.instagram.com/astrologiavalderez/" not in org["sameAs"]


def test_arroba_principal():
    redes = [{"arroba": "@a_"}, {"arroba": "@a"}, {"arroba": "@a"}]
    assert enderecos.arroba_principal(redes) == "@a"
    assert enderecos.arroba_principal([{"arroba": "@x"}]) == "@x"
    assert enderecos.arroba_principal([]) == ""

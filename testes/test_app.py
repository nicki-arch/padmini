"""
Testes do app inteiro (rotas, paywall, webhook da Cakto, busca de cidades, PDF).

Cada teste aqui existe por um motivo concreto — em geral um bug que já
aconteceu ou que quase aconteceu:
  - busca de cidades vazia / PDF "stub"  → regressão da parte 16
  - webhook aceitando evento forjado     → vulnerabilidade da parte 17
  - `sck` montado no front ≠ lido no back → dados de nascimento perdidos
  - link do e-mail não abrindo o completo → comprador paga e não recebe

Rodar:  python -m pytest -q testes
"""
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# Ambiente de teste — precisa vir ANTES de importar o app (os módulos leem na importação).
SEGREDO_WEBHOOK = "segredo-de-teste-webhook"
os.environ["PADMINI_SECRET"] = "segredo-de-teste-tokens"
os.environ["PADMINI_CAKTO_WEBHOOK_SECRET"] = SEGREDO_WEBHOOK
os.environ["PADMINI_SITE_URL"] = "https://padmini.teste"
os.environ.pop("PADMINI_MODO_ABERTO", None)
os.environ.pop("RESEND_API_KEY", None)
os.environ.pop("ANTHROPIC_API_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402
import app as app_mod  # noqa: E402

cliente = TestClient(app_mod.app)

PESSOA = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30",
          "lat": -23.5505, "lon": -46.6333, "cidade": "São Paulo, SP"}
PESSOA_B = {"nome": "Bruno", "data": "1992-03-10", "hora": "08:00",
            "lat": -22.9068, "lon": -43.1729, "cidade": "Rio de Janeiro, RJ"}


# ---------------------------------------------------------------- rotas
@pytest.mark.parametrize("rota", ["/", "/mapa", "/compatibilidade", "/privacidade", "/termos"])
def test_paginas_respondem(rota):
    r = cliente.get(rota)
    assert r.status_code == 200
    assert "<html" in r.text.lower()


def test_checkout_ligado_nos_dois_produtos():
    """Os botões de compra precisam apontar para a Cakto (constante vazia = botão morto)."""
    mapa = cliente.get("/mapa").text
    compat = cliente.get("/compatibilidade").text
    assert re.search(r'LINK_CHECKOUT_INDIVIDUAL = "https://pay\.cakto\.com\.br/[^"]+"', mapa)
    assert re.search(r'LINK_CHECKOUT = "https://pay\.cakto\.com\.br/[^"]+"', compat)


# ---------------------------------------------------------------- cidades (parte 16)
def test_busca_de_cidades_retorna_resultados():
    r = cliente.get("/api/cidades", params={"q": "Porto Alegre"})
    assert r.status_code == 200
    rotulos = [c["rotulo"] for c in r.json()]
    assert any("Porto Alegre" in x for x in rotulos), rotulos


def test_indice_de_cidades_nao_e_stub():
    assert (RAIZ / "data" / "cidades_index.tsv").stat().st_size > 1_000_000


# ---------------------------------------------------------------- paywall
def test_amostra_mapa_gratis_e_sem_detalhe():
    r = cliente.post("/api/mapa", json={**PESSOA, "nivel": "amostra"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["nivel"] == "amostra"
    assert "grahas" not in corpo and "dashas" not in corpo  # o detalhe é pago


def test_completo_mapa_bloqueado_sem_token():
    assert cliente.post("/api/mapa", json={**PESSOA, "nivel": "completo"}).status_code == 402
    assert cliente.post("/api/mapa", json={**PESSOA, "nivel": "completo",
                                           "token": "falso"}).status_code == 402


def test_amostra_compat_gratis_e_sem_kootas():
    r = cliente.post("/api/compatibilidade", json={"a": PESSOA, "b": PESSOA_B, "nivel": "amostra"})
    assert r.status_code == 200
    assert "kootas" not in r.json()


def test_completo_compat_bloqueado_sem_token():
    r = cliente.post("/api/compatibilidade", json={"a": PESSOA, "b": PESSOA_B, "nivel": "completo"})
    assert r.status_code == 402


def test_pdf_bloqueado_sem_token():
    assert cliente.post("/api/pdf", json={**PESSOA, "nivel": "completo"}).status_code == 402


# ---------------------------------------------------------------- webhook (parte 17)
def _assinar(corpo: bytes, ts: str, segredo: str = SEGREDO_WEBHOOK) -> str:
    return "v1=" + hmac.new(segredo.encode(), f"{ts}.".encode() + corpo, hashlib.sha256).hexdigest()


def _evento(sck: str, email: str = "compradora@teste.com") -> dict:
    return {"event": "purchase_approved",
            "data": {"status": "paid", "customer": {"name": "Ana", "email": email},
                     "sck": sck, "utm_source": "afiliado", "utm_campaign": "PEDRO"}}


def _postar_webhook(evento: dict, assinar=True, segredo=SEGREDO_WEBHOOK):
    corpo = json.dumps(evento).encode()
    ts = str(int(time.time()))
    headers = {"Content-Type": "application/json", "X-Cakto-Timestamp": ts}
    if assinar:
        headers["X-Cakto-Signature"] = _assinar(corpo, ts, segredo)
    return cliente.post("/webhook/cakto", content=corpo, headers=headers)


SCK_MAPA = "m~1990-05-15~14:30~-23.5505~-46.6333~Ana~São Paulo, SP"
SCK_CASAL = ("c~1990-05-15~14:30~-23.5505~-46.6333~Ana~São Paulo"
             "~1992-03-10~08:00~-22.9068~-43.1729~Bruno~Rio de Janeiro")


def test_webhook_rejeita_evento_sem_assinatura():
    assert _postar_webhook(_evento(SCK_MAPA), assinar=False).status_code == 401


def test_webhook_rejeita_assinatura_errada():
    assert _postar_webhook(_evento(SCK_MAPA), segredo="outro-segredo").status_code == 401


def test_webhook_rejeita_segredo_cru_no_header():
    corpo = json.dumps(_evento(SCK_MAPA)).encode()
    r = cliente.post("/webhook/cakto", content=corpo,
                     headers={"Content-Type": "application/json",
                              "X-Cakto-Signature": SEGREDO_WEBHOOK})
    assert r.status_code == 401


def _params(link: str) -> dict:
    return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(link).query))


def test_compra_do_mapa_ponta_a_ponta():
    """Webhook assinado → link do e-mail → o link abre o completo e o PDF."""
    r = _postar_webhook(_evento(SCK_MAPA))
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["produto"] == "mapa"
    q = _params(corpo["link"])
    # a página lê o link e manda lat/lon como número — o token tem que bater assim
    pedido = {"nome": q["nome"], "data": q["data"], "hora": q["hora"],
              "lat": float(q["lat"]), "lon": float(q["lon"]), "cidade": q["cidade"],
              "nivel": "completo", "token": q["token"]}
    completo = cliente.post("/api/mapa", json=pedido)
    assert completo.status_code == 200, completo.text
    assert completo.json()["nivel"] == "completo"
    pdf = cliente.post("/api/pdf", json=pedido)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF" and len(pdf.content) > 20_000  # não é stub


def test_compra_do_casal_ponta_a_ponta():
    r = _postar_webhook(_evento(SCK_CASAL))
    assert r.status_code == 200, r.text
    assert r.json()["produto"] == "compat"
    q = _params(r.json()["link"])

    def pessoa(p):
        return {k: (float(q[f"{p}_{k}"]) if k in ("lat", "lon") else q[f"{p}_{k}"])
                for k in ("nome", "data", "hora", "lat", "lon", "cidade")}

    completo = cliente.post("/api/compatibilidade",
                            json={"a": pessoa("a"), "b": pessoa("b"),
                                  "nivel": "completo", "token": q["token"]})
    assert completo.status_code == 200, completo.text
    assert "kootas" in completo.json()


def test_webhook_ignora_pagamento_nao_aprovado():
    ev = _evento(SCK_MAPA)
    ev["event"] = "purchase_refused"
    ev["data"]["status"] = "refused"
    r = _postar_webhook(ev)
    assert r.status_code == 200 and "ignorado" in r.json()


def test_webhook_sem_dados_de_nascimento_sinaliza():
    r = _postar_webhook(_evento(""))
    # sem sck não há produto nem dados: não pode emitir token
    assert r.status_code in (200, 422)
    assert not r.json().get("link")


# ---------------------------------------------------------------- contrato front ↔ back
@pytest.mark.skipif(shutil.which("node") is None, reason="node não instalado")
@pytest.mark.parametrize("dados,esperado", [
    ({"produto": "mapa", **PESSOA}, "mapa"),
    ({"produto": "compat", "a": PESSOA, "b": PESSOA_B}, "compat"),
])
def test_sck_do_front_e_lido_pelo_back(dados, esperado):
    """O `sck` que o afiliado.js monta precisa ser o mesmo que o cakto.py desmonta."""
    js = (
        "global.location={search:'',origin:'https://padmini.teste'};"
        "global.sessionStorage={getItem(){return null},setItem(){}};global.window=global;"
        f"eval(require('fs').readFileSync({json.dumps(str(RAIZ / 'static' / 'afiliado.js'))},'utf8'));"
        f"const u=new URL(window.linkCheckout('https://pay.cakto.com.br/x',{json.dumps(dados)}));"
        "process.stdout.write(u.searchParams.get('sck'));"
    )
    sck = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    import cakto
    pd = cakto.coletar_pd({"data": {"sck": sck}})
    produto = cakto.produto_do_evento({}, pd)
    assert produto == esperado
    assert cakto.dados_nascimento(pd, produto) is not None
    assert len(sck) <= 200  # URL curta: o sck não pode crescer sem controle


def test_saude_sem_banco():
    r = cliente.get("/api/saude")
    assert r.status_code == 200 and r.json() == {"ok": True, "banco": None}

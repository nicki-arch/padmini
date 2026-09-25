"""
Testes da revisão de segurança de 25/set/2026 (docs/seguranca.md).

Cada teste aqui falharia com o código anterior à correção (regra 6):
  - pagar o mapa com um `sck` de casal entregava a compatibilidade;
  - a amostra grátis do casal chamava a IA (custo) com texto_ia=true;
  - webhook assinado velho era aceito (replay);
  - qualquer "approved" escondido no payload virava pagamento aprovado;
  - a senha do live podia ser chutada sem limite;
  - nenhum cabeçalho de segurança;
  - o nome do comprador entrava cru no HTML do e-mail;
  - o PostHog recebia o token do relatório pago na URL.
"""

import hashlib
import hmac
import json
import re
import shutil
import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from test_app import (  # noqa: E402  (test_app prepara o ambiente antes de importar o app)
    PESSOA, PESSOA_B, RAIZ, SCK_CASAL, SCK_MAPA, SEGREDO_WEBHOOK, _assinar, _evento,
    _postar_webhook, app_mod, cliente,
)

import cakto  # noqa: E402
import entrega  # noqa: E402
import limites  # noqa: E402
import ofertas  # noqa: E402
import seguranca  # noqa: E402


def _cliente_ip(ip: str) -> TestClient:
    """Cliente que se apresenta com outro IP (como a Cloudflare repassa)."""
    return TestClient(app_mod.app, headers={"CF-Connecting-IP": ip})


# ============================================================ 1. troca de produto no checkout
def test_pagar_o_mapa_com_sck_de_casal_nao_entrega_a_compatibilidade():
    """O bug: o `sck` decidia o produto. Pagando o mapa (R$47) com sck=c~...
    o webhook mandava o link da compatibilidade (R$97)."""
    ev = _evento(SCK_CASAL, oferta={"offer": {"id": ofertas.codigo("mapa")}})
    r = _postar_webhook(ev)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert not corpo.get("link") and not corpo.get("links")
    assert corpo["produto"] == "mapa" and "pendente" in corpo


def test_pagar_o_casal_com_sck_de_mapa_fica_pendente():
    ev = _evento(SCK_MAPA, oferta={"offer": {"id": ofertas.codigo("compat")}})
    corpo = _postar_webhook(ev).json()
    assert not corpo.get("link") and "pendente" in corpo


def test_produto_vem_da_oferta_paga_mesmo_pela_checkout_url():
    ev = _evento(SCK_CASAL, oferta={
        "checkoutUrl": f"https://pay.cakto.com.br/{ofertas.codigo('mapa')}_1125341?callback=x"})
    assert cakto.produto_do_evento(ev, cakto.coletar_pd(ev)) == ""  # pagou mapa, pediu casal


def test_oferta_desconhecida_nao_entrega_no_escuro():
    """Sem saber o que foi pago, não emite token só com base no sck."""
    ev = _evento(SCK_MAPA, oferta={"offer": {"id": "oferta-que-nao-existe"}})
    corpo = _postar_webhook(ev).json()
    assert not corpo.get("link") and "pendente" in corpo


def test_bump_sem_oferta_configurada_nao_vira_dois_mapas(monkeypatch):
    """Antes, com o código do bump vazio, QUALQUER order bump com sck de casal
    entregava os dois mapas."""
    monkeypatch.setattr(cakto, "OFERTA_BUMP_MAPAS", "")
    ev = _evento(SCK_CASAL, oferta={"offer": {"id": "um-bump-barato"}})
    ev["data"] |= {"id": "bump-x", "offer_type": "orderbump"}
    corpo = _postar_webhook(ev).json()
    assert "ignorado" in corpo and not corpo.get("links")


# ============================================================ 2. IA na amostra grátis
@pytest.fixture
def ia_falsa(monkeypatch):
    chamadas = []
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste")
    monkeypatch.setattr(app_mod, "gerar_com_claude", lambda p: chamadas.append(p) or "Texto.")
    return chamadas


def test_amostra_do_casal_nao_chama_a_ia(ia_falsa):
    r = cliente.post("/api/compatibilidade",
                     json={"a": PESSOA, "b": PESSOA_B, "nivel": "amostra", "texto_ia": True})
    assert r.status_code == 402
    assert ia_falsa == []


def test_completo_do_casal_usa_o_texto_guardado(ia_falsa, monkeypatch):
    import acesso
    import db
    monkeypatch.setattr(db, "texto_ia", lambda chave: "Texto guardado.")
    chave = acesso.chave_compat(
        (PESSOA["data"], PESSOA["hora"], PESSOA["lat"], PESSOA["lon"]),
        (PESSOA_B["data"], PESSOA_B["hora"], PESSOA_B["lat"], PESSOA_B["lon"]))
    token = acesso.emitir_token("compat", chave)
    r = cliente.post("/api/compatibilidade", json={"a": PESSOA, "b": PESSOA_B, "nivel": "completo",
                                                   "texto_ia": True, "token": token})
    assert r.status_code == 200, r.text
    assert r.json()["texto_ia"] == "Texto guardado." and ia_falsa == []


def test_completo_do_casal_sem_token_nao_chama_a_ia(ia_falsa):
    r = cliente.post("/api/compatibilidade", json={"a": PESSOA, "b": PESSOA_B,
                                                   "nivel": "completo", "texto_ia": True})
    assert r.status_code == 402 and ia_falsa == []


# ============================================================ 3. webhook: replay e aprovação
def _postar_com_ts(evento: dict, ts: int, corpo_secret: str | None = None, assinar=True):
    if corpo_secret is not None:
        evento = {**evento, "secret": corpo_secret}
    corpo = json.dumps(evento).encode()
    headers = {"Content-Type": "application/json", "X-Cakto-Timestamp": str(ts)}
    if assinar:
        headers["X-Cakto-Signature"] = _assinar(corpo, str(ts))
    return cliente.post("/webhook/cakto", content=corpo, headers=headers)


def test_webhook_assinado_ha_mais_de_5_minutos_e_recusado():
    assert _postar_com_ts(_evento(SCK_MAPA), int(time.time()) - 6 * 60).status_code == 401


def test_webhook_com_timestamp_no_futuro_e_recusado():
    assert _postar_com_ts(_evento(SCK_MAPA), int(time.time()) + 6 * 60).status_code == 401


def test_webhook_assinado_recente_passa():
    assert _postar_com_ts(_evento(SCK_MAPA), int(time.time()) - 60).status_code == 200


def test_webhook_pelo_secret_do_corpo_ainda_passa_e_pode_ser_desligado(monkeypatch):
    ev = _evento(SCK_MAPA)
    assert _postar_com_ts(ev, int(time.time()), corpo_secret=SEGREDO_WEBHOOK,
                          assinar=False).status_code == 200
    monkeypatch.setenv("PADMINI_CAKTO_EXIGIR_ASSINATURA", "1")
    assert _postar_com_ts(ev, int(time.time()), corpo_secret=SEGREDO_WEBHOOK,
                          assinar=False).status_code == 401
    # com a assinatura válida continua passando
    assert _postar_com_ts(ev, int(time.time())).status_code == 200


def test_webhook_com_texto_estranho_responde_401_e_nao_500():
    corpo = json.dumps({**_evento(SCK_MAPA), "secret": "segrédo-çom-acento"}).encode()
    r = cliente.post("/webhook/cakto", content=corpo,
                     headers={"Content-Type": "application/json",
                              "X-Cakto-Timestamp": str(int(time.time())),
                              "X-Cakto-Signature": "v1=não-é-hex".encode("latin-1")})
    assert r.status_code == 401


def test_assinatura_aceita_lista_de_versoes():
    corpo, ts = b'{"a":1}', str(int(time.time()))
    v1 = hmac.new(SEGREDO_WEBHOOK.encode(), f"{ts}.".encode() + corpo, hashlib.sha256).hexdigest()
    assert cakto.verificar(f"v1={v1},v2=outra", ts, corpo, SEGREDO_WEBHOOK)
    assert not cakto.verificar(f"v2={v1}", ts, corpo, SEGREDO_WEBHOOK)


@pytest.mark.parametrize("evento,esperado", [
    ({"event": "purchase_approved", "data": {"status": "paid"}}, True),
    ({"data": {"status": "paid"}}, True),
    # reembolso com o bloco da adquirente dizendo "approved" lá dentro
    ({"event": "refund", "data": {"status": "refunded", "pix": {"status": "approved"}}}, False),
    ({"event": "purchase_approved", "data": {"status": "refunded", "card": {"status": "paid"}}}, False),
    ({"event": "pix_gerado", "data": {"status": "waiting_payment", "type": "success"}}, False),
    ({"event": "chargeback", "data": {"status": "chargedback"}}, False),
])
def test_aprovacao_olha_so_os_campos_oficiais(evento, esperado):
    assert cakto.is_aprovado(evento) is esperado


# ============================================================ 4. limites (força bruta, abuso)
SENHA_LIVE = "senha-do-pedro-123"


def test_senha_do_live_trava_depois_de_5_erros(monkeypatch):
    monkeypatch.setenv("PADMINI_LIVE_SENHA", SENHA_LIVE)
    c = _cliente_ip("203.0.113.10")
    for _ in range(5):
        assert c.post("/api/live/entrar", json={"senha": "chute"}).status_code == 401
    # nem a senha certa entra enquanto o IP está travado
    assert c.post("/api/live/entrar", json={"senha": SENHA_LIVE}).status_code == 429
    # outro IP continua entrando
    assert _cliente_ip("203.0.113.11").post(
        "/api/live/entrar", json={"senha": SENHA_LIVE}).status_code == 200


def test_senha_do_live_tem_teto_global_contra_troca_de_ip(monkeypatch):
    monkeypatch.setenv("PADMINI_LIVE_SENHA", SENHA_LIVE)
    for i in range(limites.LIVE_FALHAS_GLOBAL.maximo):
        _cliente_ip(f"198.51.100.{i}").post("/api/live/entrar", json={"senha": "chute"})
    r = _cliente_ip("198.51.100.250").post("/api/live/entrar", json={"senha": "chute"})
    assert r.status_code == 429


def test_senha_do_live_com_acento_da_401_e_nao_500(monkeypatch):
    monkeypatch.setenv("PADMINI_LIVE_SENHA", SENHA_LIVE)
    assert cliente.post("/api/live/entrar", json={"senha": "sênha"}).status_code == 401


def test_calculo_em_loop_recebe_429():
    c = _cliente_ip("203.0.113.20")
    corpo = {**PESSOA, "nivel": "amostra"}
    for _ in range(limites.CALCULO.maximo):
        assert c.post("/api/mapa", json=corpo).status_code == 200
    r = c.post("/api/mapa", json=corpo)
    assert r.status_code == 429 and "Retry-After" in r.headers
    # outra pessoa não é afetada
    assert _cliente_ip("203.0.113.21").post("/api/mapa", json=corpo).status_code == 200


def test_lista_de_espera_tem_limite():
    c = _cliente_ip("203.0.113.30")
    corpo = {"email": "x@y.com", "aceita_email": True, "site": "robo"}  # honeypot: não grava
    for _ in range(limites.LISTA.maximo):
        assert c.post("/api/lista", json=corpo).status_code == 200
    assert c.post("/api/lista", json=corpo).status_code == 429


def test_ip_do_cliente_prefere_o_da_cloudflare():
    from starlette.requests import Request

    def req(headers):
        return Request({"type": "http", "headers": [(k.encode(), v.encode()) for k, v in headers],
                        "client": ("10.0.0.1", 1)})
    assert limites.ip_do_cliente(req([("cf-connecting-ip", "1.2.3.4"),
                                      ("x-forwarded-for", "9.9.9.9")])) == "1.2.3.4"
    assert limites.ip_do_cliente(req([("x-forwarded-for", "5.6.7.8, 10.1.1.1")])) == "5.6.7.8"
    assert limites.ip_do_cliente(req([])) == "10.0.0.1"


def test_limite_janela_deslizante_libera_depois():
    lim = limites.Limite("t", maximo=2, janela=10)
    assert lim.consumir("a", agora=0) and lim.consumir("a", agora=1)
    assert not lim.consumir("a", agora=5)
    assert lim.consumir("a", agora=10.5)


# ============================================================ 5. cabeçalhos de segurança
@pytest.mark.parametrize("rota", ["/", "/mapa", "/lista", "/live", "/api/saude",
                                  "/static/afiliado.js", "/nao-existe"])
def test_cabecalhos_de_seguranca_em_toda_resposta(rota):
    h = cliente.get(rota).headers
    csp = h["content-security-policy"]
    assert "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
    assert h["x-frame-options"] == "DENY"
    assert h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"] == "strict-origin-when-cross-origin"
    assert h["strict-transport-security"].startswith("max-age=")


def test_cabecalhos_tambem_no_erro_429():
    c = _cliente_ip("203.0.113.40")
    for _ in range(limites.PDF.maximo + 1):
        r = c.post("/api/pdf", json={**PESSOA, "nivel": "completo"})
    assert r.status_code == 429 and "content-security-policy" in r.headers


def test_csp_cobre_recursos_externos_das_paginas():
    """Se alguém puser um <script>/<link> de outro domínio numa página sem
    atualizar seguranca.py, o navegador bloquearia em produção."""
    csp = seguranca.politica_csp()
    diretivas = dict((d.split()[0], d.split()[1:]) for d in csp.split("; "))
    for pagina in (RAIZ / "static").glob("*.html"):
        html = pagina.read_text(encoding="utf-8")
        for m in re.finditer(r'<script[^>]+src="(https://[^/"]+)', html):
            assert m.group(1) in diretivas["script-src"], (pagina.name, m.group(1))
        for m in re.finditer(r'<link[^>]+rel="stylesheet"[^>]+href="(https://[^/"]+)', html):
            assert m.group(1) in diretivas["style-src"], (pagina.name, m.group(1))


def test_csp_acompanha_o_host_do_posthog(monkeypatch):
    monkeypatch.setenv("PADMINI_POSTHOG_HOST", "https://eu.i.posthog.com")
    csp = seguranca.politica_csp()
    assert "https://eu.i.posthog.com" in csp and "https://eu-assets.i.posthog.com" in csp


# ============================================================ 6. e-mail
def test_nome_do_comprador_e_escapado_no_email():
    nome = '<a href="https://golpe.example">Clique</a>'
    html = entrega.email_completo_html("mapa", "https://padmini.teste/mapa?a=1&token=x", nome)
    assert "<a href=\"https://golpe.example\">" not in html and "&lt;a href=" in html
    html2 = entrega.email_mapas_do_casal_html([(nome, "https://padmini.teste/mapa?x=1")], nome)
    assert "golpe.example\">" not in html2


# ============================================================ 7. PostHog sem token
@pytest.mark.skipif(shutil.which("node") is None, reason="node não instalado")
def test_analytics_tira_token_e_dados_de_nascimento_antes_de_enviar():
    evento = {"properties": {
        "$current_url": "https://padmini.com.br/mapa?data=1990-05-15&hora=14:30&lat=-23.5"
                        "&lon=-46.6&nome=Ana&cidade=SP&token=abc123&utm_source=tiktok",
        "$elements_chain": 'a:href="https://pay.cakto.com.br/x?sck=m~1990~Ana&utm_campaign=PEDRO"',
        "$set_once": {"$initial_current_url": "https://padmini.com.br/compatibilidade?a_nome=X&token=zz"},
    }}
    js = ("global.window=global;global.fetch=()=>Promise.reject(1);"
          f"eval(require('fs').readFileSync({json.dumps(str(RAIZ / 'static' / 'analytics.js'))},'utf8'));"
          f"process.stdout.write(JSON.stringify(window.padLimparParaAnalytics({json.dumps(evento)},0)));")
    saida = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    for vazado in ("abc123", "1990-05-15", "14:30", "Ana", "zz", "-23.5"):
        assert vazado not in saida, vazado
    assert "utm_source=tiktok" in saida and "utm_campaign=PEDRO" in saida

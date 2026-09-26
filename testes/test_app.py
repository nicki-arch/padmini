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


@pytest.mark.parametrize(
    "rota", ["/", "/mapa", "/compatibilidade", "/lista", "/privacidade", "/termos", "/api/saude",
             "/robots.txt", "/sitemap.xml"])
def test_head_nao_da_405(rota):
    """Parte 22: HEAD / voltava 405 (FastAPI/Starlette instalados aqui não geram HEAD
    sozinhos para @app.get). Monitores de uptime usam HEAD — sem isso, todo alarme dispara."""
    r = cliente.head(rota)
    assert r.status_code == 200


def test_checkout_ligado_nos_dois_produtos():
    """Os botões de compra precisam apontar para a Cakto (constante vazia = botão morto)."""
    mapa = cliente.get("/mapa").text
    compat = cliente.get("/compatibilidade").text
    assert re.search(r'LINK_CHECKOUT_INDIVIDUAL = "https://pay\.cakto\.com\.br/[^"]+"', mapa)
    assert re.search(r'LINK_CHECKOUT = "https://pay\.cakto\.com\.br/[^"]+"', compat)


# ------------------------------------------------- preço e link num lugar só (ofertas.yaml)
@pytest.mark.parametrize("rota", ["/", "/mapa", "/compatibilidade", "/lista"])
def test_nenhum_marcador_sobra_na_pagina(rota):
    """Template não montado vira '{{ ofertas.compat.preco }}' na cara do cliente."""
    sobrou = re.search(r"\{\{|\{%|__[A-Z][A-Z_]*__", cliente.get(rota).text)
    assert not sobrou, f"{rota} ainda tem {sobrou.group(0) if sobrou else ''}"


# ------------------------------------------------- copy fora do HTML (conteudo/home.yaml)
def test_texto_da_home_sai_do_yaml():
    """O que muda na copy tem que mudar na página — senão são duas verdades."""
    import textos
    t = textos.da_pagina("home")
    html = cliente.get("/").text
    assert t["hero"]["titulo"] in html
    assert t["faq"]["itens"][0]["pergunta"] in html
    for d in t["dimensoes"]["itens"]:
        assert d["nome"] in html and d["texto"] in html


def test_copy_nao_carrega_script():
    """Os textos entram na página como HTML (para permitir <em>). Por isso não
    podem conter script — o dia em que alguém colar um, a página executa."""
    import textos

    def cada_texto(no):
        if isinstance(no, str):
            yield no
        elif isinstance(no, dict):
            for v in no.values():
                yield from cada_texto(v)
        elif isinstance(no, list):
            for v in no:
                yield from cada_texto(v)

    for texto in cada_texto(textos.da_pagina("home")):
        baixo = texto.lower()
        for perigo in ["<script", "javascript:", "onerror=", "onload="]:
            assert perigo not in baixo, f"conteudo/home.yaml tem {perigo}: {texto[:60]}"


def test_nome_errado_no_template_quebra_no_teste_e_nao_no_ar():
    """StrictUndefined: variável inexistente levanta erro aqui, em vez de sumir
    silenciosamente e deixar um buraco na página em produção."""
    import jinja2
    import app as _app
    with pytest.raises(jinja2.UndefinedError):
        _app._jinja.from_string("{{ t.nao_existe.nada }}").render(t={}, ofertas={})


def test_preco_da_home_sai_do_ofertas_yaml():
    """O preço anunciado e o preço cobrado precisam vir da mesma fonte: se o
    YAML muda, a home muda junto — sem ninguém lembrar de editar o HTML."""
    import ofertas
    html = cliente.get("/").text
    assert f"R${ofertas.preco('compat')}" in html
    assert f"R${ofertas.preco('mapa')}" in html
    if ofertas.oferta("compat").get("preco_de"):
        assert f"−{ofertas.oferta('compat')['desconto']}%" in html
        assert f"economiza R${ofertas.oferta('compat')['economia']}" in html
    else:
        assert "economiza" not in html and 'class="poff"' not in html


def test_sem_preco_de_nao_ha_selo_de_desconto():
    """O bug (26/set): o site anunciava o casal por R$97 com R$127 riscado, mas a
    oferta na Cakto cobrava R$127 — o cupom ia só como utm_term. Sem `preco_de`
    no YAML, nenhuma página pode sugerir desconto nem "preço de fundador"."""
    import ofertas
    if ofertas.oferta("compat").get("preco_de"):
        pytest.skip("há preco_de configurado")
    for rota in ("/", "/compatibilidade", "/lista"):
        html = cliente.get(rota).text
        visivel = re.sub(r"preco-fundador", "", html)  # nome de classe CSS, não texto
        assert "economiza" not in visivel and "fundador" not in visivel.lower(), rota
        assert f"R${ofertas.preco('compat')}" in html, rota


def test_webhook_e_site_usam_o_mesmo_codigo_de_oferta():
    """O código que o webhook usa para reconhecer o produto é o do próprio link
    de checkout do site — não um segundo valor escrito no cakto.py."""
    import cakto
    import ofertas
    assert cakto.OFERTA_MAPA == ofertas.codigo("mapa") != ""
    assert cakto.OFERTA_COMPAT == ofertas.codigo("compat") != ""
    assert ofertas.codigo("mapa") in ofertas.checkout("mapa")


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


def _oferta_do_sck(sck: str) -> dict:
    """Numa entrega real a Cakto sempre diz qual oferta foi paga (offer.id)."""
    import ofertas
    if sck.startswith("c~"):
        return {"offer": {"id": ofertas.codigo("compat")}}
    if sck.startswith("m~"):
        return {"offer": {"id": ofertas.codigo("mapa")}}
    return {}


def _evento(sck: str, email: str = "compradora@teste.com", oferta: dict | None = None) -> dict:
    return {"event": "purchase_approved",
            "data": {"status": "paid", "customer": {"name": "Ana", "email": email},
                     "sck": sck, "utm_source": "afiliado", "utm_campaign": "PEDRO",
                     **(_oferta_do_sck(sck) if oferta is None else oferta)}}


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
    ev = {"data": {"sck": sck, **_oferta_do_sck(sck)}}
    pd = cakto.coletar_pd(ev)
    produto = cakto.produto_do_evento(ev, pd)
    assert produto == esperado
    assert cakto.dados_nascimento(pd, produto) is not None
    assert len(sck) <= 200  # URL curta: o sck não pode crescer sem controle


def test_saude_sem_banco():
    r = cliente.get("/api/saude")
    assert r.status_code == 200 and r.json() == {"ok": True, "banco": None, "versao": ""}


# ---------------------------------------------------------------- formatos de entrega da Cakto
def test_webhook_v2_lista_entrega_so_o_principal():
    """Webhook V2 manda todos os pedidos da cobrança numa lista (data = [...])."""
    principal = _evento(SCK_MAPA)["data"] | {"id": "p-main", "offer_type": "main"}
    bump = _evento(SCK_MAPA)["data"] | {"id": "p-bump", "offer_type": "orderbump"}
    r = _postar_webhook({"event": "purchase_approved", "data": [principal, bump]})
    assert r.status_code == 200, r.text
    res = r.json()["pedidos"]
    assert res[0]["produto"] == "mapa" and res[0]["link"]
    assert "orderbump" in res[1]["ignorado"]


def test_webhook_v1_orderbump_ignorado():
    ev = _evento(SCK_MAPA)
    ev["data"]["offer_type"] = "orderbump"
    r = _postar_webhook(ev)
    assert r.status_code == 200 and "orderbump" in r.json()["ignorado"]


def test_pedido_pago_sem_sck_fica_pendente(monkeypatch):
    """Pagou mas o sck não veio: não pode sumir — responde 200 marcando pendente."""
    import cakto
    monkeypatch.setattr(cakto, "PROD_MAPA", "prod-mapa-123")
    ev = _evento("")
    ev["data"]["product"] = {"id": "prod-mapa-123"}
    r = _postar_webhook(ev)
    assert r.status_code == 200, r.text
    assert r.json()["produto"] == "mapa" and "pendente" in r.json()
    assert not r.json().get("link")


def test_produto_identificado_pela_oferta_do_checkout():
    """Sem sck, o código da oferta (o do link do checkout) ainda diz qual é o produto."""
    import cakto
    for url, esperado in (("https://pay.cakto.com.br/39dhqty_1125341", "mapa"),
                          ("https://pay.cakto.com.br/qo8uskp_1125345", "compat")):
        ev = {"data": {"checkoutUrl": url, "offer": {"id": url.rsplit("/", 1)[-1]}}}
        assert cakto.produto_do_evento(ev, {}) == esperado
    assert cakto.produto_do_evento({"data": {"offer": {"id": "outra"}}}, {}) == ""


# ---------------------------------------------------------------- celular / busca (parte 21)
@pytest.mark.parametrize("consulta,primeiro", [
    ("Porto Alegre", "Porto Alegre, Rio Grande do Sul, Brasil"),
    ("Belo", "Belo Horizonte, Minas Gerais, Brasil"),        # antes vinha Belo, Camarões
    ("Rio", "Rio de Janeiro, Rio de Janeiro, Brasil"),
    ("Santa Maria", "Santa Maria, Rio Grande do Sul, Brasil"),
    ("Paris", "Paris, Île-de-France, França"),                # exterior continua achável
    ("Lisboa", "Lisbon, Lisbon, Portugal"),
])
def test_busca_prioriza_brasil_sem_esconder_exterior(consulta, primeiro):
    r = cliente.get("/api/cidades", params={"q": consulta})
    assert r.json()[0]["rotulo"] == primeiro


# ---------------------------------------------------------------- busca: apelidos (parte 23)
@pytest.mark.parametrize("consulta,primeiro", [
    ("porto", "Porto Alegre, Rio Grande do Sul, Brasil"),  # vinha Santana/AP, cujo apelido é "Porto"
    ("sao", "São Paulo, São Paulo, Brasil"),               # vinha o Rio em 2º ("São Sebastião do Rio...")
])
def test_apelido_nao_ganha_do_nome_de_verdade(consulta, primeiro):
    """O índice guarda apelidos das cidades grandes (Lisbon→"Lisboa"), e eles estavam
    competindo de igual para igual com o nome real: quem digitava "porto" via Santana
    do Amapá em primeiro, e quem digitava "sao" via o Rio de Janeiro."""
    assert cliente.get("/api/cidades", params={"q": consulta}).json()[0]["rotulo"] == primeiro


def test_cidade_grande_ganha_de_cidade_pequena_de_nome_exato():
    """"porto" tem de trazer Porto Alegre (1,4 mi) antes de Porto/PI (12 mil), mesmo
    o nome de Porto/PI sendo exato. Quem digita pouco quer a cidade conhecida."""
    rotulos = [c["rotulo"] for c in cliente.get("/api/cidades", params={"q": "porto"}).json()]
    assert rotulos.index("Porto Alegre, Rio Grande do Sul, Brasil") < rotulos.index("Porto, Piauí, Brasil")


def test_apelido_continua_encontrando_a_cidade():
    """A correção acima não pode desligar os apelidos: quem digita em português
    "Lisboa" ou "Nova York" precisa achar Lisbon e New York."""
    for consulta, esperado in [("Lisboa", "Lisbon, Lisbon, Portugal"),
                               ("Nova York", "New York City, New York, Estados Unidos")]:
        assert cliente.get("/api/cidades", params={"q": consulta}).json()[0]["rotulo"] == esperado


def test_paginas_legais_sem_placeholder():
    """As páginas legais ficaram um tempo com [RAZÃO SOCIAL] / [CNPJ] / [E-MAIL] no ar.
    Página legal sem os dados de quem responde pelo serviço não pode ir a produção."""
    for pagina in ["privacidade.html", "termos.html"]:
        texto = (RAIZ / "static" / pagina).read_text(encoding="utf-8")
        for marca in ["[RAZÃO SOCIAL]", "[CNPJ]", "[CIDADE/UF]", "[E-MAIL]"]:
            assert marca not in texto, f"{pagina} ainda tem {marca}"
        assert "55.428.936/0001-00" in texto
        assert "contato@pedrosperbmonteiro.com.br" in texto


@pytest.mark.parametrize("pagina", ["home.html", "index.html", "compatibilidade.html", "lista.html"])
def test_og_image_e_url_absoluta(pagina):
    """WhatsApp e Facebook ignoram og:image com caminho relativo — o link vira
    prévia sem imagem, que é justamente o canal onde o produto circula."""
    texto = (RAIZ / "static" / pagina).read_text(encoding="utf-8")
    achou = re.search(r'<meta property="og:image" content="([^"]+)"', texto)
    assert achou, f"{pagina} sem og:image"
    assert achou.group(1).startswith("https://"), f"{pagina} com og:image relativo"


@pytest.mark.parametrize("pagina", ["home.html", "index.html", "compatibilidade.html", "lista.html"])
def test_paginas_publicas_tem_canonical(pagina):
    """Com o site respondendo em padmini.com.br e em padmini.onrender.com, sem
    canonical o buscador trata os dois como páginas diferentes."""
    texto = (RAIZ / "static" / pagina).read_text(encoding="utf-8")
    assert re.search(r'<link rel="canonical" href="https://padmini\.com\.br', texto), \
        f"{pagina} sem canonical"


def test_robots_aponta_o_sitemap_e_esconde_o_live():
    r = cliente.get("/robots.txt")
    assert r.status_code == 200
    assert "Sitemap: https://padmini.teste/sitemap.xml" in r.text
    assert "Disallow: /live" in r.text
    assert "Disallow: /*?token=" in r.text


def test_sitemap_lista_as_paginas_do_produto():
    r = cliente.get("/sitemap.xml")
    assert r.status_code == 200
    for caminho in ["https://padmini.teste/", "https://padmini.teste/mapa",
                    "https://padmini.teste/compatibilidade"]:
        assert f"<loc>{caminho}</loc>" in r.text


def test_sitemap_com_captura_ligada_so_anuncia_a_lista(monkeypatch):
    """Com a trava ligada as outras páginas redirecionam; anunciá-las faria o
    buscador indexar redirecionamento."""
    monkeypatch.setenv("PADMINI_CAPTURA", "1")
    r = cliente.get("/sitemap.xml")
    assert "<loc>https://padmini.teste/lista</loc>" in r.text
    assert "<loc>https://padmini.teste/mapa</loc>" not in r.text


def test_atributo_hidden_sempre_esconde():
    """Sem essa regra, `#resultado{display:grid}` deixava um bloco vazio no celular."""
    css = (RAIZ / "static" / "base.css").read_text(encoding="utf-8")
    assert "[hidden] { display: none !important; }" in css


# ---------------------------------------------------------------- combo: mapas do casal (order bump)
def test_bump_no_casal_entrega_os_dois_mapas(monkeypatch):
    import cakto
    monkeypatch.setattr(cakto, "OFERTA_BUMP_MAPAS", "bumpmapas")
    ev = _evento(SCK_CASAL)
    ev["data"] |= {"id": "bump-1", "offer_type": "orderbump", "offer": {"id": "bumpmapas"}}
    r = _postar_webhook(ev)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["produto"] == "mapas_casal" and len(corpo["links"]) == 2
    for link, nome in zip(corpo["links"], ("Ana", "Bruno")):
        q = _params(link)
        assert q["nome"] == nome
        pedido = {"nome": q["nome"], "data": q["data"], "hora": q["hora"], "lat": float(q["lat"]),
                  "lon": float(q["lon"]), "cidade": q["cidade"], "nivel": "completo", "token": q["token"]}
        assert cliente.post("/api/mapa", json=pedido).status_code == 200


def test_bump_de_outra_oferta_e_ignorado(monkeypatch):
    import cakto
    monkeypatch.setattr(cakto, "OFERTA_BUMP_MAPAS", "bumpmapas")
    ev = _evento(SCK_CASAL)
    ev["data"] |= {"offer_type": "orderbump", "offer": {"id": "outrobump"}}
    assert "ignorado" in _postar_webhook(ev).json()
    ev["data"]["offer"] = {"id": "bumpmapas"}
    assert _postar_webhook(ev).json()["produto"] == "mapas_casal"


# ---------------------------------------------------------------- pré-lançamento: lista de espera
def test_lista_responde_e_fica_fora_da_trava():
    assert cliente.get("/lista").status_code == 200


def test_trava_desligada_por_padrao():
    assert cliente.get("/mapa", follow_redirects=False).status_code == 200


def test_trava_ligada_manda_para_a_lista_mantendo_o_ref(monkeypatch):
    monkeypatch.setenv("PADMINI_CAPTURA", "1")
    for rota in ("/", "/mapa", "/compatibilidade"):
        r = cliente.get(rota + "?ref=PEDRO", follow_redirects=False)
        assert r.status_code == 302 and r.headers["location"] == "/lista?ref=PEDRO"


def test_trava_ligada_nao_bloqueia_link_de_entrega(monkeypatch):
    monkeypatch.setenv("PADMINI_CAPTURA", "1")
    assert cliente.get("/mapa?token=abc", follow_redirects=False).status_code == 200


def test_chave_de_previa_libera_e_grava_cookie(monkeypatch):
    monkeypatch.setenv("PADMINI_CAPTURA", "1")
    monkeypatch.setenv("PADMINI_PREVIA_CHAVE", "segredo123")
    c = TestClient(app_mod.app)
    assert c.get("/?previa=errada", follow_redirects=False).status_code == 302
    assert c.get("/?previa=segredo123", follow_redirects=False).status_code == 200
    assert c.get("/compatibilidade", follow_redirects=False).status_code == 200  # cookie


def test_inscricao_exige_email_valido_e_consentimento():
    base = {"email": "ana@teste.com", "aceita_email": True}
    assert cliente.post("/api/lista", json=base | {"email": "ana"}).status_code == 422
    assert cliente.post("/api/lista", json=base | {"aceita_email": False}).status_code == 422
    assert cliente.post("/api/lista", json=base | {"whatsapp": "123"}).status_code == 422


def test_inscricao_sem_banco_avisa_em_vez_de_perder(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    r = cliente.post("/api/lista", json={"email": "ana@teste.com", "aceita_email": True})
    assert r.status_code == 503


def test_honeypot_finge_sucesso_sem_gravar(monkeypatch):
    import db
    chamadas = []
    monkeypatch.setattr(db, "registrar_lead", lambda *a, **k: chamadas.append(a) or True)
    r = cliente.post("/api/lista", json={"email": "bot@x.com", "aceita_email": True, "site": "http://spam"})
    assert r.status_code == 200 and chamadas == []


# ---------------------------------------------------------------- modo live (parte 22)
SENHA_LIVE = "senha-do-pedro-123"


def _cliente_live(monkeypatch, entrar=True):
    """Cliente próprio: o cookie do live não pode vazar para os outros testes."""
    monkeypatch.setenv("PADMINI_LIVE_SENHA", SENHA_LIVE)
    c = TestClient(app_mod.app)
    if entrar:
        assert c.post("/api/live/entrar", json={"senha": SENHA_LIVE}).status_code == 200
    return c


def test_pagina_live_abre_e_nao_e_indexada():
    r = cliente.get("/live")
    assert r.status_code == 200
    assert "noindex" in r.text and "Modo live" in r.text


def test_live_sem_senha_configurada_nao_entra():
    r = TestClient(app_mod.app).post("/api/live/entrar", json={"senha": "qualquer"})
    assert r.status_code == 503


def test_live_senha_errada_e_certa(monkeypatch):
    c = _cliente_live(monkeypatch, entrar=False)
    assert c.post("/api/live/entrar", json={"senha": "chute"}).status_code == 401
    assert c.get("/api/live/sessao").json() == {"ativa": False, "configurado": True}
    assert c.post("/api/live/entrar", json={"senha": SENHA_LIVE}).status_code == 200
    assert c.get("/api/live/sessao").json()["ativa"] is True
    c.post("/api/live/sair")
    assert c.get("/api/live/sessao").json()["ativa"] is False


def test_live_sem_sessao_nao_emite_token():
    r = cliente.post("/api/live/token/mapa", json=PESSOA)
    assert r.status_code == 401


def test_live_gera_o_completo_dos_dois_produtos(monkeypatch):
    c = _cliente_live(monkeypatch)
    t = c.post("/api/live/token/mapa", json=PESSOA).json()["token"]
    completo = c.post("/api/mapa", json={**PESSOA, "nivel": "completo", "token": t})
    assert completo.status_code == 200 and completo.json()["nivel"] == "completo"

    casal = {"a": PESSOA, "b": PESSOA_B}
    t2 = c.post("/api/live/token/compat", json=casal).json()["token"]
    r = c.post("/api/compatibilidade", json={**casal, "nivel": "completo", "token": t2})
    assert r.status_code == 200 and "kootas" in r.json()


def test_cookie_do_live_e_assinado_e_expira():
    import acesso
    valido = acesso.emitir_sessao("live", int(time.time()) + 60)
    assert acesso.sessao_valida("live", valido)
    assert not acesso.sessao_valida("live", acesso.emitir_sessao("live", int(time.time()) - 1))
    assert not acesso.sessao_valida("live", valido[:-1] + ("0" if valido[-1] != "0" else "1"))
    assert not acesso.sessao_valida("live", "9999999999.qualquercoisa")
    assert not acesso.sessao_valida("live", None)


def test_live_nao_abre_o_completo_de_outro_nascimento(monkeypatch):
    c = _cliente_live(monkeypatch)
    t = c.post("/api/live/token/mapa", json=PESSOA).json()["token"]
    outro = {**PESSOA, "data": "1991-05-15"}
    assert c.post("/api/mapa", json={**outro, "nivel": "completo", "token": t}).status_code == 402

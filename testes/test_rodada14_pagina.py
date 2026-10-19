"""
Rodada 14, Fases 2 e 3: os textos, a página, o PDF, o arquivo de agenda e a amostra de
"A sua Lua no ano" (/calendario-lunar, /api/ocidental/calendario*).

Critérios do brief: com hora, a casa; sem hora, o aviso e só signos e planetas; o .ics e o
link sem nenhum dado de nascimento (só o token); a amostra sem texto pago no JSON; oculto =
404 em produção (link pago abre sempre).
"""
import re
from datetime import date, datetime

import pytest

from test_app import app_mod, cliente  # primeiro: define os segredos de teste

import acesso
import calendario_lunar as cl
import catalogo
import entrega
import mapa_ocidental as mo
import marketing
import ofertas
import montar_calendario as mc
import montar_texto_ocidental as mt
import revisao

pytestmark = pytest.mark.catalogo_real
HTML = {"accept": "text/html"}
PESSOA = {"nome": "Ana Beatriz", "data": "1990-05-15", "hora": "14:30", "lat": -23.5505, "lon": -46.6333,
          "cidade": "São Paulo, SP"}
INICIO = "2026-10"


@pytest.fixture
def ocidental(monkeypatch):
    monkeypatch.setenv("PADMINI_SISTEMA", "ocidental")
    monkeypatch.delenv("PADMINI_CAPTURA", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("PADMINI_PREVIA_CHAVE", "chave-de-previa")
    app_mod._paginas_prontas.clear()
    cliente.cookies.clear()  # o pad_previa de outro teste abriria a página oculta
    yield
    app_mod._paginas_prontas.clear()
    cliente.cookies.clear()


def _token(p=PESSOA, inicio=INICIO):
    return acesso.emitir_token_calendario(p["data"], p["hora"], p["lat"], p["lon"], inicio)


def _natal(p=PESSOA):
    if p["hora"]:
        return mo.calcular_mapa_ocidental(datetime.fromisoformat(p["data"] + "T" + p["hora"]), p["lat"], p["lon"])
    return mo.calcular_mapa_ocidental(None, p["lat"], p["lon"], data=date.fromisoformat(p["data"]))


def _cal(p=PESSOA, inicio=INICIO, fuso="America/Sao_Paulo"):
    return cl.calcular_calendario(_natal(p), date.fromisoformat(inicio + "-01"), fuso)


def _dados_de_nascimento(p=PESSOA) -> list[str]:
    """Tudo o que identificaria o nascimento, em vários formatos."""
    d = date.fromisoformat(p["data"])
    out = [p["data"], d.strftime("%d/%m/%Y"), d.strftime("%Y%m%d"), p["cidade"], "São Paulo",
           str(p["lat"]), str(p["lon"]), f"{p['lat']:.4f}", f"{p['lon']:.4f}", p["nome"], "Beatriz"]
    if p["hora"]:
        out += [f"{p['hora']}|", f"nascimento às {p['hora']}"]
    return out


# ------------------------------------------------------------------ o token cifrado
def test_token_leva_o_pedido_cifrado_e_volta_igual():
    t = _token()
    assert t.startswith("oc-cal-") and acesso.sistema_do_token(t) == "ocidental"
    for dado in _dados_de_nascimento():
        assert dado not in t
    assert acesso.abrir_token_calendario(t) == {"data": PESSOA["data"], "hora": PESSOA["hora"],
                                                 "lat": round(PESSOA["lat"], 4), "lon": round(PESSOA["lon"], 4),
                                                 "inicio": INICIO}
    assert _token() != t  # nonce novo a cada emissão; os dois abrem
    assert acesso.abrir_token_calendario(_token()) == acesso.abrir_token_calendario(t)


def test_token_alterado_ou_sem_segredo_nao_abre(monkeypatch):
    t = _token()
    meio = len(t) // 2
    trocado = t[:meio] + ("A" if t[meio] != "A" else "B") + t[meio + 1:]
    for ruim in (trocado, t[:-3], "oc-cal-", "oc-cal-!!!", "", None, "oc-" + "a" * 32, t + "x" * 400):
        assert acesso.abrir_token_calendario(ruim) is None, ruim
    monkeypatch.setattr(acesso, "SEGREDO", "outro-segredo-qualquer")
    assert acesso.abrir_token_calendario(t) is None
    monkeypatch.setattr(acesso, "SEGREDO", "")
    assert acesso.abrir_token_calendario(t) is None
    with pytest.raises(RuntimeError):
        _token()


def test_link_de_entrega_leva_so_o_token():
    link = entrega.link_completo("calendario", {**PESSOA, "inicio": INICIO}, "ocidental")
    assert re.fullmatch(re.escape(entrega.SITE_URL) + r"/calendario-lunar\?token=oc-cal-[A-Za-z0-9_-]+", link), link
    for dado in _dados_de_nascimento():
        assert dado not in link


# ------------------------------------------------------------------ o produto oculto
def test_oculto_e_com_preco(ocidental):
    """Rodada 20: o preço foi decidido (R$47, "de R$97"), mas o produto continua OCULTO."""
    p = next(x for x in catalogo.produtos_do_yaml() if x["chave"] == "calendario")
    assert p["estado"] == "oculto" and p.get("oferta") == "calendario"
    oferta = ofertas.oferta("calendario", "ocidental")
    assert (oferta["preco"], oferta["preco_de"]) == (47, 97) and not oferta.get("checkout")
    assert not catalogo.vende("calendario")
    assert cliente.get("/calendario-lunar", headers=HTML).status_code == 404


def test_previa_e_link_pago_abrem(ocidental):
    r = cliente.get("/calendario-lunar?previa=chave-de-previa", headers=HTML)
    assert r.status_code == 200 and "sua Lua" in r.text
    assert "R$" not in r.text and 'data-comprar="calendario"' not in r.text
    r = cliente.get(f"/calendario-lunar?token={_token()}", headers=HTML)
    assert r.status_code == 200 and 'name="referrer" content="no-referrer"' in r.text


def test_oculto_some_do_menu_e_das_leituras(ocidental):
    for rota in ("/", "/mapa", "/leituras"):
        assert "/calendario-lunar" not in cliente.get(rota, headers=HTML).text, rota


def test_pagina_nao_tem_a_caixa_da_sequencia(ocidental):
    html = cliente.get("/calendario-lunar?previa=chave-de-previa", headers=HTML).text
    assert 'id="aceita-sequencia"' not in html and 'id="email"' in html
    # as outras páginas continuam com a caixa
    assert 'id="aceita-sequencia"' in cliente.get("/seu-ano?previa=chave-de-previa", headers=HTML).text


# ------------------------------------------------------------------ amostra (critério 4)
def test_amostra_pede_email(ocidental):
    assert cliente.post("/api/ocidental/calendario", json=PESSOA).status_code == 422


def test_amostra_sem_texto_pago_no_json(ocidental, monkeypatch):
    import rotas_ocidental
    registros = []
    monkeypatch.setenv("RESEND_API_KEY", "re_teste")
    monkeypatch.setattr(entrega, "enviar_email", lambda *a, **k: True)
    monkeypatch.setattr(rotas_ocidental.db, "registrar_amostra_email", lambda *a, **k: registros.append((a, k)))
    r = cliente.post("/api/ocidental/calendario", json={**PESSOA, "email": "ana@teste.com",
                                                        "aceita_sequencia": True})
    assert r.status_code == 200, r.text
    corpo, a = r.text, r.json()["amostra"]
    assert "texto" not in a and a["trecho"].endswith("…") and a["proximos"]
    assert all(set(e) <= {"tipo", "icone", "titulo", "data", "dia", "hora", "casa", "linha"} for e in a["proximos"])
    # os próximos 30 dias
    hoje = mc.hoje_no_fuso("America/Sao_Paulo")
    assert all(0 <= (date.fromisoformat(e["data"]) - hoje).days < 30 for e in a["proximos"])
    # nenhum texto pago do período inteiro na resposta (do 1º evento, só a metade)
    c = mc.completo(_cal(inicio=a["inicio"][:7]))
    pagos = [t for m in c["meses"] for e in m["eventos"] for t in mc.paragrafos_do_evento(e)]
    pagos += [c["revolucao_lunar"]["texto"]] if c["revolucao_lunar"] else []
    assert pagos
    for t in pagos:
        assert t[len(t) // 2:][:60] not in corpo, t[:60]
    # sem lembrete nem sequência, mesmo com a caixa marcada (nenhum e-mail de marketing novo)
    (args, kw), = registros
    assert args[3] is False and kw.get("aceita_sequencia") is False


def test_email_da_amostra_traz_o_primeiro_texto_inteiro_e_nenhum_link_pago():
    a = mc.amostra(_cal(), date(2026, 10, 19))
    html = marketing.email_amostra_html("calendario", a, {**PESSOA, "inicio": INICIO}, "ana@teste.com", "Ana",
                                        "ocidental")
    assert a["texto"] and marketing._e(a["texto"]) in html
    assert "oc-cal-" not in html and "token=" not in html
    assert all(marketing._e(e["titulo"]) in html for e in a["proximos"])


# ------------------------------------------------------------------ o completo
def test_completo_so_com_token(ocidental):
    assert cliente.post("/api/ocidental/calendario/completo", json={"token": "oc-cal-falso"}).status_code == 402
    assert cliente.post("/api/ocidental/calendario/completo", json={}).status_code == 422
    # o token de outro produto não abre
    outro = acesso.emitir_token("previsao", "x", "ocidental")
    assert cliente.post("/api/ocidental/calendario/completo", json={"token": outro}).status_code == 402


def test_completo_com_hora_tem_casa_e_destaques(ocidental):
    r = cliente.post("/api/ocidental/calendario/completo", json={"token": _token()})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["nivel"] == "completo" and d["tem_hora"] and len(d["meses"]) == 12 and not d["avisos"]
    lunacoes = [e for m in d["meses"] for e in m["eventos"] if e["tipo"] in ("nova", "cheia")]
    assert 24 <= len(lunacoes) <= 26 and all(e["casa"] in range(1, 13) for e in lunacoes)
    assert all(len(e["textos"]) >= 2 for e in lunacoes)  # o signo e a casa (e os pontos tocados)
    assert d["revolucao_lunar"]["texto"] and len(d["revolucao_lunar"]["datas"]) in (13, 14)
    assert d["agenda"].startswith("/calendario-lunar/agenda.ics?token=oc-cal-")
    # nada de nascimento na resposta
    for dado in _dados_de_nascimento():
        assert dado not in r.text, dado


def test_completo_sem_hora_aviso_e_so_signos(ocidental):
    sem = {**PESSOA, "hora": ""}
    d = cliente.post("/api/ocidental/calendario/completo", json={"token": _token(sem)}).json()
    assert not d["tem_hora"] and len(d["avisos"]) == 2
    eventos = [e for m in d["meses"] for e in m["eventos"]]
    assert all(e["casa"] is None for e in eventos)
    assert all(t["ponto"] not in ("lua", "ascendente", "meio_do_ceu") for e in eventos for t in e.get("toca", []))
    assert not any(e["tipo"] == "revolucao" for e in eventos) and d["revolucao_lunar"] is None
    lunacoes = [e for e in eventos if e["tipo"] in ("nova", "cheia")]
    assert all(e["textos"][0] == mt._t(mt.base("calendario/lunacoes_signos")[e["tipo"]][e["signo"]])
               for e in lunacoes)


def test_fuso_muda_a_hora(ocidental):
    def primeira(fuso):
        d = cliente.post("/api/ocidental/calendario/completo", json={"token": _token(), "fuso": fuso}).json()
        return next(e for m in d["meses"] for e in m["eventos"] if e["tipo"] == "nova")
    sp, acre = primeira("America/Sao_Paulo"), primeira("America/Rio_Branco")
    h = lambda e: int(e["hora"][:2])
    assert (h(sp) - h(acre)) % 24 == 2
    assert cliente.post("/api/ocidental/calendario/completo",
                        json={"token": _token(), "fuso": "Europe/Lisbon"}).status_code == 422


def test_pdf(ocidental):
    r = cliente.post("/api/ocidental/calendario/pdf", json={"token": _token()})
    assert r.status_code == 200 and r.content[:4] == b"%PDF" and len(r.content) > 50_000
    assert cliente.post("/api/ocidental/calendario/pdf", json={"token": "oc-cal-x"}).status_code == 402


# ------------------------------------------------------------------ o arquivo de agenda (critério 3)
def test_ics_sem_dado_de_nascimento(ocidental):
    t = _token()
    r = cliente.get(f"/calendario-lunar/agenda.ics?token={t}&fuso=America/Sao_Paulo")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    assert "attachment" in r.headers["content-disposition"] and "no-store" in r.headers["cache-control"]
    ics = r.text
    for dado in _dados_de_nascimento():
        assert dado not in ics, dado
    desdobrado = ics.replace("\r\n ", "")
    assert "X-WR-CALNAME:Valderez · a sua Lua" in desdobrado
    # o link da descrição leva só o token
    links = set(re.findall(r"https?://[^\s\\]+", desdobrado))
    assert links and all(re.fullmatch(re.escape(entrega.SITE_URL) + r"/calendario-lunar\?token=oc-cal-[A-Za-z0-9_-]+", l)
                         for l in links), links


def test_ics_bem_formado():
    cal = _cal()
    ics = mc.ics(cal, "https://exemplo.com/calendario-lunar?token=oc-cal-abc")
    linhas = ics.split("\r\n")
    assert ics.endswith("\r\n") and linhas[0] == "BEGIN:VCALENDAR" and linhas[-2] == "END:VCALENDAR"
    assert all(len(l.encode("utf-8")) <= 75 for l in linhas)
    eventos = ics.count("BEGIN:VEVENT")
    assert eventos == ics.count("END:VEVENT") and eventos >= 24 + 13
    desdobrado = ics.replace("\r\n ", "")
    # um evento de dia inteiro por data, com a hora no título
    for bloco in desdobrado.split("BEGIN:VEVENT")[1:]:
        ini = re.search(r"DTSTART;VALUE=DATE:(\d{8})", bloco).group(1)
        fim = re.search(r"DTEND;VALUE=DATE:(\d{8})", bloco).group(1)
        assert (datetime.strptime(fim, "%Y%m%d") - datetime.strptime(ini, "%Y%m%d")).days == 1
        assert re.search(r"SUMMARY:.+ · \d{2}:\d{2}", bloco)
        assert "DESCRIPTION:" in bloco and "UID:" in bloco
    # os UIDs não se repetem e não mudam entre downloads (reimportar não duplica)
    uids = re.findall(r"UID:(\S+)", desdobrado)
    assert len(uids) == len(set(uids)) == eventos
    assert uids == re.findall(r"UID:(\S+)", mc.ics(cal, "https://outro").replace("\r\n ", ""))
    # vírgula e ponto e vírgula escapados
    assert not re.search(r"DESCRIPTION:[^\r\n]*[^\\][,;]", desdobrado)


def test_ics_token_invalido(ocidental):
    assert cliente.get("/calendario-lunar/agenda.ics?token=oc-cal-x").status_code == 402
    assert cliente.get("/calendario-lunar/agenda.ics").status_code == 402


# ------------------------------------------------------------------ textos (Fase 2)
def test_textos_do_calendario_completos_e_no_tom():
    itens = [i for i in revisao.itens() if i["arquivo"].startswith("calendario/")]
    por = {}
    for i in itens:
        por[i["arquivo"]] = por.get(i["arquivo"], 0) + 1
        assert i["produto"] == "Calendário lunar" and i["revisado"] is False
        assert revisao.problemas(i["texto"], i["arquivo"], tuple(i["caminho"])) == [], i["id"]
    assert por == {"calendario/lunacoes_casas": 24, "calendario/lunacoes_signos": 24,
                   "calendario/lunacoes_pontos": 18, "calendario/revolucao_lunar": 12,
                   "calendario/mercurio": 12, "calendario/pecas": 10}
    assert sum(por.values()) >= 96


def test_regra_barra_sorte_e_previsao_no_calendario():
    base = " ".join(["você tende a escolher com calma o que plantar"] * 7)
    assert revisao.problemas(base, "calendario/pecas", ("abertura",)) == []
    assert any("sorte" in e for e in revisao.problemas(base + " dia de sorte", "calendario/pecas", ("abertura",)))
    assert any("vai" in e for e in revisao.problemas(base + " você vai", "calendario/pecas", ("abertura",)))
    assert any("saúde" in e for e in revisao.problemas(base + " saúde", "calendario/pecas", ("abertura",)))


def test_todo_evento_tem_texto():
    for p in (PESSOA, {**PESSOA, "hora": ""}):
        for e in mc.eventos(_cal(p)):
            if e["tipo"] in ("nova", "cheia", "mercurio"):
                assert e["textos"] and all(e["textos"]), e["titulo"]


def test_painel_conta_os_textos_do_calendario():
    import painel
    assert painel._revisao_por_produto()["calendario"] == 100

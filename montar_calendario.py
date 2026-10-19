"""
Padmini — "A sua Lua no ano" (rodada 14): do cálculo (`calendario_lunar.py`) ao
calendário: os 12 meses com cada evento, os destaques, a amostra e o arquivo de agenda.

Os textos vêm do banco revisável (`conteudo/ocidental/textos/calendario/` e, nos
eclipses, `previsao/eclipses`, no repositório privado), nunca de IA. Aqui só se escolhe
QUAL texto vai em cada evento.

Amostra (grátis): os próximos 30 dias; o primeiro evento com metade do texto aberta, os
outros só com dia, hora e título. O texto inteiro do primeiro vai só por e-mail; o resto
é pago e nunca sai do servidor (a regra da rodada 6).

Arquivo de agenda (.ics): um evento de dia inteiro por data, a hora exata no título, o
texto e o link da página na descrição. NENHUM dado de nascimento: nem nome, nem data, nem
local, nem no link (que leva só o token cifrado, acesso.emitir_token_calendario).
"""

import hashlib
from datetime import date, datetime, timedelta, timezone

import calendario_lunar as cl
import mapa_ocidental as mo
import montar_texto_ocidental as mt

MESES_PT = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
            "setembro", "outubro", "novembro", "dezembro")
SEMANA_PT = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
FASE_PT = {"nova": "Lua nova", "cheia": "Lua cheia"}
DO_PONTO = {"sol": "o seu Sol", "lua": "a sua Lua", "mercurio": "o seu Mercúrio", "venus": "a sua Vênus",
            "marte": "o seu Marte", "jupiter": "o seu Júpiter", "saturno": "o seu Saturno",
            "ascendente": "o seu Ascendente", "meio_do_ceu": "o seu Meio do Céu"}
SUBTIPO_PT = {"anular": "anular", "total": "total", "parcial": "parcial", "penumbral": "penumbral",
              "hibrido": "híbrido"}
# Ícone de cada tipo (página, PDF e título do evento na agenda).
ICONE = {"nova": "🌑", "cheia": "🌕", "eclipse_solar": "🌑", "eclipse_lunar": "🌕",
         "mercurio": "☿", "revolucao": "☽"}
NOME_AGENDA = "Valderez · a sua Lua"
DIAS_AMOSTRA = 30


def _txt(arquivo: str, *chaves) -> str:
    no = mt.base(arquivo)
    for c in chaves:
        no = (no or {}).get(c) if isinstance(no, dict) else None
    return mt._t(no)


def peca(nome: str) -> str:
    return _txt("calendario/pecas", nome)


def aviso(nome: str) -> str:
    return _txt("calendario/pecas", "avisos", nome)


def data_pt(d: date) -> str:
    return f"{d.day} de {MESES_PT[d.month - 1]} de {d.year}"


def dia_pt(d: date) -> str:
    """"sábado, 6 de fevereiro"."""
    return f"{SEMANA_PT[d.weekday()]}, {d.day} de {MESES_PT[d.month - 1]}"


def mes_pt(ano: int, mes: int) -> str:
    return f"{MESES_PT[mes - 1]} de {ano}"


# --------------------------------------------------------------------------
# Cada evento
# --------------------------------------------------------------------------
def item_lunacao(x: dict) -> dict:
    signo_pt = mo.SIGNO_PT[x["signo"]]
    titulo = f"{FASE_PT[x['fase']]} em {signo_pt}"
    textos = [_txt("calendario/lunacoes_signos", x["fase"], x["signo"])]
    if x["casa"]:
        textos.append(_txt("calendario/lunacoes_casas", x["fase"], x["casa"]))
    for t in x["toca"]:
        textos.append(_txt("calendario/lunacoes_pontos", x["fase"], t["ponto"]))
    it = {"tipo": x["fase"], "icone": ICONE[x["fase"]], "titulo": titulo,
          "data": x["data"].isoformat(), "dia": dia_pt(x["data"]), "hora": x["hora"],
          "signo": x["signo"], "signo_pt": signo_pt, "grau": x["grau_texto"], "casa": x["casa"],
          "toca": [{"ponto": t["ponto"], "ponto_pt": mo.PONTO_PT[t["ponto"]], "do_ponto": DO_PONTO[t["ponto"]],
                    "orbe": t["orbe"]} for t in x["toca"]],
          "eclipse": None, "textos": [t for t in textos if t]}
    e = x["eclipse"]
    if e:
        tipo = "Eclipse solar" if e["tipo"] == "solar" else "Eclipse lunar"
        it["eclipse"] = {"tipo": e["tipo"], "subtipo": e["subtipo"],
                         "titulo": f"{tipo} {SUBTIPO_PT[e['subtipo']]}", "hora": e["hora"],
                         "data": e["data"].isoformat(),
                         "texto": _txt("previsao/eclipses", e["tipo"], e["casa"]) if e["casa"] else ""}
        it["icone"] = ICONE[f"eclipse_{e['tipo']}"]
        it["titulo"] = f"{titulo} · {it['eclipse']['titulo']}"
    it["linha"] = linha(it)
    return it


def item_mercurio(m: dict) -> dict:
    ini, fim = m["inicio"], m["fim"]
    texto = _txt("calendario/mercurio", m["casa"]) if m["casa"] else peca("mercurio_geral")
    it = {"tipo": "mercurio", "icone": ICONE["mercurio"],
          "titulo": f"Mercúrio retrógrado em {mo.SIGNO_PT[m['signo']]}",
          "data": ini["data"].isoformat(), "dia": dia_pt(ini["data"]), "hora": ini["hora"],
          "fim": fim["data"].isoformat(), "dia_fim": dia_pt(fim["data"]), "hora_fim": fim["hora"],
          "signo": m["signo"], "signo_pt": mo.SIGNO_PT[m["signo"]], "grau": m["grau_texto"],
          "signo_fim_pt": mo.SIGNO_PT[m["signo_fim"]], "casa": m["casa"],
          "periodo": f"de {data_pt(ini['data'])} a {data_pt(fim['data'])}",
          "textos": [texto] if texto else []}
    it["linha"] = linha(it)
    return it


def item_mercurio_direto(m: dict) -> dict:
    fim = m["fim"]
    it = {"tipo": "mercurio_direto", "icone": ICONE["mercurio"],
          "titulo": f"Mercúrio volta a andar direto, em {mo.SIGNO_PT[m['signo_fim']]}",
          "data": fim["data"].isoformat(), "dia": dia_pt(fim["data"]), "hora": fim["hora"],
          "casa": None, "textos": []}
    it["linha"] = linha(it)
    return it


def item_revolucao(r: dict) -> dict:
    it = {"tipo": "revolucao", "icone": ICONE["revolucao"], "titulo": "A sua Revolução Lunar",
          "data": r["data"].isoformat(), "dia": dia_pt(r["data"]), "hora": r["hora"],
          "signo": r["signo"], "signo_pt": mo.SIGNO_PT[r["signo"]], "casa": None, "textos": []}
    it["linha"] = linha(it)
    return it


def linha(it: dict) -> str:
    """Uma linha de resumo, sem texto pago: "Lua nova em Escorpião · 01:11 · casa 2"."""
    partes = [it["titulo"], it["hora"]]
    if it.get("casa"):
        partes.append(f"casa {it['casa']}")
    if it.get("toca"):
        partes.append("sobre " + ", ".join(t["do_ponto"] for t in it["toca"]))
    return " · ".join(partes)


def eventos(cal: dict) -> list[dict]:
    """Todos os eventos do período em ordem (dia e hora)."""
    lista = [item_lunacao(x) for x in cal["lunacoes"]]
    for m in cal["mercurio"]:
        if cal["inicio"] <= m["inicio"]["data"] <= cal["fim"]:
            lista.append(item_mercurio(m))
        elif m["fim"]["data"] >= cal["inicio"]:  # já tinha começado no dia 1º: entra no 1º dia
            it = item_mercurio(m)
            it["ja_comecou"] = True
            lista.append(it)
        if cal["inicio"] <= m["fim"]["data"] <= cal["fim"]:
            lista.append(item_mercurio_direto(m))
    lista += [item_revolucao(r) for r in cal["revolucoes"]]
    return sorted(lista, key=lambda e: (e["data"] if not e.get("ja_comecou") else cal["inicio"].isoformat(),
                                        e["hora"]))


def _meses(ini: date, fim: date) -> list[tuple[int, int]]:
    out, a, m = [], ini.year, ini.month
    while (a, m) <= (fim.year, fim.month):
        out.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def meses(cal: dict, lista: list[dict] | None = None) -> list[dict]:
    lista = eventos(cal) if lista is None else lista
    por = {am: [] for am in _meses(cal["inicio"], cal["fim"])}
    for e in lista:
        d = cal["inicio"] if e.get("ja_comecou") else date.fromisoformat(e["data"])
        por[(d.year, d.month)].append(e)
    return [{"mes": f"{a}-{m:02d}", "rotulo": mes_pt(a, m), "ano": a, "numero": m, "eventos": v}
            for (a, m), v in por.items()]


def destaques(lista: list[dict], hoje: date) -> dict:
    """A próxima lua (nova ou cheia) e a próxima Revolução Lunar a partir de hoje."""
    def proxima(tipos):
        return next((e for e in lista if e["tipo"] in tipos and e["data"] >= hoje.isoformat()), None)
    return {"proxima_lua": proxima(("nova", "cheia")), "proxima_revolucao": proxima(("revolucao",))}


def avisos(cal: dict) -> list[str]:
    if cal["tem_hora"]:
        return []
    return [aviso("sem_hora"), aviso("sem_revolucao_lunar")]


def hoje_no_fuso(fuso: str) -> date:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo(fuso)).date()


# --------------------------------------------------------------------------
# Completo, amostra e tela
# --------------------------------------------------------------------------
def completo(cal: dict, hoje: date | None = None) -> dict:
    hoje = hoje or hoje_no_fuso(cal["fuso"])
    lista = eventos(cal)
    lua = cal["revolucoes"][0]["signo"] if cal["revolucoes"] else None
    return {
        "inicio": cal["inicio"].isoformat(), "fim": cal["fim"].isoformat(), "tem_hora": cal["tem_hora"],
        "periodo": f"de {data_pt(cal['inicio'])} a {data_pt(cal['fim'])}",
        "fuso": cal["fuso"], "fuso_nome": cal["fuso_nome"],
        "abertura": peca("abertura"), "como_ler": peca("como_ler"), "avisos": avisos(cal),
        "intro": {k: peca(k) for k in ("lunacoes", "eclipses", "mercurio", "revolucao_lunar")},
        "destaques": destaques(lista, hoje),
        "meses": meses(cal, lista),
        "revolucao_lunar": ({"signo": lua, "signo_pt": mo.SIGNO_PT[lua],
                             "texto": _txt("calendario/revolucao_lunar", lua),
                             "datas": [{"data": r["data"].isoformat(), "dia": dia_pt(r["data"]), "hora": r["hora"]}
                                       for r in cal["revolucoes"]]} if lua else None),
        "contagem": contagem(cal),
        "fechamento": peca("fechamento"),
    }


def contagem(cal: dict) -> dict:
    return {"lunacoes": len(cal["lunacoes"]), "eclipses": len(cal["eclipses"]),
            "mercurio": len(cal["mercurio"]), "revolucoes": len(cal["revolucoes"])}


def _metade(texto: str) -> str:
    """A primeira metade do texto (em palavras), terminando com reticências."""
    palavras = (texto or "").split()
    if len(palavras) < 8:
        return ""
    return " ".join(palavras[:len(palavras) // 2]).rstrip(",;:") + "…"


def texto_principal(it: dict, cal: dict) -> str:
    if it["tipo"] == "revolucao":
        return _txt("calendario/revolucao_lunar", it["signo"])
    return it["textos"][0] if it.get("textos") else ""


def amostra(cal: dict, hoje: date | None = None) -> dict:
    """A amostra inteira (o que vai por e-mail): os eventos dos próximos 30 dias, o
    primeiro com o texto principal. A tela recebe só a metade dele (`tela`)."""
    hoje = hoje or hoje_no_fuso(cal["fuso"])
    ate = (hoje + timedelta(days=DIAS_AMOSTRA)).isoformat()
    proximos = [e for e in eventos(cal) if hoje.isoformat() <= e["data"] < ate and e["tipo"] != "mercurio_direto"]
    primeiro = proximos[0] if proximos else None
    texto = texto_principal(primeiro, cal) if primeiro else ""
    return {
        "inicio": cal["inicio"].isoformat(), "fim": cal["fim"].isoformat(), "tem_hora": cal["tem_hora"],
        "periodo": f"de {data_pt(cal['inicio'])} a {data_pt(cal['fim'])}",
        "fuso": cal["fuso"], "fuso_nome": cal["fuso_nome"],
        "abertura": peca("abertura"), "avisos": [aviso("sem_hora")] if not cal["tem_hora"] else [],
        "proximos": [{k: e.get(k) for k in ("tipo", "icone", "titulo", "data", "dia", "hora", "casa", "linha")}
                     for e in proximos],
        "trecho": _metade(texto),
        "texto": texto,
        "contagem": contagem(cal),
    }


def tela(a: dict) -> dict:
    """O que a página mostra da amostra: sem o texto inteiro (só a metade, em `trecho`)."""
    return {k: v for k, v in a.items() if k != "texto"}


# --------------------------------------------------------------------------
# PDF: o calendário em texto, mês a mês
# --------------------------------------------------------------------------
def paragrafos_do_evento(it: dict) -> list[str]:
    out = list(it.get("textos") or [])
    if it.get("eclipse") and it["eclipse"]["texto"]:
        out.append(it["eclipse"]["texto"])
    return out


# --------------------------------------------------------------------------
# Arquivo de agenda (.ics, RFC 5545)
# --------------------------------------------------------------------------
def _escapar(texto: str) -> str:
    return (texto.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _dobrar(linha_: str) -> list[str]:
    """Linhas de no máximo 75 octetos (a continuação começa com um espaço)."""
    out, atual = [], b""
    for ch in linha_:
        b = ch.encode("utf-8")
        if len(atual) + len(b) > (75 if not out else 74):
            out.append(atual.decode("utf-8"))
            atual = b""
        atual += b
    out.append(atual.decode("utf-8"))
    return [out[0]] + [" " + x for x in out[1:]]


def _uid(it: dict, fuso: str) -> str:
    """Estável entre downloads (reimportar não duplica) e sem dado nenhum da pessoa."""
    base = f"{it['tipo']}|{it['data']}|{it['hora']}|{it.get('signo', '')}|{fuso}"
    return hashlib.sha256(base.encode()).hexdigest()[:24] + "@valderez-astrologia"


def ics(cal: dict, link: str, agora: datetime | None = None) -> str:
    """O calendário inteiro para importar na agenda. `link` é o endereço da página
    (SITE_URL + token cifrado), o único jeito de voltar a ela."""
    agora = (agora or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stamp = agora.strftime("%Y%m%dT%H%M%SZ")
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Valderez Astrologia//A sua Lua no ano//PT",
              "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{_escapar(NOME_AGENDA)}",
              f"X-WR-TIMEZONE:{cal['fuso']}"]
    for it in eventos(cal):
        d = date.fromisoformat(it["data"])
        if it.get("ja_comecou"):
            continue  # começou antes do período: a volta direta já está no calendário
        titulo = f"{it['icone']} {it['titulo']} · {it['hora']}"
        if it.get("casa"):
            titulo += f" · casa {it['casa']}"
        corpo = paragrafos_do_evento(it)
        if it["tipo"] == "revolucao":
            corpo = [texto_principal(it, cal)]
        if it["tipo"] == "mercurio":
            corpo = [f"Retrógrado {it['periodo']} (volta a andar direto às {it['hora_fim']})."] + corpo
        descricao = "\n\n".join([c for c in corpo if c] + [f"Hora exata: {it['hora']} ({cal['fuso_nome']}).",
                                                            f"O seu calendário completo: {link}"])
        linhas += ["BEGIN:VEVENT", f"UID:{_uid(it, cal['fuso'])}", f"DTSTAMP:{stamp}",
                   f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
                   f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
                   f"SUMMARY:{_escapar(titulo)}", f"DESCRIPTION:{_escapar(descricao)}",
                   f"URL:{link}", "TRANSP:TRANSPARENT", "END:VEVENT"]
    linhas.append("END:VCALENDAR")
    return "\r\n".join(x for l in linhas for x in _dobrar(l)) + "\r\n"

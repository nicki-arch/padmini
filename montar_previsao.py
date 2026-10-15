"""
Padmini — "O seu ano" (rodada 13): do cálculo (`previsao.py`) ao relatório.

Os textos vêm do banco revisável (`conteudo/ocidental/textos/previsao/`, repositório
privado, via `montar_texto_ocidental.base`), nunca de IA. Aqui só se escolhe QUAL
texto vai em cada lugar e se monta o resumo, a linha do tempo mês a mês, as áreas,
os eclipses e a Revolução Solar.

Amostra (grátis): os TÍTULOS dos 3 temas e o começo do texto do primeiro; nada mais
sai do servidor (a regra da rodada 6: o texto pago nunca vai para o navegador).
"""

from datetime import date

import mapa_ocidental as mo
import montar_texto_ocidental as mt
import previsao as pv

ARQUIVOS = ("previsao/transitos", "previsao/casas", "previsao/eclipses", "previsao/revolucao",
            "previsao/pecas")

MESES_PT = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
            "setembro", "outubro", "novembro", "dezembro")
DO_PONTO = {"sol": "o seu Sol", "lua": "a sua Lua", "mercurio": "o seu Mercúrio", "venus": "a sua Vênus",
            "marte": "o seu Marte", "jupiter": "o seu Júpiter", "saturno": "o seu Saturno",
            "ascendente": "o seu Ascendente", "meio_do_ceu": "o seu Meio do Céu"}
ECLIPSE_PT = {"solar": "Eclipse solar", "lunar": "Eclipse lunar"}

# As áreas são as dimensões do mapa natal (catalogo.yaml), para a pessoa achar o
# mesmo assunto nos dois relatórios. Júpiter natal fica em Dinheiro e Saturno natal em
# Carreira, como na rodada 12 (docs/previsao.md).
AREA_DO_PONTO = {"sol": "essencia", "lua": "emocoes", "ascendente": "como-voce-chega",
                 "mercurio": "mente", "venus": "amor", "marte": "acao", "meio_do_ceu": "carreira",
                 "saturno": "carreira", "jupiter": "dinheiro"}
AREA_DA_CASA = {1: "como-voce-chega", 2: "dinheiro", 3: "mente", 4: "familia", 5: "amor", 6: "acao",
                7: "amor", 8: "dinheiro", 9: "proposito", 10: "carreira", 11: "proposito", 12: "emocoes"}


def _txt(arquivo: str, *chaves) -> str:
    no = mt.base(f"previsao/{arquivo}")
    for c in chaves:
        no = no[c]
    return mt._t(no)


def peca(nome: str) -> str:
    return _txt("pecas", nome)


def aviso(nome: str) -> str:
    return _txt("pecas", "avisos", nome)


def data_pt(d: date) -> str:
    return f"{d.day} de {MESES_PT[d.month - 1]} de {d.year}"


def mes_pt(ano: int, mes: int) -> str:
    return f"{MESES_PT[mes - 1]} de {ano}"


# --------------------------------------------------------------------------
# Peças de cada item
# --------------------------------------------------------------------------
def titulo_transito(t: dict) -> str:
    return f"{mo.PONTO_PT[t['planeta']]} em {mo.ASPECTO_PT[t['aspecto']]} com {DO_PONTO[t['ponto']]}"


def item_transito(t: dict) -> dict:
    return {"titulo": titulo_transito(t), "planeta": t["planeta"], "ponto": t["ponto"],
            "aspecto": t["aspecto"], "grupo": t["grupo"],
            "entra": t["entra"].isoformat(), "sai": t["sai"].isoformat(),
            "exatas": [x.isoformat() for x in t["exatas"]],
            "periodo": f"de {data_pt(t['entra'])} a {data_pt(t['sai'])}",
            "retrogrado": len(t["exatas"]) > 1,
            "texto": _txt("transitos", t["planeta"], t["ponto"], t["grupo"])}


def item_ingresso(i: dict) -> dict:
    return {"titulo": f"{mo.PONTO_PT[i['planeta']]} entra na sua casa {i['casa']}", "planeta": i["planeta"],
            "casa": i["casa"], "datas": [x.isoformat() for x in i["datas"]],
            "texto": _txt("casas", i["planeta"], i["casa"])}


def item_eclipse(e: dict) -> dict:
    sub = {"anular": "anular", "total": "total", "parcial": "parcial", "penumbral": "penumbral",
           "hibrido": "híbrido"}[e["subtipo"]]
    titulo = f"{ECLIPSE_PT[e['tipo']]} {sub} em {mo.SIGNO_PT[e['signo']]} {e['grau_texto']}"
    return {"titulo": titulo, "tipo": e["tipo"], "data": e["data"].isoformat(), "casa": e["casa"],
            "toca": [{"ponto": x["ponto"], "ponto_pt": mo.PONTO_PT[x["ponto"]], "orbe": x["orbe"]} for x in e["toca"]],
            "texto": _txt("eclipses", e["tipo"], e["casa"]) if e["casa"] else ""}


def item_revolucao(rs: dict | None) -> dict | None:
    if not rs:
        return None
    r = {"data": rs["data"].isoformat(), "titulo": f"Revolução Solar em {data_pt(rs['data'])}"}
    if "ascendente" in rs:
        r.update({"ascendente": rs["ascendente"], "ascendente_pt": mo.SIGNO_PT[rs["ascendente"]],
                  "casa_do_sol": rs["casa_do_sol"],
                  "texto_ascendente": _txt("revolucao", "ascendente", rs["ascendente"]),
                  "texto_sol": _txt("revolucao", "sol_casa", rs["casa_do_sol"])})
    else:
        r["aviso"] = aviso("sem_revolucao")
    return r


# --------------------------------------------------------------------------
# Linha do tempo e áreas
# --------------------------------------------------------------------------
def _meses(ini: date, fim: date) -> list[tuple[int, int]]:
    out, a, m = [], ini.year, ini.month
    while (a, m) <= (fim.year, fim.month):
        out.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def linha_do_tempo(p: dict) -> list[dict]:
    """Mês a mês: o que começa (entra na órbita ou na casa), o que está no auge (data
    exata, eclipse, Revolução Solar) e o que termina (sai da órbita)."""
    ini, fim = p["inicio"], p["fim"]
    meses = {am: {"comeca": [], "auge": [], "termina": []} for am in _meses(ini, fim)}

    def por(d: date, onde: str, rotulo: str):
        am = (d.year, d.month)
        if am in meses and rotulo not in meses[am][onde]:
            meses[am][onde].append(rotulo)

    for t in p["transitos"]:
        tit = titulo_transito(t)
        if t["entra"] >= ini:
            por(t["entra"], "comeca", tit)
        for x in t["exatas"]:
            por(x, "auge", tit)
        if t["sai"] <= fim:
            por(t["sai"], "termina", tit)
    for i in p["ingressos"]:
        for x in i["datas"]:
            por(x, "comeca", f"{mo.PONTO_PT[i['planeta']]} entra na sua casa {i['casa']}")
    for e in p["eclipses"]:
        por(e["data"], "auge", item_eclipse(e)["titulo"])
    if p["revolucao"]:
        por(p["revolucao"]["data"], "auge", "Revolução Solar (o seu aniversário)")
    return [{"mes": f"{a}-{m:02d}", "rotulo": mes_pt(a, m), **v} for (a, m), v in meses.items()]


def areas(p: dict) -> list[dict]:
    """Os trânsitos e ingressos agrupados pelas dimensões do mapa (na ordem do catálogo)."""
    import catalogo
    grupos: dict[str, list] = {}
    for t in sorted(p["transitos"], key=lambda t: -t["peso"]):
        grupos.setdefault(AREA_DO_PONTO[t["ponto"]], []).append(item_transito(t))
    for i in p["ingressos"]:
        grupos.setdefault(AREA_DA_CASA[i["casa"]], []).append(item_ingresso(i))
    out = []
    for d in catalogo.dimensoes_mapa():
        if d["chave"] in grupos:
            out.append({"chave": d["chave"], "nome": d["nome"], "itens": grupos[d["chave"]]})
    return out


# --------------------------------------------------------------------------
# Relatório inteiro e amostra
# --------------------------------------------------------------------------
def avisos(p: dict) -> list[str]:
    out = []
    if not p["tem_hora"]:
        out.append(aviso("sem_hora"))
    if any(len(t["exatas"]) > 1 for t in p["transitos"]):
        out.append(aviso("retrogradacao"))
    return out


def completo(p: dict) -> dict:
    return {
        "inicio": p["inicio"].isoformat(), "fim": p["fim"].isoformat(), "tem_hora": p["tem_hora"],
        "periodo": f"de {data_pt(p['inicio'])} a {data_pt(p['fim'])}",
        "abertura": peca("abertura"), "como_ler": peca("como_ler"), "avisos": avisos(p),
        "intro": {k: peca(k) for k in ("temas", "linha_do_tempo", "areas", "eclipses", "revolucao")},
        "temas": [item_transito(t) for t in p["temas"]],
        "linha_do_tempo": linha_do_tempo(p),
        "areas": areas(p),
        "eclipses": [item_eclipse(e) for e in p["eclipses"]],
        "revolucao": item_revolucao(p["revolucao"]),
        "fechamento": peca("fechamento"),
    }


def amostra(p: dict) -> dict:
    """A amostra grátis inteira (o que vai por e-mail): os títulos e períodos dos 3 temas
    e o texto do PRIMEIRO. Os textos dos outros dois e todo o resto são pagos."""
    temas = [item_transito(t) for t in p["temas"]]
    return {
        "inicio": p["inicio"].isoformat(), "fim": p["fim"].isoformat(), "tem_hora": p["tem_hora"],
        "periodo": f"de {data_pt(p['inicio'])} a {data_pt(p['fim'])}",
        "abertura": peca("abertura"), "avisos": [aviso("sem_hora")] if not p["tem_hora"] else [],
        "temas": [{"titulo": t["titulo"], "periodo": t["periodo"], "planeta": t["planeta"],
                   "ponto": t["ponto"], "grupo": t["grupo"]} for t in temas],
        "trecho": mt.trecho(temas[0]["texto"]) if temas else "",
        "texto": temas[0]["texto"] if temas else "",
        "contagem": {"transitos": len(p["transitos"]), "eclipses": len(p["eclipses"]),
                     "meses": len(_meses(p["inicio"], p["fim"]))},
    }


def tela(a: dict) -> dict:
    """O que a página mostra da amostra (o resto vai por e-mail): sem o texto inteiro."""
    return {k: v for k, v in a.items() if k != "texto"}


def secoes(p: dict) -> dict[str, list[str]]:
    """O relatório em texto corrido (o PDF): {título da seção: [parágrafos]}. Um
    parágrafo que começa com "## " é um subtítulo (título do item + período)."""
    c = completo(p)
    s = {"O seu ano": [c["abertura"]] + c["avisos"] + [c["como_ler"]]}
    s["Os temas do seu ano"] = [c["intro"]["temas"]] + [
        x for t in c["temas"] for x in (f"## {t['titulo']} · {t['periodo']}", t["texto"])]
    s["Mês a mês"] = [c["intro"]["linha_do_tempo"]]
    for m in c["linha_do_tempo"]:
        partes = [(r, m[k]) for r, k in (("Começa", "comeca"), ("No auge", "auge"), ("Termina", "termina")) if m[k]]
        if partes:
            s["Mês a mês"].append(f"## {m['rotulo'].capitalize()}")
            s["Mês a mês"] += [f"{r}: {'; '.join(itens)}." for r, itens in partes]
    s["Por área da vida"] = [c["intro"]["areas"]]
    for a in c["areas"]:
        for i in a["itens"]:
            quando = i.get("periodo") or ", ".join(data_pt(date.fromisoformat(d)) for d in i["datas"])
            s["Por área da vida"] += [f"## {a['nome']}: {i['titulo']} · {quando}", i["texto"]]
    if c["eclipses"]:
        s["Eclipses"] = [c["intro"]["eclipses"]]
        for e in c["eclipses"]:
            toca = (" · toca " + ", ".join(f"o seu {x['ponto_pt']}" for x in e["toca"])) if e["toca"] else ""
            onde = f" · na sua casa {e['casa']}" if e["casa"] else ""
            s["Eclipses"].append(f"## {e['titulo']} · {data_pt(date.fromisoformat(e['data']))}{onde}{toca}")
            if e["texto"]:
                s["Eclipses"].append(e["texto"])
    rs = c["revolucao"]
    if rs:
        s["Revolução Solar"] = [c["intro"]["revolucao"], f"## {rs['titulo']}"] + (
            [f"## Ascendente da Revolução em {rs['ascendente_pt']}", rs["texto_ascendente"],
             f"## O Sol na casa {rs['casa_do_sol']} da Revolução", rs["texto_sol"]]
            if "ascendente" in rs else [rs["aviso"]])
    s["Para fechar"] = [c["fechamento"]]
    return s

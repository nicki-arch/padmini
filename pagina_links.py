"""
Valderez Astrologia — a página /links, o link da bio (rodada 19).

A bio de cada rede aponta para /links?utm_source=<rede>. O que importa aqui é a
ORIGEM: a página repassa ref, cupom e utm_* para todos os botões internos, no HTML
montado no servidor (não por JavaScript), para a origem chegar ao /mapa mesmo sem o
aceite de cookies. De lá, o afiliado.js guarda na sessão e os formulários gravam em
`amostras_email.origem`, `leads.origem` e, no checkout, `pedidos.rastreio`.

  - utm_source que vier; sem ele, "links";
  - utm_medium=bio e utm_campaign=links quando não vierem;
  - os outros campos de ORIGEM_ACEITA (ref, cupom, utm_content, utm_term), se vierem.

Os botões saem do catálogo: ligar um produto no catalogo.yaml faz ele aparecer aqui.
"""
from html import escape
from urllib.parse import urlencode

import catalogo
from rotas_ocidental import ORIGEM_ACEITA

PADRAO = {"utm_source": "links", "utm_medium": "bio", "utm_campaign": "links"}
MAX_EM_BREVE = 2
# A foto da Dona Valderez (o rosto, rodada 19.1); sem o arquivo, a roda no arco
# (marca.retrato), como em todos os outros lugares.
VAGA_FOTO = "foto-valderez-rosto"


def origem(params) -> dict:
    """A origem que segue para os botões: os campos aceitos (curtos) + os padrões."""
    o = {k: str(params.get(k)).strip()[:80] for k in ORIGEM_ACEITA if str(params.get(k) or "").strip()}
    return {**{k: v for k, v in PADRAO.items() if k not in o}, **o}


def sufixo(o: dict) -> str:
    """'?utm_source=…&utm_medium=…' na ordem de sempre (fonte, meio, campanha, o resto),
    já escapado para ir num atributo HTML."""
    ordem = [k for k in ("utm_source", "utm_medium", "utm_campaign") if k in o]
    ordem += [k for k in ORIGEM_ACEITA if k in o and k not in ordem]
    return escape("?" + urlencode([(k, o[k]) for k in ordem])) if ordem else ""


def botoes(t: dict, captura: bool) -> dict:
    """O que a página mostra, já filtrado pelo catálogo:
    {"principal": {...}, "kits": [...à venda], "produtos": [...ativos que vendem], "em_breve": [...até 2]}.
    O kit (rodada 20) vem logo abaixo do principal, só quando `catalogo.vende` (o kit ativo e
    os produtos dele à venda); leva à `entrada` dele (o /mapa), onde a compra começa."""
    principal = dict(t["principal_lista"] if captura else t["principal"],
                     rota="/lista" if captura else "/mapa", destino="lista" if captura else "mapa_gratis")
    tk = catalogo.textos()["kit"]
    kits = [] if captura else [
        {"chave": p["chave"], "rota": p["entrada"], "oferta": p["oferta"],
         "titulo": tk.get("links_titulo") or p["nome"], "linha": tk.get("links_linha") or p["resumo"]}
        for p in catalogo.kits_a_venda()]
    textos = t.get("produtos") or {}
    produtos, breve = [], []
    for p in catalogo.visiveis():
        copy = textos.get(p["chave"]) or {}
        item = {"chave": p["chave"], "rota": p["rota"], "oferta": p.get("oferta") or p["chave"],
                "titulo": copy.get("titulo") or p["nome"], "linha": copy.get("linha") or p.get("resumo", "")}
        if p["estado"] == "ativo" and catalogo.vende(p["chave"]) and not captura:
            produtos.append(item)
        elif p["estado"] == "em_breve" and len(breve) < MAX_EM_BREVE:
            breve.append(item)
    return {"principal": principal, "kits": kits, "produtos": produtos, "em_breve": breve}

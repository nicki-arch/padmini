"""
Valderez Astrologia (versão ocidental da Padmini) — dados estruturados (JSON-LD, schema.org) para o
buscador (round 5). Só o que é verdade na página: quem somos (Organization),
o site (WebSite) e as perguntas da home (FAQPage), tiradas do mesmo YAML que a
página mostra. Nada de nota/avaliação (não temos avaliações públicas).
"""
import json
import re

SITE = "https://padmini.com.br"


def _texto(t: str) -> str:
    return re.sub(r"<[^>]+>", "", str(t)).strip()


def _script(dados: dict) -> str:
    # "</" escapado: o JSON não fecha o <script> antes da hora
    corpo = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{corpo}</script>'


def home(t: dict) -> str:
    """O bloco da home ocidental, a partir de conteudo/ocidental/home.yaml."""
    return _script({"@context": "https://schema.org", "@graph": [
        {"@type": "Organization", "@id": f"{SITE}/#org", "name": "Valderez Astrologia", "url": f"{SITE}/",
         "logo": f"{SITE}/static/og-oc-home.png", "description": _texto(t["seo"]["descricao"])},
        {"@type": "WebSite", "@id": f"{SITE}/#site", "name": "Valderez Astrologia", "url": f"{SITE}/",
         "inLanguage": "pt-BR", "publisher": {"@id": f"{SITE}/#org"}},
        {"@type": "FAQPage", "@id": f"{SITE}/#perguntas", "mainEntity": [
            {"@type": "Question", "name": _texto(i["pergunta"]),
             "acceptedAnswer": {"@type": "Answer", "text": _texto(i["resposta"])}}
            for i in t["faq"]["itens"]]},
    ]})

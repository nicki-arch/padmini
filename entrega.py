"""
Padmini — entrega do relatório completo.

Monta o link assinado do completo (a partir dos dados de nascimento) e envia
o e-mail. Usado pelo webhook da Cakto após o pagamento aprovado.

E-mail: envia via Resend se RESEND_API_KEY estiver setado; caso contrário,
não envia e devolve False (o chamador registra o link para envio manual).
"""

import html
import json
import re
import os
import urllib.parse
import urllib.request

import acesso
import paleta
import sistema as _sistema

SITE_URL = os.environ.get("PADMINI_SITE_URL", "https://padmini.com.br").rstrip("/")


def link_completo(produto: str, dados: dict, sistema: str = "vedica") -> str:
    """Monta a URL do completo (com token) para o e-mail. produto: 'mapa'|'compat'.
    As rotas são as mesmas nas duas versões: é o token que diz qual versão abrir."""
    if produto == "mapa":
        chave = acesso.chave_mapa(dados["data"], dados["hora"], dados["lat"], dados["lon"])
        token = acesso.emitir_token("mapa", chave, sistema)
        q = {"data": dados["data"], "hora": dados["hora"], "lat": dados["lat"], "lon": dados["lon"],
             "cidade": dados.get("cidade", ""), "nome": dados.get("nome", ""), "token": token}
        return f"{SITE_URL}/mapa?" + urllib.parse.urlencode(q)
    if produto == "compat":
        a, b = dados["a"], dados["b"]
        chave = acesso.chave_compat((a["data"], a["hora"], a["lat"], a["lon"]),
                                    (b["data"], b["hora"], b["lat"], b["lon"]))
        token = acesso.emitir_token("compat", chave, sistema)
        q = {"token": token}
        for prefixo, pe in (("a", a), ("b", b)):
            for k in ("nome", "data", "hora", "lat", "lon", "cidade"):
                q[f"{prefixo}_{k}"] = pe.get(k, "")
        return f"{SITE_URL}/compatibilidade?" + urllib.parse.urlencode(q)
    if produto == "numerologia":
        import numerologia
        chave = acesso.chave_numerologia(numerologia.normalizar_nome(dados["nome"]), dados["data"])
        q = {"nome": dados["nome"], "data": dados["data"], "token": acesso.emitir_token(produto, chave, sistema)}
        return f"{SITE_URL}/numerologia?" + urllib.parse.urlencode(q)
    if produto == "tarot":
        chave = acesso.chave_tarot(dados["tiragem"])
        q = {"t": dados["tiragem"], "token": acesso.emitir_token(produto, chave, sistema)}
        return f"{SITE_URL}/tarot?" + urllib.parse.urlencode(q)
    raise ValueError(f"produto inválido: {produto}")


def _ola(nome: str) -> str:
    # O nome vem do `sck`, que o comprador escreve (dá para editar na URL do
    # checkout): escapado para não virar HTML/link falso no e-mail com a nossa marca.
    nome = html.escape(str(nome or "").strip()[:40])
    return f"Olá{(' ' + nome) if nome else ''},"


TITULO_EMAIL = {
    "vedica": {"compat": "seu relatório de compatibilidade", "mapa": "seu mapa completo"},
    "ocidental": {"compat": "a sinastria de vocês", "mapa": "seu mapa natal completo",
                  "numerologia": "a sua numerologia completa", "tarot": "a leitura completa da sua tiragem"},
}


def marca_do_email(c: dict, sistema: str) -> str:
    """O topo de todo e-mail: o nome da marca da versão (sistema.MARCA) e a marca
    `<!-- versao:… -->`, que o enviar_email lê para pôr o mesmo nome no remetente."""
    # a védica sai byte a byte como antes (foto em testes/dados/vedica_html): sem a marca
    versao = "" if sistema == "vedica" else f"<!-- versao:{sistema} -->"
    return (f'{versao}<p style="font-family:{c["fonte_marca"]};font-size:24px;'
            f'color:{c["acento"]};margin:0 0 18px">{_sistema.MARCA[sistema]}</p>')


# ---------------------------------------------------------------------------
# Ocidental (rodada 9, tela Sistema-Emails): a mesma casca em todo e-mail — a roda
# e o nome no topo, o conteúdo num cartão branco, a assinatura embaixo. A roda e as
# capas vêm do próprio site (SITE_URL). A védica continua com o HTML de sempre.
# ---------------------------------------------------------------------------
CAPA_DO_PRODUTO = {"mapa": "capa-mapa", "compat": "capa-amor", "numerologia": "capa-numerologia",
                   "tarot": "capa-tarot", "mapas_casal": "capa-mapa"}


def assinatura(sistema: str) -> str:
    """A linha de assinatura. Na ocidental, a frase sobre a Dona Valderez que é
    verdade hoje (revisao.yaml, regra de honestidade)."""
    if sistema != "ocidental":
        return _sistema.ASSINATURA_EMAIL[sistema]
    import textos
    return f"Valderez Astrologia · {textos.frase_revisao('email')}"


def capa_email(produto: str) -> str:
    import ilustracoes
    vaga = CAPA_DO_PRODUTO.get(produto.split(":")[-1], "capa-mapa")
    url = ilustracoes.url(vaga)
    return (f'<img src="{SITE_URL}{url}" alt="" width="100%" style="width:100%;max-width:520px;height:auto;'
            f'border-radius:12px;display:block;margin:0 0 18px">' if url else "")


def casca_ocidental(corpo: str, rodape: str = "") -> str:
    c = paleta.email("ocidental")
    return f"""<!-- versao:ocidental --><div style="font-family:{c['fonte']};background:{c['fundo']};color:{c['texto']};padding:28px 0 26px;border-radius:18px;max-width:600px;margin:auto">
  <div style="text-align:center;padding:0 24px 14px"><img src="{SITE_URL}/static/valderez/favicon-192.png" width="44" height="44" alt="" style="vertical-align:middle;margin-right:10px"><span style="display:inline-block;vertical-align:middle;text-align:left"><span style="font-family:{c['fonte_marca']};font-size:26px;line-height:1;color:{c['texto']}">Valderez</span><br><span style="font-size:10px;letter-spacing:4px;color:{c['ouro']}">ASTROLOGIA</span></span></div>
  <div style="margin:8px 20px 20px;background:{c['cartao']};border-radius:16px;padding:28px 30px">
  {corpo}
  </div>
  <p style="padding:0 32px;margin:0;font-size:12px;line-height:1.6;color:{c['fraco']};text-align:center">{assinatura("ocidental")}{rodape}<br><a href="{SITE_URL}/privacidade" style="color:{c['fraco']}">Privacidade</a></p>
</div>"""


def titulo_email(texto: str) -> str:
    c = paleta.email("ocidental")
    return f'<h1 style="font-family:{c["fonte_marca"]};font-weight:500;font-size:28px;line-height:1.15;margin:0 0 14px;color:{c["texto"]}">{texto}</h1>'


def email_completo_html(produto: str, link: str, nome: str = "", extra: str = "",
                        sistema: str = "vedica") -> str:
    """`extra`: HTML já pronto (e escapado) a acrescentar, ex.: a venda cruzada.
    Cores e fontes: paleta.email(sistema)."""
    c = paleta.email(sistema)
    if sistema == "ocidental":
        titulo = TITULO_EMAIL[sistema].get(produto) or TITULO_EMAIL[sistema]["mapa"]
        primeiro = html.escape(str(nome or "").strip().split(" ")[0][:40]) if str(nome or "").strip() else ""
        link = html.escape(link, quote=True)
        pronto = "pronto" if produto == "mapa" else "pronta"  # a sinastria, a numerologia, a leitura
        corpo = (titulo_email(f"{titulo[0].upper()}{titulo[1:]} está <em style=\"color:{c['acento']}\">{pronto}</em>"
                              f"{', ' + primeiro if primeiro else ''}")
                 + f'<p style="margin:0 0 18px;color:{c["suave"]}">Seu pagamento foi confirmado. A sua leitura completa já está aberta.</p>'
                 + capa_email(produto)
                 + f'<p style="margin:0 0 18px;text-align:center"><a href="{link}" style="{estilo_botao(c)}">Abrir minha leitura completa</a></p>'
                 + f'<p style="color:{c["fraco"]};font-size:12px;margin:0 0 4px">Se o botão não abrir, copie e cole este link no navegador:</p>'
                 + f'<p style="color:{c["fraco"]};font-size:12px;word-break:break-all;margin:0">{link}</p>'
                 + extra + _linha_minhas_leituras(sistema, c))
        return casca_ocidental(corpo, " · Este link é pessoal; não o compartilhe.")
    marca = marca_do_email(c, sistema)
    titulo = TITULO_EMAIL[sistema].get(produto) or TITULO_EMAIL[sistema]["mapa"]
    assinatura = _sistema.ASSINATURA_EMAIL[sistema]
    ola = _ola(nome)
    link = html.escape(link, quote=True)
    return f"""<div style="font-family:{c['fonte']};background:{c['fundo']};color:{c['texto']};padding:32px;border-radius:12px;max-width:520px;margin:auto">
  {marca}
  <p style="margin:0 0 12px">{ola}</p>
  <p style="margin:0 0 8px">Seu pagamento foi confirmado — {titulo} está pronto.</p>
  <p style="margin:26px 0"><a href="{link}" style="{estilo_botao(c)}">Ver meu relatório completo →</a></p>
  <p style="color:{c['suave']};font-size:13px;margin:0 0 4px">Se o botão não abrir, copie e cole este link no navegador:</p>
  <p style="color:{c['suave']};font-size:12px;word-break:break-all;margin:0">{link}</p>
  {extra}{_linha_minhas_leituras(sistema, c)}
  <p style="color:{c['fraco']};font-size:12px;margin-top:26px">{assinatura} Este link é pessoal; não o compartilhe.</p>
</div>"""


def _linha_minhas_leituras(sistema: str, c: dict) -> str:
    """Rodada 6 (só ocidental): onde pedir de novo os links, se este e-mail se perder."""
    if sistema != "ocidental":
        return ""
    return (f'<p style="color:{c["suave"]};font-size:13px;margin:22px 0 0">Perdeu este e-mail? Em '
            f'<a href="{SITE_URL}/minhas-leituras" style="color:{c["acento"]}">{SITE_URL.split("//")[-1]}/minhas-leituras</a> '
            f'você recebe de novo os links de todas as suas leituras.</p>')


def estilo_botao(c: dict) -> str:
    """O botão dos e-mails (o mesmo em todos), nas cores de `c` = paleta.email(versão)."""
    return (f"background:{c['acento']};color:{c['sobre_acento']};text-decoration:none;padding:14px 26px;"
            f"border-radius:{c['raio_botao']};font-weight:bold;display:inline-block")


def email_mapas_do_casal_html(links: list, nome: str = "", sistema: str = "vedica") -> str:
    """links: [(nome da pessoa, link do mapa completo), ...]"""
    c = paleta.email(sistema)
    marca = marca_do_email(c, sistema)
    assinatura = _sistema.ASSINATURA_EMAIL[sistema]
    ola = _ola(nome)
    links = [(html.escape(str(pessoa)[:40]), html.escape(l, quote=True)) for pessoa, l in links]
    if sistema == "ocidental":
        botoes = "".join(
            f'<p style="margin:16px 0 4px"><a href="{l}" style="{estilo_botao(c)}">Mapa natal de {pessoa}</a></p>'
            f'<p style="color:{c["fraco"]};font-size:12px;word-break:break-all;margin:0 0 8px">{l}</p>' for pessoa, l in links)
        corpo = (titulo_email(f"Os mapas natais de vocês estão <em style=\"color:{c['acento']}\">prontos</em>")
                 + f'<p style="margin:0 0 12px">{ola}</p>'
                 + f'<p style="margin:0 0 8px;color:{c["suave"]}">Um mapa para cada pessoa, cada um com o seu link.</p>'
                 + capa_email("mapa") + botoes + _linha_minhas_leituras(sistema, c))
        return casca_ocidental(corpo, " · Estes links são pessoais; não os compartilhe.")
    botoes = "".join(
        f'<p style="margin:18px 0"><a href="{l}" style="{estilo_botao(c)}">Mapa de {pessoa} →</a></p>'
        f'<p style="color:{c["suave"]};font-size:12px;word-break:break-all;margin:0 0 8px">{l}</p>'
        for pessoa, l in links)
    return f"""<div style="font-family:{c['fonte']};background:{c['fundo']};color:{c['texto']};padding:32px;border-radius:12px;max-width:520px;margin:auto">
  {marca}
  <p style="margin:0 0 12px">{ola}</p>
  <p style="margin:0 0 8px">Os mapas individuais de vocês dois estão prontos — um para cada pessoa.</p>
  {botoes}{_linha_minhas_leituras(sistema, c)}
  <p style="color:{c['fraco']};font-size:12px;margin-top:26px">{assinatura} Estes links são pessoais; não os compartilhe.</p>
</div>"""


# Nomes das leituras no e-mail de "minhas leituras". O `produto` do pedido é
# "mapa", "compat" ou "mapas_casal" na védica e "ocidental:<produto>" na ocidental.
NOME_LEITURA = {
    "vedica": {"mapa": "Mapa védico", "compat": "Compatibilidade do casal", "mapas_casal": "Mapas védicos do casal"},
    "ocidental": {"mapa": "Mapa natal", "compat": "Sinastria do casal", "numerologia": "Numerologia",
                  "tarot": "Tarot", "mapas_casal": "Mapas natais do casal"},
}


def nome_da_leitura(produto: str) -> str:
    versao, _, nome = produto.partition(":") if ":" in produto else ("vedica", "", produto)
    return NOME_LEITURA.get(versao, {}).get(nome, f"Leitura {_sistema.MARCA.get(versao, 'Padmini')}")


def email_minhas_leituras_html(leituras: list[dict]) -> str:
    """Todas as leituras compradas por um e-mail, cada uma com o seu link (que
    abre na versão em que foi comprada). leituras: [{produto, criado_em, link}]."""
    c = paleta.email("ocidental")
    marca = marca_do_email(c, "ocidental")
    blocos = []
    for item in leituras:
        links = [l for l in str(item["link"]).split("\n") if l.strip()]
        quando = item["criado_em"].strftime("%d/%m/%Y") if hasattr(item["criado_em"], "strftime") else ""
        titulo = html.escape(nome_da_leitura(item["produto"]))
        botoes = "".join(
            f'<p style="margin:10px 0"><a href="{html.escape(l, quote=True)}" style="{estilo_botao(c)}">'
            f'{"Abrir" if len(links) == 1 else f"Abrir o {i} de {len(links)}"} →</a></p>'
            for i, l in enumerate(links, 1))
        blocos.append(f'<div style="border-top:1px solid {c["linha"]};padding:16px 0 6px">'
                      f'<p style="margin:0;font-family:{c["fonte_marca"]};font-size:19px">{titulo}</p>'
                      f'<p style="margin:2px 0 6px;color:{c["suave"]};font-size:13px">Comprada em {quando}</p>{botoes}</div>')
    corpo = (titulo_email(f"Os links das suas <em style=\"color:{c['acento']}\">leituras</em>")
             + f'<p style="margin:0 0 18px;color:{c["suave"]}">Você pediu os links de novo. Aqui estão todas as leituras compradas com este e-mail:</p>'
             + "".join(blocos)
             + f'<p style="color:{c["fraco"]};font-size:13px;margin:22px 0 0">Não foi você que pediu? Pode ignorar este e-mail: os links só chegam aqui, na sua caixa.</p>')
    return casca_ocidental(corpo, " · Estes links são pessoais; não os compartilhe.")


def remetente_do_email(html_do_email: str = "") -> str:
    """O "De:" do e-mail. O endereço é sempre o de PADMINI_EMAIL_FROM (domínio
    atual, já verificado no Resend: não mexe em DNS); só o NOME que aparece para
    quem recebe segue a versão do e-mail (a marca `<!-- versao:… -->` do topo):
    "Valderez Astrologia <…>" na ocidental, o de sempre na védica."""
    padrao = os.environ.get("PADMINI_EMAIL_FROM", "Padmini <nao-responda@padmini.com.br>")
    m = re.search(r"<!-- versao:(\w+) -->", html_do_email or "")
    if not m or m.group(1) == "vedica" or m.group(1) not in _sistema.MARCA:
        return padrao
    endereco = re.search(r"<([^<>@\s]+@[^<>\s]+)>", padrao)
    endereco = endereco.group(1) if endereco else padrao.strip()
    return f"{_sistema.MARCA[m.group(1)]} <{endereco}>"


def enviar_email(destino: str, assunto: str, html: str, responder_para: str | None = None) -> bool:
    """Envia via Resend (RESEND_API_KEY). Retorna True se enviou; False se não configurado/falhou.
    `responder_para`: o Reply-To (campo `reply_to` da API do Resend), para e-mails que
    convidam a responder — o remetente padrão é nao-responda@."""
    chave = os.environ.get("RESEND_API_KEY")
    remetente = remetente_do_email(html)
    if not chave or not destino:
        return False
    corpo = {"from": remetente, "to": [destino], "subject": assunto, "html": html}
    if responder_para:
        corpo["reply_to"] = responder_para
    payload = json.dumps(corpo).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails", data=payload,
        headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception:
        return False

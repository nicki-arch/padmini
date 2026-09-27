"""
Padmini — entrega do relatório completo.

Monta o link assinado do completo (a partir dos dados de nascimento) e envia
o e-mail. Usado pelo webhook da Cakto após o pagamento aprovado.

E-mail: envia via Resend se RESEND_API_KEY estiver setado; caso contrário,
não envia e devolve False (o chamador registra o link para envio manual).
"""

import html
import json
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


def email_completo_html(produto: str, link: str, nome: str = "", extra: str = "",
                        sistema: str = "vedica") -> str:
    """`extra`: HTML já pronto (e escapado) a acrescentar, ex.: a venda cruzada.
    Cores e fontes: paleta.email(sistema)."""
    c = paleta.email(sistema)
    titulo = TITULO_EMAIL[sistema].get(produto) or TITULO_EMAIL[sistema]["mapa"]
    assinatura = _sistema.ASSINATURA_EMAIL[sistema]
    ola = _ola(nome)
    link = html.escape(link, quote=True)
    return f"""<div style="font-family:{c['fonte']};background:{c['fundo']};color:{c['texto']};padding:32px;border-radius:12px;max-width:520px;margin:auto">
  <p style="font-family:{c['fonte_marca']};font-size:24px;color:{c['acento']};margin:0 0 18px">Padmini</p>
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
    assinatura = _sistema.ASSINATURA_EMAIL[sistema]
    ola = _ola(nome)
    links = [(html.escape(str(pessoa)[:40]), html.escape(l, quote=True)) for pessoa, l in links]
    botoes = "".join(
        f'<p style="margin:18px 0"><a href="{l}" style="{estilo_botao(c)}">Mapa de {pessoa} →</a></p>'
        f'<p style="color:{c["suave"]};font-size:12px;word-break:break-all;margin:0 0 8px">{l}</p>'
        for pessoa, l in links)
    return f"""<div style="font-family:{c['fonte']};background:{c['fundo']};color:{c['texto']};padding:32px;border-radius:12px;max-width:520px;margin:auto">
  <p style="font-family:{c['fonte_marca']};font-size:24px;color:{c['acento']};margin:0 0 18px">Padmini</p>
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
    return NOME_LEITURA.get(versao, {}).get(nome, "Leitura Padmini")


def email_minhas_leituras_html(leituras: list[dict]) -> str:
    """Todas as leituras compradas por um e-mail, cada uma com o seu link (que
    abre na versão em que foi comprada). leituras: [{produto, criado_em, link}]."""
    c = paleta.email("ocidental")
    blocos = []
    for item in leituras:
        links = [l for l in str(item["link"]).split("\n") if l.strip()]
        quando = item["criado_em"].strftime("%d/%m/%Y") if hasattr(item["criado_em"], "strftime") else ""
        titulo = html.escape(nome_da_leitura(item["produto"]))
        botoes = "".join(
            f'<p style="margin:10px 0"><a href="{html.escape(l, quote=True)}" style="{estilo_botao(c)}">'
            f'{"Abrir" if len(links) == 1 else f"Abrir o {i} de {len(links)}"} →</a></p>'
            for i, l in enumerate(links, 1))
        blocos.append(f'<div style="border-top:1px solid {c["fraco"]};padding:16px 0 6px">'
                      f'<p style="margin:0;font-family:{c["fonte_marca"]};font-size:19px">{titulo}</p>'
                      f'<p style="margin:2px 0 6px;color:{c["suave"]};font-size:13px">Comprada em {quando}</p>{botoes}</div>')
    return f"""<div style="font-family:{c['fonte']};background:{c['fundo']};color:{c['texto']};padding:32px;border-radius:12px;max-width:520px;margin:auto">
  <p style="font-family:{c['fonte_marca']};font-size:24px;color:{c['acento']};margin:0 0 18px">Padmini</p>
  <p style="margin:0 0 12px">Olá,</p>
  <p style="margin:0 0 18px">Você pediu os links das suas leituras. Aqui estão todas as que foram compradas com este e-mail:</p>
  {"".join(blocos)}
  <p style="color:{c['suave']};font-size:13px;margin:22px 0 0">Não foi você que pediu? Pode ignorar este e-mail: os links só chegam aqui, na sua caixa.</p>
  <p style="color:{c['fraco']};font-size:12px;margin-top:26px">{_sistema.ASSINATURA_EMAIL["ocidental"]} Estes links são pessoais; não os compartilhe.</p>
</div>"""


def enviar_email(destino: str, assunto: str, html: str) -> bool:
    """Envia via Resend (RESEND_API_KEY). Retorna True se enviou; False se não configurado/falhou."""
    chave = os.environ.get("RESEND_API_KEY")
    remetente = os.environ.get("PADMINI_EMAIL_FROM", "Padmini <nao-responda@padmini.com.br>")
    if not chave or not destino:
        return False
    payload = json.dumps({"from": remetente, "to": [destino], "subject": assunto, "html": html}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails", data=payload,
        headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception:
        return False

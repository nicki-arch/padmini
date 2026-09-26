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
    raise ValueError(f"produto inválido: {produto}")


def _ola(nome: str) -> str:
    # O nome vem do `sck`, que o comprador escreve (dá para editar na URL do
    # checkout): escapado para não virar HTML/link falso no e-mail com a nossa marca.
    nome = html.escape(str(nome or "").strip()[:40])
    return f"Olá{(' ' + nome) if nome else ''},"


TITULO_EMAIL = {
    "vedica": {"compat": "seu relatório de compatibilidade", "mapa": "seu mapa completo"},
    "ocidental": {"compat": "a sinastria de vocês", "mapa": "seu mapa natal completo"},
}


def email_completo_html(produto: str, link: str, nome: str = "", extra: str = "",
                        sistema: str = "vedica") -> str:
    """`extra`: HTML já pronto (e escapado) a acrescentar, ex.: a venda cruzada."""
    titulo = TITULO_EMAIL[sistema]["compat" if produto == "compat" else "mapa"]
    assinatura = _sistema.ASSINATURA_EMAIL[sistema]
    ola = _ola(nome)
    link = html.escape(link, quote=True)
    return f"""<div style="font-family:Arial,Helvetica,sans-serif;background:#241522;color:#f4e9dc;padding:32px;border-radius:12px;max-width:520px;margin:auto">
  <p style="font-family:Georgia,serif;font-size:24px;color:#e7a24a;margin:0 0 18px">Padmini</p>
  <p style="margin:0 0 12px">{ola}</p>
  <p style="margin:0 0 8px">Seu pagamento foi confirmado — {titulo} está pronto.</p>
  <p style="margin:26px 0"><a href="{link}" style="background:#e7a24a;color:#2a1608;text-decoration:none;padding:14px 26px;border-radius:999px;font-weight:bold;display:inline-block">Ver meu relatório completo →</a></p>
  <p style="color:#c9b1a6;font-size:13px;margin:0 0 4px">Se o botão não abrir, copie e cole este link no navegador:</p>
  <p style="color:#c9b1a6;font-size:12px;word-break:break-all;margin:0">{link}</p>
  {extra}
  <p style="color:#8f7a76;font-size:12px;margin-top:26px">{assinatura} Este link é pessoal; não o compartilhe.</p>
</div>"""


def email_mapas_do_casal_html(links: list, nome: str = "", sistema: str = "vedica") -> str:
    """links: [(nome da pessoa, link do mapa completo), ...]"""
    assinatura = _sistema.ASSINATURA_EMAIL[sistema]
    ola = _ola(nome)
    links = [(html.escape(str(pessoa)[:40]), html.escape(l, quote=True)) for pessoa, l in links]
    botoes = "".join(
        f'<p style="margin:18px 0"><a href="{l}" style="background:#e7a24a;color:#2a1608;text-decoration:none;'
        f'padding:14px 26px;border-radius:999px;font-weight:bold;display:inline-block">Mapa de {pessoa} →</a></p>'
        f'<p style="color:#c9b1a6;font-size:12px;word-break:break-all;margin:0 0 8px">{l}</p>'
        for pessoa, l in links)
    return f"""<div style="font-family:Arial,Helvetica,sans-serif;background:#241522;color:#f4e9dc;padding:32px;border-radius:12px;max-width:520px;margin:auto">
  <p style="font-family:Georgia,serif;font-size:24px;color:#e7a24a;margin:0 0 18px">Padmini</p>
  <p style="margin:0 0 12px">{ola}</p>
  <p style="margin:0 0 8px">Os mapas individuais de vocês dois estão prontos — um para cada pessoa.</p>
  {botoes}
  <p style="color:#8f7a76;font-size:12px;margin-top:26px">{assinatura} Estes links são pessoais; não os compartilhe.</p>
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

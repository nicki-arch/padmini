"""
Padmini — e-mails que trazem a venda de volta.

  1. Amostra por e-mail: quem gerou a amostra grátis pode recebê-la no e-mail,
     já com o botão de compra (checkout da Cakto com os dados de nascimento no
     `sck`, igual ao botão do site).
  2. Lembrete: se a pessoa AUTORIZOU, um único lembrete 24–72h depois, se não
     comprou (disparado por `/api/tarefas/lembretes`, chamado pelo GitHub Actions).
  3. Carrinho abandonado: evento `checkout_abandonment` da Cakto → um e-mail de
     recuperação por pessoa e oferta.
  4. Venda cruzada: o e-mail de entrega do completo oferece o outro produto.

Todo e-mail de marketing (2 e 3) tem link de descadastro assinado; quem se
descadastra não recebe mais nenhum (tabela `email_optout`). O e-mail da
amostra (1) é resposta a um pedido da própria pessoa, e o de entrega é da compra.
"""

import hashlib
import hmac
import html
import os
import urllib.parse

import acesso
import entrega
import ofertas
import sistema as _sistema

CATEGORIA_LABEL = {
    "excepcional": "Excepcional",
    "forte": "Forte",
    "boa com atencao": "Boa, com atenção",
    "requer trabalho": "Pede trabalho",
}


# ---------------------------------------------------------------- links
def _t(v, n: int) -> str:
    return str("" if v is None else v).replace("~", "-")[:n]


def _pessoa_sck(p: dict) -> str:
    """Mesmo formato do afiliado.js → padEmpacotar (há teste garantindo)."""
    return "~".join([_t(p.get("data"), 10), _t(p.get("hora"), 5), _t(p.get("lat"), 12),
                     _t(p.get("lon"), 12), _t(p.get("nome"), 20), _t(p.get("cidade"), 24)])


def empacotar_sck(produto: str, dados: dict) -> str:
    if produto == "mapa":
        return "m~" + _pessoa_sck(dados)
    if produto == "compat":
        return "c~" + _pessoa_sck(dados["a"]) + "~" + _pessoa_sck(dados["b"])
    return ""


def link_checkout(produto: str, dados: dict | None, campanha: str, sistema: str = "vedica") -> str:
    """Checkout da Cakto com os dados de nascimento no `sck` e utm de e-mail."""
    base = ofertas.checkout(produto, sistema)
    if not base:
        return f"{entrega.SITE_URL}/{'compatibilidade' if produto == 'compat' else 'mapa'}"
    q = {"utm_source": "email", "utm_medium": campanha, "utm_campaign": campanha}
    if dados:
        q["sck"] = empacotar_sck(produto, dados)
    sep = "&" if "?" in base else "?"
    return base + sep + urllib.parse.urlencode(q)


PAGINA_DO_PRODUTO = {"compat": "compatibilidade", "mapa": "mapa", "numerologia": "numerologia", "tarot": "tarot"}


def link_site(produto: str, campanha: str) -> str:
    pagina = PAGINA_DO_PRODUTO.get(produto, "mapa")
    return f"{entrega.SITE_URL}/{pagina}?" + urllib.parse.urlencode(
        {"utm_source": "email", "utm_medium": campanha, "utm_campaign": campanha})


def token_descadastro(email: str) -> str:
    segredo = acesso.SEGREDO or os.environ.get("PADMINI_SECRET", "")
    if not segredo:
        return ""
    msg = f"optout|{email.strip().lower()}".encode("utf-8")
    return hmac.new(segredo.encode("utf-8"), msg, hashlib.sha256).hexdigest()[:32]


def descadastro_valido(email: str, token: str) -> bool:
    esperado = token_descadastro(email)
    return bool(esperado and token) and hmac.compare_digest(
        esperado.encode("utf-8"), str(token).encode("utf-8"))


def link_descadastro(email: str) -> str:
    return f"{entrega.SITE_URL}/descadastrar?" + urllib.parse.urlencode(
        {"e": email.strip().lower(), "t": token_descadastro(email)})


# ---------------------------------------------------------------- HTML
def _e(v) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)


def _botao(link: str, texto: str) -> str:
    return (f'<p style="margin:26px 0"><a href="{_e(link)}" style="background:#e7a24a;color:#2a1608;'
            f'text-decoration:none;padding:14px 26px;border-radius:999px;font-weight:bold;'
            f'display:inline-block">{_e(texto)}</a></p>')


def _moldura(corpo: str, rodape: str = "", sistema: str = "vedica") -> str:
    return f"""<div style="font-family:Arial,Helvetica,sans-serif;background:#241522;color:#f4e9dc;padding:32px;border-radius:12px;max-width:520px;margin:auto">
  <p style="font-family:Georgia,serif;font-size:24px;color:#e7a24a;margin:0 0 18px">Padmini</p>
  {corpo}
  <p style="color:#8f7a76;font-size:12px;margin-top:26px">{_sistema.ASSINATURA_EMAIL[sistema]}{rodape}</p>
</div>"""


def _rodape_descadastro(email: str) -> str:
    return (f' Não quer mais receber? <a href="{_e(link_descadastro(email))}" '
            f'style="color:#c9b1a6">Descadastrar</a>.')


def _ola(nome: str) -> str:
    nome = str(nome or "").strip()[:40]
    return f'<p style="margin:0 0 12px">Olá{(" " + _e(nome)) if nome else ""},</p>'


def _p(texto: str, estilo: str = "margin:0 0 12px") -> str:
    return f'<p style="{estilo}">{texto}</p>'


def _resumo_amostra(produto: str, amostra: dict) -> str:
    """Bloco com o conteúdo da amostra (já calculado pelo app)."""
    if produto == "compat":
        nomes = amostra["nomes"]
        cat = CATEGORIA_LABEL.get(amostra["categoria"], amostra["categoria"])
        forte, atencao = amostra.get("ponto_forte") or {}, amostra.get("ponto_atencao") or {}
        return (
            _p(f'<span style="font-size:13px;color:#c9b1a6;letter-spacing:2px">'
               f'{_e(nomes["a"]).upper()} &amp; {_e(nomes["b"]).upper()}</span><br>'
               f'<span style="font-family:Georgia,serif;font-size:44px">{_e(amostra["nota"])}</span>'
               f'<span style="color:#8f7a76"> / 36 · {_e(cat)}</span>')
            + _p(_e(amostra.get("moldura", "")))
            + (_p(f'<b style="color:#e7a24a">Ponto mais forte — {_e(forte.get("tema", ""))}</b><br>'
                  f'{_e(forte.get("texto", ""))}') if forte else "")
            + (_p(f'<b style="color:#e2a89d">Ponto de atenção — {_e(atencao.get("tema", ""))}</b><br>'
                  f'{_e(atencao.get("texto", ""))}') if atencao else ""))
    fase = amostra.get("fase") or ""
    return (
        _p(f'<b>Ascendente:</b> {_e(amostra.get("ascendente"))}<br>'
           f'<b>Lua:</b> {_e(amostra.get("lua"))}'
           + (f'<br><b>Fase atual:</b> {_e(fase)}' if fase else ""))
        + _p(_e(amostra.get("lua_texto", ""))))


def email_amostra_html(produto: str, amostra: dict, dados: dict, email: str, nome: str = "") -> str:
    preco = ofertas.preco(produto)
    oque = ("as 8 dimensões com a nota de cada uma, os pontos de atenção clássicos e como "
            "fazer a relação funcionar" if produto == "compat" else
            "o mapa inteiro, os 9 planetas casa a casa, as 12 casas, as fases da vida e o PDF")
    corpo = (_ola(nome)
             + _p("Aqui está a amostra que você gerou na Padmini:")
             + _resumo_amostra(produto, amostra)
             + _p(f"O relatório completo abre {oque}.", "margin:18px 0 0")
             + _botao(link_checkout(produto, dados, "amostra"),
                      f"Quero o completo — R${preco} →" if preco else "Quero o completo →"))
    return _moldura(corpo, _rodape_descadastro(email))


def email_lembrete_html(produto: str, amostra: dict, dados: dict, email: str) -> str:
    nome = (dados.get("a") or {}).get("nome") if produto == "compat" else dados.get("nome")
    if produto == "compat":
        atencao = (amostra.get("ponto_atencao") or {}).get("tema") or "o ponto de atenção"
        gancho = (f"Na amostra que vocês geraram apareceu a nota ({_e(amostra['nota'])}/36) e um ponto de "
                  f"atenção: <b>{_e(atencao)}</b>. O completo mostra as outras sete dimensões, uma a uma, "
                  f"e o que fazer com cada uma.")
    else:
        gancho = (f"Na sua amostra, você viu o Ascendente em <b>{_e(amostra.get('ascendente'))}</b> e a Lua em "
                  f"<b>{_e(amostra.get('lua'))}</b>. Isso é só o começo: o completo abre os 9 planetas, "
                  f"as 12 casas e as fases da sua vida.")
    corpo = (_ola(nome) + _p(gancho)
             + _botao(link_checkout(produto, dados, "lembrete"), "Ver o relatório completo →")
             + _p('<span style="color:#c9b1a6;font-size:13px">Garantia de 7 dias: se não fizer sentido '
                  'para você, devolvemos o valor.</span>'))
    return _moldura(corpo, _rodape_descadastro(email))


def email_abandono_html(produto: str, nome: str, link: str, email: str) -> str:
    titulo = "a compatibilidade de vocês" if produto == "compat" else "o seu mapa completo"
    corpo = (_ola(nome)
             + _p(f"Vimos que você começou a pedir {titulo} na Padmini, mas o pagamento não foi "
                  "concluído. Se algo deu errado no checkout, é só continuar de onde parou:")
             + _botao(link, "Continuar →")
             + _p('<span style="color:#c9b1a6;font-size:13px">Ficou alguma dúvida? Responda este e-mail. '
                  'E se o relatório não fizer sentido para você, a garantia de 7 dias devolve o valor.</span>'))
    return _moldura(corpo, _rodape_descadastro(email))


TEXTO_VENDA_CRUZADA = {
    "vedica": {
        "compat": ("Quer ir além do casal? O mapa individual de cada um mostra o Ascendente, os 9 planetas "
                   "e a fase de vida de cada pessoa — R${preco}."),
        "mapa": ("Tem alguém especial? A compatibilidade mede o encaixe de vocês dois em 8 dimensões — "
                 "com amostra grátis."),
        "botao_compat": "Ver a compatibilidade do casal →",
    },
    "ocidental": {
        "compat": ("Quer ir além do casal? O mapa natal de cada um mostra os planetas em signos e casas, "
                   "os aspectos e o Ascendente de cada pessoa — R${preco}."),
        "mapa": ("Tem alguém especial? A sinastria cruza o seu mapa com o da outra pessoa em 8 dimensões — "
                 "com amostra grátis."),
        "botao_compat": "Ver a sinastria do casal →",
    },
}


def bloco_venda_cruzada(produto_comprado: str, dados: dict, sistema: str = "vedica") -> str:
    """
    Oferta do outro produto (da mesma versão do site) no e-mail de entrega.
      - comprou o casal → o mapa individual de cada um, com o checkout já preenchido;
      - comprou o mapa → a compatibilidade (precisa dos dados do par: vai para o site).
    Cupom opcional: `cupom_pos_compra` da oferta em conteudo/<versão>/ofertas.yaml.
    """
    if sistema == "ocidental":
        return _venda_cruzada_ocidental(produto_comprado, dados)
    textos = TEXTO_VENDA_CRUZADA[sistema]
    if produto_comprado == "compat":
        alvo = ofertas.oferta("mapa", sistema)
        if not alvo.get("checkout"):
            return ""
        botoes = "".join(
            f'<p style="margin:10px 0"><a href="{_e(link_checkout("mapa", p, "pos_compra", sistema))}" '
            f'style="color:#e7a24a;font-weight:bold">Mapa individual de {_e(p.get("nome") or rotulo)} →</a></p>'
            for rotulo, p in (("Pessoa A", dados.get("a") or {}), ("Pessoa B", dados.get("b") or {})) if p)
        texto = textos["compat"].format(preco=alvo.get("preco"))
    else:
        alvo = ofertas.oferta("compat", sistema)
        if not alvo.get("checkout"):
            return ""
        botoes = (f'<p style="margin:10px 0"><a href="{_e(link_site("compat", "pos_compra"))}" '
                  f'style="color:#e7a24a;font-weight:bold">{textos["botao_compat"]}</a></p>')
        texto = textos["mapa"]
    cupom = str(alvo.get("cupom_pos_compra") or "").strip()
    if cupom:
        texto += f' Use o cupom <b>{_e(cupom)}</b> no checkout.'
    return ('<div style="border-top:1px solid #4a3346;margin-top:26px;padding-top:18px">'
            + _p(texto, "margin:0 0 6px;color:#c9b1a6") + botoes + "</div>")


# Versão ocidental: quatro produtos, cada e-mail oferece os outros que fazem
# sentido (só os que já têm checkout configurado — sem link, nada aparece).
VENDA_CRUZADA_OCIDENTAL = {
    "compat": ("numerologia",),
    "mapa": ("compat", "numerologia"),
    "numerologia": ("mapa", "tarot"),
    "tarot": ("numerologia", "mapa"),
}
TEXTO_OUTRO_PRODUTO = {
    "compat": ("Sinastria do casal", "o seu mapa cruzado com o de outra pessoa, em 8 dimensões"),
    "mapa": ("Mapa natal", "os planetas em signos e casas, os aspectos e o Ascendente"),
    "numerologia": ("Numerologia", "os números do seu nome de registro e da sua data de nascimento"),
    "tarot": ("Tarot", "três cartas — Situação, Desafio e Conselho — para pensar no momento"),
}


def _venda_cruzada_ocidental(produto_comprado: str, dados: dict) -> str:
    sistema = "ocidental"
    linhas = []
    if produto_comprado == "compat":
        # o mapa natal de cada um, com o checkout já preenchido (como na védica)
        alvo = ofertas.oferta("mapa", sistema)
        if alvo.get("checkout"):
            linhas.append(_p(TEXTO_VENDA_CRUZADA[sistema]["compat"].format(preco=alvo.get("preco")),
                             "margin:0 0 6px;color:#c9b1a6"))
            linhas += [f'<p style="margin:10px 0"><a href="{_e(link_checkout("mapa", p, "pos_compra", sistema))}" '
                       f'style="color:#e7a24a;font-weight:bold">Mapa natal de {_e(p.get("nome") or rotulo)} →</a></p>'
                       for rotulo, p in (("Pessoa A", dados.get("a") or {}), ("Pessoa B", dados.get("b") or {}))
                       if p]
    outros = [(k, ofertas.oferta(k, sistema)) for k in VENDA_CRUZADA_OCIDENTAL.get(produto_comprado, ())]
    outros = [(k, o) for k, o in outros if o.get("checkout")]
    if outros:
        linhas.append(_p("Outras leituras da Padmini, todas com amostra grátis:", "margin:14px 0 6px;color:#c9b1a6"))
        for k, o in outros:
            titulo, texto = TEXTO_OUTRO_PRODUTO[k]
            linhas.append(f'<p style="margin:10px 0"><a href="{_e(link_site(k, "pos_compra"))}" '
                          f'style="color:#e7a24a;font-weight:bold">{titulo} →</a>'
                          f'<br><span style="color:#c9b1a6;font-size:13px">{texto} · R${_e(o.get("preco"))}</span></p>')
    if not linhas:
        return ""
    return '<div style="border-top:1px solid #4a3346;margin-top:26px;padding-top:18px">' + "".join(linhas) + "</div>"


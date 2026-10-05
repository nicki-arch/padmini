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
import catalogo
import entrega
import ofertas
import paleta
import sistema as _sistema
import textos

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
    """Mesmos formatos do afiliado.js → padEmpacotar (há teste de igualdade com o JS)."""
    if produto == "mapa":
        return "m~" + _pessoa_sck(dados)
    if produto == "compat":
        return "c~" + _pessoa_sck(dados["a"]) + "~" + _pessoa_sck(dados["b"])
    if produto == "numerologia":  # o nome completo de registro inteiro: cada letra muda o resultado
        return "n~" + _t(dados.get("data"), 10) + "~" + _t(dados.get("nome"), 120)
    if produto == "tarot":        # só o número da tiragem (a pergunta nunca)
        return "t~" + _t(dados.get("tiragem"), 40)
    return ""


PAGINA_DO_PRODUTO = {"compat": "compatibilidade", "mapa": "mapa", "numerologia": "numerologia", "tarot": "tarot"}


def link_checkout(produto: str, dados: dict | None, campanha: str, sistema: str = "vedica") -> str:
    """Checkout da Cakto com os dados de nascimento no `sck` e utm de e-mail."""
    base = ofertas.checkout(produto, sistema) if catalogo.vende(produto, sistema) else ""
    if not base:  # oferta sem link, ou venda fechada (catalogo.yaml): a página do produto
        return f"{entrega.SITE_URL}/{PAGINA_DO_PRODUTO.get(produto, 'mapa')}"
    q = {"utm_source": "email", "utm_medium": campanha, "utm_campaign": campanha}
    if dados:
        q["sck"] = empacotar_sck(produto, dados)
    sep = "&" if "?" in base else "?"
    return base + sep + urllib.parse.urlencode(q)


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


# Cores e fontes dos e-mails: paleta.email(versão), sempre a versão do registro.
def _cor(sistema: str = "vedica") -> dict:
    return paleta.email(sistema)


_V, _O = paleta.email("vedica"), paleta.email("ocidental")


def _botao(link: str, texto: str, sistema: str = "vedica") -> str:
    return (f'<p style="margin:26px 0"><a href="{_e(link)}" style="{entrega.estilo_botao(_cor(sistema))}">'
            f'{_e(texto)}</a></p>')


def _moldura(corpo: str, rodape: str = "", sistema: str = "vedica") -> str:
    c = _cor(sistema)
    if sistema == "ocidental":  # rodada 9: a casca da tela Sistema-Emails
        return entrega.casca_ocidental(corpo, rodape)
    return f"""<div style="font-family:{c['fonte']};background:{c['fundo']};color:{c['texto']};padding:32px;border-radius:12px;max-width:520px;margin:auto">
  {entrega.marca_do_email(c, sistema)}
  {corpo}
  <p style="color:{c['fraco']};font-size:12px;margin-top:26px">{_sistema.ASSINATURA_EMAIL[sistema]}{rodape}</p>
</div>"""


def _rodape_descadastro(email: str, sistema: str = "vedica") -> str:
    return (f' Não quer mais receber? <a href="{_e(link_descadastro(email))}" '
            f'style="color:{_cor(sistema)["suave"]}">Descadastrar</a>.')


def _ola(nome: str) -> str:
    nome = str(nome or "").strip()[:40]
    return f'<p style="margin:0 0 12px">Olá{(" " + _e(nome)) if nome else ""},</p>'


def _p(texto: str, estilo: str = "margin:0 0 12px") -> str:
    return f'<p style="{estilo}">{texto}</p>'


# ---------------------------------------------------------------- textos por versão
# Assuntos e frases de cada versão. A versão é a do REGISTRO (a página em que a
# pessoa estava / a oferta abandonada), nunca a que está no ar na hora do envio.
TEXTOS = {
    "vedica": {
        "assunto_amostra": {"mapa": "Sua amostra da Padmini", "compat": "A amostra de vocês na Padmini"},
        "assunto_lembrete": {"mapa": "Faltou uma parte do seu mapa", "compat": "O resto da compatibilidade de vocês"},
        "assunto_abandono": "Seu pedido na Padmini ficou pela metade",
        "completo_abre": {
            "compat": ("as 8 dimensões com a nota de cada uma, os pontos de atenção clássicos e como "
                       "fazer a relação funcionar"),
            "mapa": "o mapa inteiro, os 9 planetas casa a casa, as 12 casas, as fases da vida e o PDF"},
        "abandono_titulo": {"compat": "a compatibilidade de vocês", "mapa": "o seu mapa completo"},
    },
    # Ocidental: o que cada completo entrega de fato (as listas "O que vem no
    # completo" de static/ocidental/*.html). Nada de prometer além disso.
    "ocidental": {
        "assunto_amostra": {"mapa": "Seu Sol, sua Lua e seu Ascendente", "compat": "A sinastria de vocês",
                            "numerologia": "O seu Caminho de Vida", "tarot": "As suas 3 cartas"},
        "assunto_lembrete": {"mapa": "O resto do seu mapa natal", "compat": "O resto da sinastria de vocês",
                             "numerologia": "Os outros números do seu nome", "tarot": "O que as suas cartas dizem juntas"},
        "assunto_abandono": "Seu pedido na Valderez Astrologia ficou pela metade",
        "completo_abre": {
            "mapa": ("a roda do seu mapa, todos os planetas signo a signo (e casa a casa, com a hora de "
                     "nascimento), os aspectos principais, os elementos e o PDF para guardar"),
            "compat": ("as 8 dimensões com a nota e a leitura de cada uma, os aspectos entre os planetas "
                       "de vocês e os planetas de um nas casas do outro"),
            "numerologia": ("a Expressão, a Alma e a Personalidade, o talento do seu dia de nascimento, "
                            "o seu Ano Pessoal e o PDF"),
            "tarot": ("a leitura de cada carta na sua posição, o que as três dizem juntas e o PDF — "
                      "com exatamente estas cartas"),
        },
        "abandono_titulo": {"mapa": "o seu mapa natal completo", "compat": "a sinastria de vocês",
                            "numerologia": "a sua numerologia completa", "tarot": "a leitura completa da sua tiragem"},
    },
}


def assunto(tipo: str, produto: str = "", sistema: str = "vedica") -> str:
    """Assunto do e-mail: tipo = 'amostra' | 'lembrete' | 'abandono'."""
    a = TEXTOS[sistema][f"assunto_{tipo}"]
    return a if isinstance(a, str) else a.get(produto, _sistema.MARCA[sistema])


def _nome_do_registro(produto: str, dados: dict) -> str:
    if produto == "compat":
        return (dados.get("a") or {}).get("nome") or ""
    if produto == "numerologia":
        # o nome da numerologia é o completo de registro ("Ana Maria da Silva"): no
        # "Olá", só o primeiro, como na amostra (rodada 6)
        return (dados.get("nome") or "").strip().split(" ")[0]
    return dados.get("nome") or ""


def _resumo_amostra(produto: str, amostra: dict, sistema: str = "vedica") -> str:
    """Bloco com o conteúdo da amostra (já calculado pelo app, igual ao da tela)."""
    if sistema == "ocidental":
        return _resumo_ocidental(produto, amostra)
    c = _cor(sistema)
    if produto == "compat":
        nomes = amostra["nomes"]
        cat = CATEGORIA_LABEL.get(amostra["categoria"], amostra["categoria"])
        forte, atencao = amostra.get("ponto_forte") or {}, amostra.get("ponto_atencao") or {}
        return (
            _p(f'<span style="font-size:13px;color:{c["suave"]};letter-spacing:2px">'
               f'{_e(nomes["a"]).upper()} &amp; {_e(nomes["b"]).upper()}</span><br>'
               f'<span style="font-family:{c["fonte_marca"]};font-size:44px">{_e(amostra["nota"])}</span>'
               f'<span style="color:{c["fraco"]}"> / 36 · {_e(cat)}</span>')
            + _p(_e(amostra.get("moldura", "")))
            + (_p(f'<b style="color:{c["acento"]}">Ponto mais forte — {_e(forte.get("tema", ""))}</b><br>'
                  f'{_e(forte.get("texto", ""))}') if forte else "")
            + (_p(f'<b style="color:{c["acento2"]}">Ponto de atenção — {_e(atencao.get("tema", ""))}</b><br>'
                  f'{_e(atencao.get("texto", ""))}') if atencao else ""))
    fase = amostra.get("fase") or ""
    return (
        _p(f'<b>Ascendente:</b> {_e(amostra.get("ascendente"))}<br>'
           f'<b>Lua:</b> {_e(amostra.get("lua"))}'
           + (f'<br><b>Fase atual:</b> {_e(fase)}' if fase else ""))
        + _p(_e(amostra.get("lua_texto", ""))))


def _rotulo(texto: str, c: dict) -> str:
    """Rótulo em caixa alta espaçada (o e-mail não tem versalete de verdade)."""
    return f'<span style="font-size:12px;color:{c["acento"]};letter-spacing:2px">{_e(texto).upper()}</span>'


def _resumo_ocidental(produto: str, amostra: dict) -> str:
    """A amostra da versão ocidental, com o mesmo conteúdo da página:
    mapa = Sol, Lua e Ascendente; sinastria = o índice (textos.NOME_INDICE) com o ponto forte e o
    de atenção; numerologia = o Caminho de Vida; tarot = as 3 cartas e a frase de cada."""
    c = _cor("ocidental")
    if produto == "mapa":
        # Rodada 6: a tela mostra só o texto do Sol; o e-mail traz o texto de cada
        # um (Sol, Lua e Ascendente) e o aspecto mais exato — é "o resto da leitura".
        partes = []
        for x in amostra.get("triade") or []:
            partes.append(_p(f'{_rotulo(x["nome"], c)}<br>'
                             f'<span style="font-family:{c["fonte_marca"]};font-size:22px">{_e(x["signo"])}</span>'
                             + (f' <span style="color:{c["fraco"]}">{_e(x.get("grau", ""))}</span>' if x.get("grau") else "")
                             + (f'<br>{_e(x["texto"])}' if x.get("texto") else "")))
        aspecto = amostra.get("aspecto") or {}
        if aspecto.get("texto"):
            partes.append(_p(f'{_rotulo("O aspecto mais exato do seu mapa", c)}<br>'
                             f'<b>{_e(aspecto.get("titulo", ""))}</b><br>{_e(aspecto["texto"])}'))
        for aviso in amostra.get("avisos") or []:
            partes.append(_p(f'<span style="color:{c["suave"]};font-size:13px">{_e(aviso)}</span>'))
        return "".join(partes)
    if produto == "compat":
        nomes = amostra["nomes"]
        forte, atencao = amostra.get("ponto_forte") or {}, amostra.get("ponto_atencao") or {}
        return (
            _p(f'<span style="font-size:13px;color:{c["suave"]};letter-spacing:2px">'
               f'{_e(nomes["a"]).upper()} &amp; {_e(nomes["b"]).upper()}</span><br>'
               f'<span style="font-family:{c["fonte_marca"]};font-size:44px">{_e(amostra["indice"])}</span>'
               f'<span style="color:{c["fraco"]}"> / 100</span><br>'
               f'<span style="font-size:12px;color:{c["acento2"]};letter-spacing:2px">{_e(textos.NOME_INDICE.upper())} · MÉTODO PRÓPRIO</span>')
            + _p(_e(amostra.get("indice_texto", "")))
            + (_p(f'<b style="color:{c["acento"]}">Ponto mais forte — {_e(forte.get("titulo", ""))}</b><br>'
                  f'{_e(forte.get("texto", ""))}') if forte else "")
            + (_p(f'<b style="color:{c["acento2"]}">Ponto de atenção — {_e(atencao.get("titulo", ""))}</b><br>'
                  f'{_e(atencao.get("texto", ""))}') if atencao else ""))
    if produto == "numerologia":
        cv = amostra.get("caminho_de_vida") or {}
        mestre = " · número mestre" if cv.get("mestre") else ""
        return (_p(f'{_rotulo("Caminho de Vida", c)}<br>'
                   f'<span style="font-family:{c["fonte_marca"]};font-size:44px">{_e(cv.get("valor"))}</span>'
                   f'<span style="color:{c["fraco"]}">{mestre}</span>')
                + _p(f'<span style="color:{c["suave"]}">{_e(cv.get("descricao", ""))}</span>')
                + _p(_e(cv.get("texto", ""))))
    if produto == "tarot":
        return "".join(
            _p(f'{_rotulo(x.get("posicao_pt", ""), c)}<br>'
               f'<span style="font-family:{c["fonte_marca"]};font-size:22px">{_e(x.get("nome"))}</span><br>'
               f'{_e(x.get("frase", ""))}')
            for x in amostra.get("cartas") or [])
    return ""


def email_amostra_html(produto: str, amostra: dict, dados: dict, email: str, nome: str = "",
                       sistema: str = "vedica") -> str:
    preco = ofertas.moeda(ofertas.oferta(produto, sistema).get("preco"))
    oque = TEXTOS[sistema]["completo_abre"][produto]
    if not catalogo.vende(produto, sistema):
        # venda fechada (catalogo.yaml): a amostra, sem preço nem botão de compra
        corpo = (_ola(nome)
                 + _p(f"Aqui está a amostra que você gerou na {_sistema.MARCA[sistema]}:")
                 + _resumo_amostra(produto, amostra, sistema)
                 + _p(f"A leitura completa abre em breve. Ela vai trazer {oque}.", "margin:18px 0 0")
                 + _p(f'<a href="{_e(link_site(produto, "amostra"))}#me-avise" style="color:{_cor(sistema)["acento"]}">'
                      "Quero ser avisado quando abrir →</a>"))
        return _moldura(corpo, _rodape_descadastro(email, sistema), sistema)
    corpo = (_ola(nome)
             + _p(f"Aqui está a amostra que você gerou na {_sistema.MARCA[sistema]}:")
             + _resumo_amostra(produto, amostra, sistema)
             + _p(f"O relatório completo abre {oque}.", "margin:18px 0 0")
             + _botao(link_checkout(produto, dados, "amostra", sistema),
                      f"Quero o completo — R${preco} →" if preco else "Quero o completo →", sistema))
    return _moldura(corpo, _rodape_descadastro(email, sistema), sistema)


def _gancho_lembrete(produto: str, amostra: dict, sistema: str) -> str:
    """A primeira frase do lembrete: o que a pessoa viu na amostra + o que falta."""
    if sistema == "vedica":
        if produto == "compat":
            atencao = (amostra.get("ponto_atencao") or {}).get("tema") or "o ponto de atenção"
            return (f"Na amostra que vocês geraram apareceu a nota ({_e(amostra['nota'])}/36) e um ponto de "
                    f"atenção: <b>{_e(atencao)}</b>. O completo mostra as outras sete dimensões, uma a uma, "
                    f"e o que fazer com cada uma.")
        return (f"Na sua amostra, você viu o Ascendente em <b>{_e(amostra.get('ascendente'))}</b> e a Lua em "
                f"<b>{_e(amostra.get('lua'))}</b>. Isso é só o começo: o completo abre os 9 planetas, "
                f"as 12 casas e as fases da sua vida.")
    abre = TEXTOS["ocidental"]["completo_abre"][produto]
    if produto == "mapa":
        vistos = ", ".join(f"{_e(x['nome'])} em <b>{_e(x['signo'])}</b>" for x in amostra.get("triade") or [])
        return f"Na sua amostra, você viu {vistos}. Isso é só o começo: o completo abre {abre}."
    if produto == "compat":
        atencao = (amostra.get("ponto_atencao") or {}).get("titulo") or "um ponto de atenção"
        return (f"Na amostra que vocês geraram, o {textos.NOME_INDICE} deu <b>{_e(amostra.get('indice'))}/100</b> e "
                f"apareceu um ponto de atenção: <b>{_e(atencao)}</b>. O completo abre {abre}.")
    if produto == "numerologia":
        cv = (amostra.get("caminho_de_vida") or {}).get("valor")
        return (f"O seu Caminho de Vida é <b>{_e(cv)}</b>. Os outros números do seu nome contam o resto: "
                f"o completo abre {abre}.")
    nomes = ", ".join(f"<b>{_e(x.get('nome'))}</b>" for x in amostra.get("cartas") or [])
    return f"Você tirou {nomes}. O completo traz {abre}."


def email_lembrete_html(produto: str, amostra: dict, dados: dict, email: str, sistema: str = "vedica") -> str:
    c = _cor(sistema)
    corpo = (_ola(_nome_do_registro(produto, dados)) + _p(_gancho_lembrete(produto, amostra, sistema))
             + _botao(link_checkout(produto, dados, "lembrete", sistema), "Ver o relatório completo →", sistema)
             + _p(f'<span style="color:{c["suave"]};font-size:13px">Garantia de 7 dias: se não fizer sentido '
                  'para você, devolvemos o valor.</span>'))
    return _moldura(corpo, _rodape_descadastro(email, sistema), sistema)


def email_abandono_html(produto: str, nome: str, link: str, email: str, sistema: str = "vedica") -> str:
    c = _cor(sistema)
    titulo = TEXTOS[sistema]["abandono_titulo"][produto]
    corpo = (_ola(nome)
             + _p(f"Vimos que você começou a pedir {titulo} na {_sistema.MARCA[sistema]}, mas o pagamento não foi "
                  "concluído. Se algo deu errado no checkout, é só continuar de onde parou:")
             + _botao(link, "Continuar →", sistema)
             + _p(f'<span style="color:{c["suave"]};font-size:13px">Ficou alguma dúvida? Responda este e-mail. '
                  'E se o relatório não fizer sentido para você, a garantia de 7 dias devolve o valor.</span>'))
    return _moldura(corpo, _rodape_descadastro(email, sistema), sistema)


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
        # venda fechada: o e-mail de entrega (de uma compra antiga) não oferece nada
        return _venda_cruzada_ocidental(produto_comprado, dados) if catalogo.vendas_abertas(sistema) else ""
    textos = TEXTO_VENDA_CRUZADA[sistema]
    if produto_comprado == "compat":
        alvo = ofertas.oferta("mapa", sistema)
        if not alvo.get("checkout"):
            return ""
        botoes = "".join(
            f'<p style="margin:10px 0"><a href="{_e(link_checkout("mapa", p, "pos_compra", sistema))}" '
            f'style="color:{_V["acento"]};font-weight:bold">Mapa individual de {_e(p.get("nome") or rotulo)} →</a></p>'
            for rotulo, p in (("Pessoa A", dados.get("a") or {}), ("Pessoa B", dados.get("b") or {})) if p)
        texto = textos["compat"].format(preco=ofertas.moeda(alvo.get("preco")))
    else:
        alvo = ofertas.oferta("compat", sistema)
        if not alvo.get("checkout"):
            return ""
        botoes = (f'<p style="margin:10px 0"><a href="{_e(link_site("compat", "pos_compra"))}" '
                  f'style="color:{_V["acento"]};font-weight:bold">{textos["botao_compat"]}</a></p>')
        texto = textos["mapa"]
    cupom = str(alvo.get("cupom_pos_compra") or "").strip()
    if cupom:
        texto += f' Use o cupom <b>{_e(cupom)}</b> no checkout.'
    return (f'<div style="border-top:1px solid {_V["linha"]};margin-top:26px;padding-top:18px">'
            + _p(texto, f"margin:0 0 6px;color:{_V['suave']}") + botoes + "</div>")


# Versão ocidental: quatro produtos, cada e-mail oferece os outros que fazem
# sentido (só os que já têm checkout configurado — sem link, nada aparece).
# A escada da ocidental (rodada 6): mapa natal → sinastria → numerologia → tarot.
# Cada compra sugere os próximos degraus que a pessoa ainda não tem, nessa ordem.
VENDA_CRUZADA_OCIDENTAL = {
    "compat": ("numerologia",),
    "mapa": ("compat", "numerologia"),
    "numerologia": ("mapa", "tarot"),
    "tarot": ("mapa", "numerologia"),
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
            linhas.append(_p(TEXTO_VENDA_CRUZADA[sistema]["compat"].format(preco=ofertas.moeda(alvo.get("preco"))),
                             f"margin:0 0 6px;color:{_O['suave']}"))
            linhas += [f'<p style="margin:10px 0"><a href="{_e(link_checkout("mapa", p, "pos_compra", sistema))}" '
                       f'style="color:{_O["acento"]};font-weight:bold">Mapa natal de {_e(p.get("nome") or rotulo)} →</a></p>'
                       for rotulo, p in (("Pessoa A", dados.get("a") or {}), ("Pessoa B", dados.get("b") or {}))
                       if p]
    outros = [(k, ofertas.oferta(k, sistema)) for k in VENDA_CRUZADA_OCIDENTAL.get(produto_comprado, ())]
    outros = [(k, o) for k, o in outros if o.get("checkout")]
    if outros:
        linhas.append(_p("Outras leituras da Valderez Astrologia, todas com amostra grátis:", f"margin:14px 0 6px;color:{_O['suave']}"))
        for k, o in outros:
            titulo, texto = TEXTO_OUTRO_PRODUTO[k]
            linhas.append(f'<p style="margin:10px 0"><a href="{_e(link_site(k, "pos_compra"))}" '
                          f'style="color:{_O["acento"]};font-weight:bold">{titulo} →</a>'
                          f'<br><span style="color:{_O["suave"]};font-size:13px">{texto} · R${_e(ofertas.moeda(o.get("preco")))}</span></p>')
    if not linhas:
        return ""
    return f'<div style="border-top:1px solid {_O["linha"]};margin-top:26px;padding-top:18px">' + "".join(linhas) + "</div>"


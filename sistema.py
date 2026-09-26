"""
Padmini — qual versão do site está no ar: `vedica` ou `ocidental`.

    PADMINI_SISTEMA=vedica      (padrão; é o que vale se a variável não existir)
    PADMINI_SISTEMA=ocidental

PARA TROCAR A VERSÃO NO AR: na Render, abra o serviço → Environment, mude
PADMINI_SISTEMA e salve. A Render reinicia o site sozinha; não precisa de deploy
nem de mexer em código. Voltar é mudar de novo.

As duas versões vivem no mesmo código. Este módulo é o ÚNICO lugar que lê a
variável; tudo o que muda por versão (páginas, textos em `conteudo/<versão>/`,
ofertas, e-mails, PDF, SEO) pergunta para cá.

O que NÃO depende da versão no ar (de propósito):
  - links já entregues: o token de um relatório pago diz de que versão ele é
    (ver `acesso.sistema_do_token`), então quem comprou a védica continua
    lendo a védica depois da troca, e vice-versa;
  - o webhook: reconhece as ofertas das duas versões, qualquer que seja a
    ativa — uma compra feita minutos antes da troca é entregue.
"""

import os

SISTEMAS = ("vedica", "ocidental")
PADRAO = "vedica"


class SistemaInvalido(RuntimeError):
    pass


def validar(valor: str) -> str:
    v = str(valor or "").strip().lower()
    if v not in SISTEMAS:
        raise SistemaInvalido(
            f"PADMINI_SISTEMA={valor!r} não existe. Use 'vedica' ou 'ocidental' "
            f"(ou apague a variável para ficar com '{PADRAO}').")
    return v


def ativo() -> str:
    """A versão no ar. Valor desconhecido levanta SistemaInvalido: o app chama
    isto ao subir, então um erro de digitação na Render derruba a subida com
    uma mensagem clara, em vez de pôr no ar um site meio montado."""
    bruto = os.environ.get("PADMINI_SISTEMA", "")
    return validar(bruto) if bruto.strip() else PADRAO


# --------------------------------------------------------------------------
# O que muda por versão (fora os arquivos em conteudo/<versão>/).
# --------------------------------------------------------------------------

# rota → (template em static/, nome do YAML de copy em conteudo/<versão>/)
PAGINAS = {
    "vedica": {
        "/": ("home.html", "home"),
        "/mapa": ("index.html", "index"),
        "/compatibilidade": ("compatibilidade.html", "compatibilidade"),
        "/lista": ("lista.html", "lista"),
    },
    "ocidental": {
        "/": ("ocidental/home.html", "home"),
        "/mapa": ("ocidental/mapa.html", "mapa"),
        "/compatibilidade": ("ocidental/compatibilidade.html", "compatibilidade"),
        "/lista": ("ocidental/lista.html", "lista"),
        "/numerologia": ("ocidental/numerologia.html", "numerologia"),
        "/tarot": ("ocidental/tarot.html", "tarot"),
    },
}

# Termos de uso e política de privacidade (arquivos puros em static/). A védica
# continua servindo os mesmos arquivos de sempre.
LEGAIS = {
    "vedica": {"/termos": "termos.html", "/privacidade": "privacidade.html"},
    "ocidental": {"/termos": "ocidental/termos.html", "/privacidade": "ocidental/privacidade.html"},
}

# Página do modo live (/live). A védica é servida como arquivo puro, como
# sempre foi; as outras são templates.
LIVE = {"vedica": "live.html", "ocidental": "ocidental/live.html"}

# Linha de assinatura dos e-mails (entrega e marketing).
ASSINATURA_EMAIL = {
    "vedica": "Padmini — astrologia védica para autoconhecimento.",
    "ocidental": "Padmini — astrologia para autoconhecimento.",
}

# Prefixo dos tokens do completo (ver acesso.py). A védica não tem prefixo:
# é o formato de todos os links entregues antes da Fase 0.5.
PREFIXO_TOKEN = {"vedica": "", "ocidental": "oc-"}


def pagina(rota: str, sistema: str) -> tuple[str, str]:
    return PAGINAS[sistema][rota]

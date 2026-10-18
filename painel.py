"""
Valderez Astrologia — o /painel (rodada 15): sessão, CSRF e as ações que mudam o site.

Acesso:
  - senha única em PADMINI_PAINEL_SENHA (16 caracteres ou mais). Sem ela (ou curta
    demais), o /painel responde 404: falha fechada;
  - a sessão é um cookie assinado (acesso.emitir_sessao) de 12 h, HttpOnly, Secure e
    SameSite=Strict, que leva QUEM está mexendo (Nicolas ou Pedro) e uma impressão da
    senha: trocar a senha na Render derruba as sessões abertas;
  - todo POST leva o token CSRF, amarrado à sessão;
  - o login tem limite de tentativas erradas (limites.PAINEL_FALHAS_*).

O que o painel muda mora em `estado_site.py` (tabela config_site). O painel NÃO mexe em
preço, chaves, variáveis da Render, Stripe, Cakto, nem mostra dado de cliente.
"""
import hashlib
import hmac
import os
import time

import acesso

COOKIE = "pad_painel"
COOKIE_SO_PARA_MIM = "pad_painel_eu"
HORAS_SESSAO = 12
MINIMO_SENHA = 16
QUEM = ("Nicolas", "Pedro")


def senha() -> str:
    """A senha do painel, ou '' (painel desligado) sem a variável ou com menos de 16 caracteres."""
    s = os.environ.get("PADMINI_PAINEL_SENHA", "")
    return s if len(s) >= MINIMO_SENHA else ""


def ligado() -> bool:
    return bool(senha() and acesso.SEGREDO)


def _papel(quem: str) -> str:
    impressao = hashlib.sha256(senha().encode("utf-8")).hexdigest()[:12]
    return f"painel|{quem}|{impressao}"


def emitir_sessao(quem: str, agora: int | None = None) -> tuple[str, int]:
    expira = int(agora if agora is not None else time.time()) + HORAS_SESSAO * 3600
    return f"{quem}|{acesso.emitir_sessao(_papel(quem), expira)}", expira


def quem_da_sessao(valor: str | None) -> str | None:
    """Quem está logado neste cookie, ou None (sem cookie, vencido, forjado, senha trocada)."""
    if not (ligado() and valor and "|" in valor):
        return None
    quem, _, sessao = valor.partition("|")
    if quem not in QUEM:
        return None
    return quem if acesso.sessao_valida(_papel(quem), sessao) else None


def senha_confere(digitada: str) -> bool:
    s = senha()
    # bytes: compare_digest com str não-ASCII levantaria erro (500) em vez de recusar
    return bool(s) and hmac.compare_digest(str(digitada or "").encode("utf-8"), s.encode("utf-8"))


def csrf(valor_sessao: str) -> str:
    """O token CSRF desta sessão (vai num campo escondido de cada formulário)."""
    msg = f"csrf|{valor_sessao}".encode("utf-8")
    return hmac.new(acesso.SEGREDO.encode("utf-8"), msg, hashlib.sha256).hexdigest()[:32]


def csrf_confere(valor_sessao: str | None, token: str | None) -> bool:
    if not (valor_sessao and token and acesso.SEGREDO):
        return False
    return hmac.compare_digest(str(token).encode("utf-8"), csrf(valor_sessao).encode("utf-8"))

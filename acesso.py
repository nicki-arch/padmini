"""
Padmini — controle de acesso ao relatório completo.

O completo é liberado por um TOKEN assinado (HMAC-SHA256) sobre os dados de
nascimento do pedido. Como o relatório é determinístico, o token amarra o
acesso àqueles dados exatos — o link enviado por e-mail após o pagamento
carrega os dados + o token, e o servidor confere a assinatura.

Configuração por ambiente:
- PADMINI_SECRET: segredo para assinar/conferir tokens (obrigatório em produção).
- PADMINI_MODO_ABERTO=1: libera o completo sem token (para staging/preview).
  NUNCA usar em produção pública.

Fluxo em produção: webhook da Cakto confirma o pagamento → backend chama
emitir_token(produto, chave) → manda o link com ?token=... por e-mail.

Versão do site (Fase 0.5, ver sistema.py): o token diz de que versão ele é.
  - védica:    32 hex, sem prefixo — o formato de todo link já entregue, que
               continua valendo;
  - ocidental: "oc-" + 32 hex, assinado sobre "ocidental|produto|chave".
Assim o link de um relatório pago abre na versão comprada, qualquer que seja a
versão no ar, e um token de uma versão não abre o completo da outra.
"""

import hashlib
import hmac
import os

import sistema as _sistema

SEGREDO = os.environ.get("PADMINI_SECRET", "")
MODO_ABERTO = os.environ.get("PADMINI_MODO_ABERTO") == "1"


def chave_mapa(data: str, hora: str, lat, lon) -> str:
    """Chave canônica de um nascimento (data ISO, hora HH:MM, lat, lon)."""
    return f"{data}|{hora}|{lat}|{lon}"


def chave_compat(a: tuple, b: tuple) -> str:
    """Chave canônica de um casal — a e b são (data, hora, lat, lon)."""
    return chave_mapa(*a) + "||" + chave_mapa(*b)


def chave_numerologia(nome_normalizado: str, data: str) -> str:
    """Chave de um pedido de numerologia: o nome já normalizado (numerologia.
    normalizar_nome) e a data ISO. Trocar uma letra do nome muda o resultado,
    então muda a chave."""
    return f"num|{nome_normalizado}|{data}"


def chave_tarot(tiragem: str) -> str:
    """Chave de uma tiragem de tarot: o id dela (que já diz quais são as cartas)."""
    return f"tarot|{tiragem}"


def emitir_token(produto: str, chave: str, sistema: str = "vedica") -> str:
    """Assina (produto, chave) de uma versão. produto ∈ {'mapa','compat'}. Precisa de PADMINI_SECRET."""
    if not SEGREDO:
        raise RuntimeError("PADMINI_SECRET não configurado — não é possível emitir token.")
    prefixo = _sistema.PREFIXO_TOKEN[sistema]
    msg = (f"{produto}|{chave}" if sistema == "vedica" else f"{sistema}|{produto}|{chave}").encode("utf-8")
    return prefixo + hmac.new(SEGREDO.encode("utf-8"), msg, hashlib.sha256).hexdigest()[:32]


def sistema_do_token(token: str | None) -> str:
    """De que versão é um token (pelo prefixo). Sem prefixo = védica."""
    token = str(token or "")
    for sistema, prefixo in _sistema.PREFIXO_TOKEN.items():
        if prefixo and token.startswith(prefixo):
            return sistema
    return "vedica"


def emitir_sessao(papel: str, expira_em: int) -> str:
    """Cookie assinado com prazo — usado pelo modo live (papel='live')."""
    if not SEGREDO:
        raise RuntimeError("PADMINI_SECRET não configurado — não é possível abrir sessão.")
    msg = f"sessao|{papel}|{expira_em}".encode("utf-8")
    return f"{expira_em}.{hmac.new(SEGREDO.encode('utf-8'), msg, hashlib.sha256).hexdigest()[:32]}"


def sessao_valida(papel: str, valor: str | None, agora: int | None = None) -> bool:
    """True se o cookie foi assinado por nós e ainda não venceu."""
    import time
    if not (SEGREDO and valor and "." in valor):
        return False
    expira, _, assinatura = valor.partition(".")
    if not expira.isdigit():
        return False
    if int(expira) < (agora if agora is not None else int(time.time())):
        return False
    try:
        return hmac.compare_digest(valor, emitir_sessao(papel, int(expira)))
    except Exception:
        return False


def completo_liberado(produto: str, chave: str, token: str | None, sistema: str = "vedica") -> bool:
    """True se o completo desta versão pode ser servido para este pedido."""
    if MODO_ABERTO:
        return True
    if not SEGREDO or not token:
        return False
    try:
        return hmac.compare_digest(token, emitir_token(produto, chave, sistema))
    except Exception:
        return False

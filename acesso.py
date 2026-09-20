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
"""

import hashlib
import hmac
import os

SEGREDO = os.environ.get("PADMINI_SECRET", "")
MODO_ABERTO = os.environ.get("PADMINI_MODO_ABERTO") == "1"


def chave_mapa(data: str, hora: str, lat, lon) -> str:
    """Chave canônica de um nascimento (data ISO, hora HH:MM, lat, lon)."""
    return f"{data}|{hora}|{lat}|{lon}"


def chave_compat(a: tuple, b: tuple) -> str:
    """Chave canônica de um casal — a e b são (data, hora, lat, lon)."""
    return chave_mapa(*a) + "||" + chave_mapa(*b)


def emitir_token(produto: str, chave: str) -> str:
    """Assina (produto, chave). produto ∈ {'mapa','compat'}. Precisa de PADMINI_SECRET."""
    if not SEGREDO:
        raise RuntimeError("PADMINI_SECRET não configurado — não é possível emitir token.")
    msg = f"{produto}|{chave}".encode("utf-8")
    return hmac.new(SEGREDO.encode("utf-8"), msg, hashlib.sha256).hexdigest()[:32]


def completo_liberado(produto: str, chave: str, token: str | None) -> bool:
    """True se o completo pode ser servido para este pedido."""
    if MODO_ABERTO:
        return True
    if not SEGREDO or not token:
        return False
    try:
        return hmac.compare_digest(token, emitir_token(produto, chave))
    except Exception:
        return False

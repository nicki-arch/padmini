"""
Padmini — alertas por e-mail para a equipe.

Por que existe: se o webhook deixava um pedido pago sem entrega, ou o site
dava erro, ninguém ficava sabendo até o cliente reclamar. Agora um e-mail vai
para PADMINI_ALERTA_EMAIL (pode ser mais de um, separados por vírgula).

- Sem PADMINI_ALERTA_EMAIL ou sem RESEND_API_KEY: só registra no log.
- Erros repetidos não viram enxurrada: o mesmo tipo de alerta sai no máximo
  uma vez a cada `intervalo` segundos (em memória, zera no deploy).
- Um alerta nunca derruba o que estava sendo feito: qualquer falha aqui é
  engolida e registrada no log.
"""

import html
import logging
import os
import threading
import time

import entrega

log = logging.getLogger("padmini.alertas")

_ultimo_envio: dict[str, float] = {}
_trava = threading.Lock()


def destinatarios() -> list[str]:
    return [e.strip() for e in os.environ.get("PADMINI_ALERTA_EMAIL", "").split(",") if "@" in e]


def _pode_enviar(chave: str, intervalo: float, agora: float) -> bool:
    with _trava:
        ultimo = _ultimo_envio.get(chave)
        if ultimo is not None and agora - ultimo < intervalo:
            return False
        _ultimo_envio[chave] = agora
        return True


def alertar(assunto: str, detalhes: str, chave: str | None = None, intervalo: float = 0) -> bool:
    """
    Manda um alerta. `chave` + `intervalo` (s) limitam a repetição: alertas com
    a mesma chave dentro do intervalo são descartados (ficam só no log).
    Devolve True se o e-mail saiu.
    """
    log.warning("ALERTA: %s — %s", assunto, detalhes[:500])
    try:
        if intervalo and not _pode_enviar(chave or assunto, intervalo, time.monotonic()):
            return False
        para = destinatarios()
        if not para:
            return False
        corpo = (f'<div style="font-family:Arial,sans-serif;font-size:14px">'
                 f'<p><b>{html.escape(assunto)}</b></p>'
                 f'<pre style="white-space:pre-wrap;background:#f4f4f4;padding:12px">'
                 f'{html.escape(detalhes[:5000])}</pre>'
                 f'<p style="color:#888">Alerta automático do site {html.escape(entrega.SITE_URL)}.</p></div>')
        enviado = True
        for destino in para:
            enviado = entrega.enviar_email(destino, f"[Padmini] {assunto}", corpo) and enviado
        return enviado
    except Exception:  # noqa: BLE001
        log.exception("alertas: falha ao enviar alerta")
        return False


def limpar() -> None:
    """Zera o controle de repetição (usado pelos testes)."""
    with _trava:
        _ultimo_envio.clear()

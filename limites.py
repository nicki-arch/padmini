"""
Padmini — limite de requisições por IP (anti-abuso), em memória.

Por que existe: sem limite, um script podia (a) testar a senha do modo live à
vontade — ela libera qualquer relatório pago de graça —, (b) encher a lista de
espera de lixo e (c) derrubar a instância pedindo mapas/PDFs em loop (o cálculo
pesa na CPU).

Em memória porque o site roda numa instância só (Render). Se um dia forem
várias, cada uma conta separado — o limite fica mais frouxo, mas não quebra.

IP do cliente: a Render fica atrás da Cloudflare, que põe o IP real em
`CF-Connecting-IP` (e o cliente não consegue forjar esse header passando pela
Cloudflare). Sem ele, usa o 1º item do `X-Forwarded-For` (convenção da Render)
e, por último, o IP da conexão. Um IP forjado só serve para fugir do limite
POR IP; por isso o login do live também tem um teto GLOBAL de falhas.
"""

import threading
import time
from collections import deque

from fastapi import HTTPException, Request


def ip_do_cliente(request: Request) -> str:
    h = request.headers
    ip = (h.get("cf-connecting-ip") or "").strip()
    if not ip:
        ip = (h.get("x-forwarded-for") or "").split(",")[0].strip()
    if not ip and request.client:
        ip = request.client.host
    return ip[:64] or "desconhecido"


class Limite:
    """Janela deslizante: no máximo `maximo` eventos por `janela` segundos, por chave."""

    MAX_CHAVES = 50_000  # teto de memória: acima disso, esquece as chaves mais antigas

    def __init__(self, nome: str, maximo: int, janela: float):
        self.nome, self.maximo, self.janela = nome, maximo, janela
        self._eventos: dict[str, deque] = {}
        self._trava = threading.Lock()

    def _podar(self, fila: deque, agora: float) -> None:
        while fila and fila[0] <= agora - self.janela:
            fila.popleft()

    def estourado(self, chave: str, agora: float | None = None) -> bool:
        """True se a chave já gastou a cota (não registra nada)."""
        agora = time.monotonic() if agora is None else agora
        with self._trava:
            fila = self._eventos.get(chave)
            if not fila:
                return False
            self._podar(fila, agora)
            return len(fila) >= self.maximo

    def registrar(self, chave: str, agora: float | None = None) -> None:
        agora = time.monotonic() if agora is None else agora
        with self._trava:
            if chave not in self._eventos and len(self._eventos) >= self.MAX_CHAVES:
                for velha in list(self._eventos)[: self.MAX_CHAVES // 10]:
                    del self._eventos[velha]
            fila = self._eventos.setdefault(chave, deque())
            self._podar(fila, agora)
            fila.append(agora)

    def consumir(self, chave: str, agora: float | None = None) -> bool:
        """Registra um uso; False se passou do limite (e aí não registra)."""
        agora = time.monotonic() if agora is None else agora
        with self._trava:
            fila = self._eventos.get(chave)
            if fila is not None:
                self._podar(fila, agora)
                if len(fila) >= self.maximo:
                    return False
        self.registrar(chave, agora)
        return True

    def limpar(self) -> None:
        with self._trava:
            self._eventos.clear()


def _recusar(limite: Limite) -> None:
    raise HTTPException(429, "Muitas tentativas seguidas. Espere um pouco e tente de novo.",
                        headers={"Retry-After": str(int(limite.janela))})


def exigir(limite: Limite, request: Request) -> None:
    """Consome uma unidade do limite para o IP da requisição; 429 se estourou."""
    if not limite.consumir(ip_do_cliente(request)):
        _recusar(limite)


# Números por IP, folgados de propósito: operadoras de celular no Brasil põem
# muita gente atrás do mesmo IP (CGNAT), e numa live do Pedro muitos chegam
# juntos. O objetivo é barrar robô em loop, não gente de verdade.
CALCULO = Limite("calculo", maximo=60, janela=60)
PDF = Limite("pdf", maximo=20, janela=60)
# Cada chamada nova à IA custa dinheiro (as repetidas saem do cache do banco).
TEXTO_IA = Limite("texto_ia", maximo=20, janela=60 * 60)
CIDADES = Limite("cidades", maximo=300, janela=60)
LISTA = Limite("lista", maximo=20, janela=10 * 60)
# "receber a amostra por e-mail": cada chamada manda um e-mail de verdade.
AMOSTRA_EMAIL = Limite("amostra_email", maximo=10, janela=10 * 60)
# Login do live: conta só as FALHAS. 5 por IP a cada 15 min, e 30 no total por
# hora (um atacante trocando de IP ainda esbarra no teto global). Efeito
# colateral aceito: sob ataque, o login fica travado por até 1h para todos — por
# isso o Pedro deve entrar ANTES da live (a sessão dura 12h e não é afetada).
LIVE_FALHAS_IP = Limite("live_falhas_ip", maximo=5, janela=15 * 60)
LIVE_FALHAS_GLOBAL = Limite("live_falhas_global", maximo=30, janela=60 * 60)

TODOS = (CALCULO, PDF, TEXTO_IA, CIDADES, LISTA, AMOSTRA_EMAIL, LIVE_FALHAS_IP, LIVE_FALHAS_GLOBAL)


def limpar_todos() -> None:
    """Zera os contadores (usado pelos testes)."""
    for lim in TODOS:
        lim.limpar()

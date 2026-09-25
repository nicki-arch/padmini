"""
Padmini — cabeçalhos HTTP de segurança, aplicados a toda resposta.

Por que existe: o site não mandava nenhum. O que cada um faz aqui:
  - Content-Security-Policy: só roda script/estilo/fonte das origens que o site
    usa de verdade (o próprio site, Google Fonts e o PostHog). Se um dia entrar
    uma falha de XSS, o script injetado não consegue carregar código de fora nem
    mandar dados para outro domínio. `frame-ancestors 'none'` impede o site de
    ser embutido num iframe (clickjacking).
    Limitação conhecida: as páginas têm <script> e onclick inline, então
    script-src precisa de 'unsafe-inline'. Tirar isso exigiria mover os scripts
    para arquivos .js (fica como melhoria futura, ver docs/seguranca.md).
  - Strict-Transport-Security: o navegador passa a usar sempre HTTPS.
  - Referrer-Policy: os links de entrega carregam o token do relatório pago na
    URL; com esta política, ao sair do site o outro domínio recebe só a origem
    (https://padmini.com.br/), nunca a URL com o token.
  - X-Content-Type-Options, X-Frame-Options, Permissions-Policy: o básico.

Ao adicionar um serviço externo novo (outro analytics, pixel, CDN…), ele
precisa entrar na política abaixo — senão o navegador bloqueia e aparece um
erro "Content Security Policy" no console. O teste
`test_csp_cobre_recursos_externos_das_paginas` avisa quando isso acontece.
"""

import os
from urllib.parse import urlparse


def _origem(url: str) -> str:
    u = urlparse(url.strip())
    return f"{u.scheme}://{u.netloc}" if u.scheme in ("http", "https") and u.netloc else ""


def origens_posthog() -> list[str]:
    """Origens do PostHog: a da API (eventos) e a dos assets (a lib em JS)."""
    api = _origem(os.environ.get("PADMINI_POSTHOG_HOST", "") or "https://us.i.posthog.com")
    if not api:
        return []
    # mesma regra do snippet oficial em analytics.js
    assets = api.replace(".i.posthog.com", "-assets.i.posthog.com")
    return sorted({api, assets})


def politica_csp() -> str:
    ph = " ".join(origens_posthog())
    diretivas = [
        "default-src 'self'",
        f"script-src 'self' 'unsafe-inline' {ph}",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: blob:",
        f"connect-src 'self' {ph}",
        "worker-src 'self' blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
    return "; ".join(" ".join(d.split()) for d in diretivas)


def cabecalhos() -> dict[str, str]:
    return {
        "Content-Security-Policy": politica_csp(),
        "Strict-Transport-Security": "max-age=31536000",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    }


async def cabecalhos_de_seguranca(request, call_next):
    resposta = await call_next(request)
    for nome, valor in cabecalhos().items():
        resposta.headers.setdefault(nome, valor)
    return resposta

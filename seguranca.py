"""
Padmini — cabeçalhos HTTP de segurança, aplicados a toda resposta.

Por que existe: o site não mandava nenhum. O que cada um faz aqui:
  - Content-Security-Policy: só roda script/estilo/fonte das origens que o site
    usa de verdade (o próprio site, o PostHog e, só na védica, o Google Fonts). Se um dia entrar
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


# Pixels de anúncio (rodada 6), só na versão ocidental. Cada ID vem de uma
# variável de ambiente; vazio = o pixel não existe: nem carrega, nem entra na CSP.
PIXELS = {
    "meta_pixel": "PADMINI_META_PIXEL",          # ex.: 123456789012345
    "tiktok_pixel": "PADMINI_TIKTOK_PIXEL",      # ex.: C1ABCD2EFGHIJK3LMNOP
    "google_tag": "PADMINI_GOOGLE_TAG",          # ex.: G-XXXX,AW-123456789 (vírgula separa)
    "google_ads_lead": "PADMINI_GOOGLE_ADS_LEAD",  # opcional: AW-123456789/rótulo da conversão "lead"
}

# Domínios de cada plataforma, das documentações oficiais (regra 5 do CLAUDE.md):
# Meta: developers.facebook.com/docs/meta-pixel/advanced (Content Security Policy);
# TikTok: business-api.tiktok.com/portal/docs/work-with-csp;
# Google: developers.google.com/tag-platform/security/guides/csp (GA4 e Google Ads).
CSP_PIXELS = {
    "meta_pixel": {"script": ["https://connect.facebook.net"],
                   "img": ["https://www.facebook.com"], "connect": ["https://www.facebook.com", "https://connect.facebook.net"]},
    "tiktok_pixel": {"script": ["https://analytics.tiktok.com", "https://analytics-ipv6.tiktokw.us", "https://ads.tiktok.com"],
                     "img": ["https://analytics.tiktok.com", "https://analytics-ipv6.tiktokw.us", "https://ads.tiktok.com"],
                     "connect": ["https://analytics.tiktok.com", "https://analytics-ipv6.tiktokw.us", "https://ads.tiktok.com"],
                     "frame": ["bytedance:", "sslocal:"]},
    "google_tag": {"script": ["https://www.googletagmanager.com", "https://www.googleadservices.com", "https://www.google.com"],
                   "img": ["https://www.googletagmanager.com", "https://*.google-analytics.com", "https://*.google.com",
                           "https://*.google.com.br", "https://*.g.doubleclick.net", "https://www.googleadservices.com",
                           "https://googleads.g.doubleclick.net", "https://pagead2.googlesyndication.com"],
                   "connect": ["https://www.googletagmanager.com", "https://*.google-analytics.com",
                               "https://*.analytics.google.com", "https://*.google.com", "https://*.google.com.br",
                               "https://*.g.doubleclick.net", "https://pagead2.googlesyndication.com",
                               "https://www.googleadservices.com", "https://googleads.g.doubleclick.net",
                               "https://ad.doubleclick.net"],
                   "frame": ["https://www.googletagmanager.com"]},
}


def pixels() -> dict[str, str]:
    """IDs dos pixels para /api/config. Só com a ocidental no ar: a védica não tem
    aviso de cookies, então nada de pixel nela (fica idêntica a antes)."""
    import sistema
    ligados = sistema.ativo() == "ocidental"
    return {chave: (os.environ.get(var, "").strip() if ligados else "") for chave, var in PIXELS.items()}


def _origens_pixels(tipo: str) -> str:
    ids = pixels()
    return " ".join(o for chave, dirs in CSP_PIXELS.items() if ids.get(chave) for o in dirs.get(tipo, []))


# Google Fonts: só a védica usa (as páginas dela carregam as fontes de lá). A
# ocidental (Valderez) serve as próprias fontes, então a CSP dela não libera
# fonts.googleapis.com nem fonts.gstatic.com — a não ser num link de entrega da
# védica (token sem prefixo), que abre a página védica mesmo com a ocidental no ar.
GOOGLE_FONTS = {"style": "https://fonts.googleapis.com", "font": "https://fonts.gstatic.com"}


def precisa_google_fonts(request=None) -> bool:
    import acesso
    import sistema
    if sistema.ativo() == "vedica":
        return True
    token = request.query_params.get("token") if request is not None else None
    return bool(token) and acesso.sistema_do_token(token) == "vedica"


def politica_csp(fontes_google: bool = True) -> str:
    ph = " ".join(origens_posthog())
    gf = GOOGLE_FONTS if fontes_google else {"style": "", "font": ""}
    frames = _origens_pixels("frame")
    diretivas = [
        "default-src 'self'",
        f"script-src 'self' 'unsafe-inline' {ph} {_origens_pixels('script')}",
        f"style-src 'self' 'unsafe-inline' {gf['style']}",
        f"font-src 'self' {gf['font']}",
        f"img-src 'self' data: blob: {_origens_pixels('img')}",
        f"connect-src 'self' {ph} {_origens_pixels('connect')}",
        "worker-src 'self' blob:",
        *([f"frame-src 'self' {frames}"] if frames else []),
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
    return "; ".join(" ".join(d.split()) for d in diretivas)


def cabecalhos(request=None) -> dict[str, str]:
    return {
        "Content-Security-Policy": politica_csp(precisa_google_fonts(request)),
        "Strict-Transport-Security": "max-age=31536000",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    }


async def cabecalhos_de_seguranca(request, call_next):
    resposta = await call_next(request)
    for nome, valor in cabecalhos(request).items():
        resposta.headers.setdefault(nome, valor)
    return resposta

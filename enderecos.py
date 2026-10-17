"""
Valderez Astrologia — endereços do site (rodada 18): o endereço público, o e-mail
de contato, as redes da Dona Valderez e o redirecionamento do domínio antigo.

Fonte única em `conteudo/ocidental/marca.yaml` (`site`, `contato`, `redes`). Antes,
`padmini.com.br` estava escrito à mão em ~20 arquivos e o e-mail de contato em 5.

  - SITE_URL: PADMINI_SITE_URL, na Render, vence; sem ela, o `site` do marca.yaml.
    É a base de canonical, og:url, og:image, sitemap, robots.txt, JSON-LD e e-mails.
  - Redirecionamento (PADMINI_DOMINIO_PRINCIPAL, ex.: valderezastrologia.com.br):
    pedido que chega por padmini.com.br, www.padmini.com.br ou www.<principal> vai,
    com 301, para https://<principal>, com o mesmo caminho e a query inteira (os
    links já entregues têm `token`). Sem a variável, nada redireciona: o merge é
    seguro antes do DNS ficar pronto. NUNCA redireciona /webhook/* nem /api/* (POST
    não sobrevive a 301, e o webhook da Stripe continua apontado para o domínio
    antigo), nem método que não seja GET/HEAD. padmini.onrender.com também não (é
    por ele que o ping diário chega, sem depender de DNS).
"""
import os
from pathlib import Path
from urllib.parse import urlparse

import yaml

_MARCA = yaml.safe_load((Path(__file__).parent / "conteudo" / "ocidental" / "marca.yaml")
                        .read_text(encoding="utf-8")) or {}

SITE_URL = (os.environ.get("PADMINI_SITE_URL") or _MARCA["site"]).strip().rstrip("/")
# só o domínio ("padmini.com.br"), para o texto que a pessoa lê (termos, card do casal)
SITE_HOST = urlparse(SITE_URL).netloc or SITE_URL
CONTATO = str(_MARCA["contato"]).strip()
REDES: list[dict] = [dict(r) for r in _MARCA.get("redes") or []]

# Domínios antigos que passam a só redirecionar (o registro continua: é ele que
# segura os links antigos e o webhook).
DOMINIOS_ANTIGOS = ("padmini.com.br", "www.padmini.com.br")
_SEM_REDIRECIONAR = ("/webhook/", "/api/")


def dominio_principal() -> str:
    """PADMINI_DOMINIO_PRINCIPAL sem esquema nem barra ("" = redirecionamento desligado)."""
    valor = os.environ.get("PADMINI_DOMINIO_PRINCIPAL", "").strip().lower()
    return (urlparse(valor).netloc if "//" in valor else valor).strip("/")


def destino_301(metodo: str, host: str, caminho: str, query: str) -> str | None:
    """Para onde o pedido vai com 301, ou None (atende aqui mesmo)."""
    principal = dominio_principal()
    if not principal or metodo not in ("GET", "HEAD") or caminho.startswith(_SEM_REDIRECIONAR):
        return None
    host = host.split(":")[0].strip().lower().rstrip(".")
    if host == principal or host not in (*DOMINIOS_ANTIGOS, f"www.{principal}"):
        return None
    return f"https://{principal}{caminho}" + (f"?{query}" if query else "")


async def redirecionar_dominio_antigo(request, call_next):
    """Middleware: o 301 do domínio antigo (e do www) para o principal."""
    from starlette.responses import RedirectResponse
    escopo = request.scope
    caminho = (escopo.get("raw_path") or escopo["path"].encode()).decode("latin-1")
    destino = destino_301(request.method, request.headers.get("host", ""), caminho,
                          escopo.get("query_string", b"").decode("latin-1"))
    if destino:
        return RedirectResponse(destino, status_code=301)
    return await call_next(request)

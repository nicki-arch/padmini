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

import icones

_MARCA = yaml.safe_load((Path(__file__).parent / "conteudo" / "ocidental" / "marca.yaml")
                        .read_text(encoding="utf-8")) or {}

SITE_URL = (os.environ.get("PADMINI_SITE_URL") or _MARCA["site"]).strip().rstrip("/")
# só o domínio ("padmini.com.br"), para o texto que a pessoa lê (termos, card do casal)
SITE_HOST = urlparse(SITE_URL).netloc or SITE_URL
CONTATO = str(_MARCA["contato"]).strip()
# Rodada 20.1: o User-Agent de toda chamada nossa para fora (Resend, GeoNames). O padrão do
# Python ("Python-urllib/3.x") é barrado pela proteção na frente da API do Resend (403,
# "error code: 1010") antes de chegar à conta: nenhum e-mail do site saía.
USER_AGENT = f"ValderezAstrologia/1.0 (+{SITE_URL})"
# todas as redes do YAML, ligadas ou não (a validação abaixo vale para as duas)
TODAS_AS_REDES: list[dict] = [dict(r) for r in _MARCA.get("redes") or []]
# rede com ícone que não existe ou endereço sem https quebra na subida, não na página no ar
for _r in TODAS_AS_REDES:
    if _r.get("icone") not in icones.NOMES or not str(_r.get("url", "")).startswith("https://") or not _r.get("nome"):
        raise ValueError(f"marca.yaml → redes: {_r!r} precisa de nome, url https:// e um ícone de "
                         f"static/valderez/icones/ ({', '.join(icones.NOMES)})")
    if not isinstance(_r.get("ativa", True), bool):
        raise ValueError(f"marca.yaml → redes: {_r['nome']}: `ativa` é true ou false, não {_r['ativa']!r}")


def ativas(redes: list[dict]) -> list[dict]:
    """Só as redes com `ativa` (sem a chave = ativa)."""
    return [r for r in redes if r.get("ativa", True)]


# Rodada 19.1: só as redes ATIVAS. Rodapé, "quem revisa", /links e o sameAs do JSON-LD
# leem daqui, então uma rede com `ativa: false` some de todos de uma vez.
REDES: list[dict] = ativas(TODAS_AS_REDES)


def arroba_principal(redes: list[dict]) -> str:
    """O @ que vale para "as redes" num texto só (a linha do @ da /links): o que mais redes
    ativas usam; no empate, o da primeira. Rodada 20.1: o Instagram tem um @ próprio
    (com sublinhado), então "redes[0].arroba" escreveria o do Instagram para o TikTok também."""
    arrobas = [r["arroba"] for r in redes if r.get("arroba")]
    return max(arrobas, key=arrobas.count) if arrobas else ""


ARROBA = arroba_principal(REDES)

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

"""
Smoke test contra o site publicado. Rodar depois de CADA deploy.

    python scripts/smoke_producao.py                      # padmini.com.br
    python scripts/smoke_producao.py https://padmini.onrender.com

Não compra nada e não precisa de segredo: só confere que o site responde, que a
busca de cidades funciona, que as amostras saem e que o pago continua trancado.
Sai com código 1 se algo falhar (serve para CI).
"""
import json
import sys
import time
import urllib.error
import urllib.request

# Padrão é o domínio de verdade: é por ele que o cliente chega, então o smoke
# também confere DNS e certificado, não só o app.
BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://padmini.com.br").rstrip("/")
PESSOA = {"nome": "Smoke", "data": "1990-05-15", "hora": "14:30",
          "lat": -23.5505, "lon": -46.6333, "cidade": "São Paulo"}
PESSOA_B = {**PESSOA, "nome": "Smoke B", "data": "1992-03-10", "hora": "08:00"}


def req(caminho, corpo=None, timeout=90):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    r = urllib.request.Request(BASE + caminho, data=dados,
                               headers={"Content-Type": "application/json"} if dados else {})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


CHECAGENS = []


def checar(nome):
    def deco(f):
        CHECAGENS.append((nome, f))
        return f
    return deco


for rota in ("/", "/mapa", "/compatibilidade", "/privacidade", "/termos"):
    checar(f"página {rota} responde 200")(lambda rota=rota: req(rota)[0] == 200)


@checar("botões de compra apontam para a Cakto")
def _():
    return (b"pay.cakto.com.br" in req("/mapa")[1]
            and b"pay.cakto.com.br" in req("/compatibilidade")[1])


@checar("busca de cidades retorna resultados")
def _():
    st, corpo = req("/api/cidades?q=Porto%20Alegre")
    return st == 200 and len(json.loads(corpo)) > 0


@checar("amostra do mapa sai grátis")
def _():
    return req("/api/mapa", {**PESSOA, "nivel": "amostra"})[0] == 200


@checar("amostra do casal sai grátis")
def _():
    return req("/api/compatibilidade", {"a": PESSOA, "b": PESSOA_B, "nivel": "amostra"})[0] == 200


@checar("mapa completo trancado sem token (402)")
def _():
    return req("/api/mapa", {**PESSOA, "nivel": "completo"})[0] == 402


@checar("casal completo trancado sem token (402)")
def _():
    return req("/api/compatibilidade", {"a": PESSOA, "b": PESSOA_B, "nivel": "completo"})[0] == 402


@checar("PDF trancado sem token (402)")
def _():
    return req("/api/pdf", {**PESSOA, "nivel": "completo"})[0] == 402


@checar("webhook recusa evento sem assinatura (401)")
def _():
    return req("/webhook/cakto", {"event": "purchase_approved", "data": {"status": "paid"}})[0] == 401


@checar("IA não sai na amostra grátis do casal (402)")
def _():
    return req("/api/compatibilidade",
               {"a": PESSOA, "b": PESSOA_B, "nivel": "amostra", "texto_ia": True})[0] == 402


@checar("cabeçalhos de segurança presentes (CSP, HSTS, anti-iframe, Referrer-Policy)")
def _():
    with urllib.request.urlopen(BASE + "/", timeout=60) as r:
        h = {k.lower(): v for k, v in r.headers.items()}
    return ("frame-ancestors 'none'" in h.get("content-security-policy", "")
            and h.get("strict-transport-security", "").startswith("max-age=")
            and h.get("x-frame-options") == "DENY"
            and h.get("referrer-policy") == "strict-origin-when-cross-origin")


@checar("tarefas agendadas recusam chamada sem chave (401/503)")
def _():
    return req("/api/tarefas/lembretes", {})[0] in (401, 503)


@checar("descadastro recusa link sem assinatura")
def _():
    st, corpo = req("/descadastrar?e=x%40y.com&t=errado")
    return st == 200 and "inválido".encode() in corpo


@checar("página do casal mostra o preço do ofertas.yaml")
def _():
    import pathlib
    import yaml
    raiz = pathlib.Path(__file__).resolve().parents[1]
    preco = yaml.safe_load((raiz / "conteudo" / "ofertas.yaml").read_text(encoding="utf-8"))["compat"]["preco"]
    return f"relatório completo por <b>R${preco}</b>".encode() in req("/compatibilidade")[1]


def main():
    # o plano grátis "dorme": a primeira chamada acorda o servidor
    for _ in range(3):
        try:
            if req("/", timeout=120)[0] == 200:
                break
        except Exception:
            time.sleep(5)
    falhas = 0
    for nome, f in CHECAGENS:
        try:
            ok = f()
        except Exception as e:  # noqa: BLE001
            ok, nome = False, f"{nome} ({e})"
        print(("OK   " if ok else "FALHA"), nome)
        falhas += not ok
    print(f"\n{len(CHECAGENS) - falhas}/{len(CHECAGENS)} checagens OK em {BASE}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()

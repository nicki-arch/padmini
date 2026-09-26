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


def _raiz():
    import pathlib
    return pathlib.Path(__file__).resolve().parents[1]


def _ofertas_do_yaml(versao: str) -> dict:
    import yaml
    return yaml.safe_load((_raiz() / "conteudo" / versao / "ofertas.yaml").read_text(encoding="utf-8")) or {}


def _versao_no_ar() -> str:
    """PADMINI_SISTEMA do site publicado (vedica | ocidental), via /api/config."""
    st, corpo = req("/api/config")
    return (json.loads(corpo).get("sistema") if st == 200 else "") or "vedica"


@checar("página do casal mostra o preço do ofertas.yaml")
def _():
    import re
    preco = _ofertas_do_yaml(_versao_no_ar())["compat"]["preco"]
    return re.search(rf"relatório completo por <b[^>]*>R\${preco}</b>".encode(), req("/compatibilidade")[1]) is not None


# ---------------------------------------------------------------------------
# Versão ocidental. A API dela fica publicada qualquer que seja a versão no ar
# (links já entregues nunca quebram), então é conferida SEMPRE; as páginas de
# numerologia e tarot só existem com a ocidental no ar (com a védica, 404).
# ---------------------------------------------------------------------------
NUMEROLOGIA = {"nome": "Smoke da Silva", "data": "1990-05-15"}


@checar("[ocidental] amostras dos 4 produtos saem grátis")
def _():
    tiragem = req("/api/ocidental/tarot/tirar", {})
    return (req("/api/ocidental/mapa", {**PESSOA, "nivel": "amostra"})[0] == 200
            and req("/api/ocidental/sinastria", {"a": PESSOA, "b": PESSOA_B, "nivel": "amostra"})[0] == 200
            and req("/api/ocidental/numerologia", {**NUMEROLOGIA, "nivel": "amostra"})[0] == 200
            and tiragem[0] == 200 and len(json.loads(tiragem[1])["cartas"]) == 3)


@checar("[ocidental] completos e PDFs dos 4 produtos trancados sem token (402)")
def _():
    t = json.loads(req("/api/ocidental/tarot/tirar", {})[1])["tiragem"]
    return all(req(c, corpo)[0] == 402 for c, corpo in [
        ("/api/ocidental/mapa", {**PESSOA, "nivel": "completo"}),
        ("/api/ocidental/pdf", {**PESSOA, "nivel": "completo"}),
        ("/api/ocidental/sinastria", {"a": PESSOA, "b": PESSOA_B, "nivel": "completo"}),
        ("/api/ocidental/numerologia", {**NUMEROLOGIA, "nivel": "completo"}),
        ("/api/ocidental/numerologia/pdf", {**NUMEROLOGIA, "nivel": "completo"}),
        ("/api/ocidental/tarot", {"tiragem": t, "nivel": "completo"}),
        ("/api/ocidental/tarot/pdf", {"tiragem": t, "nivel": "completo"}),
    ])


@checar("[ocidental] tiragem de tarot inventada é recusada (422)")
def _():
    return req("/api/ocidental/tarot", {"tiragem": "AAAAAAAAAAAAAAAA"})[0] == 422


@checar("páginas de numerologia e tarot: 200 com a ocidental no ar, 404 com a védica")
def _():
    esperado = 200 if _versao_no_ar() == "ocidental" else 404
    return req("/numerologia")[0] == esperado and req("/tarot")[0] == esperado


@checar("[ocidental no ar] botões de compra dos 4 produtos apontam para a Cakto")
def _():
    if _versao_no_ar() != "ocidental":
        return True  # só vale com a ocidental no ar (a védica é conferida acima)
    return all(b"pay.cakto.com.br" in req(p)[1] for p in ("/mapa", "/compatibilidade", "/numerologia", "/tarot"))


# ---------------------------------------------------------------------------
# YAML = Cakto. A checagem acima só garante site = YAML; esta fecha o ciclo:
# o preço anunciado precisa estar entre os valores que o checkout mostra.
# Foi o bug de 26/set/2026: o site dizia R$97 (com R$127 riscado) e a oferta
# cobrava R$127 — o cupom que o site repassava ia só como utm_term.
# ---------------------------------------------------------------------------
AVISOS = []
NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def valores_do_checkout(html: str) -> set:
    """Valores em reais que a página do checkout mostra ('R$ 127,00' → 127).
    Ignora os de um dígito: são o chamariz de parcelamento ("6x de R$ 9,99")
    ou centavos soltos, nunca o preço de uma oferta nossa."""
    import re
    texto = html.replace("&nbsp;", " ").replace("\u00a0", " ").replace("\xa0", " ")
    valores = set()
    for inteiro in re.findall(r"R\$\s?(\d{1,3}(?:\.\d{3})*),\d{2}", texto):
        n = int(inteiro.replace(".", ""))
        if n >= 10:
            valores.add(n)
    return valores


def conferir_precos_na_cakto(ofertas: dict, baixar=None) -> list:
    """Para cada oferta com `checkout`, confere que `preco` aparece no checkout.
    Devolve a lista de falhas (texto). Cakto fora do ar = aviso, não falha."""
    def _baixar(url):
        r = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR,
                                                 "Accept-Language": "pt-BR,pt;q=0.9"})
        with urllib.request.urlopen(r, timeout=45) as resp:
            return resp.read().decode("utf-8", "replace")
    baixar = baixar or _baixar
    falhas = []
    for chave, oferta in ofertas.items():
        url, preco = str(oferta.get("checkout") or ""), oferta.get("preco")
        if not url or not preco:
            continue
        try:
            valores = valores_do_checkout(baixar(url))
        except Exception as e:  # noqa: BLE001
            AVISOS.append(f"checkout de '{chave}' não respondeu ({e}); preço não conferido")
            continue
        if not valores:
            AVISOS.append(f"checkout de '{chave}' não mostrou nenhum valor; preço não conferido")
        elif int(preco) not in valores:
            falhas.append(f"'{chave}': site anuncia R${preco}, checkout mostra "
                          + ", ".join(f"R${v}" for v in sorted(valores)))
    return falhas


@checar("preço do ofertas.yaml bate com o que a Cakto cobra (as duas versões)")
def _():
    falhas = []
    for versao in ("vedica", "ocidental"):
        falhas += [f"[{versao}] {f}" for f in conferir_precos_na_cakto(_ofertas_do_yaml(versao))]
    for f in falhas:
        print("      ", f)
    return not falhas


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
    for aviso in AVISOS:
        print("AVISO", aviso)
    print(f"\n{len(CHECAGENS) - falhas}/{len(CHECAGENS)} checagens OK em {BASE}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()

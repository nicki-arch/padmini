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


class _SemSeguir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None  # o 302 volta como HTTPError, com o Location


def destino(caminho, timeout=90):
    """(status, Location) de `caminho` SEM seguir o redirecionamento."""
    try:
        with urllib.request.build_opener(_SemSeguir).open(BASE + caminho, timeout=timeout) as resp:
            return resp.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location", "")


def _captura_no_ar() -> bool:
    """PADMINI_CAPTURA=1 no site: `/` responde 302 para a lista de espera (/lista).

    Com a captura ligada, as páginas de compra não mostram botão nem preço — de
    propósito. Sem isto o smoke reprovava de hora em hora (28/set/2026) sem nada
    quebrado. O AVISO no fim do smoke diz que ela está ligada, para ninguém
    esquecer."""
    st, onde = destino("/")
    if not (st in (301, 302, 303, 307) and onde.split("?")[0].endswith("/lista")):
        return False
    if not any("captura ligada" in a for a in AVISOS):
        AVISOS.append("captura ligada (PADMINI_CAPTURA=1): as páginas vão para /lista; botões de compra e "
                      "preço nas páginas não foram conferidos (voltam sozinhos quando a captura desligar)")
    return True


ORIGEM = "utm_source=smoke&utm_campaign=pos-deploy&ref=SMOKE"


@checar("[captura] páginas redirecionam para /lista mantendo utm_* e ref")
def _():
    if not _captura_no_ar():
        return True
    paginas = ["/", "/mapa", "/compatibilidade"]
    if _versao_no_ar() == "ocidental":
        paginas += ["/numerologia", "/tarot"]  # com a védica no ar, 404 (conferido abaixo)
    ok = True
    for p in paginas:
        st, onde = destino(f"{p}?{ORIGEM}")
        if not (st == 302 and onde.split("?")[0].endswith("/lista") and onde.endswith("?" + ORIGEM)):
            print(f"       {p}: {st} → {onde or '(sem Location)'}")
            ok = False
    return ok


@checar("[captura] /lista responde e a inscrição sem autorização de e-mail é recusada (422)")
def _():
    if not _captura_no_ar():
        return True
    st, corpo = req("/lista")
    # sem aceita_email a API recusa antes de gravar: nada entra na lista de verdade
    recusa = req("/api/lista", {"email": "smoke@padmini.com.br", "aceita_email": False})[0]
    return st == 200 and b"/api/lista" in corpo and recusa == 422


@checar("botões de compra apontam para a Cakto")
def _():
    if _captura_no_ar() or not _vendas_abertas():
        return True
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


def _vendas_abertas() -> bool:
    """Interruptor de venda da ocidental (catalogo.yaml → vendas_abertas), via /api/config.
    Site anterior à rodada 9 (sem o campo) = vende, como sempre. Venda fechada: as
    checagens de botão e preço dão lugar às de "venda fechada" (abaixo)."""
    st, corpo = req("/api/config")
    aberta = json.loads(corpo).get("vendas_abertas", True) if st == 200 else True
    if not aberta and not any("venda fechada" in a for a in AVISOS):
        AVISOS.append("venda fechada (catalogo.yaml → vendas_abertas: false): conferido que NÃO há preço nem "
                      "link da Cakto nas páginas, em vez dos botões de compra")
    return aberta


def _versao_no_ar() -> str:
    """PADMINI_SISTEMA do site publicado (vedica | ocidental), via /api/config."""
    st, corpo = req("/api/config")
    return (json.loads(corpo).get("sistema") if st == 200 else "") or "vedica"


@checar("página do casal mostra o preço do ofertas.yaml")
def _():
    import re
    if _captura_no_ar() or not _vendas_abertas():
        return True
    preco = _ofertas_do_yaml(_versao_no_ar())["compat"]["preco"]
    return re.search(rf"relatório completo por <b[^>]*>R\${preco}</b>".encode(), req("/compatibilidade")[1]) is not None


# ---------------------------------------------------------------------------
# Versão ocidental. A API dela fica publicada qualquer que seja a versão no ar
# (links já entregues nunca quebram), então é conferida SEMPRE; as páginas de
# numerologia e tarot só existem com a ocidental no ar (com a védica, 404).
# ---------------------------------------------------------------------------
NUMEROLOGIA = {"nome": "Smoke da Silva", "data": "1990-05-15"}


@checar("[ocidental] amostras dos 4 produtos pedem o e-mail (422 sem ele)")
def _():
    # Rodada 6: sem e-mail não há amostra. O smoke confere o portão e NÃO pede
    # amostra com e-mail — isso mandaria um e-mail de verdade e gravaria no banco
    # a cada hora. A amostra com e-mail é coberta pelos testes (test_rodada6).
    return (req("/api/ocidental/mapa", {**PESSOA, "nivel": "amostra"})[0] == 422
            and req("/api/ocidental/sinastria", {"a": PESSOA, "b": PESSOA_B, "nivel": "amostra"})[0] == 422
            and req("/api/ocidental/numerologia", {**NUMEROLOGIA, "nivel": "amostra"})[0] == 422
            and req("/api/ocidental/tarot/tirar", {})[0] == 422)


@checar("[ocidental] completos e PDFs trancados sem token (402)")
def _():
    # O tarot sai desta lista: sem sorteio (que agora pede e-mail) não há tiragem
    # válida para testar; o 402 dele fica nos testes (test_tarot).
    return all(req(c, corpo)[0] == 402 for c, corpo in [
        ("/api/ocidental/mapa", {**PESSOA, "nivel": "completo"}),
        ("/api/ocidental/pdf", {**PESSOA, "nivel": "completo"}),
        ("/api/ocidental/sinastria", {"a": PESSOA, "b": PESSOA_B, "nivel": "completo"}),
        ("/api/ocidental/numerologia", {**NUMEROLOGIA, "nivel": "completo"}),
        ("/api/ocidental/numerologia/pdf", {**NUMEROLOGIA, "nivel": "completo"}),
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
    if _versao_no_ar() != "ocidental" or _captura_no_ar() or not _vendas_abertas():
        return True  # só vale com a ocidental no ar vendendo (a védica é conferida acima)
    return all(b"pay.cakto.com.br" in req(p)[1] for p in ("/mapa", "/compatibilidade", "/numerologia", "/tarot"))


# ---------------------------------------------------------------------------
# Rodada 9: catálogo e venda fechada (ocidental). Com a captura desligada e
# vendas_abertas: false, o site abre sem vender: a amostra do mapa natal sai, a
# sinastria aparece "em breve", os produtos ocultos respondem 404 e nenhuma
# página mostra preço nem link da Cakto.
# ---------------------------------------------------------------------------
PAGINAS_PUBLICAS = ("/", "/mapa", "/compatibilidade", "/numerologia", "/tarot", "/leituras")


@checar("[ocidental] produto oculto responde 404 (/comunidade)")
def _():
    if _versao_no_ar() != "ocidental":
        return True
    return req("/comunidade")[0] == 404


@checar("[venda fechada] /, /mapa e /leituras respondem 200; a sinastria mostra \"em breve\"")
def _():
    if _versao_no_ar() != "ocidental" or _captura_no_ar() or _vendas_abertas():
        return True
    st, sinastria = req("/compatibilidade")
    return (all(req(p)[0] == 200 for p in ("/", "/mapa", "/leituras"))
            and st == 200 and "em breve" in sinastria.decode("utf-8", "replace").lower())


@checar("[venda fechada] nenhuma página mostra preço nem link da Cakto")
def _():
    if _versao_no_ar() != "ocidental" or _captura_no_ar() or _vendas_abertas():
        return True
    ok = True
    for p in PAGINAS_PUBLICAS:
        corpo = req(p)[1]
        if b"R$" in corpo or b"pay.cakto" in corpo:
            print(f"       {p}: tem preço ou link da Cakto")
            ok = False
    return ok


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


def _ofertas_py():
    """ofertas.py do repositório (moeda e cálculo do cupom: a mesma conta do site)."""
    import pathlib
    raiz = str(pathlib.Path(__file__).resolve().parents[1])
    if raiz not in sys.path:
        sys.path.insert(0, raiz)
    import ofertas
    return ofertas


def conferir_precos_na_cakto(ofertas: dict, baixar=None) -> list:
    """Para cada oferta com `checkout`, confere que `preco` aparece no checkout.
    Devolve a lista de falhas (texto). Cakto fora do ar = aviso, não falha.

    - Order bump (`bump_de: compat`): não tem checkout próprio; o acréscimo
      (preço do combo − preço de tabela da oferta-mãe) tem de aparecer no
      checkout da oferta-mãe.
    - Cupom (`cupom_percentual` + `cupom_codigos`): abre o checkout com
      `?coupon=<código>`. Se o HTML trouxer o desconto ("Desconto (24%)"), o
      percentual e o preço com cupom (R$96,52) têm de ser os nossos. Na prática a
      página da Cakto é montada por JavaScript e o urllib não vê o desconto: aí
      sai um AVISO pedindo a conferência à mão (não é falha). Não pôr navegador
      no smoke/CI: ver docs/ocidental.md, "Cupom do Pedro"."""
    import re

    def _baixar(url):
        r = urllib.request.Request(url, headers={"User-Agent": NAVEGADOR,
                                                 "Accept-Language": "pt-BR,pt;q=0.9"})
        with urllib.request.urlopen(r, timeout=45) as resp:
            return resp.read().decode("utf-8", "replace")
    baixar = baixar or _baixar
    op = _ofertas_py()
    falhas = []
    # só as ofertas: o YAML também tem valores soltos (ex.: taxa_plataforma: 0.99)
    ofertas = {k: v for k, v in ofertas.items() if isinstance(v, dict)}
    for chave, oferta in ofertas.items():
        mae = ofertas.get(oferta.get("bump_de") or "") or {}
        url = str((mae if mae else oferta).get("checkout") or "")
        preco = oferta.get("preco")
        esperado = preco - mae["preco"] if mae and preco else preco
        if not url or not preco or not oferta.get("checkout"):
            continue
        try:
            html = baixar(url)
            valores = valores_do_checkout(html)
        except Exception as e:  # noqa: BLE001
            AVISOS.append(f"checkout de '{chave}' não respondeu ({e}); preço não conferido")
            continue
        if not valores:
            AVISOS.append(f"checkout de '{chave}' não mostrou nenhum valor; preço não conferido")
        elif int(esperado) not in valores:
            falhas.append(f"'{chave}': site anuncia R${op.moeda(esperado)}"
                          + (f" (bump no checkout de '{oferta['bump_de']}')" if mae else "")
                          + ", checkout mostra " + ", ".join(f"R${v}" for v in sorted(valores)))
        pct = oferta.get("cupom_percentual")
        for codigo in [str(c).strip().lower() for c in oferta.get("cupom_codigos") or []] if pct else []:
            com_cupom = op.moeda(op.com_desconto(preco, pct))
            try:
                texto = _normalizar(baixar(url + ("&" if "?" in url else "?") + "coupon=" + codigo))
            except Exception as e:  # noqa: BLE001
                AVISOS.append(f"checkout de '{chave}' com cupom '{codigo}' não respondeu ({e})")
                continue
            desconto = re.search(r"Desconto\s*\((\d+)%\)", texto)
            if not desconto:
                # A página da Cakto é montada por JavaScript: sem navegador (e o smoke
                # não tem, de propósito) o desconto nunca aparece no HTML. Não é
                # falha, é limite do smoke: a conferência do cupom é à mão.
                AVISOS.append(f"cupom '{codigo}' em '{chave}': não dá para conferir sem navegador (a página da "
                              f"Cakto é montada por JavaScript). Confira à mão: abra "
                              f"{url}{'&' if '?' in url else '?'}coupon={codigo} e veja se aparece "
                              f"R${com_cupom} ({pct}% de desconto).")
            elif int(desconto.group(1)) != int(pct) or not re.search(rf"R\$\s?{re.escape(com_cupom)}(?!\d)", texto):
                falhas.append(f"'{chave}' com cupom '{codigo}': site anuncia R${com_cupom} ({pct}%), checkout "
                              f"mostra desconto de {desconto.group(1)}%")
    return falhas


def _normalizar(html: str) -> str:
    return html.replace("&nbsp;", " ").replace("\u00a0", " ").replace("\xa0", " ")


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

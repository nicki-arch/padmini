"""
A versão ocidental está pronta para ir ao ar?

    python scripts/pronto_para_virar.py

Lista o que ainda impede trocar PADMINI_SISTEMA para `ocidental` na Render:

  1. oferta sem link de checkout em conteudo/ocidental/ofertas.yaml (o botão
     de compra fica "em breve" e o webhook não reconhece a venda);
  2. texto com `revisado: false` (a família ainda não leu) ou fora das regras
     de tom e tamanho;
  3. página, e-mail ou imagem de compartilhamento da versão ocidental que fala
     em astrologia védica (a copy da outra versão vazando).

Não mexe em nada, não precisa de rede nem de segredo. Sai com código 1 se
houver bloqueio. A troca em si continua sendo do Nicolas (ver CLAUDE.md).
"""
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Palavras que só a versão védica usa. "Padmini" (o nome da marca) pode.
VEDICO = re.compile(r"v[ée]dic|jyotish|sideral|lahiri|nakshatra|dasha|guna milan|ashtakoot|kundli|पद्मिनी", re.I)
# Ofertas que não bloqueiam: sem link, a linha do combo simplesmente some da página.
OPCIONAIS = {"bump_mapas_casal": "combo casal + 2 mapas: sem link, a oferta some da página do casal"}


def ofertas_sem_link() -> tuple[list[str], list[str]]:
    import ofertas
    bloqueios, avisos = [], []
    for chave, o in ofertas.do_sistema("ocidental").items():
        if str(o.get("checkout") or "").strip():
            continue
        linha = f"{chave} ({o.get('nome', chave)}, R${o.get('preco')}): sem link de checkout"
        (avisos if chave in OPCIONAIS else bloqueios).append(
            linha + (f" — {OPCIONAIS[chave]}" if chave in OPCIONAIS else ""))
    return bloqueios, avisos


def textos() -> tuple[list[str], dict]:
    import revisao
    problemas, por_produto = [], {}
    for i in revisao.itens():
        feito, total = por_produto.get(i["produto"], (0, 0))
        por_produto[i["produto"]] = (feito + i["revisado"], total + 1)
        for p in revisao.problemas(i["texto"], i["arquivo"], i["caminho"]):
            problemas.append(f"{i['id']}: {p}")
    return problemas, por_produto


def paginas_com_vedica() -> list[str]:
    """Renderiza as páginas e e-mails da ocidental e procura a copy da védica."""
    antes = os.environ.get("PADMINI_SISTEMA")
    os.environ["PADMINI_SISTEMA"] = "ocidental"
    try:
        return _procurar_vedica()
    finally:
        if antes is None:
            os.environ.pop("PADMINI_SISTEMA", None)
        else:
            os.environ["PADMINI_SISTEMA"] = antes


def _procurar_vedica() -> list[str]:
    from fastapi.testclient import TestClient

    import app as app_mod
    import entrega
    import sistema

    app_mod._paginas_prontas.clear()
    achados = []
    cliente = TestClient(app_mod.app)
    rotas = list(sistema.PAGINAS["ocidental"]) + list(sistema.LEGAIS["ocidental"])
    for rota in rotas:
        r = cliente.get(rota)
        if r.status_code != 200:
            achados.append(f"página {rota}: respondeu {r.status_code}")
            continue
        for m in sorted({m.group(0).lower() for m in VEDICO.finditer(r.text)}):
            achados.append(f'página {rota}: fala em "{m}"')
        for img in re.findall(r'og:image" content="https://padmini\.com\.br/(static/[^"]+)"', r.text):
            if not (RAIZ / img).exists():
                achados.append(f"página {rota}: imagem de compartilhamento {img} não existe")
            elif not Path(img).name.startswith("og-oc-"):
                achados.append(f"página {rota}: usa a imagem de compartilhamento da védica ({img})")
    live = (RAIZ / "static" / sistema.LIVE["ocidental"]).read_text(encoding="utf-8")
    for m in sorted({m.group(0).lower() for m in VEDICO.finditer(live)}):
        achados.append(f'página /live: fala em "{m}"')
    emails = {f"e-mail de entrega ({p})": entrega.email_completo_html(p, "https://padmini.com.br/x", "Ana", "",
                                                                      "ocidental")
              for p in ("mapa", "compat", "numerologia", "tarot")}
    emails["e-mail dos mapas do casal"] = entrega.email_mapas_do_casal_html([("Ana", "https://x")], "Ana",
                                                                           "ocidental")
    for nome, corpo in emails.items():
        for m in sorted({m.group(0).lower() for m in VEDICO.finditer(corpo)}):
            achados.append(f'{nome}: fala em "{m}"')
    app_mod._paginas_prontas.clear()
    return achados


def verificar() -> dict:
    sem_link, avisos = ofertas_sem_link()
    problemas, por_produto = textos()
    nao_revisados = [f"{p}: {t - f} de {t} textos com revisado: false"
                     for p, (f, t) in sorted(por_produto.items()) if f < t]
    return {"ofertas": sem_link, "avisos": avisos, "revisao": nao_revisados, "textos": problemas,
            "vedica": paginas_com_vedica(), "por_produto": por_produto}


def main() -> int:
    r = verificar()
    blocos = [("Ofertas sem link de checkout", r["ofertas"]),
              ("Textos ainda não revisados pela família", r["revisao"]),
              ("Textos fora das regras de tom e tamanho", r["textos"]),
              ("Páginas, e-mails ou imagens falando da versão védica", r["vedica"])]
    total = 0
    print("PRONTO PARA VIRAR? (versão ocidental)\n")
    for titulo, itens in blocos:
        print(f"{'OK      ' if not itens else 'BLOQUEIO'} {titulo}" + (f" ({len(itens)})" if itens else ""))
        for i in itens:
            print(f"           - {i}")
        total += len(itens)
    for a in r["avisos"]:
        print(f"AVISO    {a}")
    revisados = sum(f for f, _ in r["por_produto"].values())
    todos = sum(t for _, t in r["por_produto"].values())
    print(f"\nTextos revisados: {revisados} de {todos}.")
    print("\nPRONTO para trocar PADMINI_SISTEMA para ocidental." if not total else
          f"\nNÃO está pronto: {total} bloqueio(s) acima.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())

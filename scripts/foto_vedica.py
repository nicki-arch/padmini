"""
Foto da versão védica: as páginas, respostas da API, links e e-mails de entrega
exatamente como saem hoje, em `testes/dados/vedica_html/`.

`testes/test_sistema.py` compara o site com esta foto (com PADMINI_SISTEMA
ausente e com `vedica`): é a prova de que o trabalho da versão ocidental não
mexeu na védica. Só regenerar quando a védica mudar DE PROPÓSITO (e dizer no
commit o que mudou):

    python scripts/foto_vedica.py
"""
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "testes" / "dados" / "vedica_html"

# O mesmo ambiente dos testes (testes/test_app.py): os valores entram nos links.
AMBIENTE = {"PADMINI_SECRET": "segredo-de-teste-tokens",
            "PADMINI_CAKTO_WEBHOOK_SECRET": "segredo-de-teste-webhook",
            "PADMINI_SITE_URL": "https://padmini.teste"}
PESSOA = {"nome": "Ana", "data": "1990-05-15", "hora": "14:30",
          "lat": -23.5505, "lon": -46.6333, "cidade": "São Paulo, SP"}
PESSOA_B = {"nome": "Bruno", "data": "1992-03-10", "hora": "08:00",
            "lat": -22.9068, "lon": -43.1729, "cidade": "Rio de Janeiro, RJ"}

PAGINAS = [("/", "home.html"), ("/mapa", "mapa.html"), ("/compatibilidade", "compatibilidade.html"),
           ("/lista", "lista.html"), ("/robots.txt", "robots.txt"), ("/sitemap.xml", "sitemap.xml"),
           ("/privacidade", "privacidade.html"), ("/termos", "termos.html")]


def _json(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8")


def gerar(cliente) -> dict[str, bytes]:
    """{nome do arquivo: conteúdo}. `cliente` é um TestClient do app."""
    import entrega
    import marketing
    foto = {}
    for rota, nome in PAGINAS:
        r = cliente.get(rota)
        assert r.status_code == 200, (rota, r.status_code)
        foto[nome] = r.content
    foto["api_mapa_amostra.json"] = _json(cliente.post("/api/mapa", json={**PESSOA, "nivel": "amostra"}).json())
    foto["api_compat_amostra.json"] = _json(
        cliente.post("/api/compatibilidade", json={"a": PESSOA, "b": PESSOA_B, "nivel": "amostra"}).json())
    dm = {k: str(v) for k, v in PESSOA.items()}
    db_ = {k: str(v) for k, v in PESSOA_B.items()}
    lm = entrega.link_completo("mapa", dm)
    lc = entrega.link_completo("compat", {"a": dm, "b": db_})
    foto["links_entrega.txt"] = (lm + "\n" + lc + "\n").encode("utf-8")
    foto["email_entrega_compat.html"] = entrega.email_completo_html(
        "compat", lc, "Ana", marketing.bloco_venda_cruzada("compat", {"a": dm, "b": db_})).encode("utf-8")
    foto["email_entrega_mapa.html"] = entrega.email_completo_html(
        "mapa", lm, "Ana", marketing.bloco_venda_cruzada("mapa", dm)).encode("utf-8")
    token = lm.split("token=")[1]
    r = cliente.post("/api/mapa", json={**PESSOA, "nivel": "completo", "token": token})
    assert r.status_code == 200, r.text
    foto["api_mapa_completo.json"] = _json(r.json())
    return foto


def main():
    for k, v in AMBIENTE.items():
        os.environ[k] = v
    for k in ("PADMINI_MODO_ABERTO", "RESEND_API_KEY", "ANTHROPIC_API_KEY", "PADMINI_SISTEMA",
              "PADMINI_CAPTURA"):
        os.environ.pop(k, None)
    sys.path.insert(0, str(RAIZ))
    from fastapi.testclient import TestClient
    import app
    for nome, conteudo in gerar(TestClient(app.app)).items():
        (PASTA / nome).write_bytes(conteudo)
        print("gravado", nome)


if __name__ == "__main__":
    main()

"""
Traz para o site a planilha revisada pela família (gerada por exportar_revisao.py).

    python scripts/importar_revisao.py revisao-textos.xlsx           # só mostra o que mudaria
    python scripts/importar_revisao.py revisao-textos.xlsx --gravar  # grava nos YAMLs

Os YAMLs moram no repositório PRIVADO nicki-arch/padmini-conteudo (rodada 10). Aponte
para o clone dele com --conteudo ../padmini-conteudo ou PADMINI_CONTEUDO_DIR; sem isso,
grava na cópia que o build pôs no projeto (que some no próximo build). Depois de gravar,
o commit e o PR são no padmini-conteudo; o site muda no próximo deploy da Render.

Para cada linha:
  - "texto revisado" preenchido → vira o texto do site;
  - "aprovado?" = sim → o texto (o novo, ou o atual) fica marcado revisado: true;
  - texto revisado fora do tamanho, com palavra proibida ou com os marcadores
    {a}/{b}/{nome}... trocados → a linha é RECUSADA inteira (nada dela é gravado)
    e aparece na lista de recusados, com o motivo.
Depois de gravar: rodar os testes e abrir um PR no padmini-conteudo.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import conteudo_privado  # noqa: E402
# Os textos moram no repo privado (rodada 10): --conteudo PASTA ou PADMINI_CONTEUDO_DIR
sys.argv = conteudo_privado.tirar_argumento(sys.argv)

from openpyxl import load_workbook  # noqa: E402

import revisao  # noqa: E402

SIM = {"sim", "s", "x", "ok", "yes", "aprovado"}


def ler(planilha: Path) -> list[dict]:
    wb = load_workbook(planilha, read_only=True, data_only=True)
    linhas = []
    for ws in wb.worksheets:
        cabecalho = None
        for valores in ws.iter_rows(values_only=True):
            if cabecalho is None:
                if valores and valores[0] == "id":
                    cabecalho = [str(v or "").strip() for v in valores]
                    continue
                break  # aba sem tabela (ex.: "Como revisar")
            d = dict(zip(cabecalho, valores))
            if d.get("id"):
                linhas.append({"aba": ws.title, **d})
    return linhas


def planejar(linhas: list[dict]) -> tuple[list[dict], list[tuple], list[str]]:
    """(alterações, recusados [(id, motivos)], ids desconhecidos)."""
    por_id = {i["id"]: i for i in revisao.itens()}
    alteracoes, recusados, desconhecidos = [], [], []
    for l in linhas:
        item = por_id.get(str(l["id"]).strip())
        if not item:
            desconhecidos.append(str(l["id"]))
            continue
        novo = " ".join(str(l.get("texto revisado") or "").split())
        aprovado = str(l.get("aprovado?") or "").strip().lower() in SIM
        if novo == item["texto"]:
            novo = ""
        if novo:
            erros = revisao.problemas(novo, item["arquivo"], item["caminho"], item["texto"])
            if erros:
                recusados.append((item["id"], erros))
                continue
        if not novo and not (aprovado and not item["revisado"]):
            continue  # nada a fazer nesta linha
        alteracoes.append({"id": item["id"], "arquivo": item["arquivo"], "caminho": item["caminho"],
                           "texto": novo or None, "revisado": True if aprovado else None,
                           "onde": item["onde"]})
    return alteracoes, recusados, desconhecidos


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if any(a in ("-h", "--help") for a in args):
        print(__doc__.strip())
        return
    ruins = [a for a in args if a.startswith("-") and a != "--gravar"]
    arquivos = [a for a in args if not a.startswith("-")]
    if ruins or len(arquivos) != 1:
        sys.exit((f"Opção inválida: {' '.join(ruins)}\n" if ruins else "") + __doc__.strip())
    planilha = Path(arquivos[0])
    alteracoes, recusados, desconhecidos = planejar(ler(planilha))
    novos = [a for a in alteracoes if a["texto"]]
    aprovados = [a for a in alteracoes if a["revisado"]]
    print(f"{planilha}: {len(novos)} textos novos, {len(aprovados)} aprovados, "
          f"{len(recusados)} recusados, {len(desconhecidos)} ids desconhecidos\n")
    for a in alteracoes:
        o_que = "texto novo" + (" + aprovado" if a["revisado"] else "") if a["texto"] else "aprovado"
        print(f"  {o_que:22s} {a['onde']}")
    if recusados:
        print("\nRECUSADOS (nada destas linhas foi gravado):")
        for id_, erros in recusados:
            print(f"  {id_}: {'; '.join(erros)}")
    if desconhecidos:
        print("\nIDs que não existem mais na base (linha ignorada):", ", ".join(desconhecidos))
    if "--gravar" not in args:
        print("\nNada foi gravado. Para gravar: acrescente --gravar.")
        return
    if alteracoes:
        gravados = revisao.gravar(alteracoes)
        import montar_texto_ocidental as mt
        print("\nGravado em:", ", ".join(str(mt.PASTA / f"{g}.yaml") for g in gravados))
        if conteudo_privado.RAIZ == conteudo_privado.PROJETO:
            print("\nATENÇÃO: gravado na cópia do projeto, que o próximo build substitui. Para valer, "
                  "grave num clone do padmini-conteudo (--conteudo PASTA) e faça o commit lá.")
        else:
            print(f"\nAgora: rodar os testes e abrir um PR no padmini-conteudo ({conteudo_privado.RAIZ}).")


if __name__ == "__main__":
    main()

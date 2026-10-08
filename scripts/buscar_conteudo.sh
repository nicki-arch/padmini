#!/bin/bash
# Traz o conteúdo proprietário (rodada 10) do repositório PRIVADO
# nicki-arch/padmini-conteudo para o checkout, nos mesmos caminhos:
#
#     base_significacoes.py
#     conteudo/ocidental/textos/
#     conteudo/ocidental/blog/
#
# Usado pelo build.sh (Render) e pelo CI. De onde vem:
#   - PADMINI_CONTEUDO_DIR=<pasta>   um clone local do repo privado (sem rede);
#   - PADMINI_CONTEUDO_TOKEN=<token> clona o repo privado (token de leitura só dele).
# Sem nenhum dos dois, ou se faltar algum arquivo lá, FALHA (regra 4 do CLAUDE.md:
# segurança falha fechada): nunca sobe um site sem os textos.
set -euo pipefail

REPO="nicki-arch/padmini-conteudo"
ITENS=("base_significacoes.py" "conteudo/ocidental/textos" "conteudo/ocidental/blog")
DESTINO="$(pwd)"

if [ -n "${PADMINI_CONTEUDO_DIR:-}" ]; then
    ORIGEM="$(cd "$PADMINI_CONTEUDO_DIR" && pwd)"
    echo "Copiando o conteúdo de $ORIGEM (PADMINI_CONTEUDO_DIR)..."
    if [ "$ORIGEM" = "$DESTINO" ]; then
        echo "ERRO: PADMINI_CONTEUDO_DIR aponta para o próprio projeto; use um clone do $REPO." >&2
        exit 1
    fi
elif [ -n "${PADMINI_CONTEUDO_TOKEN:-}" ]; then
    ORIGEM="$(mktemp -d)"
    trap 'rm -rf "$ORIGEM"' EXIT
    echo "Buscando base_significacoes.py, textos e blog do repositório privado $REPO..."
    git clone --quiet --depth 1 \
        "https://x-access-token:${PADMINI_CONTEUDO_TOKEN}@github.com/${REPO}.git" "$ORIGEM"
else
    echo "ERRO: sem PADMINI_CONTEUDO_TOKEN (nem PADMINI_CONTEUDO_DIR) não há como buscar os textos de" >&2
    echo "interpretação, que moram no repositório privado $REPO. O build para aqui para não subir" >&2
    echo "um site sem textos. Na Render: Environment -> PADMINI_CONTEUDO_TOKEN (token de leitura só" >&2
    echo "desse repositório). No GitHub Actions: secret CONTEUDO_REPO_TOKEN." >&2
    exit 1
fi

for item in "${ITENS[@]}"; do
    if [ ! -e "$ORIGEM/$item" ]; then
        echo "ERRO: $item não existe no $REPO. O build para aqui (o site não sobe sem ele)." >&2
        exit 1
    fi
done
for item in "${ITENS[@]}"; do
    rm -rf "${DESTINO:?}/$item"
    mkdir -p "$(dirname "$DESTINO/$item")"
    cp -R "$ORIGEM/$item" "$DESTINO/$item"
done
echo "OK: conteúdo do $REPO copiado ($(ls "$DESTINO"/conteudo/ocidental/textos/*.yaml | wc -l) arquivos de texto ocidentais, $(ls "$DESTINO"/conteudo/ocidental/blog/*.yaml 2>/dev/null | wc -l) artigos do blog, base_significacoes.py)."

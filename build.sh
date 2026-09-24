#!/bin/bash
# Build da Render. Busca base_significacoes.py de um repositório PRIVADO separado
# (nicki-arch/padmini-conteudo) antes de instalar as dependências, para que o
# texto de interpretação não fique visível no repositório público do código.
#
# Por que assim, e não guardando no banco: o site precisa continuar funcionando
# mesmo se o Supabase estiver fora do ar (regra do db.py). Buscar aqui, só na
# hora do build, mantém essa garantia — depois de instalado, o processo não
# depende de rede nenhuma para gerar um relatório.
#
# Compatível com a transição: se PADMINI_CONTEUDO_TOKEN ainda não está configurado
# E o arquivo já existe no repositório (fase antes da migração), o build segue
# normalmente sem baixar nada.

set -e

if [ -n "$PADMINI_CONTEUDO_TOKEN" ]; then
    echo "Buscando base_significacoes.py do repositório privado de conteúdo..."
    rm -rf /tmp/padmini-conteudo
    git clone --depth 1 \
        "https://x-access-token:${PADMINI_CONTEUDO_TOKEN}@github.com/nicki-arch/padmini-conteudo.git" \
        /tmp/padmini-conteudo
    cp /tmp/padmini-conteudo/base_significacoes.py ./base_significacoes.py
    rm -rf /tmp/padmini-conteudo
    echo "OK: base_significacoes.py atualizado a partir do repositório privado."
elif [ -f "base_significacoes.py" ]; then
    echo "PADMINI_CONTEUDO_TOKEN não definido — usando base_significacoes.py já presente no repositório (fase de transição)."
else
    echo "ERRO: base_significacoes.py não existe e PADMINI_CONTEUDO_TOKEN não está definido."
    echo "Configure PADMINI_CONTEUDO_TOKEN na Render com um token de leitura do repositório nicki-arch/padmini-conteudo."
    exit 1
fi

pip install -r requirements.txt

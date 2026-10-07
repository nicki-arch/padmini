#!/bin/bash
# Build da Render. O Build Command no painel TEM de ser `bash build.sh` (o render.yaml
# não é lido: os serviços foram criados pelo painel).
#
# Rodada 10: os textos de interpretação (o ativo vendido) moram no repositório PRIVADO
# nicki-arch/padmini-conteudo, fora do repositório público do código (AGPL-3.0). O
# scripts/buscar_conteudo.sh clona esse repo com PADMINI_CONTEUDO_TOKEN e copia
# base_significacoes.py, conteudo/ocidental/textos/ e conteudo/ocidental/blog/.
# Sem o token, o build FALHA com mensagem clara: não existe mais o modo de transição
# que seguia com os arquivos do repositório público (segurança falha fechada).
#
# Por que no build, e não no banco: o site precisa continuar funcionando mesmo se o
# Supabase estiver fora do ar (regra do db.py). Depois de instalado, o processo não
# depende de rede nenhuma para gerar um relatório.

set -euo pipefail

bash scripts/buscar_conteudo.sh
pip install -r requirements.txt

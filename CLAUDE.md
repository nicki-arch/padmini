# Padmini — contexto para quem for mexer no código

Site de astrologia védica (Jyotish) para o mercado brasileiro, modelo freemium:
amostra grátis → paga na Cakto → recebe por e-mail um link assinado que abre o completo.
Sócios: Nicolas (produto/tecnologia) e Pedro Monteiro (conteúdo, lives no TikTok).

## Fontes de verdade
- **Código:** este repositório (`github.com/nicki-arch/padmini`, branch `master`).
  Cópias de código em outros lugares (ex.: Claude Project) podem estar desatualizadas — não confiar nelas.
- **Estado, decisões e pendências:** no Claude Project "Projeto Padmini":
  `claude/LEIA-PRIMEIRO.md` (ponto de entrada), `claude/decisoes.md`, `claude/checklist-de-lancamento.md`.
- **Produção:** https://padmini.onrender.com (Render, serviço `srv-dalfcj3l550s73b38jmg`,
  deploy automático a cada push na `master`).

## Mapa do código
| Arquivo | Papel |
|---|---|
| `app.py` | FastAPI: páginas, `/api/*`, `/webhook/cakto` |
| `compute_chart.py` | Cálculo do mapa (Swiss Ephemeris, sideral Lahiri, whole sign) |
| `detectar_fatos.py`, `montar_texto.py`, `base_significacoes.py` | Fatos do mapa → texto; IA (Claude) só reescreve |
| `compatibilidade.py` | Guna Milan / Ashtakoot (36 pontos), doshas |
| `acesso.py` | Token HMAC que libera o completo (sem token = 402) |
| `cakto.py` | Webhook: assinatura HMAC `v1=` sobre `{timestamp}.{corpo}`; dados de nascimento vêm no `sck` |
| `entrega.py` | Link assinado + e-mail (Resend) |
| `static/afiliado.js` | Monta o link do checkout: dados no `sck`, afiliado/cupom dobrados em `utm_*` |
| `cidades.py` + `data/cidades_index.tsv` | Autocomplete de cidades (GeoNames) |
| `gerar_pdf.py` | PDF do completo |

## Regras (cada uma vem de um erro real)
1. **Rodar os testes antes de commitar:** `python -m pytest -q testes`. Tudo verde ou não sobe.
2. **Ler o diffstat antes de commitar.** Arquivo de produção encolhendo centenas de linhas = suspeito
   (parte 16: stubs de teste de `cidades.py`/`gerar_pdf.py` foram para produção e travaram o site).
3. **Nunca sobrepor o repositório com outro diretório em bloco.** Copiar só o que mudou de propósito.
4. **Segurança falha fechada:** sem segredo configurado, webhook e completo recusam
   (parte 17: o webhook aceitava qualquer POST). Testar o caminho de rejeição, não só o de aceite.
5. **Integração externa: ler a doc oficial antes.** A Cakto só repassa `utm_*` e `sck` ao webhook.
6. **Bug encontrado = teste novo** em `testes/` que falharia com o bug.
7. **Depois de cada deploy:** `python scripts/smoke_producao.py`.
8. `PADMINI_MODO_ABERTO=1` só em staging, **nunca** em produção.

## Commits
Mensagens em português, explicando o porquê. Sem force-push na `master`.

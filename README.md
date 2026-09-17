# Padmini — Mapa Védico (v0.3)

Site com formulário (data, hora e cidade de nascimento) que calcula o mapa védico e mostra o relatório do Mapa Védico Essencial, com opção de versão escrita por IA (Claude).

## Publicação

O site roda no Render (https://padmini.onrender.com), ligado ao repositório do GitHub: cada `git push` na branch `master` publica a nova versão sozinho em 1 a 2 minutos. A chave da Anthropic fica nas variáveis de ambiente do serviço no Render.

## Rodar no Windows

Dê dois cliques em **`iniciar.bat`**. Ele faz tudo sozinho, sem depender do Anaconda:

1. Na primeira vez, baixa o [uv](https://github.com/astral-sh/uv) para `.ferramentas/` e cria um Python 3.11 só deste projeto em `.venv/` (o `pyswisseph` só tem instalador pronto para Windows até o Python 3.11). Leva alguns minutos.
2. Instala as bibliotecas, se faltar alguma.
3. Se ainda não existir o `.env`, pede a chave da Anthropic (Enter para pular).
4. Sobe o site e abre http://127.0.0.1:8000 no navegador. Fechar a janela desliga o site.

Para reinstalar do zero, apague as pastas `.venv` e `.ferramentas` e rode o `iniciar.bat` de novo.

O índice de cidades (`data/cidades_index.tsv`) já vem pronto. Se um dia precisar refazer, rode `python baixar_dados.py`.

## Chave da API (texto por IA)

A chave fica no arquivo `.env` (linha `ANTHROPIC_API_KEY=...`). O botão "Ler versão escrita por IA" só aparece quando ela existe.
- Nunca envie o `.env` para o GitHub (o `.gitignore` já o exclui).
- Para trocar de modelo, adicione `PADMINI_MODELO=nome-do-modelo` no `.env` (padrão: `claude-sonnet-5`).
- Cada texto gerado custa uma chamada à API. Num site público, isso precisa de limite de uso por visitante antes de divulgar.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `compute_chart.py` | Cálculo do mapa: Lahiri, casas por signo inteiro, nó médio, fuso automático |
| `detectar_fatos.py` | Regras clássicas: dignidades, combustão, yogas, doshas |
| `base_significacoes.py` | Textos interpretativos (rascunho por IA, precisa de revisão) |
| `montar_texto.py` | Monta o relatório em seções e o pedido para o Claude |
| `gerar_pdf.py` | Relatório completo em PDF (capa com mapa, planetas com nakshatra e dignidade, leitura, 12 casas, fases e subperíodos, glossário). Sem IA. Rodar `python gerar_pdf.py exemplo.pdf` gera um exemplo |
| `fontes/` | Inter e Cormorant Garamond usadas no PDF (SIL Open Font License, licenças na pasta) |
| `cidades.py` / `baixar_dados.py` | Busca local de cidades (GeoNames) |
| `app.py` | Servidor web (FastAPI): `/api/mapa`, `/api/pdf`, `/api/cidades` |
| `static/index.html` | A página |

## Testes

```
python testes/test_referencias.py
```

Confere 5 mapas conhecidos (Obama, Einstein, Churchill, JFK, Marilyn Monroe) contra posições da Cosmolica, com tolerância de 2'. Rodar antes de publicar qualquer mudança no cálculo.

## Pendências conhecidas

- Textos de planeta em cada casa (108) ainda não existem.
- A busca de cidades só entende o nome da cidade ("Woodstock"), não "cidade, país"; e lugares que não são cidades ("Blenheim Palace") não aparecem.
- Ainda não mostramos a relação de amizade/inimizade do planeta com o signo (a Cosmolica mostra).
- Raj Yoga só por conjunção; Neecha Bhanga só com a condição principal; Mangal Dosha sem regras de cancelamento.
- A versão por IA às vezes acrescenta ligações próprias entre os trechos (ex.: metáforas). Revisar alguns exemplos antes de liberar ao público.
- Nomes de cidades estrangeiras aparecem em inglês (ex.: "Lisbon"), embora a busca por "Lisboa" funcione.
- Licença: o Swiss Ephemeris é AGPL. Num site público, isso obriga a publicar o código-fonte do site, a menos que se compre a licença profissional do Swiss Ephemeris.
- O GeoNames (CC BY 4.0) exige o crédito que está no rodapé.

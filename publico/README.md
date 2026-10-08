# padmini-codigo

Código-fonte do site **[padmini.com.br](https://padmini.com.br)**: Padmini (astrologia védica)
e Valderez Astrologia (astrologia ocidental, numerologia e tarot), em Python/FastAPI.

## Por que este repositório existe

O site calcula os mapas com o [Swiss Ephemeris](https://www.astro.com/swisseph/) (Astrodienst,
via `pyswisseph`), sob a **GNU Affero General Public License v3.0**. A AGPL pede que quem usa o
site tenha acesso ao código que roda nele. É isso que está aqui, sob a mesma licença: veja
[`LICENSE`](LICENSE).

## Este repositório é um espelho

- Ele é atualizado sozinho a cada mudança no repositório de desenvolvimento, que é privado.
  Cada commit aqui se chama `sync: padmini@<sha>`, com o commit de origem.
- **Pull requests e issues não são aceitos aqui:** este repositório só recebe cópias. Para
  falar com a gente, use o contato do rodapé do site.

## O que NÃO está incluído (todos os direitos reservados)

Estes itens não estão neste repositório e não são cobertos pela AGPL nem por qualquer outra
licença livre:

- os **textos de interpretação** (mapa natal, sinastria, numerologia, tarot, védica) e os
  artigos do blog;
- as **ilustrações** do site;
- as **marcas** "Padmini" e "Valderez Astrologia" e os seus símbolos (a roda). Os arquivos do
  símbolo que o site usa estão aqui só porque fazem parte das páginas; isso não dá licença de
  uso da marca;
- a copy das páginas e os documentos internos.

Sem os textos, o site **não inicia**: ele avisa no log o que falta. Isso é de propósito, para
nunca subir uma versão pela metade. O código que monta as leituras a partir desses textos está
todo aqui; os textos em si moram num repositório privado e entram só na hora do build
(`scripts/buscar_conteudo.sh`).

## De terceiros

- Fontes em `static/valderez/fontes/` e `fontes/`: SIL Open Font License, com o texto ao lado de
  cada arquivo.
- Índice de cidades do [GeoNames](https://www.geonames.org/): CC BY 4.0, com o crédito no rodapé
  do site.

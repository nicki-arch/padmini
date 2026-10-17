# Domínio novo: valderezastrologia.com.br (rodada 18)

Decisão do Nicolas (16/out/2026): o domínio principal passa a ser
`https://valderezastrologia.com.br`. O `padmini.com.br` continua registrado e só
redireciona.

## Como o código decide o endereço

Fonte única: `conteudo/ocidental/marca.yaml` (`site`, `contato`, `redes`), lida pelo
`enderecos.py`.

| O quê | De onde vem |
|---|---|
| Endereço público (canonical, `og:url`, `og:image`, sitemap, `robots.txt`, JSON-LD, links dos e-mails) | `PADMINI_SITE_URL`; sem ela, `site` do `marca.yaml` |
| 301 do domínio antigo | `PADMINI_DOMINIO_PRINCIPAL` (vazio = nada redireciona) |
| E-mail de contato (rodapé, `/minhas-leituras`, `/mapa`, `/seu-ano`, termos, privacidade, Reply-To das sequências) | `contato` do `marca.yaml` (`PADMINI_EMAIL_RESPOSTA` vence só no Reply-To) |
| Redes da Dona Valderez (rodapé, "quem revisa", `sameAs`) | `redes` do `marca.yaml` |

Nos templates ocidentais: `{{ site }}`, `{{ site_host }}`, `{{ contato }}`, `{{ redes }}`.
Um teste (`testes/test_rodada18.py`) falha se `padmini.com.br` ou o e-mail de contato
voltar escrito à mão em `static/ocidental/`. A védica (`static/*.html`) não muda.

### O redirecionamento

Com `PADMINI_DOMINIO_PRINCIPAL=valderezastrologia.com.br`, pedido GET/HEAD que chega por
`padmini.com.br`, `www.padmini.com.br` ou `www.valderezastrologia.com.br` recebe 301 para
`https://valderezastrologia.com.br`, com o **mesmo caminho e a query inteira** (os links já
entregues têm `token`). Nunca redireciona:

- `/webhook/*` e `/api/*`: POST não sobrevive a 301, e o webhook da Stripe continua
  apontado para `padmini.com.br`;
- POST e outros métodos;
- `padmini.onrender.com` (o ping diário chega por ele, sem depender de DNS).

O cookie de consentimento é por domínio: quem aceitou no antigo vê o aviso uma vez no
novo. É de propósito (o consentimento não é copiado entre domínios). Os cookies do site
(`pad_previa`, `pad_live`) não têm `domain=`, então valem só no host que os gravou.
A CSP usa `'self'`: vale para os dois domínios sem mudança.

## Operação (Nicolas com o Cowork, depois do merge)

Na ordem:

1. **Render** → `padmini` → Settings → Custom Domains: adicionar `valderezastrologia.com.br`
   e `www.valderezastrologia.com.br`. A Render mostra os registros de DNS.
2. **registro.br** → `valderezastrologia.com.br` → DNS: criar os registros que a Render
   pediu. Esperar o certificado ficar verde na Render.
3. **Resend** → Domains: adicionar o domínio, criar no registro.br os registros TXT e MX
   (SPF e DKIM) e verificar. Trocar `PADMINI_EMAIL_FROM` na Render para um remetente
   `@valderezastrologia.com.br`.
4. **Render (produção)**, Environment:
   - `PADMINI_SITE_URL=https://valderezastrologia.com.br`
   - `PADMINI_DOMINIO_PRINCIPAL=valderezastrologia.com.br`
5. **Stripe**: Payment method domains → adicionar o domínio novo (Apple Pay e Google
   Pay); Settings → Public details → site e e-mail de suporte novos. **O webhook não muda.**
6. **Google Search Console**: propriedade do domínio novo (TXT no registro.br), enviar o
   sitemap e fazer a "Mudança de endereço" a partir do antigo.
7. `python scripts/smoke_producao.py https://valderezastrologia.com.br` (confere também
   o 301 do antigo e o webhook lá sem redirecionar). Depois, trocar os links das bios.
8. Manter `padmini.com.br` renovado: é ele que segura os links antigos e o webhook.

Depois que tudo estiver verde (pode ser num PR pequeno):

- trocar `site` no `marca.yaml` para `https://valderezastrologia.com.br` (o padrão passa
  a ser o domínio novo, mesmo sem a variável);
- regenerar as imagens de compartilhamento com o domínio novo escrito no pé:
  `python scripts/gerar_og_ocidental.py` e commit dos `static/og-oc-*.png`;
- trocar o `pos-deploy.yml` para rodar o smoke contra o domínio novo;
- e-mail de contato novo: só quando a caixa existir (pergunta 21), trocando `contato`
  no `marca.yaml`.

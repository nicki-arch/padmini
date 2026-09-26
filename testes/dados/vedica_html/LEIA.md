# Foto da versão védica

Gerada **antes** da Fase 0.5 (o interruptor `PADMINI_SISTEMA`), com o código da
Fase 0. `testes/test_sistema.py` renderiza as mesmas páginas, respostas e e-mails
com `PADMINI_SISTEMA` ausente e com `vedica` e exige que saiam **idênticos** — é a
prova de que a troca de versão não mexeu no site védico.

Se um dia a védica mudar de propósito (texto, preço), regenere com
`python scripts/foto_vedica.py` e explique no commit o que mudou e por quê.

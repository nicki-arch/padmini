"""
Padmini (versão ocidental) — SEQUÊNCIAS DE E-MAIL (rodada 6, Fase E).

Mesma base da rodada 4 (marketing.py): a versão viaja com o registro, todo
e-mail tem descadastro, sem banco não manda. Uma tarefa diária
(/api/tarefas/sequencias, workflow `tarefas`) chama `rodar()`.

BOAS-VINDAS — só para quem marcou a caixa do formulário da amostra
("pode me mandar mais sobre a minha leitura", até 3 e-mails; consentimento).
Para assim que a pessoa compra ou se descadastra.
  passo 1 (D+1): mais sobre a leitura dela — um trecho que a amostra não trazia;
  passo 2 (D+3): como fica o completo — as partes do relatório dela, de verdade;
  passo 3 (D+6): o convite, com o link do checkout já com os dados.
Para quem entrou a partir da rodada 6 isso substitui o lembrete único
(db.lembretes_pendentes ignora quem marcou a caixa nova).

PÓS-COMPRA — cliente da ocidental (legítimo interesse, com descadastro):
  passo 1 (D+2): "fez sentido?" — convite a responder o e-mail;
  passo 2 (D+7): a próxima leitura da escada (mapa natal → sinastria →
                 numerologia → tarot) que a pessoa ainda não tem;
  passo 3 (D+14): pedido de depoimento, por resposta ao e-mail — nada é
                 publicado sem autorização por escrito (depoimentos.py).

Regras (db.envios_sequencia): o mesmo passo nunca sai duas vezes (índice
único; a linha é reservada antes do envio); ninguém recebe dois e-mails de
sequência no mesmo dia (horário de Brasília); um passo por pessoa por dia.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import catalogo
import db
import enderecos
import entrega
import marketing
import ofertas
from marketing import _botao, _cor, _e, _moldura, _ola, _p, _rodape_descadastro, _rotulo

log = logging.getLogger("padmini.sequencias")
SISTEMA = "ocidental"

DIAS_BOAS_VINDAS = {1: 1, 2: 3, 3: 6}
DIAS_POS_COMPRA = {1: 2, 2: 7, 3: 14}
ESCADA = ("mapa", "compat", "numerologia", "tarot")


def responder_para() -> str:
    """Para onde vão as respostas do pós-compra (o remetente é nao-responda@)."""
    return os.environ.get("PADMINI_EMAIL_RESPOSTA") or enderecos.CONTATO  # padrão: marca.yaml (rodada 18)


def _primeiro_nome(produto: str, dados: dict) -> str:
    nome = ((dados.get("a") or {}).get("nome") if produto == "compat" else dados.get("nome")) or ""
    return nome.strip().split(" ")[0] if nome.strip() else ""


# ------------------------------------------------------------------ o que cada passo mostra
def trecho_extra(produto: str, dados: dict) -> tuple[str, str, str]:
    """Passo 1 da boas-vindas: (assunto, título, texto) — um trecho de verdade da
    leitura da pessoa que a amostra NÃO trazia."""
    import montar_texto_ocidental as mt
    import rotas_ocidental as ro
    if produto == "previsao":  # rodada 13: o 2º tema do ano (a amostra trazia só o título)
        temas = _previsao_da_amostra(dados)["temas"]
        if temas:
            t = temas[1] if len(temas) > 1 else temas[0]
            return ("O segundo tema do seu ano", f"{t['titulo']} · {t['periodo']}", t["texto"])
        # rodada 17: um ano sem trânsito longo (45+ dias) pode não ter tema nenhum; aí o
        # trecho é o do mapa natal da mesma pessoa
        produto, dados = "mapa", {k: v for k, v in dados.items() if k != "inicio"}
    if produto == "mapa":
        mapa, _ = ro.calcular(ro.PedidoMapaOcidental(**dados))
        venus = mapa["pontos"]["venus"]
        signo = mt._nome_signo(venus)
        return (f"A sua Vênus em {signo}", f"Vênus em {signo} · o jeito de amar",
                mt.texto_signo("venus", venus["signo"]))
    if produto == "compat":
        import sinastria as si
        ma, _ = ro.calcular(ro.PedidoMapaOcidental(**dados["a"]))
        mb, _ = ro.calcular(ro.PedidoMapaOcidental(**dados["b"]))
        a, b = dados["a"].get("nome") or "Pessoa A", dados["b"].get("nome") or "Pessoa B"
        rel = mt.montar_sinastria(si.calcular_sinastria(ma, mb), ma, mb, a, b, "completo")
        vistos = {rel["ponto_forte"]["chave"], rel["ponto_atencao"]["chave"]}
        outras = [d for d in rel["dimensoes"] if d["chave"] not in vistos and d["nota"] is not None]
        d = max(outras, key=lambda x: x["nota"]) if outras else rel["dimensoes"][0]
        nota = f" — {d['nota']}/100" if d["nota"] is not None else ""
        return ("Uma das oito dimensões de vocês", f"{d['titulo']}{nota}", d["texto"])
    if produto == "numerologia":
        import numerologia as nu
        from datetime import date
        rel = mt.montar_numerologia(nu.calcular_numerologia(dados["nome"], date.fromisoformat(dados["data"])),
                                    "completo")
        x = next(n for n in rel["numeros"] if n["chave"] == "expressao")
        return ("O número do seu nome", f"{x['nome']}: {x['valor']}", f"{x['descricao']} {x['texto']}")
    import tarot
    cartas = tarot.cartas_da_tiragem(dados["tiragem"])
    return ("As suas três cartas, juntas", "O que as três cartas dizem juntas",
            mt.conjunto_tarot(cartas)[0])


def _previsao_da_amostra(dados: dict) -> dict:
    """O ano da amostra registrada (o mesmo período que ela viu), já montado."""
    import montar_previsao as mp
    import rotas_ocidental as ro
    from datetime import date
    pessoa = {k: v for k, v in dados.items() if k != "inicio"}
    prev = ro.calcular_previsao(ro.PedidoMapaOcidental(**pessoa), date.fromisoformat(dados["inicio"] + "-01"))
    return mp.completo(prev)


def partes_do_completo(produto: str, dados: dict) -> list[str]:
    """Passo 2 da boas-vindas: as partes do relatório completo DELA (títulos reais)."""
    import montar_texto_ocidental as mt
    import rotas_ocidental as ro
    if produto == "previsao":
        c = _previsao_da_amostra(dados)
        return ([f"Os três temas do seu ano: {'; '.join(t['titulo'] for t in c['temas'])}",
                 "Mês a mês, o que começa, o que está no auge e o que termina",
                 f"Por área da vida: {', '.join(a['nome'] for a in c['areas'])}"]
                + ([f"{len(c['eclipses'])} eclipses do período, na casa de cada um"] if c["eclipses"] else [])
                + (["A sua Revolução Solar"] if c["revolucao"] else []) + ["O relatório em PDF"])
    if produto == "mapa":
        mapa, _ = ro.calcular(ro.PedidoMapaOcidental(**dados))
        return [t for t in mt.montar_secoes(mapa) if t not in ("Antes de começar", "Para terminar")] \
            + ["A roda do seu mapa e o PDF"]
    if produto == "compat":
        import sinastria as si
        return ([f"As oito dimensões: {', '.join(d['titulo'] for d in si.DIMENSOES.values())}",
                 "A rosa das oito dimensões, com a nota de cada uma",
                 "Os aspectos entre os planetas de vocês, um a um",
                 "Os planetas de um nas casas do outro (com a hora de nascimento)"])
    if produto == "numerologia":
        import numerologia as nu
        return [nu.NOME_PT[k] for k in ("caminho_de_vida", "expressao", "alma", "personalidade", "dia", "ano_pessoal")] \
            + ["O relatório em PDF"]
    return ["A leitura de cada carta na sua posição: Situação, Desafio e Conselho",
            "O que as três cartas dizem juntas", "As mesmas cartas, guardadas no seu link, e o PDF"]


NO_COMPLETO = {"mapa": "no seu mapa natal completo", "compat": "na sinastria completa de vocês",
               "numerologia": "na sua numerologia completa", "tarot": "na leitura completa das suas cartas",
               "previsao": "no seu ano completo"}
NOME_DO_COMPLETO = {"mapa": "o seu mapa natal completo", "compat": "a sinastria completa de vocês",
                    "numerologia": "a sua numerologia completa", "tarot": "a leitura completa das suas cartas",
                    "previsao": "o seu ano completo"}
COM_SEQUENCIA = ESCADA + ("previsao",)  # produtos com texto de boas-vindas


# ------------------------------------------------------------------ e-mails
def email_boas_vindas(passo: int, produto: str, dados: dict, email: str) -> tuple[str, str]:
    """(assunto, html) do passo `passo` da boas-vindas."""
    c = _cor(SISTEMA)
    nome = _primeiro_nome(produto, dados)
    # venda fechada (catalogo.yaml): sem preço (a tarefa nem chega aqui; isto é a segunda trava)
    # rodada 16.1: "de R$97 por R$47" quando o ofertas.yaml tem `preco_de`; senão "R$47"
    preco = ofertas.texto_preco(ofertas.oferta(produto, SISTEMA)) if catalogo.vende(produto, SISTEMA) else ""
    link = marketing.link_checkout(produto, dados, f"boas_vindas_{passo}", SISTEMA)
    if passo == 1:
        assunto, titulo, texto = trecho_extra(produto, dados)
        corpo = (_ola(nome)
                 + _p("Prometemos mais sobre a sua leitura — aqui vai um pedaço que a amostra não mostrava:")
                 + _p(f'{_rotulo(titulo, c)}<br>{_e(texto)}')
                 + _p(f'<span style="color:{c["suave"]};font-size:13px">Isso é um trecho do completo. '
                      f'Daqui a uns dias a gente mostra como ele fica inteiro.</span>'))
    elif passo == 2:
        assunto = f"Como fica {NOME_DO_COMPLETO[produto]}"
        itens = "".join(f"<li style=\"margin:0 0 6px\">{_e(x)}</li>" for x in partes_do_completo(produto, dados))
        extra = (f'<p style="margin:0 0 12px"><a href="{_e(entrega.SITE_URL)}/compatibilidade#como-fica" '
                 f'style="color:{c["acento"]}">Veja um exemplo de relatório completo →</a></p>'
                 if produto == "compat" else "")
        corpo = (_ola(nome)
                 + _p(f"Isto é o que vem {NO_COMPLETO[produto]}, feito com os dados que você já preencheu:")
                 + f'<ul style="margin:0 0 14px;padding-left:20px">{itens}</ul>' + extra
                 + _botao(link, f"Ver o completo — {preco} →" if preco else "Ver o completo →", SISTEMA))
    else:
        assunto = "A sua leitura completa, quando você quiser"
        corpo = (_ola(nome)
                 + _p(f"Último e-mail desta série. Se quiser ir fundo, {NOME_DO_COMPLETO[produto]} está a um clique "
                      "— o link já leva os dados que você preencheu, é só pagar.")
                 + _botao(link, f"Quero o completo — {preco} →" if preco else "Quero o completo →", SISTEMA)
                 + _p(f'<span style="color:{c["suave"]};font-size:13px">Garantia de 7 dias: se não fizer sentido '
                      'para você, devolvemos o valor. E se não for agora, tudo bem: não mandamos mais nada '
                      'desta série.</span>'))
    return assunto, _moldura(corpo, _rodape_descadastro(email, SISTEMA), SISTEMA)


LEITURA_COMPRADA = {"mapa": "o seu mapa natal", "compat": "a sinastria de vocês", "numerologia": "a sua numerologia",
                    "tarot": "a leitura das suas cartas", "mapas_casal": "os mapas natais de vocês",
                    "previsao": "o seu ano"}


def proxima_da_escada(comprados: list[str]) -> str | None:
    """O próximo degrau (mapa → sinastria → numerologia → tarot) que a pessoa não tem."""
    tem = {p.split(":", 1)[-1] for p in comprados}
    if "mapas_casal" in tem:
        tem.add("mapa")
    return next((p for p in ESCADA if p not in tem), None)


def email_pos_compra(passo: int, produto: str, nome: str, email: str, comprados: list[str]) -> tuple[str, str] | None:
    """(assunto, html) do passo; None = não há o que mandar (passo pulado)."""
    c = _cor(SISTEMA)
    primeiro = (nome or "").strip().split(" ")[0]
    leitura = LEITURA_COMPRADA.get(produto.split(":", 1)[-1], "a sua leitura")
    if passo == 1:
        assunto = "Fez sentido?"
        corpo = (_ola(primeiro)
                 + _p(f"Faz dois dias que {_e(leitura)} chegou para "
                      "você. Fez sentido? Se alguma parte ficou confusa, ou se bateu forte, responda este e-mail "
                      "contando — a gente lê cada resposta.")
                 + _p(f'<span style="color:{c["suave"]};font-size:13px">E se não fez sentido nenhum, a garantia '
                      'de 7 dias continua valendo: é só responder pedindo o reembolso.</span>'))
    elif passo == 2:
        prox = proxima_da_escada(comprados)
        # o passo 2 só existe para oferecer a próxima leitura: com a venda fechada
        # (ou a próxima leitura fora do ar), é pulado
        if not prox or not catalogo.vende(prox, SISTEMA):
            return None
        titulo, texto = marketing.TEXTO_OUTRO_PRODUTO[prox]
        assunto = f"A próxima leitura: {titulo.lower()}"
        corpo = (_ola(primeiro)
                 + _p(f"Se a sua leitura abriu uma porta, a próxima costuma ser a <b>{_e(titulo.lower())}</b>: "
                      f"{_e(texto)}. Também começa por uma amostra grátis.")
                 + _botao(marketing.link_site(prox, "pos_compra"), f"Ver a {titulo.lower()} →", SISTEMA))
    else:
        assunto = "Posso te pedir uma coisa?"
        corpo = (_ola(primeiro)
                 + _p("Se a sua leitura fez alguma diferença, você toparia contar em duas ou três frases? "
                      "É só responder este e-mail.")
                 + _p(f'<span style="color:{c["suave"]};font-size:13px">Só publicamos um depoimento com a sua '
                      'autorização por escrito, e do jeito que você escolher (por exemplo, primeiro nome e a '
                      'inicial do sobrenome). Se preferir não, tudo bem — este é o último e-mail desta série.</span>'))
    return assunto, _moldura(corpo, _rodape_descadastro(email, SISTEMA), SISTEMA)


# ------------------------------------------------------------------ a tarefa diária
def _vencido(criado_em, dias: int, agora: datetime) -> bool:
    if criado_em.tzinfo is None:
        criado_em = criado_em.replace(tzinfo=timezone.utc)
    return agora >= criado_em + timedelta(days=dias)


def _enviar(email: str, sequencia: str, passo: int, referencia: int, montar, responder: str | None = None) -> str:
    """Reserva o passo, monta e envia. Devolve 'enviado' | 'pulado' | 'falhou' | 'repetido'."""
    try:
        msg = montar()
    except Exception:  # noqa: BLE001
        log.exception("sequência %s passo %s: falha ao montar", sequencia, passo)
        return "falhou"
    reserva = db.reservar_passo(email, sequencia, passo, referencia, pulado=msg is None)
    if reserva is None:
        return "repetido"  # o passo já existia (ou o banco falhou): nunca manda duas vezes
    if msg is None:
        return "pulado"
    assunto, html = msg
    ok = (entrega.enviar_email(email, assunto, html, responder_para=responder) if responder
          else entrega.enviar_email(email, assunto, html))
    if not ok:
        db.desfazer_reserva(reserva)  # tenta de novo amanhã
        return "falhou"
    return "enviado"


# ------------------------------------------------------------------ aniversário (rodada 13)
DIAS_ANTES_DO_ANIVERSARIO = 30


def aniversarios_alvo(hoje) -> list[str]:
    """Os "MM-DD" de quem faz aniversário daqui a 30 dias. Quem nasceu em 29/02, em ano
    que não é bissexto, entra junto com 1º/03."""
    alvo = hoje + timedelta(days=DIAS_ANTES_DO_ANIVERSARIO)
    dias = [alvo.strftime("%m-%d")]
    if alvo.strftime("%m-%d") == "03-01" and not (alvo.year % 4 == 0 and (alvo.year % 100 or alvo.year % 400 == 0)):
        dias.append("02-29")
    return dias


def email_aniversario(dados: dict, email: str, aniversario) -> tuple[str, str]:
    """(assunto, html): "o seu ano astrológico começa em…", com link para a amostra.
    Sem preço: quem decide é a página (e o e-mail só sai com o produto à venda)."""
    c = _cor(SISTEMA)
    nome = _primeiro_nome("previsao", dados)
    quando = f"{aniversario.day} de {('janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro')[aniversario.month - 1]}"
    link = marketing.link_site("previsao", "aniversario")
    corpo = (_ola(nome)
             + _p(f"O seu ano astrológico começa em <b>{_e(quando)}</b>, no seu aniversário: é quando o Sol volta "
                  "ao grau em que estava quando você nasceu.")
             + _p("Que tal olhar com calma para os próximos 12 meses? Em \"O seu ano\" você vê os três temas que "
                  "mais pesam no período, mês a mês o que começa e o que se encerra, e as janelas que se abrem. "
                  "Não é previsão de acontecimentos: é o clima do ano, para você escolher o que fazer com ele.")
             + _botao(link, "Ver os temas do meu ano, de graça →", SISTEMA)
             + _p(f'<span style="color:{c["suave"]};font-size:13px">Você recebe este e-mail porque pediu, numa '
                  "amostra, para receber mais sobre a sua leitura. Um por ano, perto do aniversário.</span>"))
    return "O seu ano astrológico começa em " + quando, _moldura(corpo, _rodape_descadastro(email, SISTEMA), SISTEMA)


def rodar_aniversarios(hoje, ja_hoje: set, contagem: dict) -> None:
    """Desligado até "O seu ano" estar à venda (catalogo.yaml: ativo e vendas abertas)."""
    if not catalogo.vende("previsao", SISTEMA):
        return
    alvo = hoje + timedelta(days=DIAS_ANTES_DO_ANIVERSARIO)
    for item in db.candidatos_aniversario(aniversarios_alvo(hoje)):
        if item["email"] in ja_hoje:
            continue
        # passo = o ano do aniversário: o índice único garante um por ano, nunca dois
        r = _enviar(item["email"], "aniversario", alvo.year, item["id"],
                    lambda i=item: email_aniversario(i["dados"], i["email"], alvo))
        contagem[r] += 1
        if r == "enviado":
            ja_hoje.add(item["email"])


def rodar(agora: datetime | None = None) -> dict:
    """Um passo por pessoa por dia, no máximo. Sem banco, não faz nada."""
    agora = agora or datetime.now(timezone.utc)
    contagem = {"enviado": 0, "pulado": 0, "falhou": 0, "repetido": 0}
    if not db.ativo():
        return contagem
    ja_hoje = set()
    # pós-compra primeiro: quem comprou sai da boas-vindas (a consulta já filtra)
    for item in db.candidatos_pos_compra():
        passo = item["feitos"] + 1
        if passo > 3 or item["recebeu_hoje"] or item["email"] in ja_hoje:
            continue
        if not _vencido(item["criado_em"], DIAS_POS_COMPRA[passo], agora):
            continue
        r = _enviar(item["email"], "pos_compra", passo, item["id"],
                    lambda i=item, n=passo: email_pos_compra(n, i["produto"], i["nome"], i["email"], i["comprados"]),
                    responder_para())
        contagem[r] += 1
        if r == "enviado":
            ja_hoje.add(item["email"])
    # Boas-vindas existe para levar à compra: com a venda fechada (catalogo.yaml),
    # fica parada — nenhum passo sai nem é marcado; volta quando a venda abrir.
    for item in (db.candidatos_boas_vindas() if catalogo.vendas_abertas(SISTEMA) else []):
        passo = item["feitos"] + 1
        if passo > 3 or item["recebeu_hoje"] or item["email"] in ja_hoje or item["sistema"] != SISTEMA:
            continue
        if item["produto"] not in COM_SEQUENCIA or not catalogo.vende(item["produto"], SISTEMA):
            continue  # boas-vindas só leva a produto que está à venda ("O seu ano" oculto: nada)
        if not _vencido(item["criado_em"], DIAS_BOAS_VINDAS[passo], agora):
            continue
        r = _enviar(item["email"], "boas_vindas", passo, item["id"],
                    lambda i=item, n=passo: email_boas_vindas(n, i["produto"], i["dados"], i["email"]))
        contagem[r] += 1
        if r == "enviado":
            ja_hoje.add(item["email"])
    rodar_aniversarios(agora.astimezone(ZoneInfo("America/Sao_Paulo")).date(), ja_hoje, contagem)
    return contagem

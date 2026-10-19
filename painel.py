"""
Valderez Astrologia — o /painel (rodada 15): sessão, CSRF e as ações que mudam o site.

Acesso:
  - senha única em PADMINI_PAINEL_SENHA (16 caracteres ou mais). Sem ela (ou curta
    demais), o /painel responde 404: falha fechada;
  - a sessão é um cookie assinado (acesso.emitir_sessao) de 12 h, HttpOnly, Secure e
    SameSite=Strict, que leva QUEM está mexendo (Nicolas ou Pedro) e uma impressão da
    senha: trocar a senha na Render derruba as sessões abertas;
  - todo POST leva o token CSRF, amarrado à sessão;
  - o login tem limite de tentativas erradas (limites.PAINEL_FALHAS_*).

O que o painel muda mora em `estado_site.py` (tabela config_site). O painel NÃO mexe em
preço, chaves, variáveis da Render, Stripe, Cakto, nem mostra dado de cliente.
"""
import hashlib
import hmac
import os
import time

import acesso

COOKIE = "pad_painel"
COOKIE_SO_PARA_MIM = "pad_painel_eu"
HORAS_SESSAO = 12
MINIMO_SENHA = 16
QUEM = ("Nicolas", "Pedro")


def senha() -> str:
    """A senha do painel, ou '' (painel desligado) sem a variável ou com menos de 16 caracteres."""
    s = os.environ.get("PADMINI_PAINEL_SENHA", "")
    return s if len(s) >= MINIMO_SENHA else ""


def ligado() -> bool:
    return bool(senha() and acesso.SEGREDO)


def _papel(quem: str) -> str:
    impressao = hashlib.sha256(senha().encode("utf-8")).hexdigest()[:12]
    return f"painel|{quem}|{impressao}"


def emitir_sessao(quem: str, agora: int | None = None) -> tuple[str, int]:
    expira = int(agora if agora is not None else time.time()) + HORAS_SESSAO * 3600
    return f"{quem}|{acesso.emitir_sessao(_papel(quem), expira)}", expira


def quem_da_sessao(valor: str | None) -> str | None:
    """Quem está logado neste cookie, ou None (sem cookie, vencido, forjado, senha trocada)."""
    if not (ligado() and valor and "|" in valor):
        return None
    quem, _, sessao = valor.partition("|")
    if quem not in QUEM:
        return None
    return quem if acesso.sessao_valida(_papel(quem), sessao) else None


def senha_confere(digitada: str) -> bool:
    s = senha()
    # bytes: compare_digest com str não-ASCII levantaria erro (500) em vez de recusar
    return bool(s) and hmac.compare_digest(str(digitada or "").encode("utf-8"), s.encode("utf-8"))


def csrf(valor_sessao: str) -> str:
    """O token CSRF desta sessão (vai num campo escondido de cada formulário)."""
    msg = f"csrf|{valor_sessao}".encode("utf-8")
    return hmac.new(acesso.SEGREDO.encode("utf-8"), msg, hashlib.sha256).hexdigest()[:32]


def csrf_confere(valor_sessao: str | None, token: str | None) -> bool:
    if not (valor_sessao and token and acesso.SEGREDO):
        return False
    return hmac.compare_digest(str(token).encode("utf-8"), csrf(valor_sessao).encode("utf-8"))


# =========================================================================== o que a tela mostra
import html as _html  # noqa: E402
import logging  # noqa: E402
from datetime import datetime  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

import catalogo  # noqa: E402
import estado_site  # noqa: E402
import ofertas  # noqa: E402

log = logging.getLogger("padmini.painel")
FUSO = ZoneInfo("America/Sao_Paulo")
NOMES_ESTADO = {"ativo": "Ativo", "em_breve": "Em breve", "oculto": "Oculto"}
# O efeito de cada modo, escrito na confirmação (o que a pessoa vai causar).
EFEITO_MODO = {
    "aberto": "O site volta ao normal: os produtos e a venda como estão neste painel.",
    "lista_espera": "O site vai mandar todo mundo para a lista de espera. Quem já comprou continua lendo.",
    "manutencao": "O site vai mostrar “Voltamos já” para todo mundo. Quem já comprou continua lendo pelo "
                  "link do e-mail.",
    "tudo_liberado_previa": "Todo mundo que abrir a prévia vai ver todos os produtos, com a venda de teste aberta.",
    "tudo_liberado_producao": "O público continua vendo o site normal. Só os navegadores logados neste painel "
                              "veem tudo liberado (e a leitura completa sem pagar).",
}
PALAVRA_ABRIR = "ABRIR"


class Recusa(ValueError):
    """Uma ação que o painel não faz; a mensagem vai para a tela como está."""


def efeito_do_modo(modo: str) -> str:
    if modo == "tudo_liberado":
        return EFEITO_MODO[f"tudo_liberado_{estado_site.ambiente()}"]
    return EFEITO_MODO[modo]


def vendas_decididas() -> bool:
    """O interruptor como está decidido (painel → YAML), sem o "tudo liberado" nem a venda de teste."""
    v = estado_site.salvo().get("vendas_abertas")
    return v if isinstance(v, bool) else bool(catalogo.dados()["vendas_abertas"])


def tem_preco(produto: dict) -> bool:
    """Produto sem `oferta` no catálogo não é vendido (comunidade, cursos…): não precisa de preço."""
    if not produto.get("oferta"):
        return True
    return bool(ofertas.oferta(produto["oferta"], "ocidental").get("preco"))


def _revisao_por_produto() -> dict:
    """Textos sem revisão por produto (conteudo/ocidental/textos/, repositório privado)."""
    try:
        import montar_texto_ocidental as mt
        contagem = mt.contagem_de_revisao()
    except Exception:  # noqa: BLE001
        log.exception("painel: não deu para contar os textos sem revisão")
        return {}
    contagem.pop("_total", None)
    faltam = {"mapa": 0, "compat": 0, "numerologia": 0, "tarot": 0, "previsao": 0, "calendario": 0}
    for arquivo, (revisados, total) in contagem.items():
        dono = {"sinastria": "compat", "numerologia": "numerologia", "tarot": "tarot"}.get(arquivo)
        if dono is None:
            dono = ("previsao" if arquivo.startswith("previsao/")
                    else "calendario" if arquivo.startswith("calendario/") else "mapa")
        faltam[dono] += total - revisados
    return faltam


def produtos() -> list[dict]:
    """Uma linha por produto do catálogo: o estado decidido (painel → YAML) e os avisos."""
    revisao = _revisao_por_produto()
    linhas = []
    for p in catalogo.produtos_do_yaml():
        estado = estado_site.estado_salvo(p["chave"], p["estado"])
        avisos = []
        if not tem_preco(p):
            avisos.append("sem preço")
        if revisao.get(p["chave"]):
            avisos.append(f"textos sem revisão: {revisao[p['chave']]}")
        faltam = faltam_para_o_kit(p)
        if faltam:
            avisos.append(aviso_do_kit(p))
        linhas.append({"chave": p["chave"], "nome": p["nome"], "rota": p["rota"] or p["entrada"], "estado": estado,
                       "do_painel": f"produto:{p['chave']}" in estado_site.salvo(), "avisos": avisos,
                       "kit_faltam": len(faltam)})
    return linhas


def faltam_para_o_kit(p: dict) -> list[dict]:
    """Rodada 20: os produtos de um kit que não estão ATIVOS como decidido aqui (painel → YAML).
    Enquanto faltar algum, o kit não aparece em lugar nenhum nem se vende (catalogo.vende),
    mesmo marcado como ativo. Vazio para produto comum."""
    return [x for x in catalogo.produtos_do_yaml()
            if x["chave"] in p["inclui"] and estado_site.estado_salvo(x["chave"], x["estado"]) != "ativo"]


def aviso_do_kit(p: dict) -> str:
    """"precisa de Mapa natal, O seu ano e A sua Lua no ano ativos"."""
    nomes = [x["nome"] for x in catalogo.produtos_do_yaml() if x["chave"] in p["inclui"]]
    lista = ", ".join(nomes[:-1]) + " e " + nomes[-1] if len(nomes) > 1 else "".join(nomes)
    return f"precisa de {lista} ativos"


def paginas() -> list[dict]:
    salvo = estado_site.salvo()
    return [{"rota": r, "nome": n, "visivel": salvo.get(f"pagina:{r}") is not False}
            for r, n in estado_site.PAGINAS.items()]


def resumo() -> str:
    """"Agora: aberto · venda aberta · 1 produto ativo, 3 em breve, 5 ocultos"."""
    contagem = {e: 0 for e in NOMES_ESTADO}
    linhas = produtos()
    for p in linhas:
        contagem[p["estado"]] += 1

    def n(qtd, um, varios):
        return f"{qtd} {um if qtd == 1 else varios}"
    # o kit (rodada 20): ATIVO aqui, mas parado enquanto faltar um dos produtos dele
    kits = [p for p in linhas if p["kit_faltam"] and p["estado"] == "ativo"]
    parado = "".join(f" · kit {p['nome']} parado ({'falta' if p['kit_faltam'] == 1 else 'faltam'} "
                     f"{n(p['kit_faltam'], 'produto ativo', 'produtos ativos')})" for p in kits)
    return (f"Agora: {estado_site.NOMES_MODO[estado_site.modo()].lower()} · "
            f"venda {'aberta' if vendas_decididas() else 'fechada'} · "
            f"{n(contagem['ativo'], 'produto ativo', 'produtos ativos')}, {contagem['em_breve']} em breve, "
            f"{n(contagem['oculto'], 'oculto', 'ocultos')}{parado}")


def ativos_sem_preco(mudando: dict | None = None) -> list[str]:
    """Nomes dos produtos que ficariam ativos sem preço (com `mudando` = {chave: estado} aplicado)."""
    mudando = mudando or {}
    faltam = []
    for p in catalogo.produtos_do_yaml():
        estado = mudando.get(p["chave"], estado_site.estado_salvo(p["chave"], p["estado"]))
        if estado == "ativo" and not tem_preco(p):
            faltam.append(p["nome"])
    return faltam


# =========================================================================== as ações
def mudancas(acao: str, form: dict) -> tuple[dict, str]:
    """(o que gravar em config_site, a frase do que mudou). Levanta Recusa se não pode."""
    if acao == "modo":
        valor = form.get("valor")
        if valor not in estado_site.MODOS:
            raise Recusa("Modo desconhecido.")
        return {"modo": valor}, f"o site para {estado_site.NOMES_MODO[valor]}"
    if acao == "vendas":
        abrir = form.get("valor") == "abrir"
        if abrir:
            if estado_site.ambiente() == "producao" and str(form.get("confirmacao", "")).strip() != PALAVRA_ABRIR:
                raise Recusa(f"Para abrir a venda na produção, digite {PALAVRA_ABRIR} na confirmação.")
            faltam = ativos_sem_preco()
            if faltam:
                raise Recusa("A venda não abriu: falta preço no ofertas.yaml para " + ", ".join(faltam) + ".")
        return {"vendas_abertas": abrir}, "a venda para " + ("aberta" if abrir else "fechada")
    if acao == "produto":
        p = catalogo.produto(form.get("chave", ""))
        estado = form.get("valor")
        if p is None or estado not in NOMES_ESTADO:
            raise Recusa("Produto ou estado desconhecido.")
        if estado == "ativo" and vendas_decididas() and not tem_preco(p):
            raise Recusa(f"{p['nome']} não ficou ativo: a venda está aberta e falta o preço no ofertas.yaml.")
        return {f"produto:{p['chave']}": estado}, f"{p['nome']} para {NOMES_ESTADO[estado]}"
    if acao == "pagina":
        rota = form.get("rota")
        if rota not in estado_site.PAGINAS:
            raise Recusa("Essa página não pode ser escondida pelo painel.")
        visivel = form.get("valor") == "mostrar"
        return ({f"pagina:{rota}": visivel},
                f"a página {estado_site.PAGINAS[rota]} para {'visível' if visivel else 'escondida'}")
    raise Recusa("Ação desconhecida.")


# =========================================================================== histórico e aviso
def _valor_legivel(chave: str, valor) -> str:
    if valor is None:
        return "padrão"
    if chave == "modo":
        return estado_site.NOMES_MODO.get(valor, str(valor))
    if chave == "vendas_abertas":
        return "aberta" if valor else "fechada"
    if chave.startswith("produto:"):
        return NOMES_ESTADO.get(valor, str(valor))
    if chave.startswith("pagina:"):
        return "visível" if valor else "escondida"
    return str(valor)


def _chave_legivel(chave: str) -> str:
    if chave == "modo":
        return "Modo do site"
    if chave == "vendas_abertas":
        return "Venda"
    if chave.startswith("produto:"):
        p = catalogo.produto(chave.split(":", 1)[1])
        return p["nome"] if p else chave
    if chave.startswith("pagina:"):
        return "Página " + estado_site.PAGINAS.get(chave.split(":", 1)[1], chave)
    return chave


def historico(linhas: list[dict]) -> list[dict]:
    return [{"o_que": _chave_legivel(h["chave"]),
             "de": _valor_legivel(h["chave"], h["de"]), "para": _valor_legivel(h["chave"], h["para"]),
             "quem": h["quem"] or "?",
             "quando": h["quando"].astimezone(FUSO).strftime("%d/%m %H:%M") if h["quando"] else ""}
            for h in linhas]


def avisar(quem: str, frase: str, agora: datetime | None = None) -> bool:
    """O e-mail curto para PADMINI_ALERTA_EMAIL: "Nicolas mudou o site para Lista de espera às 14:03"."""
    import alertas
    import entrega
    hora = (agora or datetime.now(FUSO)).astimezone(FUSO).strftime("%H:%M")
    assunto = f"{quem} mudou {frase} às {hora}"
    lugar = "PRODUÇÃO" if estado_site.ambiente() == "producao" else "PRÉVIA"
    corpo = (f'<div style="font-family:Arial,sans-serif;font-size:14px"><p><b>{_html.escape(assunto)}</b></p>'
             f'<p>{lugar} · {_html.escape(entrega.SITE_URL)}/painel</p>'
             f'<p>{_html.escape(resumo())}</p></div>')
    enviado = False
    for destino in alertas.destinatarios():
        try:
            enviado = entrega.enviar_email(destino, f"[Painel] {assunto}", corpo) or enviado
        except Exception:  # noqa: BLE001
            log.exception("painel: o aviso por e-mail não saiu")
    return enviado

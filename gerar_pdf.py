"""
Padmini — relatório completo em PDF (Mapa Védico).

Monta um PDF A4 a partir do mesmo cálculo e das mesmas regras do site, com
mais detalhe do que cabe na tela:
  1. Capa: dados de nascimento, resumo e o mapa (Rashi D1)
  2. Planetas: signo, grau, casa, nakshatra, dignidade e o que cada um representa
  3. Leitura: Ascendente, Lua e nakshatra, fase atual e destaques
  4. As 12 casas: tema, signo, regente, onde o regente está, planetas presentes
  5. Fases da vida: Vimshottari completo, com idades, e os subperíodos
     (antardashas) da fase atual e da próxima
  6. Glossário, método e avisos

Nada aqui usa IA: é tudo cálculo e texto da base. Fontes: Inter e Cormorant
Garamond (SIL Open Font License, ver fontes/).
"""

from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    CondPageBreak, Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from base_significacoes import NOME_PT, SIGNO_PT
from compute_chart import SIGNOS, VIMSHOTTARI_ANOS, VIMSHOTTARI_SEQ, nakshatra_de
from detectar_fatos import DIGNIDADES, SIGN_LORDS
from montar_texto import dasha_atual

# ---------------------------------------------------------------- aparência
FONTES = Path(__file__).parent / "fontes"
for nome, arquivo in [("Inter", "Inter-Regular.ttf"), ("Inter-SemiBold", "Inter-SemiBold.ttf"),
                      ("Cormorant", "Cormorant-Medium.ttf"), ("Cormorant-SemiBold", "Cormorant-SemiBold.ttf"),
                      ("Cormorant-Italic", "Cormorant-Italic.ttf")]:
    pdfmetrics.registerFont(TTFont(nome, str(FONTES / arquivo)))
pdfmetrics.registerFontFamily("Inter", normal="Inter", bold="Inter-SemiBold", italic="Inter", boldItalic="Inter-SemiBold")
pdfmetrics.registerFontFamily("Cormorant", normal="Cormorant", bold="Cormorant-SemiBold",
                              italic="Cormorant-Italic", boldItalic="Cormorant-SemiBold")

TINTA = colors.HexColor("#1f1a2e")
TINTA_SUAVE = colors.HexColor("#5b5470")
NOITE = colors.HexColor("#2a2350")
ACENTO = colors.HexColor("#c2410c")
ACENTO_SUAVE = colors.HexColor("#fbe7d6")
SUPERFICIE = colors.HexColor("#f3ece0")
FUNDO = colors.HexColor("#faf6ef")
LINHA = colors.HexColor("#e4dccd")

LARGURA_PAGINA, ALTURA_PAGINA = A4
MARGEM = 20 * mm
LARGURA_UTIL = LARGURA_PAGINA - 2 * MARGEM

E = {
    "capa_marca": ParagraphStyle("capa_marca", fontName="Cormorant-SemiBold", fontSize=20, leading=24, textColor=NOITE),
    "capa_titulo": ParagraphStyle("capa_titulo", fontName="Cormorant-SemiBold", fontSize=44, leading=48, textColor=NOITE),
    "capa_nome": ParagraphStyle("capa_nome", fontName="Cormorant-Italic", fontSize=24, leading=30, textColor=ACENTO),
    "h1": ParagraphStyle("h1", fontName="Cormorant-SemiBold", fontSize=28, leading=32, textColor=NOITE, spaceAfter=4),
    "h2": ParagraphStyle("h2", fontName="Cormorant-SemiBold", fontSize=19, leading=23, textColor=NOITE,
                         spaceBefore=12, spaceAfter=4),
    "intro": ParagraphStyle("intro", fontName="Inter", fontSize=10, leading=15, textColor=TINTA_SUAVE, spaceAfter=10),
    "corpo": ParagraphStyle("corpo", fontName="Inter", fontSize=10, leading=15.5, textColor=TINTA, spaceAfter=7),
    "destaque": ParagraphStyle("destaque", fontName="Inter", fontSize=10, leading=15.5, textColor=TINTA,
                               leftIndent=10, borderPadding=0, spaceAfter=7),
    "celula": ParagraphStyle("celula", fontName="Inter", fontSize=8.5, leading=11.5, textColor=TINTA),
    "celula_suave": ParagraphStyle("celula_suave", fontName="Inter", fontSize=8, leading=11, textColor=TINTA_SUAVE),
    "rotulo": ParagraphStyle("rotulo", fontName="Inter", fontSize=8, leading=10, textColor=TINTA_SUAVE),
    "valor": ParagraphStyle("valor", fontName="Inter-SemiBold", fontSize=12, leading=15, textColor=TINTA),
    "nota": ParagraphStyle("nota", fontName="Inter", fontSize=8, leading=11.5, textColor=TINTA_SUAVE, spaceAfter=4),
    "centro": ParagraphStyle("centro", fontName="Cormorant-Italic", fontSize=16, leading=20, textColor=NOITE,
                             alignment=TA_CENTER),
}

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
ABREV = {"Surya": "Sol", "Chandra": "Lua", "Mangala": "Mar", "Budha": "Mer", "Guru": "Júp",
         "Shukra": "Vên", "Shani": "Sat", "Rahu": "Rah", "Ketu": "Ket"}
ORDEM_GRAHAS = ["Surya", "Chandra", "Mangala", "Budha", "Guru", "Shukra", "Shani", "Rahu", "Ketu"]

# Layout sul-indiano: a posição de cada signo é fixa na grade 4x4.
SUL_INDIANO = {
    "Meena": (0, 0), "Mesha": (0, 1), "Vrishabha": (0, 2), "Mithuna": (0, 3),
    "Kumbha": (1, 0), "Karka": (1, 3),
    "Makara": (2, 0), "Simha": (2, 3),
    "Dhanu": (3, 0), "Vrishchika": (3, 1), "Tula": (3, 2), "Kanya": (3, 3),
}

TEMAS_CASAS = {
    1: "Corpo, identidade e jeito de se apresentar",
    2: "Recursos, família, fala e valores",
    3: "Iniciativa, coragem, irmãos e comunicação",
    4: "Lar, mãe, raízes e paz interior",
    5: "Criatividade, filhos, estudo e inteligência",
    6: "Rotina, serviço, saúde e obstáculos",
    7: "Parcerias, casamento e acordos",
    8: "Transformações, crises e o que é oculto",
    9: "Dharma, mestres, fé e boa sorte",
    10: "Carreira, ação no mundo e reputação",
    11: "Ganhos, amizades, redes e aspirações",
    12: "Recolhimento, gastos, perdas e espiritualidade",
}

SIGNIFICADOS_GRAHAS = {
    "Surya": "Alma, vitalidade, pai, autoridade e propósito",
    "Chandra": "Mente, emoções, mãe, memória e necessidade de acolhimento",
    "Mangala": "Energia, coragem, ação, irmãos e capacidade de defesa",
    "Budha": "Intelecto, fala, aprendizado, comércio e adaptação",
    "Guru": "Sabedoria, mestres, fé, expansão e filhos",
    "Shukra": "Amor, beleza, arte, prazer e conforto",
    "Shani": "Disciplina, tempo, trabalho, limites e maturidade",
    "Rahu": "Desejo, o novo, o estrangeiro e a ambição sem freio",
    "Ketu": "Desapego, espiritualidade, intuição e o que vem do passado",
}

GLOSSARIO = [
    ("Jyotish", "Astrologia védica, a tradição astrológica da Índia."),
    ("Ascendente (Lagna)", "O signo que nascia no horizonte leste no momento do nascimento. Define a casa 1 e, "
                           "a partir dela, todas as outras."),
    ("Rashi (D1)", "O mapa principal, com os planetas nos doze signos."),
    ("Graha", "Os nove corpos usados no Jyotish: Sol, Lua, Marte, Mercúrio, Júpiter, Vênus, Saturno e os nós "
              "lunares Rahu e Ketu."),
    ("Nakshatra", "Cada uma das 27 divisões da faixa do zodíaco (13°20' cada). A nakshatra da Lua é uma das "
                  "informações mais importantes do mapa."),
    ("Pada", "Cada nakshatra é dividida em quatro partes iguais, chamadas padas."),
    ("Casa", "Área da vida. Aqui usamos casas por signo inteiro: o signo do Ascendente é a casa 1, o seguinte é a "
             "casa 2, e assim por diante."),
    ("Regente", "O planeta que governa um signo. O regente de uma casa leva os assuntos dela para onde ele está."),
    ("Dignidade", "Força do planeta pelo signo onde está: exaltado (muito forte), signo próprio (forte), "
                  "debilitado (precisa de mais esforço para se expressar)."),
    ("Retrógrado (R)", "Planeta que, visto da Terra, parecia andar para trás no dia do nascimento. A tradição lê "
                       "como energia mais voltada para dentro ou para revisão."),
    ("Combustão", "Planeta muito próximo do Sol, cuja expressão fica ofuscada pela vontade central."),
    ("Yoga", "Combinação específica de planetas que a tradição associa a um resultado."),
    ("Vimshottari Dasha", "Sistema de fases da vida que soma 120 anos. Cada fase é regida por um planeta, que dá "
                          "o tom do período. A primeira fase depende da nakshatra da Lua."),
    ("Antardasha", "Subperíodo dentro de uma fase. Segue a mesma ordem dos planetas e colore a fase principal."),
    ("Ayanamsa Lahiri", "A correção entre o zodíaco tropical (o das colunas de horóscopo) e o sideral (o das "
                        "estrelas), usada pelo governo da Índia. Por isso o seu signo aqui pode ser diferente "
                        "do que você conhece."),
]


# ---------------------------------------------------------------- utilidades
def _p(texto: str, estilo: str = "corpo") -> Paragraph:
    return Paragraph(texto, E[estilo])


def _grau(g: float) -> str:
    d = int(g)
    m = round((g - d) * 60)
    if m == 60:
        d, m = d + 1, 0
    return f"{d}°{m:02d}'"


def _data_br(iso_ou_date) -> str:
    d = date.fromisoformat(iso_ou_date) if isinstance(iso_ou_date, str) else iso_ou_date
    return d.strftime("%d/%m/%Y")


def _mes_ano(d: date) -> str:
    return f"{MESES[d.month - 1]}/{d.year}"


def _idade(nascimento: date, quando: date) -> int:
    return quando.year - nascimento.year - ((quando.month, quando.day) < (nascimento.month, nascimento.day))


def _dignidade(nome: str, signo: str) -> str:
    regra = DIGNIDADES.get(nome)
    if not regra:
        return "—"
    if signo == regra["exaltacao"][0]:
        return "Exaltado"
    if signo == regra["debilitacao"][0]:
        return "Debilitado"
    if signo in regra["proprio"]:
        return "Signo próprio"
    return "—"


def _tabela(dados, larguras, cabecalho=True, destacar_linhas=(), respiro=5):
    t = Table(dados, colWidths=larguras, repeatRows=1 if cabecalho else 0)
    estilo = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), respiro),
        ("BOTTOMPADDING", (0, 0), (-1, -1), respiro),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINHA),
    ]
    if cabecalho:
        estilo += [("LINEBELOW", (0, 0), (-1, 0), 0.9, NOITE)]
    for i in destacar_linhas:
        estilo += [("BACKGROUND", (0, i), (-1, i), ACENTO_SUAVE)]
    t.setStyle(TableStyle(estilo))
    return t


def _cab(*titulos):
    return [Paragraph(f"<b>{escape(t)}</b>", E["celula_suave"]) for t in titulos]


# ---------------------------------------------------------------- mapa desenhado
class MapaSulIndiano(Flowable):
    def __init__(self, resultado: dict, lado: float):
        super().__init__()
        self.r = resultado
        self.lado = lado

    def wrap(self, *_):
        return self.lado, self.lado

    def draw(self):
        c = self.canv
        cel = self.lado / 4
        por_signo = {}
        for nome in ORDEM_GRAHAS:
            g = self.r["grahas"][nome]
            retro = " (R)" if g["retrogrado"] and nome not in ("Rahu", "Ketu") else ""
            por_signo.setdefault(g["signo"], []).append(f"{ABREV[nome]}{retro} {_grau(g['grau_no_signo'])}")
        lagna = self.r["lagna"]["signo"]

        for signo, (lin, col) in SUL_INDIANO.items():
            x, y = col * cel, self.lado - (lin + 1) * cel
            c.setFillColor(ACENTO_SUAVE if signo == lagna else colors.white)
            c.setStrokeColor(LINHA)
            c.setLineWidth(0.6)
            c.rect(x, y, cel, cel, fill=1, stroke=1)
            if signo == lagna:
                c.setFillColor(ACENTO)
                t = c.beginPath()
                t.moveTo(x + cel - 12, y + cel)
                t.lineTo(x + cel, y + cel)
                t.lineTo(x + cel, y + cel - 12)
                t.close()
                c.drawPath(t, fill=1, stroke=0)
            c.setFillColor(TINTA_SUAVE)
            c.setFont("Inter", 7)
            c.drawString(x + 5, y + cel - 11, SIGNO_PT[signo])
            linhas = ([("Asc " + _grau(self.r["lagna"]["grau"]), True)] if signo == lagna else []) + \
                     [(t, False) for t in por_signo.get(signo, [])]
            yy = y + cel - 25
            # signos com muitos planetas (stellium): reduz a letra para caber na casinha
            passo = min(10.5, (cel - 29) / max(len(linhas) - 1, 1))
            tamanho = min(8.2, passo * 0.82)
            for texto, negrito in linhas:
                c.setFillColor(TINTA)
                c.setFont("Inter-SemiBold" if negrito else "Inter", tamanho)
                c.drawString(x + 5, yy, texto)
                yy -= passo

        # centro
        c.setFillColor(FUNDO)
        c.setStrokeColor(LINHA)
        c.rect(cel, cel, 2 * cel, 2 * cel, fill=1, stroke=1)
        c.setFillColor(NOITE)
        c.setFont("Cormorant-SemiBold", 20)
        c.drawCentredString(self.lado / 2, self.lado / 2 + 6, "Rashi")
        c.setFont("Cormorant-Italic", 12)
        c.drawCentredString(self.lado / 2, self.lado / 2 - 12, "mapa principal (D1)")
        # moldura
        c.setStrokeColor(NOITE)
        c.setLineWidth(1.6)
        c.rect(0, 0, self.lado, self.lado, fill=0, stroke=1)


class Lotus(Flowable):
    """A marca da Padmini (mesmo desenho do ícone do site)."""

    def __init__(self, tamanho: float = 28):
        super().__init__()
        self.t = tamanho

    def wrap(self, *_):
        return self.t, self.t

    def draw(self):
        c = self.canv
        s = self.t / 32
        c.saveState()
        c.translate(0, self.t)
        c.scale(s, -s)  # o SVG original tem o eixo y para baixo
        p = c.beginPath()
        p.moveTo(16, 5); p.curveTo(19, 9, 20, 13, 16, 19); p.curveTo(12, 13, 13, 9, 16, 5)
        c.setFillColor(ACENTO)
        c.drawPath(p, fill=1, stroke=0)
        p = c.beginPath()
        p.moveTo(4, 14); p.curveTo(9, 14, 13, 17, 16, 21); p.curveTo(11, 23, 6, 21, 4, 14)
        p.moveTo(28, 14); p.curveTo(23, 14, 19, 17, 16, 21); p.curveTo(21, 23, 26, 21, 28, 14)
        c.setFillColor(colors.HexColor("#e08a3c"))
        c.drawPath(p, fill=1, stroke=0)
        c.setStrokeColor(NOITE)
        c.setLineWidth(1.5)
        c.setLineCap(1)
        c.line(6, 24, 26, 24)
        c.restoreState()


# ---------------------------------------------------------------- dashas
def _anos(n: float) -> timedelta:
    return timedelta(days=n * 365.2425)


def antardashas(regente: str, inicio_teorico: datetime, nascimento: datetime) -> list[tuple[str, datetime, datetime]]:
    """Subperíodos de uma fase, na ordem Vimshottari, cortando o que foi antes do nascimento."""
    anos_md = VIMSHOTTARI_ANOS[regente]
    pos = VIMSHOTTARI_SEQ.index(regente)
    cursor, saida = inicio_teorico, []
    for i in range(9):
        sub = VIMSHOTTARI_SEQ[(pos + i) % 9]
        fim = cursor + _anos(anos_md * VIMSHOTTARI_ANOS[sub] / 120)
        if fim > nascimento:
            saida.append((sub, max(cursor, nascimento), fim))
        cursor = fim
    return saida


def _inicio_teorico(fase: dict) -> datetime:
    fim = datetime.fromisoformat(fase["fim"])
    return fim - _anos(VIMSHOTTARI_ANOS[fase["regente"]])


# ---------------------------------------------------------------- páginas
def _cabecalho_rodape(titulo_curto: str):
    def desenhar(canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setFont("Cormorant-SemiBold", 11)
            canvas.setFillColor(NOITE)
            canvas.drawString(MARGEM, ALTURA_PAGINA - 12 * mm, "Padmini")
            canvas.setFont("Inter", 7.5)
            canvas.setFillColor(TINTA_SUAVE)
            canvas.drawRightString(LARGURA_PAGINA - MARGEM, ALTURA_PAGINA - 12 * mm, titulo_curto)
            canvas.setStrokeColor(LINHA)
            canvas.setLineWidth(0.5)
            canvas.line(MARGEM, ALTURA_PAGINA - 14 * mm, LARGURA_PAGINA - MARGEM, ALTURA_PAGINA - 14 * mm)
        canvas.setFont("Inter", 7.5)
        canvas.setFillColor(TINTA_SUAVE)
        canvas.drawString(MARGEM, 10 * mm, "Ferramenta de autoconhecimento inspirada no Jyotish. "
                                           "Não é previsão nem substitui orientação profissional.")
        canvas.drawRightString(LARGURA_PAGINA - MARGEM, 10 * mm, f"{doc.page}")
        canvas.restoreState()
    return desenhar


def _caixas_resumo(itens):
    celulas = [[_p(escape(rot), "rotulo"), _p(escape(val), "valor")] for rot, val in itens]
    larg = (LARGURA_UTIL - 2 * 6) / 3
    t = Table([[Table([[a], [b]], colWidths=[larg - 16]) for a, b in celulas]],
              colWidths=[larg + 4] * 3)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SUPERFICIE),
        ("LINEAFTER", (0, 0), (1, 0), 6, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def gerar_pdf(*, resultado: dict, fatos: list[dict], secoes: dict, nome: str, cidade: str,
              nascimento: datetime, hoje: date | None = None) -> bytes:
    hoje = hoje or date.today()
    grahas = resultado["grahas"]
    lagna = resultado["lagna"]
    idx_lagna = SIGNOS.index(lagna["signo"])
    atual = dasha_atual(resultado, hoje)
    nak_lua = resultado["nakshatra_lua"]
    fuso = resultado["fuso_resolvido"]
    offset = fuso["offset_horas_na_data"]
    nome_exibido = nome.strip()
    titulo_curto = f"Mapa Védico de {nome_exibido}" if nome_exibido else "Mapa Védico"

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=MARGEM, rightMargin=MARGEM,
                            topMargin=20 * mm, bottomMargin=18 * mm,
                            title=titulo_curto, author="Padmini", subject="Mapa védico (Jyotish)")
    h = []

    # ---- 1. capa
    marca = Table([[Lotus(26), _p("Padmini", "capa_marca")]], colWidths=[34, 200], hAlign="LEFT")
    marca.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    h += [marca, Spacer(1, 8 * mm), _p("Mapa Védico", "capa_titulo")]
    if nome_exibido:
        h.append(_p(escape(nome_exibido), "capa_nome"))
    h.append(Spacer(1, 3 * mm))
    fuso_txt = f"{fuso['nome_iana']} (UTC{'+' if offset >= 0 else ''}{offset:g})"
    h.append(_p(f"Nascimento em <b>{nascimento.strftime('%d/%m/%Y')}</b>, às <b>{nascimento.strftime('%H:%M')}</b>, "
                f"em <b>{escape(cidade)}</b><br/>Fuso usado: {escape(fuso_txt)} · Relatório gerado em "
                f"{hoje.strftime('%d/%m/%Y')}", "intro"))
    h.append(Spacer(1, 2 * mm))
    fase_txt = f"{NOME_PT[atual['regente']]} ({atual['inicio'][:4]}–{atual['fim'][:4]})" if atual else "—"
    h.append(_caixas_resumo([
        ("Ascendente", f"{SIGNO_PT[lagna['signo']]} {_grau(lagna['grau'])}"),
        ("Lua", f"{SIGNO_PT[grahas['Chandra']['signo']]} · {nak_lua['nome']}"),
        ("Fase atual", fase_txt),
    ]))
    h.append(Spacer(1, 7 * mm))
    lado = 138 * mm
    mapa = Table([[MapaSulIndiano(resultado, lado)]], colWidths=[LARGURA_UTIL])
    mapa.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    h.append(mapa)
    h.append(Spacer(1, 3 * mm))
    h.append(_p("Mapa no estilo sul-indiano: cada signo ocupa sempre a mesma casinha. O Ascendente está destacado. "
                "(R) indica planeta retrógrado.", "nota"))
    h.append(PageBreak())

    # ---- 2. planetas
    h.append(_p("Os planetas no seu mapa", "h1"))
    h.append(_p("Onde cada graha estava no momento do seu nascimento, pelo zodíaco sideral. A nakshatra mostra a "
                "divisão mais fina do céu em que ele estava, e a dignidade indica o quanto o signo favorece "
                "a expressão do planeta.", "intro"))
    linhas = [_cab("Planeta", "Signo", "Grau", "Casa", "Nakshatra (pada)", "Dignidade")]
    asc_long = idx_lagna * 30 + lagna["grau"]
    n, pada, _ = nakshatra_de(asc_long)
    linhas.append([_p("<b>Ascendente</b>", "celula"), _p(SIGNO_PT[lagna["signo"]], "celula"),
                   _p(_grau(lagna["grau"]), "celula"), _p("1", "celula"), _p(f"{n} ({pada})", "celula"),
                   _p("—", "celula")])
    for nome_g in ORDEM_GRAHAS:
        g = grahas[nome_g]
        n, pada, _ = nakshatra_de(g["longitude_sideral"])
        retro = " (R)" if g["retrogrado"] and nome_g not in ("Rahu", "Ketu") else ""
        linhas.append([_p(f"<b>{NOME_PT[nome_g]}</b>{retro}", "celula"), _p(SIGNO_PT[g["signo"]], "celula"),
                       _p(_grau(g["grau_no_signo"]), "celula"), _p(str(g["casa_whole_sign"]), "celula"),
                       _p(f"{n} ({pada})", "celula"), _p(_dignidade(nome_g, g["signo"]), "celula")])
    h.append(_tabela(linhas, [30 * mm, 28 * mm, 20 * mm, 14 * mm, 43 * mm, LARGURA_UTIL - 135 * mm],
                     destacar_linhas=(1,)))
    h.append(Spacer(1, 2 * mm))
    h.append(_p("Rahu e Ketu são os nós da Lua: pontos, não corpos físicos. Andam sempre para trás e ficam sempre "
                "em signos opostos; por isso não levam a marca (R) nem dignidade nesta tabela.", "nota"))

    h.append(_p("O que cada planeta representa", "h2"))
    linhas = [_cab("Planeta", "Representa", "No seu mapa")]
    for nome_g in ORDEM_GRAHAS:
        g = grahas[nome_g]
        linhas.append([_p(f"<b>{NOME_PT[nome_g]}</b>", "celula"), _p(SIGNIFICADOS_GRAHAS[nome_g], "celula"),
                       _p(f"{SIGNO_PT[g['signo']]}, casa {g['casa_whole_sign']} "
                          f"({TEMAS_CASAS[g['casa_whole_sign']].split(',')[0].lower()})", "celula")])
    h.append(_tabela(linhas, [26 * mm, 72 * mm, LARGURA_UTIL - 98 * mm]))
    h.append(PageBreak())

    # ---- 3. leitura
    h.append(_p("Leitura do mapa", "h1"))
    h.append(_p("Os pontos centrais do seu mapa, interpretados a partir das regras clássicas do Jyotish.", "intro"))
    for titulo, conteudo in secoes.items():
        blocos = conteudo if isinstance(conteudo, list) else [conteudo]
        if not blocos:
            continue
        itens = [_p(escape(titulo), "h2")]
        estilo = "destaque" if titulo == "Destaques do mapa" else "corpo"
        itens += [_p(("•&nbsp;&nbsp;" if estilo == "destaque" else "") + escape(b), estilo) for b in blocos]
        h.append(KeepTogether(itens[:2]))
        h.extend(itens[2:])
    if not secoes.get("Destaques do mapa"):
        h.append(_p("Nenhuma das combinações clássicas que este relatório procura (dignidades, combustão, yogas e "
                    "Mangal Dosha) apareceu de forma marcante no seu mapa.", "nota"))
    h.append(PageBreak())

    # ---- 4. casas
    h.append(_p("As 12 casas", "h1"))
    h.append(_p("Cada casa é uma área da vida. O regente de uma casa é o planeta que governa o signo dela: ele leva "
                "os assuntos daquela casa para a casa onde está. Planetas dentro de uma casa dão destaque a ela.",
                "intro"))
    linhas = [_cab("Casa", "Área da vida", "Signo", "Regente", "Regente está na", "Planetas na casa")]
    for casa in range(1, 13):
        signo = SIGNOS[(idx_lagna + casa - 1) % 12]
        regente = SIGN_LORDS[signo]
        dentro = [NOME_PT[x] for x in ORDEM_GRAHAS if grahas[x]["casa_whole_sign"] == casa]
        linhas.append([_p(f"<b>{casa}</b>", "celula"), _p(TEMAS_CASAS[casa], "celula"), _p(SIGNO_PT[signo], "celula"),
                       _p(NOME_PT[regente], "celula"), _p(f"casa {grahas[regente]['casa_whole_sign']}", "celula"),
                       _p(", ".join(dentro) or "—", "celula")])
    h.append(_tabela(linhas, [12 * mm, 58 * mm, 24 * mm, 20 * mm, 22 * mm, LARGURA_UTIL - 136 * mm],
                     destacar_linhas=(1,)))
    h.append(Spacer(1, 2 * mm))
    h.append(_p("Casas por signo inteiro: o signo do Ascendente inteiro é a casa 1. Este relatório ainda não "
                "interpreta cada planeta em cada casa; essa leitura faz parte de uma próxima versão.", "nota"))
    h.append(PageBreak())

    # ---- 5. fases
    h.append(_p("Fases da vida (Vimshottari)", "h1"))
    h.append(_p("A vida é dividida em fases regidas por planetas. O planeta da fase dá o tom do período; os "
                "subperíodos, dentro dela, trazem nuances. A primeira fase começa no nascimento com o tempo que "
                "restava dela, conforme a posição da Lua.", "intro"))
    nasc_d = nascimento.date()
    linhas = [_cab("Fase", "Início", "Fim", "Sua idade", "Duração")]
    destacar = []
    for i, d in enumerate(resultado["vimshottari_dasha"], start=1):
        ini, fim = date.fromisoformat(d["inicio"]), date.fromisoformat(d["fim"])
        if atual and d == atual:
            destacar.append(i)
        dur = (fim - ini).days / 365.2425
        linhas.append([_p(f"<b>{NOME_PT[d['regente']]}</b>", "celula"), _p(_mes_ano(ini), "celula"),
                       _p(_mes_ano(fim), "celula"), _p(f"{_idade(nasc_d, ini)} a {_idade(nasc_d, fim)} anos", "celula"),
                       _p(f"{dur:.1f} anos".replace(".", ","), "celula")])
    h.append(_tabela(linhas, [34 * mm, 30 * mm, 30 * mm, 40 * mm, LARGURA_UTIL - 134 * mm], destacar_linhas=destacar))

    fases = resultado["vimshottari_dasha"]
    if atual:
        i_atual = fases.index(atual)
        alvo = [(atual, "atual")] + ([(fases[i_atual + 1], "seguinte")] if i_atual + 1 < len(fases) else [])
    else:
        alvo = []
    for fase, rotulo in alvo:
        subs = antardashas(fase["regente"], _inicio_teorico(fase), nascimento)
        bloco = [_p(f"Subperíodos da fase {rotulo}: {NOME_PT[fase['regente']]}", "h2")]
        linhas = [_cab("Subperíodo", "De", "Até", "Sua idade")]
        destacar = []
        for j, (sub, ini, fim) in enumerate(subs, start=1):
            if ini.date() <= hoje < fim.date():
                destacar.append(j)
            linhas.append([_p(f"{NOME_PT[fase['regente']]} / <b>{NOME_PT[sub]}</b>", "celula"),
                           _p(_mes_ano(ini.date()), "celula"), _p(_mes_ano(fim.date()), "celula"),
                           _p(f"{_idade(nasc_d, ini.date())} a {_idade(nasc_d, fim.date())} anos", "celula")])
        bloco.append(_tabela(linhas, [60 * mm, 32 * mm, 32 * mm, LARGURA_UTIL - 124 * mm], destacar_linhas=destacar))
        h.append(CondPageBreak(60 * mm))
        h.extend(bloco)
    h.append(Spacer(1, 2 * mm))
    h.append(_p("Datas aproximadas ao mês. A linha destacada é o período em que você está hoje.", "nota"))
    h.append(PageBreak())

    # ---- 6. glossário e método
    h.append(_p("Glossário", "h1"))
    linhas = [[_p(f"<b>{escape(t)}</b>", "celula"), _p(escape(d), "celula")] for t, d in GLOSSARIO]
    h.append(_tabela(linhas, [40 * mm, LARGURA_UTIL - 40 * mm], cabecalho=False, respiro=3.2))
    h.append(_p("Como este mapa foi calculado", "h2"))
    for texto in [
        "Posições planetárias calculadas com o Swiss Ephemeris, no zodíaco sideral com ayanamsa Lahiri, "
        "nós lunares médios e casas por signo inteiro.",
        "O fuso horário e o horário de verão da data e do local de nascimento são aplicados automaticamente. "
        "Antes da adoção da hora padrão no local, usamos a hora média local, calculada pela longitude.",
        "O Ascendente muda de signo a cada duas horas, em média. Se a hora de nascimento não for exata, confira "
        "a hora na certidão: poucos minutos podem mudar o Ascendente e as casas.",
        "As interpretações vêm de uma base de textos organizada por regras clássicas. Nenhuma informação foi "
        "inventada para preencher espaço.",
        "Dados de cidades: GeoNames (CC BY 4.0). Fontes tipográficas: Inter e Cormorant Garamond "
        "(SIL Open Font License).",
    ]:
        h.append(_p(escape(texto)))
    h.append(_p("<b>Este relatório é uma ferramenta de autoconhecimento inspirada na tradição védica (Jyotish). Não é "
                "previsão de acontecimentos e não substitui orientação médica, psicológica, jurídica ou "
                "financeira.</b>"))

    capa_rodape = _cabecalho_rodape(titulo_curto)
    doc.build(h, onFirstPage=capa_rodape, onLaterPages=capa_rodape)
    return buf.getvalue()


if __name__ == "__main__":
    import sys
    from compute_chart import calcular_mapa
    from detectar_fatos import detectar_todos_os_fatos
    from montar_texto import montar_secoes

    nasc = datetime(1961, 8, 4, 19, 24)
    res = calcular_mapa(dt_local_naive=nasc, lat=21.3069, lon=-157.8583)
    fatos = detectar_todos_os_fatos(res)
    secoes, _ = montar_secoes(res, fatos)
    pdf = gerar_pdf(resultado=res, fatos=fatos, secoes=secoes, nome="Exemplo",
                    cidade="Honolulu, Hawaii, Estados Unidos", nascimento=nasc)
    saida = sys.argv[1] if len(sys.argv) > 1 else "exemplo.pdf"
    Path(saida).write_bytes(pdf)
    print(f"{saida}: {len(pdf) / 1024:.0f} KB")

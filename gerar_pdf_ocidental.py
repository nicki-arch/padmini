"""
Padmini (versão ocidental) — mapa natal completo em PDF.

  1. Capa: dados de nascimento, Sol/Lua/Ascendente e a roda do mapa
  2. Posições: planetas, Ascendente, Meio do Céu e Nodo, com signo, grau e casa
  3. Aspectos, elementos e modalidades
  4. A leitura (as mesmas seções do site, da base de textos)
  5. Método e avisos

Nada aqui usa IA. Reaproveita a aparência do PDF védico (fontes, cores,
tabelas) de gerar_pdf.py, sem mudar nada nele.
"""

import math
from datetime import date, datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import CondPageBreak, Flowable, PageBreak, SimpleDocTemplate, Spacer, Table, TableStyle

import mapa_ocidental as mo
from gerar_pdf import (
    ACENTO, ALTURA_PAGINA, LARGURA_PAGINA, LARGURA_UTIL, LINHA, MARGEM, NOITE, SUPERFICIE, TINTA, TINTA_SUAVE,
    Lotus, _cab, _caixas_resumo, _p, _tabela,
)
from reportlab.lib.styles import ParagraphStyle  # noqa: E402  (estilos extras abaixo)

ABREV = {"sol": "Sol", "lua": "Lua", "mercurio": "Mer", "venus": "Vên", "marte": "Mar", "jupiter": "Júp",
         "saturno": "Sat", "urano": "Ura", "netuno": "Net", "plutao": "Plu", "nodo_norte": "Nodo"}
SIGNO_CURTO = {"aries": "Ári", "touro": "Tou", "gemeos": "Gêm", "cancer": "Cân", "leao": "Leão",
               "virgem": "Vir", "libra": "Lib", "escorpiao": "Esc", "sagitario": "Sag",
               "capricornio": "Cap", "aquario": "Aqu", "peixes": "Pei"}
COR_ASPECTO = {"conjuncao": NOITE, "sextil": colors.HexColor("#2f7d6d"), "trigono": colors.HexColor("#2f7d6d"),
               "quadratura": ACENTO, "oposicao": ACENTO}


def separar_rotulos(longitudes: dict, minimo: float = 7.0) -> dict:
    """Ângulo de desenho de cada rótulo, empurrando os vizinhos que ficariam
    encavalados (a posição real continua marcada por um tracinho)."""
    ordem = sorted(longitudes.items(), key=lambda kv: kv[1])
    angulos = {k: v for k, v in ordem}
    for _ in range(20):
        mexeu = False
        for i in range(len(ordem)):
            a, b = ordem[i][0], ordem[(i + 1) % len(ordem)][0]
            d = (angulos[b] - angulos[a]) % 360
            if len(ordem) > 1 and d < minimo:
                empurra = (minimo - d) / 2
                angulos[a] -= empurra
                angulos[b] += empurra
                mexeu = True
        if not mexeu:
            break
    return angulos


class RodaZodiacal(Flowable):
    """A roda do mapa: signos por fora, casas (se houver hora), planetas por
    dentro e as linhas dos aspectos no miolo. Ascendente à esquerda."""

    def __init__(self, mapa: dict, lado: float):
        super().__init__()
        self.m, self.lado = mapa, lado

    def wrap(self, *_):
        return self.lado, self.lado

    def draw(self):
        c, m = self.canv, self.m
        r = self.lado / 2
        cx = cy = r
        base = m["pontos"]["ascendente"]["longitude"] if m["tem_hora"] else 0.0

        def xy(longitude, raio):
            ang = math.radians(180 + (longitude - base))
            return cx + raio * math.cos(ang), cy + raio * math.sin(ang)

        r_ext, r_signos, r_planetas, r_miolo = r * 0.98, r * 0.84, r * 0.70, r * 0.52
        c.saveState()
        c.setStrokeColor(NOITE)
        c.setLineWidth(0.9)
        c.setFillColor(SUPERFICIE)
        c.circle(cx, cy, r_ext, stroke=1, fill=1)
        c.setFillColor(colors.white)
        c.circle(cx, cy, r_signos, stroke=1, fill=1)
        c.setLineWidth(0.4)
        c.setStrokeColor(LINHA)
        c.circle(cx, cy, r_miolo, stroke=1, fill=0)
        # signos
        c.setFont("Inter", 7.5)
        for i, s in enumerate(mo.SIGNOS):
            c.setStrokeColor(NOITE)
            c.setLineWidth(0.6)
            c.line(*xy(i * 30, r_signos), *xy(i * 30, r_ext))
            x, y = xy(i * 30 + 15, (r_signos + r_ext) / 2)
            c.setFillColor(NOITE)
            c.drawCentredString(x, y - 2.5, SIGNO_CURTO[s])
        # casas
        if m["casas"]:
            for n, cusp in enumerate(m["casas"]["cuspides"], start=1):
                eixo = n in (1, 4, 7, 10)
                c.setStrokeColor(ACENTO if eixo else LINHA)
                c.setLineWidth(1.1 if eixo else 0.5)
                c.line(*xy(cusp, r_miolo), *xy(cusp, r_signos))
                prox = m["casas"]["cuspides"][n % 12]
                meio = cusp + ((prox - cusp) % 360) / 2
                x, y = xy(meio, r_miolo + 7)
                c.setFillColor(TINTA_SUAVE)
                c.setFont("Inter", 6)
                c.drawCentredString(x, y - 2, str(n))
            c.setFont("Inter-SemiBold", 7)
            c.setFillColor(ACENTO)
            x, y = xy(m["pontos"]["ascendente"]["longitude"], r_ext + 1)
            c.drawRightString(x - 2, y - 2.5, "ASC")
            x, y = xy(m["pontos"]["meio_do_ceu"]["longitude"], r_ext + 4)
            c.drawCentredString(x, y, "MC")
        # aspectos
        for a in m["aspectos"]:
            if a["a"] in mo.PLANETAS and a["b"] in mo.PLANETAS:
                c.setStrokeColor(COR_ASPECTO[a["tipo"]])
                c.setLineWidth(0.5 if a["orbe"] > 3 else 0.9)
                c.line(*xy(m["pontos"][a["a"]]["longitude"], r_miolo - 2),
                       *xy(m["pontos"][a["b"]]["longitude"], r_miolo - 2))
        # planetas
        pontos = {k: m["pontos"][k]["longitude"] for k in ABREV}
        rotulos = separar_rotulos(pontos)
        c.setFont("Inter-SemiBold", 7)
        for k, lng in pontos.items():
            c.setStrokeColor(NOITE)
            c.setLineWidth(0.6)
            c.line(*xy(lng, r_signos), *xy(lng, r_signos - 4))
            x, y = xy(rotulos[k], r_planetas)
            c.setFillColor(TINTA)
            retro = " R" if m["pontos"][k].get("retrogrado") else ""
            c.drawCentredString(x, y - 2.5, ABREV[k] + retro)
        c.restoreState()


def _rodape(titulo_curto: str):
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
        canvas.drawString(MARGEM, 10 * mm, "Ferramenta de autoconhecimento. "
                                           "Não é previsão nem substitui orientação profissional.")
        canvas.drawRightString(LARGURA_PAGINA - MARGEM, 10 * mm, f"{doc.page}")
        canvas.restoreState()
    return desenhar


def _nome_signo(p: dict) -> str:
    if p.get("signo_incerto"):
        return " ou ".join(mo.SIGNO_PT[s] for s in p["signos_possiveis"])
    return p["signo_pt"]


def gerar_pdf_ocidental(*, mapa: dict, secoes: dict, nome: str, cidade: str, data_nascimento: date,
                        hora: str = "", hoje: date | None = None) -> bytes:
    hoje = hoje or date.today()
    nome_exibido = nome.strip()
    titulo_curto = f"Mapa Natal de {nome_exibido}" if nome_exibido else "Mapa Natal"
    fuso = mapa["fuso_resolvido"]
    offset = fuso["offset_horas_na_data"]
    pts = mapa["pontos"]

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=MARGEM, rightMargin=MARGEM,
                            topMargin=20 * mm, bottomMargin=18 * mm,
                            title=titulo_curto, author="Padmini", subject="Mapa natal (astrologia ocidental)")
    h = []

    # ---- 1. capa
    marca = Table([[Lotus(26), _p("Padmini", "capa_marca")]], colWidths=[34, 200], hAlign="LEFT")
    marca.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    h += [marca, Spacer(1, 8 * mm), _p("Mapa Natal", "capa_titulo")]
    if nome_exibido:
        h.append(_p(escape(nome_exibido), "capa_nome"))
    h.append(Spacer(1, 3 * mm))
    quando = data_nascimento.strftime("%d/%m/%Y") + (f"</b>, às <b>{escape(hora)}" if hora else "")
    fuso_txt = f"{fuso['nome_iana']} (UTC{'+' if offset >= 0 else ''}{offset:g})"
    h.append(_p(f"Nascimento em <b>{quando}</b>, em <b>{escape(cidade)}</b><br/>"
                f"Fuso usado: {escape(fuso_txt)} · Relatório gerado em {hoje.strftime('%d/%m/%Y')}"
                + ("" if hora else "<br/>Sem hora de nascimento: sem Ascendente, Meio do Céu e casas."), "intro"))
    h.append(Spacer(1, 2 * mm))
    h.append(_caixas_resumo([
        ("Sol", f"{pts['sol']['signo_pt']} {pts['sol']['grau_texto']}"),
        ("Lua", _nome_signo(pts["lua"]) if pts["lua"].get("signo_incerto")
         else f"{pts['lua']['signo_pt']} {pts['lua']['grau_texto']}"),
        ("Ascendente", f"{pts['ascendente']['signo_pt']} {pts['ascendente']['grau_texto']}"
         if "ascendente" in pts else "sem hora"),
    ]))
    h.append(Spacer(1, 7 * mm))
    roda = Table([[RodaZodiacal(mapa, 130 * mm)]], colWidths=[LARGURA_UTIL])
    roda.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    h.append(roda)
    h.append(Spacer(1, 3 * mm))
    h.append(_p("Zodíaco tropical. " + ("Ascendente à esquerda; linhas laranja são os eixos das casas 1–7 e 4–10. "
                                        if mapa["tem_hora"] else "Áries à esquerda (sem hora não há casas). ")
                + "Linhas no miolo: aspectos (laranja = tensos, verde = harmônicos). R = retrógrado.", "nota"))
    h.append(PageBreak())

    # ---- 2. posições
    h.append(_p("As posições no seu mapa", "h1"))
    h.append(_p("Onde cada planeta e ponto estava no momento do seu nascimento, pelo zodíaco tropical.", "intro"))
    linhas = [_cab("Ponto", "Signo", "Grau", "Casa", "Movimento")]
    for k in list(mo.PLANETAS) + ["nodo_norte", "ascendente", "meio_do_ceu"]:
        if k not in pts:
            continue
        p = pts[k]
        mov = ("retrógrado" if p.get("retrogrado") else "direto") if k in mo.PLANETAS else "—"
        linhas.append([_p(mo.PONTO_PT[k], "celula"), _p(_nome_signo(p), "celula"), _p(p["grau_texto"], "celula"),
                       _p(str(p.get("casa", "—")), "celula"), _p(mov, "celula_suave")])
    h.append(_tabela(linhas, [LARGURA_UTIL * f for f in (0.26, 0.26, 0.16, 0.12, 0.20)]))
    if mapa["casas"]:
        sistema = "Placidus" if mapa["casas"]["sistema"] == "placidus" else "Porfírio"
        h.append(Spacer(1, 2 * mm))
        h.append(_p(f"Casas pelo sistema {sistema}. Cúspides: " + " · ".join(
            f"{n}: {mo.SIGNO_PT[mo.signo_de(cusp)[0]]} {mo.grau_minuto(mo.signo_de(cusp)[1])}"
            for n, cusp in enumerate(mapa["casas"]["cuspides"], start=1)), "nota"))

    # ---- 3. aspectos e equilíbrio
    h.append(CondPageBreak(60 * mm))
    h.append(_p("Aspectos", "h2"))
    if mapa["aspectos"]:
        linhas = [_cab("Ponto", "Aspecto", "Ponto", "Orbe")]
        for a in mapa["aspectos"]:
            linhas.append([_p(mo.PONTO_PT[a["a"]], "celula"), _p(mo.ASPECTO_PT[a["tipo"]], "celula"),
                           _p(mo.PONTO_PT[a["b"]], "celula"), _p(mo.grau_minuto(a["orbe"]), "celula")])
        h.append(_tabela(linhas, [LARGURA_UTIL * f for f in (0.3, 0.25, 0.3, 0.15)], respiro=3))
        h.append(_p("Orbes: 8° (10° quando o Sol ou a Lua participam); sextil, 6°.", "nota"))
    else:
        h.append(_p("Não há aspectos maiores dentro dos orbes usados."))
    h.append(CondPageBreak(40 * mm))
    h.append(_p("Elementos e modalidades", "h2"))
    linhas = [_cab("", "Quantos", "Quais")]
    for grupo, rotulos in ((mapa["elementos"], mo.ELEMENTO_PT), (mapa["modalidades"], mo.MODALIDADE_PT)):
        for chave, lista in grupo.items():
            linhas.append([_p(rotulos[chave], "celula"), _p(str(len(lista)), "celula"),
                           _p(", ".join(mo.PONTO_PT[x] for x in lista) or "—", "celula_suave")])
    h.append(_tabela(linhas, [LARGURA_UTIL * f for f in (0.2, 0.12, 0.68)], respiro=3))
    h.append(PageBreak())

    # ---- 4. leitura
    h.append(_p("A leitura do seu mapa", "h1"))
    for titulo, conteudo in secoes.items():
        h.append(CondPageBreak(30 * mm))
        h.append(_p(escape(titulo), "h2"))
        for par in (conteudo if isinstance(conteudo, list) else [conteudo]):
            h.append(_p(escape(par)))

    # ---- 5. método
    h.append(CondPageBreak(60 * mm))
    h.append(_p("Como este mapa foi calculado", "h2"))
    for texto in [
        "Zodíaco tropical (o usado na astrologia ocidental), com as efemérides do Swiss Ephemeris. "
        "Casas pelo sistema Placidus (Porfírio perto dos polos, onde o Placidus não existe). "
        "Nodo Norte verdadeiro. Regentes modernos (Escorpião: Plutão; Aquário: Urano; Peixes: Netuno).",
        "O fuso horário e o horário de verão do dia do nascimento são resolvidos automaticamente pela cidade, "
        "com o histórico oficial de cada lugar.",
        "O Ascendente muda de signo a cada duas horas, em média. Se a hora não for exata, confira a certidão: "
        "poucos minutos podem mudar o Ascendente e as casas.",
        "Dados de cidades: GeoNames (CC BY 4.0). Fontes tipográficas: Inter e Cormorant Garamond "
        "(SIL Open Font License).",
    ]:
        h.append(_p(escape(texto)))
    h.append(_p("<b>Este relatório é uma ferramenta de autoconhecimento. Descreve tendências, não destino, e não "
                "substitui orientação médica, psicológica, jurídica ou financeira.</b>"))

    rodape = _rodape(titulo_curto)
    doc.build(h, onFirstPage=rodape, onLaterPages=rodape)
    return buf.getvalue()


if __name__ == "__main__":
    import sys
    from pathlib import Path

    import montar_texto_ocidental as mt

    nasc = datetime(1990, 5, 15, 14, 30)
    m = mo.calcular_mapa_ocidental(nasc, -23.5505, -46.6333)
    pdf = gerar_pdf_ocidental(mapa=m, secoes=mt.montar_secoes(m), nome="Exemplo", cidade="São Paulo, SP",
                              data_nascimento=nasc.date(), hora="14:30")
    saida = sys.argv[1] if len(sys.argv) > 1 else "exemplo-ocidental.pdf"
    Path(saida).write_bytes(pdf)
    print(f"{saida}: {len(pdf) / 1024:.0f} KB")


# --------------------------------------------------------------------------
# Numerologia (e o esqueleto comum dos PDFs sem roda)
# --------------------------------------------------------------------------
def _capa(titulo: str, nome: str, linha: str, caixas: list, subject: str):
    buf = BytesIO()
    titulo_curto = f"{titulo} de {nome}" if nome else titulo
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=MARGEM, rightMargin=MARGEM,
                            topMargin=20 * mm, bottomMargin=18 * mm,
                            title=titulo_curto, author="Padmini", subject=subject)
    marca = Table([[Lotus(26), _p("Padmini", "capa_marca")]], colWidths=[34, 200], hAlign="LEFT")
    marca.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    h = [marca, Spacer(1, 8 * mm), _p(escape(titulo), "capa_titulo")]
    if nome:
        h.append(_p(escape(nome), "capa_nome"))
    h += [Spacer(1, 3 * mm), _p(linha, "intro"), Spacer(1, 2 * mm), _caixas_resumo(caixas), Spacer(1, 8 * mm)]
    return buf, doc, h, _rodape(titulo_curto)


def gerar_pdf_numerologia(*, rel: dict, nome: str, data_nascimento: date, hoje: date | None = None) -> bytes:
    hoje = hoje or date.today()
    por = {x["chave"]: x for x in rel["numeros"]}
    buf, doc, h, rodape = _capa(
        "Numerologia", nome,
        f"Nascimento em <b>{data_nascimento.strftime('%d/%m/%Y')}</b> · Numerologia pitagórica pelo nome "
        f"completo de registro · Relatório gerado em {hoje.strftime('%d/%m/%Y')}",
        [("Caminho de Vida", str(por["caminho_de_vida"]["valor"])),
         ("Expressão", str(por["expressao"]["valor"])),
         ("Ano Pessoal " + str(rel["ano_corrente"]), str(por["ano_pessoal"]["valor"]))],
        "Numerologia pitagórica")
    linhas = [_cab("Número", "Valor", "O que ele mostra")]
    for x in rel["numeros"]:
        valor = "—" if x["valor"] is None else f"{x['valor']}{' (mestre)' if x['mestre'] else ''}"
        linhas.append([_p(x["nome"], "celula"), _p(valor, "celula"), _p(escape(x["descricao"]), "celula_suave")])
    h.append(_tabela(linhas, [LARGURA_UTIL * f for f in (0.24, 0.14, 0.62)]))
    h.append(PageBreak())
    h.append(_p("A leitura dos seus números", "h1"))
    for x in rel["numeros"]:
        h.append(CondPageBreak(40 * mm))
        titulo = f"{x['nome']} {x['valor']}" if x["valor"] is not None else x["nome"]
        h.append(_p(escape(titulo), "h2"))
        h.append(_p(escape(x["descricao"]), "intro"))
        h.append(_p(escape(x["texto"])))
    h.append(CondPageBreak(50 * mm))
    h.append(_p("Como os números foram calculados", "h2"))
    for texto in [
        "Numerologia pitagórica: A=1 a I=9, J=1 a R=9, S=1 a Z=9. Acentos são removidos e Ç conta como C. "
        "Y conta como vogal e W como consoante.",
        "Caminho de Vida: dia, mês e ano reduzidos separadamente e depois somados. Expressão: todas as letras do "
        "nome; Alma: as vogais; Personalidade: as consoantes. Os números mestres 11, 22 e 33 não são reduzidos.",
        f"Ano Pessoal: o seu dia e mês de nascimento com o ano de {rel['ano_corrente']}.",
    ]:
        h.append(_p(escape(texto)))
    h.append(_p("<b>Esta leitura é uma ferramenta de autoconhecimento. Descreve tendências, não destino, e não "
                "substitui orientação profissional.</b>"))
    doc.build(h, onFirstPage=rodape, onLaterPages=rodape)
    return buf.getvalue()

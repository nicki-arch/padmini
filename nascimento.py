"""
Padmini — validação dos dados de nascimento, comum às duas versões do site.
(Estava no app.py; veio para cá sem mudar nada quando a versão ocidental
passou a usar as mesmas regras.)
"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException


def aviso_de_horario(dt: datetime, nome_fuso: str) -> str | None:
    """Detecta horários que não existem ou são ambíguos por causa do horário de verão."""
    if "hora média local" in nome_fuso:
        return ("Nascimento antes da adoção da hora padrão nesse local: usamos a hora média local, "
                "calculada pela longitude da cidade.")
    z = ZoneInfo(nome_fuso)
    ida_volta = dt.replace(tzinfo=z).astimezone(timezone.utc).astimezone(z).replace(tzinfo=None)
    if ida_volta != dt:
        return ("Esse horário não existiu nesse local: o relógio foi adiantado para o horário de verão "
                "nesse dia. Confira a hora na certidão de nascimento.")
    if dt.replace(tzinfo=z, fold=0).utcoffset() != dt.replace(tzinfo=z, fold=1).utcoffset():
        return ("Esse horário aconteceu duas vezes nesse dia (fim do horário de verão). "
                "Usamos a primeira ocorrência; se a pessoa nasceu na segunda, o Ascendente pode mudar.")
    return None


def validar_datetime(d: date, hora: str) -> datetime:
    """Valida hora e faixa de data; devolve o datetime local ingênuo."""
    h, m = map(int, hora.split(":"))
    if not (0 <= h < 24 and 0 <= m < 60):
        raise HTTPException(422, "Hora inválida.")
    dt = datetime(d.year, d.month, d.day, h, m)
    if not (datetime(1800, 1, 1) <= dt <= datetime.now()):
        raise HTTPException(422, "A data de nascimento precisa estar entre 1800 e hoje.")
    return dt


def validar_data(d: date) -> None:
    """Para nascimento sem hora: só a faixa de datas (a mesma do validar_datetime)."""
    if not (date(1800, 1, 1) <= d <= date.today()):
        raise HTTPException(422, "A data de nascimento precisa estar entre 1800 e hoje.")

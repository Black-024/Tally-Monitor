"""Mensaje de la pestaña Inicio según fecha y hora locales (sin Qt, probado automáticamente).
Los textos están en strings.py (GREET_*), en el idioma activo."""
from __future__ import annotations

from datetime import datetime

from . import strings as S


def greeting_for(now: datetime) -> tuple[str, str]:
    """(título, subtítulo). Las fechas especiales tienen prioridad; si no, momento del día + día de la semana."""
    special = S.GREET_SPECIAL.get((now.month, now.day))
    if special:
        return special
    if now.month == 12 and 26 <= now.day <= 30:
        return S.GREET_BETWEEN_HOLIDAYS
    h = now.hour
    title = (S.GREET_NIGHT if h < 5 else S.GREET_MORNING if h < 12
             else S.GREET_AFTERNOON if h < 20 else S.GREET_EVENING)
    return title, S.GREET_WEEKDAY[now.weekday()]

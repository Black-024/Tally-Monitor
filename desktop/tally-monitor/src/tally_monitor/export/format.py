"""Formato de números y fechas para textos de exportación, según el idioma activo (es: 1,5 y dd/mm/aaaa; en: 1.5 y mm/dd/yyyy)."""
from __future__ import annotations

from ..core.language import pick

DEC_SEP = pick(",", ".")
DT_FMT = pick("%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M")
PCT_FMT = pick("{value} %", "{value}%")


def dec(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}".replace(".", DEC_SEP)


def pct(value: float | None) -> str:
    return "—" if value is None else PCT_FMT.format(value=dec(value, 1))


def dt(value) -> str:
    return value.strftime(DT_FMT) if value else "—"

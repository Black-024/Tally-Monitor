"""Filtros de tiempo (24 h, 7 d, 30 d, todo, rango personalizado). Inicio inclusivo, fin exclusivo."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone, tzinfo

from ..core.language import pick as _t
from .models import ResolvedFilter

KINDS = ("all", "24h", "7d", "30d", "custom")
_WINDOWS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
_LABELS = {"all": _t("Todo el período", "All time"), "24h": _t("Últimas 24 horas", "Last 24 hours"),
           "7d": _t("Últimos 7 días", "Last 7 days"), "30d": _t("Últimos 30 días", "Last 30 days")}
_DATE_FMT = _t("%d/%m/%Y", "%m/%d/%Y")


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def resolve_filter(kind: str, now: datetime, tz: tzinfo, *, start_date: date | None = None,
                   end_date: date | None = None) -> ResolvedFilter:
    """`now` debe tener zona. Rango personalizado: días COMPLETOS en la hora local, ambos extremos incluidos."""
    if now.tzinfo is None:
        raise ValueError("now debe tener zona horaria")
    if kind == "all":
        return ResolvedFilter("all", None, None, _LABELS["all"])
    if kind in _WINDOWS:
        return ResolvedFilter(kind, to_iso(now - _WINDOWS[kind]), to_iso(now + timedelta(seconds=1)), _LABELS[kind])
    if kind == "custom":
        if start_date is None or end_date is None:
            raise ValueError("El rango personalizado necesita fecha de inicio y de fin")
        if start_date > end_date:
            raise ValueError("La fecha de inicio es posterior a la de fin")
        start = datetime.combine(start_date, time.min, tzinfo=tz)
        end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
        a, b = start_date.strftime(_DATE_FMT), end_date.strftime(_DATE_FMT)
        label = _t(f"Del {a} al {b}", f"From {a} to {b}")
        return ResolvedFilter("custom", to_iso(start), to_iso(end), label)
    raise ValueError(f"Filtro desconocido: {kind}")

"""Ritmo de respuestas: semana actual vs anterior, día y hora más activos, % de completados. Función pura."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Iterable

WEEK = timedelta(days=7)


@dataclass(frozen=True)
class Trends:
    last7: int
    prev7: int
    delta_pct: int | None                 # None si prev7 == 0
    completion_pct: int | None            # None si no hay envíos
    by_weekday: tuple[int, ...] = field(default_factory=lambda: (0,) * 7)     # lunes = 0
    by_hour: tuple[int, ...] = field(default_factory=lambda: (0,) * 24)
    peak_weekday: int | None = None
    peak_hour: int | None = None


def _to_utc(value) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _round_div(n: int, d: int) -> int:
    """n/d redondeado a entero, mitades alejándose de cero (87,5 → 88; -12,5 → -13)."""
    q, r = divmod(abs(n) * 2 + d, 2 * d)
    return q if n >= 0 else -q


def _peak(counts: tuple[int, ...]) -> int | None:
    top = max(counts)
    return counts.index(top) if top > 0 else None        # empate: el menor índice


def count_last7(times: Iterable, now: datetime) -> int:
    """Envíos en [now − 7 d, now]."""
    now_u = _to_utc(now)
    start = now_u - WEEK
    return sum(1 for t in times if start <= _to_utc(t) <= now_u)


def trends(submissions: Iterable[tuple], now: datetime, tz: tzinfo, *,
           all_submissions: Iterable[tuple] | None = None) -> Trends:
    """submissions: (submitted_at_utc, is_completed) del PERÍODO elegido → por día, por hora y % de completados
    (en la hora local `tz`). last7/prev7/delta ignoran el período y usan `all_submissions` (todos los guardados;
    si no se pasa, se usa `submissions`). last7 = [now − 7 d, now]; prev7 = [now − 14 d, now − 7 d)."""
    if now.tzinfo is None:
        raise ValueError("now debe tener zona horaria")
    period = [(_to_utc(t), bool(c)) for t, c in submissions]
    allsubs = period if all_submissions is None else [(_to_utc(t), bool(c)) for t, c in all_submissions]
    now_u = _to_utc(now)
    last7 = sum(1 for t, _ in allsubs if now_u - WEEK <= t <= now_u)
    prev7 = sum(1 for t, _ in allsubs if now_u - 2 * WEEK <= t < now_u - WEEK)
    delta = _round_div((last7 - prev7) * 100, prev7) if prev7 else None
    wd, hr = [0] * 7, [0] * 24
    for t, _ in period:
        local = t.astimezone(tz)
        wd[local.weekday()] += 1
        hr[local.hour] += 1
    completion = _round_div(sum(1 for _, c in period if c) * 100, len(period)) if period else None
    wd_t, hr_t = tuple(wd), tuple(hr)
    return Trends(last7, prev7, delta, completion, wd_t, hr_t, _peak(wd_t), _peak(hr_t))

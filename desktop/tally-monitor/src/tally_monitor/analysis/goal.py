"""Proyección de una meta de respuestas. Función pura: sin Qt, SQLite ni red."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

MAX_ETA_DAYS = 3650          # más allá de ~10 años se considera «sin ritmo suficiente»
WINDOW_DAYS = 7


@dataclass(frozen=True)
class GoalProjection:
    done: bool                 # local_count >= goal
    pct: int                   # 0..100 (entero hacia abajo, tope 100: 199 de 200 es 99 %, no 100 %)
    remaining: int             # max(0, goal - local_count)
    per_day: float             # last7_count / 7
    eta_days: int | None       # días hasta llegar; None si ya se alcanzó, no hay ritmo o supera MAX_ETA_DAYS
    eta_date: date | None      # fecha local (la de `now`) de llegada estimada


def goal_projection(local_count: int, goal: int, last7_count: int, now: datetime) -> GoalProjection:
    """`last7_count`: envíos guardados con submitted_at en las 7×24 h previas a `now`.
    `now` debe tener zona: eta_date es la fecha en esa zona."""
    if now.tzinfo is None:
        raise ValueError("now debe tener zona horaria")
    if isinstance(goal, bool) or not isinstance(goal, int) or goal < 1:
        raise ValueError("la meta debe ser un entero positivo")
    local = max(0, int(local_count))
    last7 = max(0, int(last7_count))
    done = local >= goal
    remaining = max(0, goal - local)
    pct = min(100, local * 100 // goal)
    per_day = last7 / WINDOW_DAYS
    eta_days: int | None = None
    eta_date: date | None = None
    if not done and last7 > 0:
        days = -(-remaining * WINDOW_DAYS // last7)         # ceil(remaining / per_day) sin errores de coma flotante
        if days <= MAX_ETA_DAYS:
            eta_days = days
            eta_date = (now + timedelta(days=days)).date()
    return GoalProjection(done, pct, remaining, per_day, eta_days, eta_date)

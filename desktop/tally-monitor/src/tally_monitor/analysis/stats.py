"""Estadísticas puras. Reglas (ver docs/ESTADISTICAS.md):
- «respondió» = respuesta no vacía; «sin respuesta» = vacía; «no traía la pregunta» se cuenta aparte;
- porcentajes sobre quienes respondieron esa pregunta; en selección múltiple, de personas (puede superar 100 %);
- los números internos son enteros; el redondeo es cosa de quien muestra."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Iterable

from ..core.language import pick as _t
from .models import (AnswerPoint, OptionStat, Overview, QuestionInfo, QuestionStats, SubmissionPoint, TimeBucket,
                     Timeline)

_BASE_NOTES = {
    "single": _t("% sobre quienes respondieron esta pregunta", "% of those who answered this question"),
    "multi": _t("% de personas que respondieron esta pregunta (puede sumar más de 100 %)",
                "% of people who answered this question (may add up to more than 100%)"),
    "text": "",
    "raw": "",
}
_KIND_BY_TYPE = {"MULTIPLE_CHOICE": "single", "CHECKBOXES": "multi", "TEXTAREA": "text"}


def parse_iso(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)


def _local_date(iso: str, tz: tzinfo):
    return parse_iso(iso).astimezone(tz).date()


def pct(count: int, base: int) -> float | None:
    return None if base <= 0 else count * 100.0 / base


# ---------- resumen ----------
def overview(submissions: Iterable[SubmissionPoint], tz: tzinfo) -> Overview:
    subs = list(submissions)
    if not subs:
        return Overview(0, 0, 0, None, None, 0, None)
    completed = sum(1 for s in subs if s.is_completed)
    first = min(s.submitted_at for s in subs)
    last = max(s.submitted_at for s in subs)
    span = (_local_date(last, tz) - _local_date(first, tz)).days + 1
    return Overview(len(subs), completed, len(subs) - completed, first, last, span, len(subs) / span)


# ---------- por pregunta ----------
def question_stats(q: QuestionInfo, answers: Iterable[AnswerPoint], total_submissions: int) -> QuestionStats:
    kind = _KIND_BY_TYPE.get(q.type, "raw")
    rows: dict[int, AnswerPoint] = {}
    for a in answers:
        rows[a.key] = a                       # una respuesta por envío y pregunta
    asked = len(rows)
    answered_rows = [a for a in rows.values() if not a.is_blank]
    answered, blank = len(answered_rows), asked - len(answered_rows)
    common = dict(question_id=q.question_id, position=q.position, type=q.type, title=q.title, kind=kind,
                  asked=asked, answered=answered, blank=blank, not_asked=max(0, total_submissions - asked),
                  base_note=_BASE_NOTES[kind], is_deleted=q.is_deleted)
    if kind in ("single", "multi"):
        declared: Counter[str] = Counter()
        other: Counter[str] = Counter()
        orphan: Counter[str] = Counter()
        for a in answered_rows:
            seen: set[tuple[str, str]] = set()
            for text, origin in a.choices:
                if (text, origin) in seen:
                    continue                  # una persona cuenta una sola vez por opción
                seen.add((text, origin))
                {"declared": declared, "other": other}.get(origin, orphan)[text] += 1
        options = [OptionStat(t, declared.get(t, 0), pct(declared.get(t, 0), answered)) for t in q.options]
        known = set(q.options)
        # opciones «declared» que ya no figuran en la pregunta: se muestran, nunca se pierden
        extra = [OptionStat(t, n, pct(n, answered)) for t, n in sorted(declared.items()) if t not in known]
        return QuestionStats(**common, interpreted=True, options=tuple(options + extra),
                             other_count=sum(other.values()), other_values=_ranked(other),
                             orphan_count=sum(orphan.values()), orphan_values=_ranked(orphan))
    if kind == "text":
        lens = [a.text_len or 0 for a in answered_rows]
        return QuestionStats(**common, interpreted=True, avg_len=(sum(lens) / len(lens)) if lens else None,
                             max_len=max(lens) if lens else None)
    return QuestionStats(**common, interpreted=False)


def _ranked(counter: Counter) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))


def all_question_stats(questions: Iterable[QuestionInfo], answers: Iterable[AnswerPoint],
                       total_submissions: int) -> tuple[QuestionStats, ...]:
    by_q: dict[str, list[AnswerPoint]] = defaultdict(list)
    for a in answers:
        by_q[a.question_id].append(a)
    return tuple(question_stats(q, by_q.get(q.question_id, ()), total_submissions)
                 for q in sorted(questions, key=lambda x: (x.position, x.question_id)))


# ---------- evolución en el tiempo ----------
def _floor(dt: datetime, bucket: str) -> datetime:
    if bucket == "hour":
        return dt.replace(minute=0, second=0, microsecond=0)
    if bucket == "day":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next(dt: datetime, bucket: str) -> datetime:
    if bucket == "hour":
        return dt + timedelta(hours=1)
    if bucket == "day":
        return dt + timedelta(days=1)
    return dt.replace(year=dt.year + 1, month=1) if dt.month == 12 else dt.replace(month=dt.month + 1)


def choose_bucket(first: datetime, last: datetime) -> str:
    span = last - first
    if span <= timedelta(hours=48):
        return "hour"
    if span <= timedelta(days=400):
        return "day"
    return "month"


def timeline(submissions: Iterable[SubmissionPoint], tz: tzinfo, *, start: datetime | None = None,
             end: datetime | None = None) -> Timeline:
    """Cuenta por intervalo en hora local, rellenando con ceros. `start`/`end` (UTC, aware) fijan el eje
    (p. ej. las 24 h completas aunque no haya respuestas); si faltan, se usa de la primera a la última respuesta."""
    locs = [parse_iso(s.submitted_at).astimezone(tz).replace(tzinfo=None) for s in submissions]
    if not locs and (start is None or end is None):
        return Timeline("day", (), 0)
    lo = start.astimezone(tz).replace(tzinfo=None) if start else min(locs)
    hi = end.astimezone(tz).replace(tzinfo=None) if end else max(locs)
    if hi < lo:
        hi = lo
    bucket = choose_bucket(lo, hi)
    counts: Counter[datetime] = Counter(_floor(d, bucket) for d in locs)
    points, cur, last = [], _floor(lo, bucket), _floor(hi, bucket)
    while cur <= last:
        points.append(TimeBucket(cur, counts.get(cur, 0)))
        cur = _next(cur, bucket)
    return Timeline(bucket, tuple(points), len(locs))

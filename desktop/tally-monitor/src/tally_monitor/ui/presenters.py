"""Lógica de presentación SIN Qt (probada automáticamente): textos, estados y formatos."""
from __future__ import annotations

from datetime import datetime, timezone

from . import strings as S

# estado -> tono visual. El tono nunca es la única señal: el badge siempre lleva texto.
_TONES = {"active": "ok", "key_rejected": "danger", "no_credential": "danger",
          "check_failed": "warn", "unverified": "neutral"}
_ATTENTION = {"key_rejected", "no_credential", "check_failed"}


def status_view(status: str) -> tuple[str, str]:
    return S.STATUS_LABELS.get(status, status), _TONES.get(status, "neutral")


def needs_attention(account) -> bool:
    return account.status in _ATTENTION


def summarize(accounts) -> dict[str, int]:
    return {"total": len(accounts),
            "active": sum(a.status == "active" for a in accounts),
            "attention": sum(needs_attention(a) for a in accounts)}


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)


def format_local(iso: str | None) -> str:
    if not iso:
        return "—"
    return _parse(iso).astimezone().strftime(S.DATETIME_FMT)


def format_dt_local(dt: datetime) -> str:
    return dt.astimezone().strftime(S.DATETIME_FMT)


def format_relative(iso: str | None, now: datetime | None = None) -> str:
    if not iso:
        return S.REL_NEVER
    secs = int(((now or datetime.now(timezone.utc)) - _parse(iso)).total_seconds())
    if secs < 45:
        return S.REL_NOW
    if secs < 3600:
        return S.REL_MIN.format(n=max(1, secs // 60))
    if secs < 86400:
        return S.REL_HOUR.format(n=secs // 3600)
    days = secs // 86400
    return (S.REL_DAY_ONE if days == 1 else S.REL_DAY_MANY).format(n=days)


def account_subtitle(account, now: datetime | None = None) -> str:
    """Línea de detalle de una cuenta (sin ningún dato de la clave)."""
    label, _ = status_view(account.status)
    parts = [label]
    if account.status in ("check_failed", "key_rejected") and account.last_check_result:
        detail = S.CHECK_DETAILS.get(account.last_check_result)
        if detail and detail != label:
            parts.append(detail)
    if account.last_validated_at:
        parts.append(S.ACCOUNT_VALIDATED_REL.format(when=format_relative(account.last_validated_at, now)))
    else:
        parts.append(S.ACCOUNT_NOT_VALIDATED)
    if account.status != "no_credential":
        parts.append(S.KEY_SAVED)
    return " · ".join(parts)


def account_help(account) -> str:
    return S.STATUS_HELP.get(account.status, "")


def suggest_account_name(existing: list[str]) -> str:
    taken = {n.casefold() for n in existing}
    n = len(existing) + 1
    while S.ACCOUNT_DEFAULT_NAME.format(n=n).casefold() in taken:
        n += 1
    return S.ACCOUNT_DEFAULT_NAME.format(n=n)


def format_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 ** 2:.1f} MB"


def reason_label(reason: str) -> str:
    return S.REASONS.get(reason, reason)


def format_local_seconds(iso: str | None) -> str:
    if not iso:
        return "—"
    return _parse(iso).astimezone().strftime(S.DATETIME_SEC_FMT)


def survey_status_text(s) -> str:
    if s.is_closed:
        return S.SURVEY_CLOSED
    return {"DRAFT": S.SURVEY_DRAFT}.get(str(s.status).upper(), S.SURVEY_OPEN)


def survey_counts_text(s, now: datetime | None = None) -> str:
    """«27 respuestas guardadas · sincronizada hace 5 min»; sin datos inventados."""
    if s.never_synced:
        saved = S.NEVER_SYNCED
        if s.reported_submissions is not None:
            saved += (S.SURVEY_REPORTED_ONE if s.reported_submissions == 1 else S.SURVEY_REPORTED_MANY).format(
                n=s.reported_submissions)
        return saved
    n = s.local_submissions
    parts = [(S.SURVEY_SAVED_ONE if n == 1 else S.SURVEY_SAVED_MANY).format(n=n),
             S.SURVEY_SYNCED_REL.format(when=format_relative(s.last_synced_at, now))]
    return " · ".join(parts)


def filter_surveys(surveys, *, text: str = "", mode: str = "all", recents: list[str] | None = None,
                   tag: str | None = None, show_archived: bool = False):
    """Filtra y ordena: favoritas primero. «Recientes» sigue el orden de apertura (la más nueva primero).
    La búsqueda mira el nombre, la nota y las etiquetas; las archivadas solo se ven si se pidió."""
    q = (text or "").strip().casefold()

    def matches(s) -> bool:
        if not q:
            return True
        hay = [s.name, getattr(s, "note", "") or "", *(getattr(s, "tags", ()) or ())]
        return any(q in h.casefold() for h in hay)

    out = [s for s in surveys if matches(s)]
    if not show_archived:
        out = [s for s in out if not getattr(s, "archived", False)]
    if tag:
        want = tag.casefold()
        out = [s for s in out if any(t.casefold() == want for t in (getattr(s, "tags", ()) or ()))]
    if mode == "fav":
        out = [s for s in out if s.is_favorite]
    elif mode == "recent":
        order = {fid: i for i, fid in enumerate(recents or [])}
        out = sorted((s for s in out if s.form_id in order), key=lambda s: order[s.form_id])
        return out
    return sorted(out, key=lambda s: (not s.is_favorite,))      # estable: conserva el orden previo dentro de cada grupo


def all_tags(surveys, *, show_archived: bool = False) -> list[str]:
    """Etiquetas en uso (sin repetir sin distinguir mayúsculas), ordenadas alfabéticamente."""
    seen: dict[str, str] = {}
    for s in surveys:
        if getattr(s, "archived", False) and not show_archived:
            continue
        for t in getattr(s, "tags", ()) or ():
            seen.setdefault(t.casefold(), t)
    return [seen[k] for k in sorted(seen)]


def has_archived(surveys) -> bool:
    return any(getattr(s, "archived", False) for s in surveys)


def sync_result_text(r) -> str:
    """Resumen de una sincronización de encuesta para mostrar a la persona."""
    if r.mode == "nochange":
        text = S.SYNC_RESULT_NOCHANGE
    elif r.mode == "initial":
        text = (S.SYNC_RESULT_INITIAL_ONE if r.new == 1 else S.SYNC_RESULT_INITIAL_MANY).format(n=r.new)
    elif r.mode == "incremental":
        text = (S.SYNC_RESULT_NEW_ONE if r.new == 1 else S.SYNC_RESULT_NEW_MANY).format(n=r.new) \
            if r.new else S.SYNC_RESULT_NONE_NEW
    else:
        text = (S.SYNC_RESULT_FULL_MISSING if r.missing else S.SYNC_RESULT_FULL).format(
            new=r.new, updated=r.updated, missing=r.missing)
    if "count_mismatch" in r.warnings:
        text += S.SYNC_RESULT_MISMATCH.format(local=r.local_total, remote=r.remote_total)
    return text


def answer_lines(answer) -> list[str]:
    """Texto para mostrar de una respuesta (sin Qt)."""
    if answer.is_blank:
        return [S.ANSWER_BLANK]
    if answer.kind in ("single", "multi"):
        lines = []
        for c in answer.choices:
            suffix = {"other": f" {S.ANSWER_OTHER}", "unmatched": f" {S.ANSWER_UNMATCHED}"}.get(c.origin, "")
            lines.append(c.text + suffix)
        return lines or [answer.text or S.ANSWER_BLANK]
    if answer.kind == "raw":
        return [answer.text or S.ANSWER_RAW]
    return [answer.text or S.ANSWER_BLANK]


def response_matches(view, query: str) -> bool:
    """Búsqueda por etiqueta: «012», «usuario 12», «A001»."""
    q = (query or "").strip().casefold()
    if not q:
        return True
    return q in view.label.casefold()


# ---------------- Análisis ----------------
def format_decimal(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}".replace(".", S.DECIMAL_SEP)


def format_pct(pct: float | None) -> str:
    return "—" if pct is None else S.PCT_FMT.format(value=format_decimal(pct, 1))


def bar_rows(q) -> list[tuple[str, int, float]]:
    """Filas (texto, cantidad, fracción 0..1 sobre quienes respondieron) para el gráfico de barras de una pregunta."""
    base = q.answered or 0

    def frac(n: int) -> float:
        return (n / base) if base else 0.0

    rows = [(o.text, o.count, frac(o.count)) for o in q.options]
    if q.other_count:
        rows.append((S.ANALYSIS_OTHER_ROW, q.other_count, frac(q.other_count)))
    if q.orphan_count:
        rows.append((S.ANALYSIS_ORPHAN_ROW, q.orphan_count, frac(q.orphan_count)))
    return rows


def bar_value_text(count: int, fraction: float) -> str:
    return f"{count} · {format_pct(fraction * 100)}"


def question_counts_text(q) -> str:
    parts = [S.ANALYSIS_ANSWERED.format(n=q.answered), S.ANALYSIS_BLANK.format(n=q.blank)]
    if q.not_asked:
        parts.append(S.ANALYSIS_NOT_ASKED.format(n=q.not_asked))
    return " · ".join(parts)


def other_values_text(q, limit: int = 8) -> str:
    items = [S.OTHER_ITEM_TIMES.format(text=t[:40], n=n) if n > 1 else S.OTHER_ITEM.format(text=t[:40])
             for t, n in q.other_values[:limit]]
    extra = len(q.other_values) - limit
    if extra > 0:
        items.append(S.OTHER_MORE.format(n=extra))
    return S.ANALYSIS_OTHER_VALUES.format(items=", ".join(items)) if items else ""


def overview_tiles(o) -> list[tuple[str, str]]:
    labels = S.ANALYSIS_TILES
    return [(labels[0], str(o.total)), (labels[1], str(o.completed)), (labels[2], str(o.partial)),
            (labels[3], format_decimal(o.per_day, 2))]


def span_text(o) -> str:
    if not o.first_at:
        return ""
    return S.ANALYSIS_SPAN.format(first=format_local(o.first_at), last=format_local(o.last_at))


def timeline_label(bucket: str, start: datetime) -> str:
    if bucket == "hour":
        return start.strftime(S.TL_HOUR_FMT)
    if bucket == "month":
        return start.strftime(S.TL_MONTH_FMT)
    return start.strftime(S.TL_DAY_FMT)


def timeline_series(t) -> list[tuple[str, int]]:
    return [(timeline_label(t.bucket, p.start), p.count) for p in t.points]


def survey_options(surveys) -> list[tuple[str, str]]:
    """Encuestas analizables (con respuestas guardadas): (form_id, nombre)."""
    return [(s.form_id, s.name) for s in surveys if s.local_submissions]


def format_local_naive(value: datetime) -> str:
    """Fecha y hora ya en hora local (sin zona): «10/11/2026 13:20»."""
    return value.strftime(S.DATETIME_FMT)


def format_count(n: int) -> str:
    """12345 -> «12.345» (es) o «12,345» (en)."""
    return f"{int(n):,}".replace(",", S.THOUSANDS_SEP)


def format_duration(seconds: float) -> str:
    """Duración aproximada y legible: «10 segundos», «3 minutos», «1 hora y 20 minutos»."""
    s = max(1, int(round(seconds)))
    if s < 60:
        return S.DUR_SECOND_ONE if s == 1 else S.DUR_SECONDS.format(n=s)
    m = round(s / 60)
    if m < 60:
        return S.DUR_MINUTES.format(n=m) if m != 1 else S.DUR_ONE_MINUTE
    h, rest = divmod(m, 60)
    base = (S.DUR_HOUR_ONE if h == 1 else S.DUR_HOUR_MANY).format(n=h)
    return base + (S.DUR_AND_MINUTES.format(n=rest) if rest else "")


# ---------- Inicio ----------
from dataclasses import dataclass  # noqa: E402


@dataclass(frozen=True)
class HomeOverview:
    survey_count: int
    response_total: int
    open_count: int
    last_at: str | None
    pending: tuple          # ((account_id, SurveySummary), ...) con respuestas sin actualizar
    new_count: int          # respuestas que Tally informa de más
    top: tuple              # ((account_id, SurveySummary), ...) las de actividad más reciente


def home_overview(per_account, top_n: int = 4) -> HomeOverview:
    """per_account: iterable de (account_id, [SurveySummary]). Solo cuenta lo ya guardado."""
    items = [(aid, s) for aid, surveys in per_account for s in surveys]
    items = [(a, s) for a, s in items if not getattr(s, "archived", False)]       # las archivadas no cuentan en Inicio
    pending = tuple((a, s) for a, s in items if s.has_new_hint)
    new = sum(max(0, (s.reported_submissions or 0) - s.local_submissions) for _a, s in pending)
    lasts = [s.last_submission_at for _a, s in items if s.last_submission_at]
    top = tuple(sorted(items, key=lambda it: it[1].last_submission_at or "", reverse=True)[:top_n])
    return HomeOverview(len(items), sum(s.local_submissions for _a, s in items), sum(1 for _a, s in items if not s.is_closed),
                        max(lasts) if lasts else None, pending, new, top)


# ---------- 1.1: metas ----------
def format_date(d) -> str:
    return d.strftime(S.DATE_FMT)


def goal_line(local: int, goal: int, g) -> str:
    """«124 de 200 (62 %)»."""
    return S.GOAL_LINE.format(done=format_count(local), goal=format_count(goal), pct=g.pct)


def goal_eta_text(g) -> str:
    if g.done:
        return S.GOAL_REACHED
    if g.per_day <= 0:
        return S.GOAL_NO_PACE_ZERO
    if g.eta_days is None or g.eta_date is None:
        return S.GOAL_NO_PACE_ENOUGH
    return S.GOAL_ETA.format(per_day=format_decimal(g.per_day, 1), date=format_date(g.eta_date))


def goal_items(per_account_surveys, per_account_goals):
    """Para la sección «Metas» de Inicio: [(account_id, survey, GoalProjection)] de las encuestas con meta NO archivadas.
    per_account_*: iterables de (account_id, lista) / (account_id, {form_id: GoalProjection})."""
    goals = {aid: g for aid, g in per_account_goals}
    out = []
    for aid, surveys in per_account_surveys:
        for s in surveys:
            g = goals.get(aid, {}).get(s.form_id)
            if g is not None and getattr(s, "goal", None) and not getattr(s, "archived", False):
                out.append((aid, s, g))
    return out


# ---------- 1.1: ritmo ----------
def rhythm_week_text(t) -> str:
    text = S.RHYTHM_WEEK.format(n=t.last7, word=S.RHYTHM_WORD_ONE if t.last7 == 1 else S.RHYTHM_WORD_MANY)
    if t.delta_pct is not None:
        sign = "+" if t.delta_pct > 0 else ""
        text += S.RHYTHM_WEEK_DELTA.format(delta=S.PCT_FMT.format(value=f"{sign}{t.delta_pct}"))
    return text


def rhythm_peak_text(t) -> str:
    if t.peak_weekday is None or t.peak_hour is None:
        return S.RHYTHM_NO_PEAK
    return S.RHYTHM_PEAK.format(day=S.WEEKDAYS[t.peak_weekday], hour=t.peak_hour)


def rhythm_completion_text(t) -> str:
    return "" if t.completion_pct is None else S.RHYTHM_COMPLETION.format(pct=t.completion_pct)


def weekday_rows(t) -> list[tuple[str, int, float]]:
    """Filas para BarChart: la barra es proporcional al día más activo."""
    top = max(t.by_weekday) or 1
    return [(S.WEEKDAYS[i].capitalize(), n, n / top) for i, n in enumerate(t.by_weekday)]


def hour_series(t) -> list[tuple[str, int]]:
    return [(S.HOUR_LABEL.format(h=h), n) for h, n in enumerate(t.by_hour)]


# ---------- 1.1: cruce de preguntas ----------
def cross_ribbon_text(a, question_title: str) -> str:
    return S.CROSS_RIBBON.format(matched=a.matched, total=a.total_in_period, option=a.answer_filter.option_text,
                                 question=question_title)

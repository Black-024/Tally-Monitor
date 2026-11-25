from datetime import date, datetime, timedelta, timezone

import pytest

from tally_monitor.analysis import crosscheck, stats, timefilter
from tally_monitor.analysis.models import AnswerPoint, QuestionInfo, SubmissionPoint

UTC = timezone.utc
AR = timezone(timedelta(hours=-3))


def S(key, iso, ok=True):
    return SubmissionPoint(key, iso, ok)


def A(key, qid="q", kind="single", blank=False, choices=(), text_len=None):
    return AnswerPoint(key, qid, kind, blank, text_len, tuple(choices))


SINGLE = QuestionInfo("q", 0, "MULTIPLE_CHOICE", "¿Te gustó?", ("Sí", "No", "Otro"), True)
MULTI = QuestionInfo("m", 1, "CHECKBOXES", "Colores", ("Rojo", "Verde", "Azul"))
TEXT = QuestionInfo("t", 2, "TEXTAREA", "Comentarios")


# ---------- por pregunta (resultados calculados a mano) ----------
def test_single_choice_counts_percentages_other_blank_and_not_asked():
    answers = [A(1, choices=[("Sí", "declared")]), A(2, choices=[("Sí", "declared")]),
               A(3, choices=[("No", "declared")]), A(4, blank=True),
               A(5, choices=[("Quizás", "other")])]                 # el envío 6 no trae la pregunta
    q = stats.question_stats(SINGLE, answers, total_submissions=6)
    assert (q.asked, q.answered, q.blank, q.not_asked) == (5, 4, 1, 1)
    assert [(o.text, o.count, o.pct) for o in q.options] == [("Sí", 2, 50.0), ("No", 1, 25.0), ("Otro", 0, 0.0)]
    assert q.other_count == 1 and q.other_values == (("Quizás", 1),) and q.orphan_count == 0
    assert q.kind == "single" and q.interpreted


def test_multi_choice_is_percent_of_people_and_can_exceed_100():
    answers = [A(1, "m", "multi", choices=[("Rojo", "declared"), ("Verde", "declared")]),
               A(2, "m", "multi", choices=[("Rojo", "declared")]),
               A(3, "m", "multi", choices=[("Azul", "declared"), ("Violeta", "unmatched")]),
               A(4, "m", "multi", blank=True)]
    q = stats.question_stats(MULTI, answers, 4)
    assert (q.answered, q.blank) == (3, 1)
    got = {o.text: (o.count, round(o.pct, 2)) for o in q.options}
    assert got == {"Rojo": (2, 66.67), "Verde": (1, 33.33), "Azul": (1, 33.33)}
    assert sum(o.pct for o in q.options) > 100
    assert q.orphan_count == 1 and q.orphan_values == (("Violeta", 1),)


def test_duplicate_choice_in_one_answer_counts_once():
    q = stats.question_stats(MULTI, [A(1, "m", "multi", choices=[("Rojo", "declared"), ("Rojo", "declared")])], 1)
    assert q.options[0].count == 1 and q.options[0].pct == 100.0


def test_declared_option_missing_from_question_is_kept_not_lost():
    q = stats.question_stats(SINGLE, [A(1, choices=[("Antigua", "declared")])], 1)
    assert [o.text for o in q.options] == ["Sí", "No", "Otro", "Antigua"] and q.options[-1].count == 1


def test_text_question_lengths():
    answers = [A(1, "t", "text", text_len=5), A(2, "t", "text", text_len=10), A(3, "t", "text", blank=True)]
    q = stats.question_stats(TEXT, answers, 3)
    assert (q.answered, q.blank, q.avg_len, q.max_len, q.kind) == (2, 1, 7.5, 10, "text")


def test_unknown_type_is_not_interpreted_but_still_counted():
    q = stats.question_stats(QuestionInfo("x", 0, "RATING", "Nota"), [A(1, "x", "raw"), A(2, "x", "raw", blank=True)], 2)
    assert not q.interpreted and (q.asked, q.answered, q.blank) == (2, 1, 1) and q.options == ()


def test_nobody_answered_gives_no_percentages_and_zero_division_is_safe():
    q = stats.question_stats(SINGLE, [A(1, blank=True)], 1)
    assert q.answered == 0 and all(o.pct is None and o.count == 0 for o in q.options)
    q0 = stats.question_stats(SINGLE, [], 0)
    assert (q0.asked, q0.answered, q0.not_asked) == (0, 0, 0)
    assert stats.pct(1, 0) is None and stats.pct(1, 4) == 25.0


def test_last_answer_per_submission_wins_no_double_counting():
    q = stats.question_stats(SINGLE, [A(1, choices=[("Sí", "declared")]), A(1, choices=[("Sí", "declared")])], 1)
    assert q.asked == 1 and q.answered == 1


def test_all_question_stats_orders_by_position():
    res = stats.all_question_stats([TEXT, SINGLE, MULTI], [], 0)
    assert [r.question_id for r in res] == ["q", "m", "t"]


# ---------- resumen ----------
def test_overview_uses_local_days():
    subs = [S(1, "2026-11-10T02:30:00.000Z"),       # 09/11 23:30 en Argentina
            S(2, "2026-11-10T04:00:00.000Z", ok=False),    # 10/11 01:00
            S(3, "2026-11-12T15:00:00.000Z")]       # 12/11 12:00
    o = stats.overview(subs, AR)
    assert (o.total, o.completed, o.partial) == (3, 2, 1)
    assert o.span_days == 4 and o.per_day == 0.75
    assert o.first_at == "2026-11-10T02:30:00.000Z" and o.last_at == "2026-11-12T15:00:00.000Z"
    assert stats.overview(subs, UTC).span_days == 3          # en UTC la primera es el día 10


def test_overview_empty():
    o = stats.overview([], AR)
    assert (o.total, o.span_days, o.per_day, o.first_at) == (0, 0, None, None)


# ---------- línea de tiempo ----------
def test_timeline_days_filled_with_zeros_in_local_time():
    subs = [S(1, "2026-11-10T02:30:00.000Z"), S(2, "2026-11-10T04:00:00.000Z"), S(3, "2026-11-12T15:00:00.000Z")]
    t = stats.timeline(subs, AR)
    assert t.bucket == "day" and t.total == 3
    assert [(p.start.day, p.count) for p in t.points] == [(9, 1), (10, 1), (11, 0), (12, 1)]


def test_timeline_24h_axis_has_hourly_buckets_even_without_data():
    now = datetime(2026, 11, 12, 15, 20, tzinfo=UTC)
    subs = [S(1, "2026-11-12T15:00:00.000Z"), S(2, "2026-11-11T20:30:00.000Z")]
    t = stats.timeline(subs, AR, start=now - timedelta(hours=24), end=now)
    assert t.bucket == "hour" and len(t.points) == 25
    nonzero = {(p.start.day, p.start.hour): p.count for p in t.points if p.count}
    assert nonzero == {(11, 17): 1, (12, 12): 1}
    assert stats.timeline([], AR, start=now - timedelta(hours=24), end=now).total == 0
    assert stats.timeline([], AR).points == ()


def test_timeline_switches_to_months_for_long_spans():
    subs = [S(1, "2024-01-15T12:00:00.000Z"), S(2, "2026-03-02T12:00:00.000Z")]
    t = stats.timeline(subs, UTC)
    assert t.bucket == "month" and len(t.points) == 27 and t.points[0].count == 1 and t.points[-1].count == 1
    assert stats.choose_bucket(datetime(2026, 1, 1), datetime(2026, 1, 3)) == "hour"
    assert stats.choose_bucket(datetime(2026, 1, 1), datetime(2026, 1, 3, 0, 1)) == "day"


# ---------- filtros de tiempo ----------
NOW = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)


def test_rolling_windows_and_all():
    f = timefilter.resolve_filter("24h", NOW, AR)
    assert (f.start_iso, f.end_iso) == ("2026-11-11T15:00:00.000Z", "2026-11-12T15:00:01.000Z")
    assert timefilter.resolve_filter("7d", NOW, AR).start_iso == "2026-11-05T15:00:00.000Z"
    assert timefilter.resolve_filter("30d", NOW, AR).start_iso == "2026-10-13T15:00:00.000Z"
    a = timefilter.resolve_filter("all", NOW, AR)
    assert a.start_iso is None and a.end_iso is None and a.label == "Todo el período"


def test_custom_range_is_whole_local_days_end_exclusive():
    f = timefilter.resolve_filter("custom", NOW, AR, start_date=date(2026, 11, 10), end_date=date(2026, 11, 12))
    assert (f.start_iso, f.end_iso) == ("2026-11-10T03:00:00.000Z", "2026-11-13T03:00:00.000Z")
    assert f.label == "Del 10/11/2026 al 12/11/2026"
    one = timefilter.resolve_filter("custom", NOW, AR, start_date=date(2026, 11, 10), end_date=date(2026, 11, 10))
    assert one.end_iso == "2026-11-11T03:00:00.000Z"


@pytest.mark.parametrize("kw", [dict(kind="custom"), dict(kind="custom", start_date=date(2026, 11, 12),
                                                          end_date=date(2026, 11, 10)), dict(kind="semana")])
def test_invalid_filters(kw):
    with pytest.raises(ValueError):
        timefilter.resolve_filter(kw.pop("kind"), NOW, AR, **kw)
    with pytest.raises(ValueError):
        timefilter.resolve_filter("24h", datetime(2026, 1, 1), AR)


# ---------- segundo camino de cálculo ----------
def test_crosscheck_detects_a_discrepancy_and_accepts_a_match():
    questions_raw = {"questions": [{"id": "q", "type": "MULTIPLE_CHOICE"}]}
    subs = [{"isCompleted": True, "responses": [{"questionId": "q", "answer": ["Sí"]}]},
            {"isCompleted": False, "responses": [{"questionId": "q", "answer": []}]},
            {"isCompleted": True, "responses": [{"questionId": "q", "answer": ["Quizás"]}]}]
    raw = crosscheck.raw_counts(questions_raw, subs)
    assert raw["q"] == {"type": "MULTIPLE_CHOICE", "asked": 3, "answered": 2, "labels": {"Sí": 1, "Quizás": 1}}
    answers = [A(1, choices=[("Sí", "declared")]), A(2, blank=True), A(3, choices=[("Quizás", "other")])]
    qs = (stats.question_stats(SINGLE, answers, 3),)
    assert crosscheck.compare(qs, raw, total=3, completed=2, raw_total=3, raw_completed=2) == []
    bad = (stats.question_stats(SINGLE, answers[:1], 3),)
    assert crosscheck.compare(bad, raw, total=3, completed=2, raw_total=3, raw_completed=2)

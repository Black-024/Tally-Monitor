"""goal_projection, trends y matching_keys: funciones puras."""
from datetime import date, datetime, timedelta, timezone

import pytest

from tally_monitor.analysis.answerfilter import filterable_questions, matching_keys, norm
from tally_monitor.analysis.goal import MAX_ETA_DAYS, goal_projection
from tally_monitor.analysis.models import AnswerFilter, AnswerPoint, QuestionInfo
from tally_monitor.analysis.trends import count_last7, trends

UTC = timezone.utc
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


# ---------------- goal_projection ----------------
def test_goal_basic_example():
    g = goal_projection(124, 200, 25, NOW)          # 25/7 ≈ 3,57 por día; faltan 76 → 22 días
    assert (g.done, g.pct, g.remaining) == (False, 62, 76)
    assert g.per_day == pytest.approx(25 / 7)
    assert g.eta_days == 22 and g.eta_date == date(2026, 12, 12)


def test_goal_exact_ceil_without_float_error():
    g = goal_projection(0, 7, 7, NOW)               # 1 por día, faltan 7 → 7 exactos
    assert g.eta_days == 7
    assert goal_projection(0, 10, 7, NOW).eta_days == 10
    assert goal_projection(0, 1, 7, NOW).eta_days == 1
    assert goal_projection(0, 1, 1, NOW).eta_days == 7                    # 1/7 por día: 7 días


def test_goal_reached_and_exceeded():
    for local in (200, 250):
        g = goal_projection(local, 200, 10, NOW)
        assert g.done and g.pct == 100 and g.remaining == 0 and g.eta_days is None and g.eta_date is None


def test_goal_pct_rounds_down_and_caps():
    assert goal_projection(199, 200, 0, NOW).pct == 99
    assert goal_projection(1, 1_000_000, 0, NOW).pct == 0
    assert goal_projection(0, 5, 0, NOW).pct == 0
    assert goal_projection(1, 3, 0, NOW).pct == 33


def test_goal_no_pace():
    g = goal_projection(10, 100, 0, NOW)
    assert not g.done and g.per_day == 0 and g.eta_days is None and g.eta_date is None and g.remaining == 90


def test_goal_eta_cap_3650_days():
    # restan 3650 con 7 en la semana → 3650 días exactos: se informa
    g = goal_projection(0, 3650, 7, NOW)
    assert g.eta_days == MAX_ETA_DAYS
    assert goal_projection(0, 3651, 7, NOW).eta_days is None            # 3651: pasa el tope
    assert goal_projection(0, 1_000_000, 1, NOW).eta_days is None


def test_goal_eta_date_uses_now_zone():
    tz = timezone(timedelta(hours=-3))
    late = datetime(2026, 11, 20, 23, 30, tzinfo=tz)                    # en UTC ya es el 21
    assert goal_projection(0, 7, 7, late).eta_date == date(2026, 11, 27)


def test_goal_invalid_inputs():
    with pytest.raises(ValueError):
        goal_projection(1, 0, 1, NOW)
    with pytest.raises(ValueError):
        goal_projection(1, -5, 1, NOW)
    with pytest.raises(ValueError):
        goal_projection(1, 10, 1, datetime(2026, 1, 1))                  # sin zona
    assert goal_projection(-3, 10, -2, NOW).remaining == 10             # negativos se tratan como 0


# ---------------- trends ----------------
def ev(days_ago=0, hours_ago=0, done=True):
    return (NOW - timedelta(days=days_ago, hours=hours_ago), done)


def test_trends_windows_and_delta():
    subs = [ev(0), ev(3), ev(6, 23)] + [ev(8), ev(9), ev(13), ev(14, 1)]       # 3 esta semana, 3 la anterior
    t = trends(subs, NOW, UTC)
    assert (t.last7, t.prev7, t.delta_pct) == (3, 3, 0)
    t = trends([ev(1), ev(2), ev(3), ev(4), ev(5), ev(8), ev(9), ev(10)], NOW, UTC)
    assert (t.last7, t.prev7, t.delta_pct) == (5, 3, 67)                       # +66,7 %
    t = trends([ev(1), ev(8), ev(9), ev(10)], NOW, UTC)
    assert (t.last7, t.prev7, t.delta_pct) == (1, 3, -67)
    t = trends([ev(1), ev(2), ev(8), ev(9), ev(10), ev(11)], NOW, UTC)
    assert t.delta_pct == -50


def test_trends_boundaries():
    t = trends([(NOW, True)], NOW, UTC)
    assert t.last7 == 1                                                        # justo «ahora» entra
    t = trends([(NOW - timedelta(days=7), True)], NOW, UTC)
    assert (t.last7, t.prev7) == (1, 0)                                        # hace 7×24 h exactas: última semana
    t = trends([(NOW - timedelta(days=7, seconds=1), True)], NOW, UTC)
    assert (t.last7, t.prev7) == (0, 1)
    t = trends([(NOW - timedelta(days=14), True)], NOW, UTC)
    assert (t.last7, t.prev7) == (0, 1)
    t = trends([(NOW - timedelta(days=14, seconds=1), True)], NOW, UTC)
    assert (t.last7, t.prev7) == (0, 0)
    t = trends([(NOW + timedelta(seconds=1), True)], NOW, UTC)
    assert (t.last7, t.prev7) == (0, 0)                                        # el futuro no cuenta


def test_trends_delta_none_when_prev_zero_and_rounding():
    assert trends([ev(1)], NOW, UTC).delta_pct is None
    assert trends([], NOW, UTC).delta_pct is None
    # 18 vs 15 = +20 %
    subs = [ev(1)] * 18 + [ev(10)] * 15
    assert trends(subs, NOW, UTC).delta_pct == 20
    # mitad exacta: 1 vs 8 = -87,5 → -88 (se aleja de cero)
    assert trends([ev(1)] + [ev(10)] * 8, NOW, UTC).delta_pct == -88
    # 9 vs 8 = +12,5 → 13
    assert trends([ev(1)] * 9 + [ev(10)] * 8, NOW, UTC).delta_pct == 13


def test_trends_completion_pct():
    assert trends([], NOW, UTC).completion_pct is None
    subs = [(NOW, True)] * 7 + [(NOW, False)]
    assert trends(subs, NOW, UTC).completion_pct == 88                          # 87,5 → 88
    assert trends([(NOW, False)], NOW, UTC).completion_pct == 0
    assert trends([(NOW, True)], NOW, UTC).completion_pct == 100


def test_trends_weekday_hour_local_tz():
    # 2026-11-20 es viernes (weekday 4)
    t = trends([(datetime(2026, 11, 20, 12, 0, tzinfo=UTC), True)], NOW, UTC)
    assert t.by_weekday[4] == 1 and t.by_hour[12] == 1 and t.peak_weekday == 4 and t.peak_hour == 12
    # 02:00 UTC del sábado 21 = 23:00 del viernes 20 en UTC-3
    ba = timezone(timedelta(hours=-3))
    s = [(datetime(2026, 11, 21, 2, 0, tzinfo=UTC), True)]
    assert trends(s, NOW, UTC).peak_weekday == 5
    t = trends(s, NOW, ba)
    assert t.peak_weekday == 4 and t.peak_hour == 23
    # lunes = 0
    assert trends([(datetime(2026, 11, 16, 5, 0, tzinfo=UTC), True)], NOW, UTC).peak_weekday == 0
    assert trends([(datetime(2026, 11, 22, 5, 0, tzinfo=UTC), True)], NOW, UTC).peak_weekday == 6


def test_trends_tz_across_dst_like_offsets():
    # +05:30: medianoche local cae a las 18:30 UTC del día anterior
    ist = timezone(timedelta(hours=5, minutes=30))
    t = trends([(datetime(2026, 11, 19, 18, 30, tzinfo=UTC), True)], NOW, ist)
    assert t.peak_weekday == 4 and t.peak_hour == 0                             # viernes 00:00 local


def test_trends_ties_pick_lowest_index_and_empty():
    subs = [(datetime(2026, 11, 17, 9, 0, tzinfo=UTC), True), (datetime(2026, 11, 19, 7, 0, tzinfo=UTC), True)]
    t = trends(subs, NOW, UTC)
    assert t.peak_weekday == 1 and t.peak_hour == 7                             # martes < jueves; 7 h < 9 h
    e = trends([], NOW, UTC)
    assert e.peak_weekday is None and e.peak_hour is None
    assert e.by_weekday == (0,) * 7 and e.by_hour == (0,) * 24 and (e.last7, e.prev7) == (0, 0)


def test_trends_period_vs_all_submissions():
    period = [ev(1), ev(2)]                      # el filtro de Resumen deja 2
    allsubs = period + [ev(3), ev(4), ev(10)]
    t = trends(period, NOW, UTC, all_submissions=allsubs)
    assert (t.last7, t.prev7) == (4, 1)          # ritmo: todos los guardados
    assert sum(t.by_weekday) == 2 and sum(t.by_hour) == 2                       # distribución: solo el período


def test_trends_accepts_iso_strings_and_naive_as_utc():
    t = trends([("2026-11-19T10:00:00.000Z", True), (datetime(2026, 11, 19, 11, 0), False)], NOW, UTC)
    assert t.last7 == 2 and t.completion_pct == 50
    with pytest.raises(ValueError):
        trends([], datetime(2026, 1, 1), UTC)


def test_count_last7():
    assert count_last7([NOW, NOW - timedelta(days=7), NOW - timedelta(days=8)], NOW) == 2


# ---------------- cruce: matching_keys ----------------
def ap(key, choices, q="q1", blank=False):
    return AnswerPoint(key, q, "single", blank, None, tuple(choices))


def test_matching_single_multi_and_origin():
    flt = AnswerFilter("q1", "Sí")
    answers = [ap(1, [("Sí", "declared")]), ap(2, [("No", "declared")]),
               ap(3, [("Rojo", "declared"), ("Sí", "declared")]),                # múltiple: basta con que esté
               ap(4, [("Sí", "other")]),                                         # texto escrito en «Otro»: no cuenta
               ap(5, [("Sí", "unmatched")]),
               ap(6, [("Sí", "declared")], blank=True),
               ap(7, [("Sí", "declared")], q="otra")]
    assert matching_keys(answers, flt) == {1, 3}


def test_matching_normalizes_spaces_and_is_exact():
    assert matching_keys([ap(1, [("Muy  bueno ", "declared")])], AnswerFilter("q1", " Muy bueno")) == {1}
    assert matching_keys([ap(1, [("Muy bueno", "declared")])], AnswerFilter("q1", "muy bueno")) == set()   # sin mayúsculas: exacto
    assert matching_keys([ap(1, [("Muy bueno!", "declared")])], AnswerFilter("q1", "Muy bueno")) == set()
    assert matching_keys([], AnswerFilter("q1", "x")) == set()
    assert norm("  a \t b\n") == "a b"


def test_filterable_questions():
    qs = [QuestionInfo("a", 1, "MULTIPLE_CHOICE", "A"), QuestionInfo("b", 2, "CHECKBOXES", "B"),
          QuestionInfo("c", 3, "TEXTAREA", "C"), QuestionInfo("d", 4, "MULTIPLE_CHOICE", "D", is_deleted=True),
          QuestionInfo("e", 5, "DROPDOWN", "E")]
    assert [q.question_id for q in filterable_questions(qs)] == ["a", "b"]

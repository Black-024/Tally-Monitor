import time
from datetime import date, timezone

import pytest

from support.fixtures import *  # noqa: F401,F403
from support.forms import FORM_ID, Q_MULTI, Q_SINGLE, Q_TEXT, add_form, submission
from support.shared import KEY_A
from tally_monitor.core.errors import SurveyNotFoundError
from tally_monitor.core.secret import SecretStr
from tally_monitor.sync.models import AnswerRow, ChoiceRow, SubmissionRow


@pytest.fixture
def acct(core):
    core.analysis._tz = timezone.utc            # resultados independientes de la zona del equipo
    return core.accounts.add_account("Cuenta", SecretStr(KEY_A))


def by_id(result):
    return {q.question_id: q for q in result.questions}


def test_analysis_matches_hand_computed_values_and_crosscheck(core, tally, acct):
    add_form(tally, [
        submission(800, single="Sí", multi=("Rojo", "Verde"), text="hola"),             # dentro de 24 h
        submission(810, single="Sí", multi=("Rojo",), text="chau!!"),
        submission(820, single="No", multi=("Azul",), text=""),
        submission(830, single="Algo propio", multi=("Violeta",), text="largo texto"),   # «otro» + huérfana
        submission(840, single=None, multi=None, text="x", completed=False),            # incompleto, vacíos
        submission(100, single="Sí", multi=("Verde",), text="viejo")])                   # fuera de 24 h
    core.sync.sync_form(acct.account_id, FORM_ID)
    r = core.analysis.analyze(acct.account_id, FORM_ID, "all")
    assert (r.overview.total, r.overview.completed, r.overview.partial) == (6, 5, 1)
    q = by_id(r)
    s = q[Q_SINGLE]
    assert (s.asked, s.answered, s.blank) == (6, 5, 1)
    assert {o.text: o.count for o in s.options} == {"Sí": 3, "No": 1, "Otro": 0}
    assert s.other_count == 1 and s.other_values == (("Algo propio", 1),)
    m = q[Q_MULTI]
    assert (m.answered, m.blank) == (5, 1)
    assert {o.text: o.count for o in m.options} == {"Rojo": 2, "Verde": 2, "Azul": 1}
    assert m.orphan_count == 1 and m.orphan_values == (("Violeta", 1),)
    t = q[Q_TEXT]
    assert (t.answered, t.blank, t.max_len) == (5, 1, 11)
    assert core.analysis.crosscheck(acct.account_id, FORM_ID) == []

    # sin incompletos
    r2 = core.analysis.analyze(acct.account_id, FORM_ID, "all", include_incomplete=False)
    assert r2.overview.total == 5 and by_id(r2)[Q_SINGLE].answered == 5 and by_id(r2)[Q_SINGLE].blank == 0
    assert core.analysis.crosscheck(acct.account_id, FORM_ID, include_incomplete=False) == []

    # 24 h con reloj fijo 2026-11-11 12:00 UTC: entran los envíos desde el 10/11 12:00 (minuto >= 720)
    r3 = core.analysis.analyze(acct.account_id, FORM_ID, "24h")
    assert r3.overview.total == 5 and r3.filter.kind == "24h"
    assert r3.timeline.bucket == "hour" and len(r3.timeline.points) == 25 and r3.timeline.total == 5

    # rango personalizado: solo el día 10 completo (los 6 envíos), y un día sin envíos
    r4 = core.analysis.analyze(acct.account_id, FORM_ID, "custom", start_date=date(2026, 11, 10),
                               end_date=date(2026, 11, 10))
    assert r4.overview.total == 6
    r5 = core.analysis.analyze(acct.account_id, FORM_ID, "custom", start_date=date(2026, 11, 1),
                               end_date=date(2026, 11, 9))
    assert r5.overview.total == 0 and all(o.pct is None for o in by_id(r5)[Q_SINGLE].options)
    assert r5.timeline.total == 0


def test_removed_from_tally_submissions_are_excluded(core, tally, acct):
    add_form(tally, [submission(n) for n in (10, 20, 30)])
    core.sync.sync_form(acct.account_id, FORM_ID)
    f = tally.forms[FORM_ID]
    f["submissions"] = [s for s in f["submissions"] if s["id"] != "sub0020"]
    core.sync.sync_form(acct.account_id, FORM_ID)
    r = core.analysis.analyze(acct.account_id, FORM_ID)
    assert r.overview.total == 2 and core.analysis.crosscheck(acct.account_id, FORM_ID) == []


def test_unsynced_or_unknown_survey_and_warnings(core, tally, acct):
    with pytest.raises(SurveyNotFoundError):
        core.analysis.analyze(acct.account_id, "nada")
    add_form(tally, [submission(10)])
    core.sync.sync_forms(acct.account_id)                       # encuesta conocida pero sin respuestas guardadas
    r = core.analysis.analyze(acct.account_id, FORM_ID)
    assert r.overview.total == 0 and all(q.answered == 0 for q in r.questions) and r.warnings == ()


def test_question_added_later_is_reported_as_not_asked(core, tally, acct):
    add_form(tally, [submission(10), submission(20)])
    # el segundo envío no trae la pregunta de texto (se agregó después)
    for s in tally.forms[FORM_ID]["submissions"]:
        if s["id"] == "sub0010":
            s["responses"] = [x for x in s["responses"] if x["questionId"] != Q_TEXT]
    core.sync.sync_form(acct.account_id, FORM_ID)
    r = core.analysis.analyze(acct.account_id, FORM_ID)
    t = by_id(r)[Q_TEXT]
    assert (t.asked, t.not_asked) == (1, 1) and "preguntas_agregadas_despues" in r.warnings
    assert core.analysis.crosscheck(acct.account_id, FORM_ID) == []


def test_ten_thousand_submissions_are_fast_and_consistent(core, tally, acct):
    add_form(tally, [submission(10), submission(20)])
    core.sync.sync_form(acct.account_id, FORM_ID)
    repo = core.sync._subs
    rows, raws = [], []
    for i in range(10_000):
        ts = f"2026-10-{1 + i % 28:02d}T{(i // 28) % 24:02d}:{i % 60:02d}:00.000Z"
        rows.append((SubmissionRow(
            f"bulk{i:05d}", FORM_ID, ts, True, ts, ts,
            (AnswerRow(Q_SINGLE, "single", ["Sí", "No"][i % 2], False, "[]", (ChoiceRow(["Sí", "No"][i % 2], "declared"),)),
             AnswerRow(Q_TEXT, "text", "t" * (i % 50), i % 50 == 0, "\"\""))), {"id": f"bulk{i:05d}", "responses": []}))
    repo.upsert_page(acct.account_id, rows)
    repo.assign_numbers(acct.account_id, FORM_ID)
    t0 = time.perf_counter()
    r = core.analysis.analyze(acct.account_id, FORM_ID)
    elapsed = time.perf_counter() - t0
    assert r.overview.total == 10_002
    s = by_id(r)[Q_SINGLE]
    assert s.options[0].count + s.options[1].count == s.answered == 10_002
    assert elapsed < 3.0, f"el análisis tardó {elapsed:.2f}s"


def test_analysis_never_touches_the_network(core, tally, acct):
    add_form(tally, [submission(10)])
    core.sync.sync_form(acct.account_id, FORM_ID)
    tally.requests.clear()
    core.analysis.analyze(acct.account_id, FORM_ID, "7d")
    core.analysis.crosscheck(acct.account_id, FORM_ID)
    assert tally.requests == []


# ---- 1.1: cruce de preguntas, ritmo y metas ----
def test_answer_filter_subset_and_counts(core, tally, acct):
    from tally_monitor.analysis.models import AnswerFilter
    from tally_monitor.core.errors import InvalidFilterError
    add_form(tally, [submission(800, single="Sí", multi=("Rojo", "Verde")), submission(810, single="Sí", multi=("Azul",)),
                     submission(820, single="No", multi=("Rojo",)), submission(830, single="No", multi=("Verde",)),
                     submission(840, single=None, multi=("Rojo",), completed=False)])
    core.sync.sync_form(acct.account_id, FORM_ID)
    base = core.analysis.analyze(acct.account_id, FORM_ID, "all")
    assert base.matched is None and base.answer_filter is None
    r = core.analysis.analyze(acct.account_id, FORM_ID, "all", answer_filter=AnswerFilter(Q_SINGLE, "Sí"))
    assert (r.matched, r.total_in_period, r.overview.total) == (2, 5, 2)
    q = by_id(r)
    assert {o.text: o.count for o in q[Q_SINGLE].options} == {"Sí": 2, "No": 0, "Otro": 0}
    assert q[Q_SINGLE].options[0].pct == 100.0                                   # la pregunta filtrada, 100 % en su opción
    assert {o.text: o.count for o in q[Q_MULTI].options} == {"Rojo": 1, "Verde": 1, "Azul": 1}
    assert sum(p.count for p in r.timeline.points) == 2
    assert r.trends.last7 + r.trends.prev7 <= 2
    # cruce desde una pregunta múltiple
    r = core.analysis.analyze(acct.account_id, FORM_ID, "all", answer_filter=AnswerFilter(Q_MULTI, "Rojo"))
    assert (r.matched, r.total_in_period) == (3, 5)
    # nadie
    r = core.analysis.analyze(acct.account_id, FORM_ID, "all", answer_filter=AnswerFilter(Q_SINGLE, "Otro"))
    assert (r.matched, r.total_in_period, r.overview.total) == (0, 5, 0)
    # combinado con «sin incompletos»
    r = core.analysis.analyze(acct.account_id, FORM_ID, "all", include_incomplete=False,
                              answer_filter=AnswerFilter(Q_MULTI, "Rojo"))
    assert (r.matched, r.total_in_period) == (2, 4)
    # pregunta no filtrable / inexistente
    for bad in (AnswerFilter(Q_TEXT, "x"), AnswerFilter("nope", "x")):
        with pytest.raises(InvalidFilterError):
            core.analysis.analyze(acct.account_id, FORM_ID, "all", answer_filter=bad)


def test_trends_in_analysis_ignore_time_filter_for_last7(core, tally, acct):
    # clock del núcleo = 2026-11-11 12:00 UTC; los envíos son del 2026-11-10 (hace ~1 día)
    add_form(tally, [submission(800), submission(810), submission(820)])
    core.sync.sync_form(acct.account_id, FORM_ID)
    r = core.analysis.analyze(acct.account_id, FORM_ID, "24h")
    assert r.trends.last7 == 3 and r.trends.prev7 == 0 and r.trends.delta_pct is None
    assert sum(r.trends.by_hour) == r.overview.total
    assert r.trends.completion_pct == 100


def test_survey_goals(core, tally, acct):
    add_form(tally, [submission(800), submission(810), submission(820), submission(830)])
    core.sync.sync_forms(acct.account_id)
    core.sync.sync_form(acct.account_id, FORM_ID)
    assert core.surveys.goals(acct.account_id) == {}
    core.surveys.set_survey_meta(acct.account_id, FORM_ID, 10, "", [])
    g = core.surveys.goals(acct.account_id)[FORM_ID]
    assert (g.done, g.pct, g.remaining) == (False, 40, 6)
    assert g.per_day == pytest.approx(4 / 7) and g.eta_days == 11               # ceil(6 / (4/7)) = ceil(10,5)
    core.surveys.set_survey_meta(acct.account_id, FORM_ID, 4, "", [])
    assert core.surveys.goals(acct.account_id)[FORM_ID].done

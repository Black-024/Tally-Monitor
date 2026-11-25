import json

import pytest

from support.forms import FORM_ID, Q_MULTI, Q_SINGLE, Q_TEXT, add_form, submission
from support.fake_tally import FakeTally
from tally_monitor.sync import normalizer, sanitizer
from tally_monitor.sync.numbering import format_user_label, parse_user_label


@pytest.mark.parametrize("n,label", [
    (1, "Usuario 001"), (12, "Usuario 012"), (999, "Usuario 999"), (1000, "Usuario 1000"),
    (9999, "Usuario 9999"), (10000, "Usuario A001"), (19998, "Usuario A9999"), (19999, "Usuario B001"),
    (10000 + 9999 * 26, "Usuario AA001")])
def test_labels_roundtrip(n, label):
    assert format_user_label(n) == label
    assert parse_user_label(label) == n


def test_labels_are_unique_and_ordered_over_a_wide_range():
    labels = [format_user_label(n) for n in range(1, 60000)]
    assert len(set(labels)) == len(labels)


@pytest.mark.parametrize("bad", [0, -1, "3", None, 1.5])
def test_label_rejects_invalid(bad):
    with pytest.raises(ValueError):
        format_user_label(bad)


def test_parse_accepts_plain_number_and_rejects_text():
    assert parse_user_label("12") == 12 and parse_user_label("a001") == 10000
    assert parse_user_label("hola") is None and parse_user_label("A000") is None


def _form():
    t = FakeTally()
    return add_form(t, [submission(1)])


def test_sanitizer_drops_identifiers_and_reports_only_unknown_field_names():
    raw = submission(1)
    raw["campoNuevo"] = "VALOR-SECRETO"
    raw["responses"][0]["extra"] = "OTRO-SECRETO"
    s = sanitizer.sanitize_submission(raw)
    text = json.dumps(s.data)
    for forbidden in ("RESP-SECRET", "SESSION-SECRET", "SECRET", "previewUrl", "pdfUrl", "respondentId",
                      "sessionUuid", "locale"):
        assert forbidden not in text
    assert set(s.unknown_fields) == {"submission.campoNuevo", "response.extra"}
    assert "VALOR-SECRETO" not in json.dumps(s.unknown_fields)


def test_sanitizer_form_drops_settings_and_html_but_keeps_options():
    f = _form()
    s = sanitizer.sanitize_form(f["detail"])
    assert "settings" not in s.data and "safeHTMLSchema" not in json.dumps(s.data)
    assert any(b.get("payload", {}).get("text") == "Sí" for b in s.data["blocks"])
    assert s.unknown_fields == ()


def test_normalizer_links_options_via_group_uuid_and_other():
    f = _form()
    d = sanitizer.sanitize_form(f["detail"]).data
    q = sanitizer.sanitize_questions(f["questions"]).data
    rows = {r.question_id: r for r in normalizer.question_rows(d, q)}
    assert rows[Q_SINGLE].options == ("Sí", "No", "Otro") and rows[Q_SINGLE].has_other_option
    assert rows[Q_MULTI].options == ("Rojo", "Verde", "Azul") and not rows[Q_MULTI].has_other_option
    assert [r.position for r in sorted(rows.values(), key=lambda r: r.position)] == [0, 1, 2]


def _qmap():
    f = _form()
    d = sanitizer.sanitize_form(f["detail"]).data
    q = sanitizer.sanitize_questions(f["questions"]).data
    return {r.question_id: r for r in normalizer.question_rows(d, q)}


def test_answers_declared_other_unmatched_and_blank():
    qm = _qmap()
    sub = sanitizer.sanitize_submission(submission(1, single="Algo escrito", multi=("Rojo", "Violeta"), text="  "))
    row = normalizer.submission_row(sub.data, qm)
    a = {x.question_id: x for x in row.answers}
    assert [(c.option_text, c.origin) for c in a[Q_SINGLE].choices] == [("Algo escrito", "other")]
    assert {(c.option_text, c.origin) for c in a[Q_MULTI].choices} == {("Rojo", "declared"), ("Violeta", "unmatched")}
    assert a[Q_TEXT].is_blank and a[Q_TEXT].kind == "text"


def test_blank_choice_and_unknown_question_type_kept_as_raw():
    qm = _qmap()
    row = normalizer.submission_row(
        sanitizer.sanitize_submission(submission(1, single=None, multi=None)).data, qm)
    a = {x.question_id: x for x in row.answers}
    assert a[Q_SINGLE].is_blank and a[Q_SINGLE].choices == ()
    sub = {"id": "x", "formId": FORM_ID, "submittedAt": "2026-11-10T00:00:00.000Z", "isCompleted": True,
           "responses": [{"questionId": "desconocida", "answer": {"a": 1}}]}
    r = normalizer.submission_row(sub, qm).answers[0]
    assert r.kind == "raw" and not r.is_blank


def test_is_other_option_is_kept_and_is_folded_dropped():
    from support.forms import _blocks
    blocks = _blocks()
    for b in blocks:
        if b["groupUuid"] == "g-multi":
            b["payload"]["isFolded"] = False
    blocks[-2]["payload"]["isOtherOption"] = True        # opción «Otro» en la pregunta múltiple
    s = sanitizer.sanitize_form({"id": "x", "blocks": blocks})
    assert s.unknown_fields == ()
    assert any(b.get("payload", {}).get("isOtherOption") for b in s.data["blocks"])
    assert "isFolded" not in json.dumps(s.data)
    f = _form()
    q = sanitizer.sanitize_questions(f["questions"]).data
    rows = {r.question_id: r for r in normalizer.question_rows(s.data, q)}
    assert rows[Q_MULTI].has_other_option

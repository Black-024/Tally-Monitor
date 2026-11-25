import json
import sqlite3

import pytest

from support.fixtures import *  # noqa: F401,F403
from support.forms import FORM_ID, Q_SINGLE, Q_TEXT, add_form, push, submission
from support.shared import KEY_A, KEY_B
from tally_monitor.api.errors import ApiAuthError, ApiNetworkError
from tally_monitor.core.errors import SyncCancelled
from tally_monitor.core.secret import SecretStr


@pytest.fixture
def acct(core):
    return core.accounts.add_account("Cuenta", SecretStr(KEY_A))


def labels(core, a):
    return [r.label for r in core.surveys.responses(a.account_id, FORM_ID, limit=5000)]


def test_initial_sync_numbers_by_submission_date_ascending(core, tally, acct):
    add_form(tally, [submission(n) for n in (30, 10, 20)])
    r = core.sync.sync_form(acct.account_id, FORM_ID)
    assert r.mode == "initial" and r.new == 3 and r.local_total == 3 and not r.warnings
    views = core.surveys.responses(acct.account_id, FORM_ID)
    assert [v.label for v in views] == ["Usuario 001", "Usuario 002", "Usuario 003"]
    assert [v.submitted_at[11:16] for v in views] == ["00:10", "00:20", "00:30"]


def test_incremental_sync_only_requests_new_and_keeps_numbers(core, tally, acct):
    add_form(tally, [submission(n) for n in (10, 20)])
    core.sync.sync_form(acct.account_id, FORM_ID)
    before = {v.label: v.submitted_at for v in core.surveys.responses(acct.account_id, FORM_ID)}
    push(tally, submission(30))
    tally.requests.clear()
    r = core.sync.sync_form(acct.account_id, FORM_ID)
    assert r.mode == "incremental" and r.new == 1 and r.updated == 1   # el pivote (inclusivo) se vuelve a leer
    after = {v.label: v.submitted_at for v in core.surveys.responses(acct.account_id, FORM_ID)}
    assert {k: after[k] for k in before} == before and "Usuario 003" in after
    assert any("startDate=" in q["path"] for q in tally.requests)


def test_no_changes_is_cheap_and_stable(core, tally, acct):
    add_form(tally, [submission(n) for n in (10, 20)])
    core.sync.sync_form(acct.account_id, FORM_ID)
    tally.requests.clear()
    r = core.sync.sync_form(acct.account_id, FORM_ID)
    assert r.mode == "nochange" and r.new == 0
    assert not any("/submissions" in q["path"] and "limit=500" in q["path"] for q in tally.requests)


def test_multi_page_download_over_500_submissions(core, tally, acct):
    add_form(tally, [submission(n) for n in range(1, 1200 // 2)])   # 599 envíos → 2 páginas de 500
    r = core.sync.sync_form(acct.account_id, FORM_ID)
    assert r.local_total == 599 and r.remote_total == 599 and not r.warnings
    assert len(set(labels(core, acct))) == 599


def test_remote_deletion_marks_missing_without_deleting_and_creates_backup(core, tally, acct):
    add_form(tally, [submission(n) for n in (10, 20, 30)])
    core.sync.sync_form(acct.account_id, FORM_ID)
    f = tally.forms[FORM_ID]
    f["submissions"] = [s for s in f["submissions"] if s["id"] != "sub0020"]
    r = core.sync.sync_form(acct.account_id, FORM_ID)
    assert r.mode == "full" and r.missing == 1 and r.local_total == 2
    assert [b for b in core.backups.list_backups() if b.reason == "pre_reconciliacion"]
    # no se reutiliza el número 002 al llegar uno nuevo
    push(tally, submission(40))
    core.sync.sync_form(acct.account_id, FORM_ID)
    assert labels(core, acct) == ["Usuario 001", "Usuario 003", "Usuario 004"]


def test_forced_full_sync_and_restored_submission_clears_missing(core, tally, acct):
    add_form(tally, [submission(n) for n in (10, 20)])
    core.sync.sync_form(acct.account_id, FORM_ID)
    r = core.sync.sync_form(acct.account_id, FORM_ID, full=True)
    assert r.mode == "full" and r.missing == 0 and r.local_total == 2


def test_edit_of_an_answer_is_picked_up_by_full_sync_only(core, tally, acct):
    add_form(tally, [submission(n) for n in (10, 20)])
    core.sync.sync_form(acct.account_id, FORM_ID)
    for s in tally.forms[FORM_ID]["submissions"]:
        if s["id"] == "sub0010":
            s["responses"][2]["answer"] = "editado"
    core.sync.sync_form(acct.account_id, FORM_ID)
    core.sync.sync_form(acct.account_id, FORM_ID, full=True)
    v = core.surveys.response_by_number(acct.account_id, FORM_ID, 1)
    assert [a.text for a in v.answers if a.kind == "text"] == ["editado"]


def test_answers_choices_and_titles_are_readable(core, tally, acct):
    add_form(tally, [submission(10, single="Otro texto libre", multi=("Rojo", "Azul"), text="hola")])
    core.sync.sync_form(acct.account_id, FORM_ID)
    v = core.surveys.response_by_number(acct.account_id, FORM_ID, 1)
    by = {a.question_title: a for a in v.answers}
    assert by["¿Te gustó?"].choices[0].origin == "other"
    assert {c.text for c in by["Colores"].choices} == {"Rojo", "Azul"}
    assert by["Comentarios"].text == "hola"
    assert core.surveys.find_by_label(acct.account_id, FORM_ID, "Usuario 001").number == 1


def test_database_holds_no_sensitive_identifiers(core, tally, acct, paths):
    add_form(tally, [submission(10)])
    core.sync.sync_form(acct.account_id, FORM_ID)
    core.sync.sync_forms(acct.account_id)
    conn = sqlite3.connect(paths.library_db)
    dump = "\n".join(conn.iterdump())
    conn.close()
    for forbidden in ("RESP-SECRET", "SESSION-SECRET", "tally.so/preview", "tally.so/pdf", KEY_A, "user-A",
                      "createdByUserId", "respondentId", "sessionUuid"):
        assert forbidden not in dump


def test_sync_forms_lists_surveys_and_hints_new_submissions(core, tally, acct):
    add_form(tally, [submission(n) for n in (10, 20)])
    assert core.sync.sync_forms(acct.account_id).count == 1
    s = core.surveys.list_surveys(acct.account_id)[0]
    assert s.never_synced and s.has_new_hint and s.local_submissions == 0 and s.reported_submissions == 2
    core.sync.sync_form(acct.account_id, FORM_ID)
    s = core.surveys.list_surveys(acct.account_id)[0]
    assert not s.has_new_hint and s.local_submissions == 2 and not s.never_synced
    push(tally, submission(30))
    core.sync.sync_forms(acct.account_id)
    assert core.surveys.list_surveys(acct.account_id)[0].has_new_hint


def test_cached_data_still_readable_without_network(core, make_core, tally, acct):
    add_form(tally, [submission(10)])
    core.sync.sync_form(acct.account_id, FORM_ID)
    tally.stop()
    with pytest.raises(ApiNetworkError):
        core.sync.sync_form(acct.account_id, FORM_ID)
    assert labels(core, acct) == ["Usuario 001"]


def test_interrupted_initial_sync_resumes_without_duplicates_or_numbers(core, tally, acct):
    add_form(tally, [submission(n) for n in range(1, 601)])
    calls = {"n": 0}

    def cancel():
        calls["n"] += 1
        return calls["n"] > 3          # corta al pedir la segunda página

    with pytest.raises(SyncCancelled):
        core.sync.sync_form(acct.account_id, FORM_ID, cancel=cancel)
    assert core.surveys.responses(acct.account_id, FORM_ID) == []        # sin números hasta completar
    r = core.sync.sync_form(acct.account_id, FORM_ID)
    assert r.local_total == 600 and not r.warnings
    assert labels(core, acct)[0] == "Usuario 001" and len(set(labels(core, acct))) == 600


def test_auth_error_propagates_and_other_account_has_its_own_data(core, tally, acct):
    add_form(tally, [submission(10)])
    other = core.accounts.add_account("Otra", SecretStr(KEY_B))
    core.sync.sync_form(acct.account_id, FORM_ID)
    assert core.surveys.responses(other.account_id, FORM_ID) == []
    tally.users.pop(KEY_A)
    with pytest.raises(ApiAuthError):
        core.sync.sync_form(acct.account_id, FORM_ID)


def test_deleting_account_removes_its_surveys_and_submissions(core, tally, acct, paths):
    add_form(tally, [submission(10)])
    core.sync.sync_forms(acct.account_id)
    core.sync.sync_form(acct.account_id, FORM_ID)
    core.favorites.set_favorite(acct.account_id, FORM_ID, True)
    core.accounts.delete_account(acct.account_id)
    conn = sqlite3.connect(paths.library_db)
    for t in ("raw_form", "raw_submission", "data_form", "data_submission", "data_answer", "state_user_number",
              "state_favorite", "state_sync"):
        assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0, t
    conn.close()


def test_favorites_and_recents(core, tally, acct):
    add_form(tally, [submission(10)])
    core.sync.sync_forms(acct.account_id)
    core.favorites.set_favorite(acct.account_id, FORM_ID, True)
    assert core.surveys.list_surveys(acct.account_id)[0].is_favorite
    for i in range(12):
        core.favorites.touch_recent(acct.account_id, f"f{i}")
    r = core.favorites.recents(acct.account_id)
    assert len(r) == 10 and r[0] == "f11"
    core.favorites.set_favorite(acct.account_id, FORM_ID, False)
    assert not core.surveys.list_surveys(acct.account_id)[0].is_favorite


def test_sync_mode_setting_defaults_to_manual(core):
    assert core.settings.get("sync_mode") == "manual"
    core.settings.set("sync_mode", "auto")
    assert core.settings.get("sync_mode") == "auto"
    with pytest.raises(ValueError):
        core.settings.set("sync_mode", "otro")


def test_survey_not_found(core, acct):
    from tally_monitor.core.errors import SurveyNotFoundError
    with pytest.raises(SurveyNotFoundError):
        core.surveys.get_survey(acct.account_id, "nada")


def test_invalid_form_id_is_rejected_before_any_request(core, tally, acct):
    tally.requests.clear()
    with pytest.raises(ValueError):
        core.sync.sync_form(acct.account_id, "../users/me?x=1")
    assert tally.requests == []

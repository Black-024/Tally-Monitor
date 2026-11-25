"""Meta, nota, etiquetas y archivada: validaciones, atomicidad, copias de seguridad y restauración de copias viejas."""
import pytest

from support.fixtures import *  # noqa: F401,F403
from support.forms import FORM_ID, add_form, submission
from support.shared import KEY_A
from tally_monitor.core.errors import InvalidSurveyMetaError, SurveyNotFoundError
from tally_monitor.core.secret import SecretStr
from tally_monitor.services import survey_service as ss


@pytest.fixture
def acct(core, tally):
    a = core.accounts.add_account("Cuenta", SecretStr(KEY_A))
    add_form(tally, [submission(1), submission(2)])
    core.sync.sync_forms(a.account_id)
    return a.account_id


# ---- validaciones puras ----
@pytest.mark.parametrize("goal", [1, 200, 1_000_000, None])
def test_goal_ok(goal):
    assert ss.validate_goal(goal) == goal


@pytest.mark.parametrize("goal", [0, -1, 1_000_001, 2.5, "10", True, False])
def test_goal_invalid(goal):
    with pytest.raises(InvalidSurveyMetaError):
        ss.validate_goal(goal)


def test_note_strip_and_limit():
    assert ss.normalize_note("  hola \n") == "hola"
    assert ss.normalize_note(None) == "" and ss.normalize_note("   ") == ""
    assert len(ss.normalize_note("x" * 500)) == 500
    assert len(ss.normalize_note(" " + "x" * 500 + " ")) == 500          # el límite se mide tras el strip
    with pytest.raises(InvalidSurveyMetaError):
        ss.normalize_note("x" * 501)
    with pytest.raises(InvalidSurveyMetaError):
        ss.normalize_note(5)


def test_tags_rules():
    assert ss.normalize_tags(["  Clientes   VIP ", "clientes vip", "Otra", "OTRA"]) == ["Clientes VIP", "Otra"]
    assert ss.normalize_tags(None) == [] and ss.normalize_tags([]) == []
    assert ss.normalize_tags(["a" * 24]) == ["a" * 24]
    for bad in ("", "   ", "a" * 25):
        with pytest.raises(InvalidSurveyMetaError):
            ss.normalize_tags([bad])
    assert len(ss.normalize_tags([f"t{i}" for i in range(8)])) == 8
    with pytest.raises(InvalidSurveyMetaError):
        ss.normalize_tags([f"t{i}" for i in range(9)])
    # los duplicados no cuentan para el máximo
    assert len(ss.normalize_tags([f"t{i}" for i in range(8)] + ["T0", "t1"])) == 8
    with pytest.raises(InvalidSurveyMetaError):
        ss.normalize_tags([None])


def test_tags_internal_whitespace_collapsed_tabs_newlines():
    assert ss.normalize_tags(["a\t\n b"]) == ["a b"]


# ---- servicio ----
def test_summary_defaults(core, acct):
    s = core.surveys.get_survey(acct, FORM_ID)
    assert (s.goal, s.note, s.tags, s.archived) == (None, "", (), False)


def test_set_meta_roundtrip_and_list(core, acct):
    s = core.surveys.set_survey_meta(acct, FORM_ID, 200, "  nota  ", ["B", "a"])
    assert (s.goal, s.note, s.tags, s.archived) == (200, "nota", ("B", "a"), False)
    assert core.surveys.list_surveys(acct)[0].tags == ("B", "a")
    s = core.surveys.set_survey_meta(acct, FORM_ID, None, "", [])
    assert (s.goal, s.note, s.tags) == (None, "", ())


def test_set_meta_is_atomic(core, acct):
    core.surveys.set_survey_meta(acct, FORM_ID, 10, "uno", ["x"])
    with pytest.raises(InvalidSurveyMetaError):
        core.surveys.set_survey_meta(acct, FORM_ID, 99, "dos", ["ok", "a" * 30])     # etiqueta mala
    with pytest.raises(InvalidSurveyMetaError):
        core.surveys.set_survey_meta(acct, FORM_ID, 0, "dos", ["ok"])                 # meta mala
    s = core.surveys.get_survey(acct, FORM_ID)
    assert (s.goal, s.note, s.tags) == (10, "uno", ("x",))                           # nada cambió


def test_archive_roundtrip_and_independent_of_edit(core, acct):
    core.surveys.set_archived(acct, FORM_ID, True)
    assert core.surveys.get_survey(acct, FORM_ID).archived
    core.surveys.set_survey_meta(acct, FORM_ID, 5, "n", [])
    assert core.surveys.get_survey(acct, FORM_ID).archived                            # editar no desarchiva
    core.surveys.set_archived(acct, FORM_ID, False)
    assert not core.surveys.get_survey(acct, FORM_ID).archived
    assert core.surveys.get_survey(acct, FORM_ID).goal == 5


def test_archive_without_meta_row_creates_it(core, acct):
    core.surveys.set_archived(acct, FORM_ID, True)
    s = core.surveys.get_survey(acct, FORM_ID)
    assert s.archived and s.goal is None and s.note == ""


def test_unknown_survey(core, acct):
    with pytest.raises(SurveyNotFoundError):
        core.surveys.set_survey_meta(acct, "nope", 1, "", [])
    with pytest.raises(SurveyNotFoundError):
        core.surveys.set_archived(acct, "nope", True)


def test_meta_survives_resync_and_dies_with_account(core, tally, acct):
    core.surveys.set_survey_meta(acct, FORM_ID, 7, "n", ["t"])
    core.sync.sync_forms(acct)
    core.sync.sync_form(acct, FORM_ID)
    assert core.surveys.get_survey(acct, FORM_ID).tags == ("t",)
    core.accounts.delete_account(acct)
    with core.backups._m._db.connection() as c:
        assert c.execute("SELECT COUNT(*) FROM survey_meta").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM survey_tags").fetchone()[0] == 0


# ---- copias de seguridad ----
def test_backup_includes_meta_and_restore_brings_it_back(core, acct):
    core.surveys.set_survey_meta(acct, FORM_ID, 50, "antes", ["a"])
    info = core.backups.create_manual()
    core.surveys.set_survey_meta(acct, FORM_ID, 60, "despues", ["b"])
    core.backups.restore(info.filename)
    s = core.surveys.get_survey(acct, FORM_ID)
    assert (s.goal, s.note, s.tags) == (50, "antes", ("a",))


def test_restoring_an_old_backup_without_the_tables_migrates(core, acct, tmp_path):
    """Una copia v2 (sin survey_meta) se restaura y la migración 3 se aplica después."""
    import sqlite3
    old = core.backups.create_manual()
    db_path = old.path
    con = sqlite3.connect(db_path)
    con.executescript("DROP TABLE survey_tags; DROP TABLE survey_meta; PRAGMA user_version = 2;")
    con.execute("DELETE FROM app_migration_log WHERE version = 3")
    con.commit()
    con.close()
    core.surveys.set_survey_meta(acct, FORM_ID, 5, "actual", [])
    core.backups.restore(old.filename)
    s = core.surveys.get_survey(acct, FORM_ID)
    assert (s.goal, s.note, s.tags, s.archived) == (None, "", (), False)
    core.surveys.set_survey_meta(acct, FORM_ID, 9, "ok", ["t"])                       # las tablas existen y andan
    assert core.surveys.get_survey(acct, FORM_ID).goal == 9
    with core.backups._m._db.connection() as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 3

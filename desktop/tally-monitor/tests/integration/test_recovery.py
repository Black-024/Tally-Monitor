"""Recuperación ante cortes y diagnóstico seguro."""
import pytest

from support.fixtures import *  # noqa: F401,F403
from support.forms import FORM_ID, add_form, submission
from support.shared import KEY_A
from tally_monitor.api.errors import ApiNetworkError
from tally_monitor.core.secret import SecretStr


@pytest.fixture
def acct(core):
    return core.accounts.add_account("Cuenta", SecretStr(KEY_A))


def test_cut_during_second_page_then_resume_without_duplicates(make_core, tally, acct, monkeypatch):
    add_form(tally, [submission(n) for n in range(1, 600)])           # 599 → 2 páginas
    c = make_core()
    real = c.sync._client.list_submissions
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:
            raise ApiNetworkError("corte simulado")
        return real(*a, **k)

    monkeypatch.setattr(c.sync._client, "list_submissions", flaky)
    with pytest.raises(Exception):
        c.sync.sync_form(acct.account_id, FORM_ID)
    monkeypatch.undo()
    # «reinicio» de la app y nuevo intento: termina completo, sin duplicados ni números repetidos
    c2 = make_core()
    c2.startup.run()
    r = c2.sync.sync_form(acct.account_id, FORM_ID)
    labels = [v.label for v in c2.surveys.responses(acct.account_id, FORM_ID, limit=5000)]
    assert len(labels) == 599 == len(set(labels)) and r.local_total == 599
    assert sorted(labels)[0] == "Usuario 001" and sorted(labels)[-1] == "Usuario 599"


def test_data_survives_restart_and_credentials_stay_separate(make_core, tally, acct, paths):
    add_form(tally, [submission(n) for n in (10, 20)])
    make_core().sync.sync_form(acct.account_id, FORM_ID)
    c2 = make_core()
    c2.startup.run()
    assert len(c2.surveys.responses(acct.account_id, FORM_ID)) == 2
    for p in paths.home.rglob("*"):
        if p.is_file() and p.name != "credentials.dat":
            assert KEY_A.encode() not in p.read_bytes(), p


def test_diagnostic_report_has_no_key_names_or_texts(core, tally, acct, paths):
    add_form(tally, [submission(10, text="texto-privado-xyz")])
    core.sync.sync_form(acct.account_id, FORM_ID)
    log = paths.logs_dir
    log.mkdir(parents=True, exist_ok=True)
    (log / "tally_monitor.log").write_text(f"linea con {KEY_A} y mas\n", encoding="utf-8")
    text = core.diagnostics.report("9.9.9")
    assert "9.9.9" in text and KEY_A not in text and "texto-privado-xyz" not in text
    assert "Cuenta" not in text.replace("cuentas", "")


def test_diagnostic_report_works_with_corrupt_database(make_core, paths):
    c = make_core()
    c.startup.run()
    for s in ("", "-wal", "-shm"):
        (paths.home / f"library.db{s}").unlink(missing_ok=True)
    paths.library_db.write_bytes(b"basura" * 300)
    assert "Informe de diagnóstico" in make_core().diagnostics.report("1.0")

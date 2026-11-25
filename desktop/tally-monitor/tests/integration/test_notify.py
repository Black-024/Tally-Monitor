"""Chequeo de respuestas nuevas: lógica sin Qt, con servicios y reloj inyectados."""
from types import SimpleNamespace as NS

import pytest

from support.fixtures import *  # noqa: F401,F403
from support.forms import FORM_ID, add_form, submission
from support.shared import KEY_A, FakeClock
from tally_monitor.api.errors import ApiAuthError, ApiNetworkError, ApiRateLimitError
from tally_monitor.core.secret import SecretStr
from tally_monitor.services.notify_service import NewResponsesChecker, notification_text


class FakeAccounts:
    def __init__(self, accounts):
        self.accounts, self.validated = accounts, []

    def list_accounts(self):
        return self.accounts

    def validate_account(self, aid):
        self.validated.append(aid)


class FakeSync:
    def __init__(self):
        self.calls, self.fail = [], {}

    def sync_forms(self, aid):
        self.calls.append(aid)
        if aid in self.fail:
            raise self.fail[aid]


class FakeSurveys:
    def __init__(self):
        self.data = {}

    def list_surveys(self, aid):
        return self.data.get(aid, [])


def sv(fid, reported, local, archived=False):
    return NS(form_id=fid, reported_submissions=reported, local_submissions=local, archived=archived)


@pytest.fixture
def env(core):
    accs = FakeAccounts([NS(account_id="a", status="active"), NS(account_id="b", status="active")])
    sync, surveys = FakeSync(), FakeSurveys()
    ch = NewResponsesChecker(accs, sync, surveys, core.settings, FakeClock())
    return ch, accs, sync, surveys, core.settings


def test_text_pluralization():
    assert notification_text(3, 2) == ("3 respuestas nuevas en 2 encuestas", "Tocá para abrir Tally Monitor")
    assert notification_text(1, 1)[0] == "1 respuesta nueva en 1 encuesta"


def test_defaults_and_settings_validation(core):
    ch = NewResponsesChecker(None, None, None, core.settings)
    assert not ch.is_enabled() and ch.interval_minutes() == 60 and ch.notified_total() == 0
    ch.set_enabled(True)
    ch.set_interval(15)
    assert ch.is_enabled() and ch.interval_minutes() == 15
    for bad in (0, 10, 61):
        with pytest.raises(ValueError):
            ch.set_interval(bad)
    for bad in ("x", "-1", "1.5", ""):
        with pytest.raises(ValueError):
            core.settings.set("notified_new_total", bad)
    with pytest.raises(ValueError):
        core.settings.set("notify_mode", "maybe")
    for m in (15, 30, 60, 360):
        ch.set_interval(m)
        assert ch.interval_minutes() == m


def test_notifies_sums_accounts_and_skips_archived(env):
    ch, accs, sync, surveys, _ = env
    surveys.data = {"a": [sv("f1", 10, 8), sv("f2", 5, 5), sv("f9", 100, 0, archived=True)],
                    "b": [sv("f3", 4, 3)]}
    out = ch.check()
    assert (out.total, out.surveys, out.notify) == (3, 2, True)
    assert out.title == "3 respuestas nuevas en 2 encuestas" and out.body == "Tocá para abrir Tally Monitor"
    assert sync.calls == ["a", "b"] and ch.notified_total() == 3


def test_dedupe_only_when_total_grows(env):
    ch, _a, _s, surveys, _ = env
    surveys.data = {"a": [sv("f1", 10, 7)]}
    assert ch.check().notify                                        # 3
    assert not ch.check().notify                                    # mismo total: no repite
    surveys.data = {"a": [sv("f1", 11, 7)]}
    out = ch.check()
    assert out.notify and out.total == 4                            # subió
    surveys.data = {"a": [sv("f1", 10, 8)]}                          # bajó (sincronizó algunas)
    assert not ch.check().notify and ch.notified_total() == 2
    surveys.data = {"a": [sv("f1", 11, 8)]}                          # 3 > 2: nuevas desde que se sincronizó
    assert ch.check().notify
    surveys.data = {"a": [sv("f1", 11, 11)]}
    out = ch.check()
    assert (out.total, out.notify) == (0, False) and ch.notified_total() == 0
    surveys.data = {"a": [sv("f1", 12, 11)]}
    assert ch.check().notify                                        # tras llegar a 0, una sola nueva avisa de nuevo


def test_unknown_reported_counts_as_zero(env):
    ch, _a, _s, surveys, _ = env
    surveys.data = {"a": [sv("f1", None, 5), sv("f2", 3, 9)]}
    out = ch.check()
    assert (out.total, out.notify) == (0, False)


@pytest.mark.parametrize("exc", [ApiNetworkError("x"), ApiRateLimitError(), ])
def test_errors_are_silent_and_leave_state_untouched(env, exc):
    ch, accs, sync, surveys, _ = env
    surveys.data = {"a": [sv("f1", 10, 7)], "b": [sv("f2", 9, 0)]}
    ch.check()
    before = ch.notified_total()
    sync.fail["b"] = exc
    surveys.data = {"a": [sv("f1", 20, 7)], "b": []}
    out = ch.check()
    assert out.errors == 1 and not out.notify and ch.notified_total() == before
    sync.fail.clear()
    out = ch.check()
    assert out.notify and out.errors == 0                           # se reintenta en el próximo ciclo


def test_auth_error_marks_account_via_validation(env):
    ch, accs, sync, surveys, _ = env
    sync.fail["a"] = ApiAuthError(401)
    surveys.data = {"b": [sv("f", 5, 0)]}
    out = ch.check()
    assert out.errors == 1 and not out.notify and accs.validated == ["a"]


def test_accounts_without_usable_key_are_skipped(env):
    ch, accs, sync, surveys, _ = env
    accs.accounts = [NS(account_id="a", status="no_credential"), NS(account_id="b", status="key_rejected"),
                     NS(account_id="c", status="check_failed")]
    surveys.data = {"c": [sv("f", 2, 0)]}
    out = ch.check()
    assert sync.calls == ["c"] and out.total == 2 and out.notify


def test_no_accounts_no_notification(env):
    ch, accs, sync, _s, _ = env
    accs.accounts = []
    out = ch.check()
    assert (out.total, out.notify, out.errors) == (0, False, 0)


def test_real_services_end_to_end(core, tally):
    a = core.accounts.add_account("Cuenta", SecretStr(KEY_A))
    add_form(tally, [submission(1), submission(2)])
    ch = core.notifier
    out = ch.check()                                                # trae el listado: Tally informa 2, hay 0 guardadas
    assert (out.total, out.surveys, out.notify) == (2, 1, True)
    assert not ch.check().notify
    core.sync.sync_form(a.account_id, FORM_ID)
    assert ch.check().total == 0
    core.surveys.set_archived(a.account_id, FORM_ID, True)
    add_form(tally, [submission(1), submission(2), submission(3)])
    assert not ch.check().notify                                    # archivada: no cuenta
    core.surveys.set_archived(a.account_id, FORM_ID, False)
    assert ch.check().notify

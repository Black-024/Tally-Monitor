import pytest

from support.fake_tally import FakeTally
from support.shared import KEY_A
from tally_monitor.api.client import TallyClient
from tally_monitor.api.errors import ApiUnexpectedError
from tally_monitor.core.secret import SecretStr

K = SecretStr(KEY_A)


@pytest.fixture
def srv():
    s = FakeTally().start()
    s.users[KEY_A] = "u"
    yield s
    s.stop()


@pytest.mark.parametrize("bad", ["", "../x", "a/b", "a?b=1", "a b", "x" * 80, "a%2Fb"])
def test_form_id_validation_blocks_injection(srv, bad):
    c = TallyClient(srv.url, sleep=lambda s: None)
    for call in (c.get_form, c.get_questions, c.list_submissions):
        with pytest.raises(ValueError):
            call(K, bad)
    assert srv.requests == []


def test_submission_params_validated_and_capped(srv):
    from support.forms import add_form, submission
    add_form(srv, [submission(1)])
    c = TallyClient(srv.url, sleep=lambda s: None)
    with pytest.raises(ValueError):
        c.list_submissions(K, "AbC123", filter="todo")
    with pytest.raises(ValueError):
        c.list_submissions(K, "AbC123", start_date="2026-01-01&limit=1")
    c.list_submissions(K, "AbC123", limit=99999, start_date="2026-11-10T00:00:00.000Z")
    path = srv.requests[-1]["path"]
    assert "limit=500" in path and "startDate=2026-11-10T00%3A00%3A00.000Z" in path


def test_only_get_requests_are_sent(srv):
    from support.forms import add_form, submission
    add_form(srv, [submission(1)])
    c = TallyClient(srv.url, sleep=lambda s: None)
    c.list_forms(K); c.get_form(K, "AbC123"); c.get_questions(K, "AbC123"); c.list_submissions(K, "AbC123")
    assert {r["method"] for r in srv.requests} == {"GET"}


def test_waits_for_window_reset_when_remaining_is_low(srv):
    waits = []
    now = [1000.0]
    srv.rate_headers = {"x-ratelimit-limit": "100", "x-ratelimit-remaining": "1", "x-ratelimit-reset": "1007"}
    c = TallyClient(srv.url, sleep=waits.append, wall_clock=lambda: now[0])
    c.list_forms(K)
    assert waits == []
    c.list_forms(K)
    assert waits == [7.0]
    assert c.rate.limit == 100


def test_min_interval_spaces_requests(srv):
    waits, t = [], [0.0]
    c = TallyClient(srv.url, sleep=waits.append, min_interval=0.75, monotonic=lambda: t[0])
    c.list_forms(K)
    c.list_forms(K)
    assert waits == [0.75]


def test_non_object_body_is_unexpected(srv):
    srv.forms["AbC123"] = {"summary": {}, "detail": [1, 2], "questions": {}, "submissions": []}
    c = TallyClient(srv.url, sleep=lambda s: None)
    with pytest.raises(ApiUnexpectedError):
        c.get_form(K, "AbC123")

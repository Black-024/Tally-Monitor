import socket

import pytest

from support.fixtures import tally  # noqa: F401,E402
from support.shared import KEY_A
from tally_monitor.api.client import USER_AGENT, TallyClient
from tally_monitor.api.errors import (ApiAuthError, ApiNetworkError, ApiRateLimitError,
                                      ApiServerError, ApiUnexpectedError)
from tally_monitor.core.secret import SecretStr

K = SecretStr(KEY_A)


def mk(tally, sleeps=None):
    return TallyClient(tally.url, sleep=(sleeps.append if sleeps is not None else (lambda s: None)))


def test_ok_returns_only_id(tally):
    u = mk(tally).get_current_user(K)
    assert u.tally_user_id == "user-A"
    assert not hasattr(u, "email")


def test_user_without_id(tally):
    tally.users[KEY_A] = None
    assert mk(tally).get_current_user(K).tally_user_id is None


def test_request_is_get_with_own_user_agent_and_bearer(tally):
    mk(tally).get_current_user(K)
    r = tally.requests[0]
    assert r["method"] == "GET" and r["path"] == "/users/me"
    assert r["headers"]["user-agent"] == USER_AGENT and not r["headers"]["user-agent"].startswith("Python")
    assert r["headers"]["authorization"] == f"Bearer {KEY_A}"


@pytest.mark.parametrize("status", [401, 403])
def test_auth_errors_not_retried(tally, status):
    tally.queue += [(status, {})]
    with pytest.raises(ApiAuthError) as e:
        mk(tally).get_current_user(K)
    assert e.value.category == "auth" and len(tally.requests) == 1


def test_wrong_key_is_auth_error(tally):
    with pytest.raises(ApiAuthError):
        mk(tally).get_current_user(SecretStr("tly-incorrecta00000000"))


def test_429_retries_then_recovers_honoring_retry_after(tally):
    tally.queue += [(429, {"Retry-After": "7"})]
    sleeps = []
    assert mk(tally, sleeps).get_current_user(K).tally_user_id == "user-A"
    assert sleeps == [7.0] and len(tally.requests) == 2


def test_429_persistent_is_rate_limit_not_auth(tally):
    tally.queue += [(429, {})] * 3
    with pytest.raises(ApiRateLimitError) as e:
        mk(tally).get_current_user(K)
    assert e.value.category == "rate_limit" and len(tally.requests) == 3


def test_5xx_retries_then_recovers(tally):
    tally.queue += [(503, {}), (502, {})]
    assert mk(tally).get_current_user(K).tally_user_id == "user-A"


def test_5xx_persistent_is_server_error(tally):
    tally.queue += [(500, {})] * 3
    with pytest.raises(ApiServerError) as e:
        mk(tally).get_current_user(K)
    assert e.value.category == "server" and e.value.status == 500


def test_other_4xx_is_unexpected_not_auth(tally):
    tally.queue += [(404, {})]
    with pytest.raises(ApiUnexpectedError) as e:
        mk(tally).get_current_user(K)
    assert e.value.category == "unexpected"


def test_network_error_is_not_auth():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()                                  # puerto cerrado: conexión rechazada
    with pytest.raises(ApiNetworkError) as e:
        TallyClient(f"http://127.0.0.1:{port}", sleep=lambda x: None).get_current_user(K)
    assert e.value.category == "network" and KEY_A not in str(e.value)


def test_200_without_id_field(tally):
    tally.queue += [(200, {})]                 # cuerpo '{"message":"forced"}': JSON válido sin id
    assert mk(tally).get_current_user(K).tally_user_id is None


def test_redirect_is_not_followed(tally):
    tally.queue += [(302, {"Location": "http://127.0.0.1:1/robar"})]
    with pytest.raises(ApiUnexpectedError):
        mk(tally).get_current_user(K)
    assert len(tally.requests) == 1


def test_refuses_plain_http_to_remote_hosts():
    with pytest.raises(ValueError):
        TallyClient("http://api.tally.so")
    TallyClient("https://api.tally.so")
    TallyClient("http://127.0.0.1:1234")


def test_errors_never_contain_key(tally):
    for status in (401, 403, 404, 429, 500):
        tally.queue += [(status, {})] * 3
        with pytest.raises(Exception) as e:
            mk(tally).get_current_user(K)
        assert KEY_A not in str(e.value) and KEY_A not in repr(e.value)

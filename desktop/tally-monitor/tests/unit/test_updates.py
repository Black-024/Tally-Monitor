import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from support.fixtures import *  # noqa: F401,F403
from tally_monitor.api.update_client import UpdateClient
from tally_monitor.core.versioning import is_newer, parse_version
from tally_monitor.services.update_service import UpdateService


class Gh:
    def __init__(self):
        self.reply = (200, {"tag_name": "v9.0.0", "html_url": "https://github.com/me/app/releases/tag/v9.0.0"})
        self.hits, self.headers = [], []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def do_GET(self):
                outer.hits.append(self.path)
                outer.headers.append(dict(self.headers))
                code, body = outer.reply
                if code == 302:
                    self.send_response(302); self.send_header("Location", "http://evil.invalid/"); self.end_headers(); return
                data = json.dumps(body).encode()
                self.send_response(code); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

        self.srv = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_port}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()


@pytest.fixture
def gh():
    g = Gh()
    yield g
    g.srv.shutdown()


@pytest.fixture
def svc(core, gh):
    return UpdateService(UpdateClient(gh.url), core.settings, "0.1.0", "me/app")


def test_version_compare():
    assert parse_version("v1.2.3") == (1, 2, 3) and parse_version("1.2") is None
    assert is_newer("v0.10.0", "0.9.9") and not is_newer("0.1.0", "0.1.0") and not is_newer("basura", "0.1.0")


def test_off_by_default_makes_no_request(svc, gh):
    assert not svc.enabled()
    assert svc.check().state == "disabled" and gh.hits == []


def test_enabled_reports_available_and_sends_no_credentials(svc, gh):
    svc.set_enabled(True)
    st = svc.check()
    assert st.state == "available" and st.latest == "9.0.0" and st.url.endswith("v9.0.0")
    assert gh.hits == ["/repos/me/app/releases/latest"]
    assert "Authorization" not in gh.headers[0]


def test_up_to_date_and_manual_check_even_when_off(svc, gh):
    gh.reply = (200, {"tag_name": "v0.1.0", "html_url": "https://github.com/me/app/releases/tag/v0.1.0"})
    assert svc.check(force=True).state == "up_to_date"


def test_foreign_url_redirect_and_errors_are_safe(core, gh):
    svc = UpdateService(UpdateClient(gh.url), core.settings, "0.1.0", "me/app")
    gh.reply = (200, {"tag_name": "v9.0.0", "html_url": "https://evil.example/x"})
    assert svc.check(force=True).state == "error"            # enlace que no es del repositorio: se descarta
    gh.reply = (302, {})
    assert svc.check(force=True).state == "error"            # no se siguen redirecciones
    gh.reply = (500, {})
    assert svc.check(force=True).state == "error"
    gh.srv.shutdown()
    assert svc.check(force=True).state == "error"            # sin red: sin excepción


def test_not_configured_until_published(core, gh):
    svc = UpdateService(UpdateClient(gh.url), core.settings, "0.1.0", "")
    svc.set_enabled(True)
    assert svc.check().state == "not_configured" and gh.hits == []


def test_bad_repo_name_is_rejected(gh):
    with pytest.raises(ValueError):
        UpdateClient(gh.url).latest_release("../../etc")

import json
import logging
import sys
import threading

import pytest

from support.fixtures import *  # noqa: F401,F403
from support.forms import FORM_ID, add_form, push, submission
from support.shared import KEY_A, KEY_B
from tally_monitor import testmode
from tally_monitor.api.client import TallyClient, describe_request
from tally_monitor.api.errors import ApiAuthError
from tally_monitor.app import build_core
from tally_monitor.core.secret import SecretStr
from tally_monitor.core.session_report import SessionRecorder, scrub_text

NAME = "NOMBRE-PRIVADO-DE-LA-CUENTA"


@pytest.fixture
def rec_core(paths, protector, tally, clock, monkeypatch):
    rec = SessionRecorder(paths.reports_dir, app_version="0.1.0", flush_every=0)
    client = TallyClient(tally.url, sleep=lambda s: None, on_event=rec.request)
    core = build_core(paths=paths, protector=protector, client=client, clock=clock, configure_logging=True,
                      recorder=rec)
    monkeypatch.setattr("atexit.register", lambda f: None)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    logger = logging.getLogger("tally_monitor")
    before = list(logger.handlers)
    core.startup.run()
    testmode.attach(rec, core)
    yield rec, core
    logger.handlers[:] = before


def load(rec):
    return json.loads(rec.path.read_text(encoding="utf-8"))


def test_report_tells_what_happened_without_secrets(rec_core, tally, paths):
    rec, core = rec_core
    a = core.accounts.add_account(NAME, SecretStr(KEY_A))
    with pytest.raises(ApiAuthError):
        core.accounts.add_account("Otra", SecretStr("tly-incorrecta1234567890"))
    add_form(tally, [submission(10, text="TEXTO-PRIVADO-DE-UNA-PERSONA"), submission(20)])
    core.sync.sync_forms(a.account_id)
    core.sync.sync_form(a.account_id, FORM_ID)
    push(tally, submission(30))
    core.sync.sync_form(a.account_id, FORM_ID)
    core.sync.sync_form(a.account_id, FORM_ID)
    path = rec.finish("normal")
    doc = json.loads(path.read_text(encoding="utf-8"))
    text = path.read_text(encoding="utf-8")

    for forbidden in (NAME, KEY_A, KEY_A[4:], "TEXTO-PRIVADO", "RESP-SECRET", "SESSION-SECRET", "persona@example.com",
                      "incorrecta1234567890"):
        assert forbidden not in text, forbidden
    assert doc["completo"] and doc["salida"] == {"motivo": "normal"}
    assert doc["autorevision"]["patron_clave_encontrado"] is False
    calls = doc["resumen"]["llamadas"]
    assert calls["accounts.add_account"] == {"ok": 1, "error": 1, "ms_total": calls["accounts.add_account"]["ms_total"]}
    assert calls["sync.sync_form"]["ok"] == 3
    modes = [e["resumen"]["mode"] for e in doc["eventos"] if e.get("metodo") == "sync_form"]
    assert modes == ["initial", "incremental", "nochange"]
    err = next(e for e in doc["resumen"]["errores"] if e["donde"] == "accounts.add_account")
    assert err["categoria"] == "auth" and err["http"] == 401
    add = next(e for e in doc["eventos"] if e.get("metodo") == "add_account")
    assert add["args"]["name"].startswith("<texto de") and add["args"]["api_key"] == "<clave>"
    assert add["args"].get("account_id") is None
    sync_ev = next(e for e in doc["eventos"] if e.get("metodo") == "sync_form")
    assert sync_ev["args"]["account_id"] == "Cuenta 1" and sync_ev["args"]["form_id"] == FORM_ID


def test_requests_are_generic_and_logs_are_captured(rec_core, tally):
    rec, core = rec_core
    a = core.accounts.add_account("Uno", SecretStr(KEY_A))
    add_form(tally, [submission(10)])
    core.sync.sync_form(a.account_id, FORM_ID)
    doc = load(rec)
    reqs = [e for e in doc["eventos"] if e["kind"] == "solicitud"]
    assert reqs and all(FORM_ID not in e["ruta"] for e in reqs)
    assert "/forms/{id}/submissions" in {e["ruta"] for e in reqs}
    assert any(e.get("consulta", {}).get("limit") == "500" for e in reqs)
    assert all(e["metodo"] == "GET" for e in reqs)
    assert doc["resumen"]["solicitudes_tally"]["por_estado"]["200"] >= 3
    assert any(e["kind"] == "log" and "Cuenta agregada" in e["mensaje"] for e in doc["eventos"])


def test_network_and_server_failures_are_classified(rec_core, tally):
    rec, core = rec_core
    a = core.accounts.add_account("Uno", SecretStr(KEY_A))
    add_form(tally, [submission(10)])
    tally.queue += [(500, {})] * 3
    with pytest.raises(Exception):
        core.sync.sync_form(a.account_id, FORM_ID)
    doc = load(rec)
    assert any(e.get("error") == "server" and e.get("estado") == 500 for e in doc["eventos"] if e["kind"] == "solicitud")
    assert any(x["categoria"] == "server" for x in doc["resumen"]["errores"])


def test_final_state_has_counts_only(rec_core, tally):
    rec, core = rec_core
    a = core.accounts.add_account(NAME, SecretStr(KEY_A))
    add_form(tally, [submission(10), submission(20)])
    core.sync.sync_forms(a.account_id)
    core.sync.sync_form(a.account_id, FORM_ID)
    rec.finish("normal")
    st = load(rec)["estado_final"]
    assert st["library"]["version_esquema"] == 3 and st["library"]["integridad_ok"]
    assert st["library"]["filas"]["data_submission"] == 2 and st["library"]["envios_sin_numero"] == 0
    assert st["credenciales"]["coinciden_con_cuentas"] is True
    assert st["ajustes"]["sync_mode"] == "manual"
    assert NAME not in json.dumps(st)


def test_coverage_reports_done_and_missing(rec_core):
    rec, core = rec_core
    core.accounts.add_account("Uno", SecretStr(KEY_A))
    rec.event("pantalla", pantalla="encuestas")
    rec.finish("normal")
    cov = load(rec)["cobertura"]
    done = {d["id"] for d in cov["detalle"] if d["cubierto"]}
    assert {"cuenta_agregar", "pantalla_encuestas", "cierre_normal"} <= done
    assert "backup_restaurar" in cov["no_cubiertos"] and cov["cubiertos"] + len(cov["no_cubiertos"]) == cov["total"]


def test_partial_report_exists_before_closing_and_shows_call_in_flight(rec_core, tally):
    rec, core = rec_core
    cid = rec.call_started("sync", "sync_form", {})
    rec.event("pantalla", pantalla="cuentas")
    doc = load(rec)                              # sin cerrar: el archivo ya existe
    assert doc["completo"] is False and doc["llamadas_en_curso"][0]["metodo"] == "sync_form"
    assert doc["salida"]["motivo"].startswith("en curso")


def test_finish_is_idempotent_and_later_events_ignored(rec_core):
    rec, _ = rec_core
    rec.finish("normal")
    rec.finish("salida_inesperada")
    rec.event("pantalla", pantalla="x")
    doc = load(rec)
    assert doc["salida"] == {"motivo": "normal"} and not any(e.get("pantalla") == "x" for e in doc["eventos"])


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_uncaught_exceptions_are_recorded_with_scrubbed_paths(rec_core):
    rec, core = rec_core

    def boom():
        raise RuntimeError(r"fallo en C:\Users\Marcos\Documentos\x.txt con tly-ABCDEFGH12345")
    t = threading.Thread(target=boom)
    t.start(); t.join()
    doc = load(rec)
    ex = next(e for e in doc["eventos"] if e["kind"] == "excepcion")
    blob = json.dumps(ex)
    assert "Marcos" not in blob and "tly-ABCDEFGH" not in blob and ex["donde"] == "hilo de trabajo"


def test_report_pruning_and_scrub_helpers(tmp_path):
    assert "Marcos" not in scrub_text(r"C:\Users\Marcos\a.txt") and "<usuario>" in scrub_text("/home/marcos/x")
    assert scrub_text("a@b.com") == "<correo>"
    assert len(scrub_text("x" * 1000)) <= 241
    for i in range(25):
        r = SessionRecorder(tmp_path, app_version="t")
        r.path = tmp_path / f"informe-{i:04d}.json"
        r.finish("normal")
    assert len(list(tmp_path.glob("informe-*.json"))) == 20


def test_event_cap_counts_dropped(tmp_path):
    r = SessionRecorder(tmp_path, app_version="t", flush_every=10_000)
    for i in range(6100):
        r.event("pantalla", pantalla="a")
    r.finish("normal")
    d = json.loads(r.path.read_text(encoding="utf-8"))
    assert d["resumen"]["eventos_descartados"] > 0 and len(d["eventos"]) <= 6001


@pytest.mark.parametrize("path,expected", [
    ("/forms/AbC123/submissions?page=2&limit=500&filter=all&startDate=2026-11-10T00%3A00%3A00.000Z",
     ("/forms/{id}/submissions", {"page": "2", "limit": "500", "filter": "all", "startDate": True})),
    ("/forms?page=1", ("/forms", {"page": "1"})), ("/users/me", ("/users/me", {})),
    ("/forms/abc", ("/forms/{id}", {}))])
def test_describe_request(path, expected):
    assert describe_request(path) == expected


def test_normal_mode_has_no_recorder_overhead(core):
    assert type(core.accounts).__name__ == "AccountService"


def test_selfcheck_reports_each_item(monkeypatch, tmp_path, protector):
    from tally_monitor import selfcheck
    monkeypatch.setattr("tally_monitor.security.protector.default_protector", lambda: protector)
    monkeypatch.setenv("TEMP", str(tmp_path))
    selfcheck.run()
    text = (tmp_path / "tally-monitor-autodiagnostico.txt").read_text(encoding="utf-8")
    assert "[OK] migraciones SQL incluidas" in text and "[OK] almacén seguro de claves (DPAPI / llavero)" in text
    assert "[OK] bases creadas y migradas" in text and "RESULTADO:" in text


def test_main_version_and_selfcheck_do_not_need_qt(monkeypatch, tmp_path, protector, capsys):
    from tally_monitor import __main__ as entry
    from tally_monitor._version import __version__
    assert entry.main(["--version"]) == 0
    assert __version__ in capsys.readouterr().out
    monkeypatch.setattr("tally_monitor.security.protector.default_protector", lambda: protector)
    monkeypatch.setenv("TEMP", str(tmp_path))
    entry.main(["--self-check"])
    assert (tmp_path / "tally-monitor-autodiagnostico.txt").exists()


def test_selfcheck_without_keyring_warns_but_still_checks_the_rest(monkeypatch, tmp_path):
    """En un equipo sin llavero (servidor, CI) el autodiagnóstico avisa pero no falla por eso."""
    from tally_monitor import selfcheck
    from tally_monitor.core.errors import ProtectionUnavailableError

    def unavailable():
        raise ProtectionUnavailableError()

    monkeypatch.setattr("tally_monitor.security.protector.default_protector", unavailable)
    monkeypatch.setenv("TEMP", str(tmp_path))
    selfcheck.run()
    text = (tmp_path / "tally-monitor-autodiagnostico.txt").read_text(encoding="utf-8")
    assert "[AVISO] almacén seguro de claves" in text and "[OK] bases creadas y migradas" in text
    assert "[FALLO] núcleo" not in text and "[FALLO] almacén" not in text

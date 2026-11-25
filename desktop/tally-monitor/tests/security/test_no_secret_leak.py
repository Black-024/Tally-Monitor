"""Recorre todo el flujo (con éxitos y fallos) y busca la clave en cualquier salida."""
import logging

import pytest

from support.fixtures import core, make_core, paths, protector, clock, tally  # noqa: F401,E402
from support.shared import KEY_A, KEY_B, KEY_C
from tally_monitor.api.errors import ApiError
from tally_monitor.core.errors import TallyMonitorError
from tally_monitor.core.secret import SecretStr

A, B, C = SecretStr(KEY_A), SecretStr(KEY_B), SecretStr(KEY_C)
NEEDLES = [KEY_A, KEY_B, KEY_C, KEY_A[4:], KEY_B[4:], KEY_C[4:], "persona@example.com", "Ana"]


def all_bytes(paths):
    return {p: p.read_bytes() for p in paths.home.rglob("*") if p.is_file()}


def test_key_never_appears_anywhere(make_core, paths, tally, capsys, caplog):
    caplog.set_level(logging.DEBUG)
    core = make_core(logging=True)
    core.startup.run()
    seen_errors = []

    def attempt(fn, *a):
        try:
            return fn(*a)
        except TallyMonitorError as exc:
            seen_errors.append((str(exc), repr(exc), exc.user_message))

    a = core.accounts.add_account("Uno", A)
    attempt(core.accounts.add_account, "Dos", SecretStr("tly-incorrecta1234567890"))
    tally.queue += [(401, {})]
    attempt(core.accounts.add_account, "Tres", B)
    tally.queue += [(429, {})] * 3
    attempt(core.accounts.validate_account, a.account_id)
    tally.queue += [(500, {})] * 3
    attempt(core.accounts.validate_account, a.account_id)
    attempt(core.accounts.add_account, "Uno", B)               # nombre repetido
    attempt(core.accounts.replace_key, a.account_id, B)        # otro usuario
    core.accounts.replace_key(a.account_id, C)
    b = core.accounts.add_account("Otra", B)
    attempt(core.accounts.replace_key, b.account_id, C)        # clave duplicada
    info = core.backups.create_manual()
    core.backups.restore(info.filename)
    core.accounts.rename_account(a.account_id, "Principal")
    core.accounts.validate_all()
    core.accounts.delete_account(b.account_id)
    core.startup.run()
    for h in logging.getLogger("tally_monitor").handlers:
        h.flush()

    out = capsys.readouterr()
    haystacks = [out.out, out.err, caplog.text, "\n".join(" ".join(t) for t in seen_errors)]
    for h in haystacks:
        for n in NEEDLES:
            assert n not in h, f"apareció {n[:8]}… en la salida"
    for path, data in all_bytes(paths).items():
        for n in NEEDLES:
            assert n.encode() not in data, f"{n[:8]}… encontrado en {path.relative_to(paths.home)}"
    assert (paths.logs_dir / "tally_monitor.log").stat().st_size > 0      # se registró actividad
    assert len(seen_errors) >= 5                                            # y hubo errores reales


def test_user_id_not_in_databases(core, paths):
    """El id de usuario de Tally vive solo en credentials.dat (cifrado), no en las bases ni en backups."""
    core.accounts.add_account("Uno", A)
    core.backups.create_manual()
    for p, data in all_bytes(paths).items():
        assert b"user-A" not in data, p.name


def test_api_errors_are_safe_by_construction(tally):
    from tally_monitor.api.client import TallyClient
    for status in (401, 403, 429, 500, 404):
        tally.queue += [(status, {})] * 3
        with pytest.raises(ApiError) as e:
            TallyClient(tally.url, sleep=lambda s: None).get_current_user(A)
        assert KEY_A not in e.value.user_message and e.value.__cause__ is None


def test_sync_flow_never_leaks_key_or_identifiers(make_core, paths, tally, capsys, caplog):
    from support.forms import FORM_ID, add_form, push, submission
    caplog.set_level(logging.DEBUG)
    core = make_core(logging=True)
    core.startup.run()
    a = core.accounts.add_account("Uno", A)
    add_form(tally, [submission(10), submission(20)])
    core.sync.sync_forms(a.account_id)
    core.sync.sync_form(a.account_id, FORM_ID)
    push(tally, submission(30))
    tally.queue += [(429, {})]
    core.sync.sync_form(a.account_id, FORM_ID)
    tally.queue += [(500, {})] * 3
    with pytest.raises(ApiError):
        core.sync.sync_form(a.account_id, FORM_ID, full=True)
    out = capsys.readouterr()
    text = out.out + out.err + caplog.text
    for needle in NEEDLES + ["RESP-SECRET", "SESSION-SECRET", "tally.so/preview"]:
        assert needle not in text
    for p, data in all_bytes(paths).items():
        if p.name == "credentials.dat":
            continue
        for needle in NEEDLES[:6] + ["RESP-SECRET", "SESSION-SECRET"]:
            assert needle.encode() not in data, (p.name, needle)

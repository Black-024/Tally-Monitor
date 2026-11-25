import pytest

from support.fixtures import core, make_core, paths, protector, clock, tally  # noqa: F401,E402
from support.shared import KEY_A, KEY_B, KEY_C
from support.fake_protector import FakeProtector
from tally_monitor.api.errors import (ApiAuthError, ApiNetworkError, ApiRateLimitError,
                                      ApiServerError)
from tally_monitor.core.errors import (AccountNameTakenError, AccountNotFoundError, DuplicateKeyError,
                                       InvalidAccountNameError, InvalidKeyFormatError,
                                       KeyBelongsToOtherAccountError)
from tally_monitor.core.secret import SecretStr

A, B, C = SecretStr(KEY_A), SecretStr(KEY_B), SecretStr(KEY_C)


def test_add_persists_across_restart(make_core):
    c1 = make_core()
    c1.startup.run()
    acct = c1.accounts.add_account("  Mi cuenta  ", A)
    assert acct.name == "Mi cuenta" and acct.status == "active" and acct.last_validated_at
    c2 = make_core()                       # "reinicio": todo nuevo sobre la misma carpeta
    rep = c2.startup.run()
    assert rep.orphans_removed == [] and rep.marked_no_credential == []
    [again] = c2.accounts.list_accounts()
    assert again.account_id == acct.account_id
    assert c2.accounts.validate_account(acct.account_id).result == "ok"   # la clave sigue funcionando


def test_add_multiple_accounts_any_time(core):
    core.accounts.add_account("Uno", A)
    core.accounts.add_account("Dos", B)
    assert [a.name for a in core.accounts.list_accounts()] == ["Uno", "Dos"]


@pytest.mark.parametrize("queue,exc", [
    ([(401, {})], ApiAuthError), ([(403, {})], ApiAuthError),
    ([(429, {})] * 3, ApiRateLimitError), ([(503, {})] * 3, ApiServerError)])
def test_failed_add_leaves_no_residue(core, tally, queue, exc):
    tally.queue += queue
    with pytest.raises(exc):
        core.accounts.add_account("X", A)
    assert core.accounts.list_accounts() == []
    assert core.accounts._store.ids() == set()


def test_add_with_no_network_leaves_no_residue(paths, protector, clock):
    from tally_monitor.api.client import TallyClient
    from tally_monitor.app import build_core
    c = build_core(paths=paths, protector=protector, clock=clock, configure_logging=False,
                   client=TallyClient("http://127.0.0.1:1", sleep=lambda s: None))
    c.startup.run()
    with pytest.raises(ApiNetworkError):
        c.accounts.add_account("X", A)
    assert c.accounts.list_accounts() == [] and c.accounts._store.ids() == set()


def test_add_rolls_back_if_saving_credential_fails(core, monkeypatch):
    def boom(*a, **k):
        raise OSError("disco lleno")
    monkeypatch.setattr(core.accounts._store, "save", boom)
    with pytest.raises(OSError):
        core.accounts.add_account("X", A)
    assert core.accounts.list_accounts() == []


def test_name_and_key_validation(core):
    core.accounts.add_account("Uno", A)
    with pytest.raises(AccountNameTakenError):
        core.accounts.add_account("uno", B)                  # sin distinguir mayúsculas
    with pytest.raises(DuplicateKeyError):
        core.accounts.add_account("Otra", A)
    for bad in ("", "   ", "x" * 61):
        with pytest.raises(InvalidAccountNameError):
            core.accounts.add_account(bad, B)
    with pytest.raises(InvalidKeyFormatError):
        core.accounts.add_account("Vacia", SecretStr("   "))
    assert len(core.accounts.list_accounts()) == 1


def test_validate_distinguishes_causes_and_keeps_key(core, tally):
    a = core.accounts.add_account("Uno", A)
    first_ok = core.accounts.get_account(a.account_id).last_validated_at
    cases = [([(401, {})], "auth", "key_rejected"),
             ([(403, {})], "auth", "key_rejected"),
             ([(429, {})] * 3, "rate_limit", "check_failed"),
             ([(500, {})] * 3, "server", "check_failed"),
             ([(404, {})], "unexpected", "check_failed")]
    for queue, result, status in cases:
        tally.queue += queue
        out = core.accounts.validate_account(a.account_id)
        assert (out.result, out.account.status) == (result, status), result
        assert out.account.last_validated_at == first_ok          # solo avanza con éxito
        assert core.accounts._store.has(a.account_id)             # la clave nunca se borra
    tally.users.clear()                                           # caída de red simulada abajo
    # red caída: se prueba con un cliente apuntando a un puerto cerrado
    core.accounts._client._base = "http://127.0.0.1:1"
    out = core.accounts.validate_account(a.account_id)
    assert out.result == "network" and out.account.status == "check_failed"
    assert core.accounts._store.load(a.account_id).api_key.reveal() == KEY_A


def test_recovers_after_transient_failure(core, tally):
    a = core.accounts.add_account("Uno", A)
    tally.queue += [(500, {})] * 3
    assert core.accounts.validate_account(a.account_id).account.status == "check_failed"
    out = core.accounts.validate_account(a.account_id)
    assert out.result == "ok" and out.account.status == "active"


def test_validate_without_credential(core):
    a = core.accounts.add_account("Uno", A)
    core.accounts._store.delete(a.account_id)
    out = core.accounts.validate_account(a.account_id)
    assert out.result == "no_credential" and out.account.status == "no_credential"


def test_unreadable_credential_becomes_no_credential(make_core):
    c1 = make_core()
    c1.startup.run()
    a = c1.accounts.add_account("Uno", A)
    c2 = make_core(prot=FakeProtector())                  # otro usuario de Windows: no puede descifrar
    rep = c2.startup.run()
    assert rep.marked_no_credential == [a.account_id]
    assert c2.accounts.get_account(a.account_id).status == "no_credential"
    assert "Hay cuentas sin clave guardada: usá «Reemplazar clave»." in rep.messages
    c2.accounts.replace_key(a.account_id, A)              # se repara reemplazando
    assert c2.accounts.get_account(a.account_id).status == "active"


def test_rename(core):
    a = core.accounts.add_account("Uno", A)
    core.accounts.add_account("Dos", B)
    assert core.accounts.rename_account(a.account_id, " Principal ").name == "Principal"
    with pytest.raises(AccountNameTakenError):
        core.accounts.rename_account(a.account_id, "dos")
    with pytest.raises(AccountNotFoundError):
        core.accounts.rename_account("no-existe", "X")


# ---------- reemplazo de clave: la anterior se conserva si falla ----------
def test_replace_ok_same_user(core):
    a = core.accounts.add_account("Uno", A)
    res = core.accounts.replace_key(a.account_id, C)       # C: otra clave del mismo usuario "user-A"
    assert res.identity_verified is True
    assert core.accounts._store.load(a.account_id).api_key.reveal() == KEY_C


@pytest.mark.parametrize("queue,exc", [([(401, {})], ApiAuthError), ([(429, {})] * 3, ApiRateLimitError),
                                       ([(500, {})] * 3, ApiServerError)])
def test_replace_keeps_old_key_if_new_fails(core, tally, queue, exc):
    a = core.accounts.add_account("Uno", A)
    tally.queue += queue
    with pytest.raises(exc):
        core.accounts.replace_key(a.account_id, C)
    assert core.accounts._store.load(a.account_id).api_key.reveal() == KEY_A
    assert core.accounts.get_account(a.account_id).status == "active"


def test_replace_with_invalid_key_keeps_old(core):
    a = core.accounts.add_account("Uno", A)
    with pytest.raises(ApiAuthError):
        core.accounts.replace_key(a.account_id, SecretStr("tly-no-existe-0000000000"))
    assert core.accounts._store.load(a.account_id).api_key.reveal() == KEY_A


def test_replace_with_key_of_other_user_keeps_old(core):
    a = core.accounts.add_account("Uno", A)                # user-A
    with pytest.raises(KeyBelongsToOtherAccountError):
        core.accounts.replace_key(a.account_id, B)         # user-B
    assert core.accounts._store.load(a.account_id).api_key.reveal() == KEY_A


def test_replace_with_key_already_in_other_account(core):
    a = core.accounts.add_account("Uno", A)
    core.accounts.add_account("Dos", B)
    with pytest.raises(DuplicateKeyError):
        core.accounts.replace_key(a.account_id, B)
    assert core.accounts._store.load(a.account_id).api_key.reveal() == KEY_A


def test_replace_identity_not_verifiable_is_flagged(core, tally):
    tally.users[KEY_A] = None                              # Tally no devolvió id al agregar
    a = core.accounts.add_account("Uno", A)
    assert core.accounts._store.load(a.account_id).tally_user_id is None
    res = core.accounts.replace_key(a.account_id, B)
    assert res.identity_verified is False


def test_validate_backfills_missing_identity(core, tally):
    tally.users[KEY_A] = None
    a = core.accounts.add_account("Uno", A)
    tally.users[KEY_A] = "user-A"
    core.accounts.validate_account(a.account_id)
    assert core.accounts._store.load(a.account_id).tally_user_id == "user-A"
    with pytest.raises(KeyBelongsToOtherAccountError):
        core.accounts.replace_key(a.account_id, B)


def test_delete_removes_row_and_credential(core):
    a = core.accounts.add_account("Uno", A)
    core.accounts.delete_account(a.account_id)
    assert core.accounts.list_accounts() == [] and core.accounts._store.ids() == set()
    with pytest.raises(AccountNotFoundError):
        core.accounts.delete_account(a.account_id)
    core.accounts.add_account("Otra vez", A)               # la clave puede volver a usarse


def test_reconcile_removes_orphans(core):
    a = core.accounts.add_account("Uno", A)
    core.accounts._store.save("huerfana", B, None)
    rec = core.accounts.reconcile_credentials()
    assert rec["orphans_removed"] == ["huerfana"] and core.accounts._store.ids() == {a.account_id}


# ---------- backups: sin credenciales ----------
def test_backups_exclude_credentials_and_restore_flags_missing_key(core, paths):
    a = core.accounts.add_account("Uno", A)
    core.accounts.add_account("Dos", B)
    b1 = core.backups.create_manual()
    core.accounts.delete_account(a.account_id)             # borra fila y clave
    core.backups.restore(b1.filename)
    names = {x.name for x in core.accounts.list_accounts()}
    assert names == {"Uno", "Dos"}                         # la fila vuelve...
    for p in paths.backups_dir.iterdir():
        data = p.read_bytes()
        assert KEY_A.encode() not in data and KEY_B.encode() not in data and b"tly-" not in data
        assert b"user-A" not in data and b"user-B" not in data
    restored = next(x for x in core.accounts.list_accounts() if x.name == "Uno")
    assert restored.status == "no_credential"              # restaurar ya marca las cuentas sin clave
    assert core.accounts.reconcile_credentials()["marked_no_credential"] == []   # y es idempotente
    core.accounts.replace_key(restored.account_id, A)
    assert core.accounts.get_account(restored.account_id).status == "active"


def test_restore_does_not_touch_credentials_file(core, paths):
    core.accounts.add_account("Uno", A)
    b = core.backups.create_manual()
    before = paths.credentials.read_bytes()
    core.backups.restore(b.filename)
    assert paths.credentials.read_bytes() == before


@pytest.mark.parametrize("bad", ["", "   ", "\x16", "x", "tly-", "tly-ab", "sin-prefijo-123456789",
                                 "tly-con espacio 12345", "tly-con\x16control1234", "tly-ñandú12345", "tly-" + "a" * 300])
def test_malformed_key_rejected_before_any_network_call(core, tally, bad):
    """Una clave mal pegada (p. ej. Ctrl+V → '\\x16') no llega a Tally ni se confunde con una rechazada."""
    n = len(tally.requests)
    with pytest.raises(InvalidKeyFormatError):
        core.accounts.add_account("X", SecretStr(bad))
    a = core.accounts.add_account("Real", A)
    with pytest.raises(InvalidKeyFormatError):
        core.accounts.replace_key(a.account_id, SecretStr(bad))
    assert len(tally.requests) == n + 1                       # solo la del alta válida
    assert core.accounts._store.load(a.account_id).api_key.reveal() == KEY_A

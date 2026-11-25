import json
import os

import pytest

from support.fixtures import protector  # noqa: F401,E402
from support.shared import KEY_A, KEY_B
from support.fake_protector import FakeProtector
from tally_monitor.core.errors import CredentialUnreadableError
from tally_monitor.core.secret import SecretStr
from tally_monitor.security.credential_store import CredentialStore


@pytest.fixture
def store(tmp_path, protector):
    return CredentialStore(tmp_path / "credentials.dat", protector)


def test_roundtrip_and_persistence(tmp_path, protector, store):
    store.save("a1", SecretStr(KEY_A), "user-A")
    again = CredentialStore(tmp_path / "credentials.dat", protector)   # "reinicio"
    c = again.load("a1")
    assert c.api_key.reveal() == KEY_A and c.tally_user_id == "user-A"
    assert again.load("nada") is None and again.has("a1") and again.ids() == {"a1"}


def test_file_has_no_plaintext(tmp_path, store):
    store.save("a1", SecretStr(KEY_A), "user-A")
    raw = (tmp_path / "credentials.dat").read_bytes()
    assert KEY_A.encode() not in raw and b"tly-" not in raw and b"user-A" not in raw


def test_replace_and_delete(store):
    store.save("a1", SecretStr(KEY_A), "user-A")
    store.save("a1", SecretStr(KEY_B), "user-B")
    assert store.load("a1").api_key.reveal() == KEY_B
    store.delete("a1")
    assert store.load("a1") is None
    store.delete("a1")  # idempotente


def test_repr_hides(store):
    store.save("a1", SecretStr(KEY_A), "user-A")
    assert KEY_A not in repr(store.load("a1")) and "user-A" not in repr(store.load("a1"))


def test_corrupt_file_is_quarantined_not_overwritten(tmp_path, store):
    p = tmp_path / "credentials.dat"
    p.write_text("esto no es json", encoding="utf-8")
    assert store.ids() == set()
    assert store.last_quarantine is not None and store.last_quarantine.exists()
    assert store.last_quarantine.read_text() == "esto no es json"
    store.save("a1", SecretStr(KEY_A), None)       # sigue funcionando
    assert store.has("a1")


def test_wrong_structure_is_quarantined(tmp_path, store):
    (tmp_path / "credentials.dat").write_text(json.dumps({"format": 99, "entries": {}}))
    store.ids()
    assert store.last_quarantine is not None


def test_one_bad_entry_does_not_affect_others(tmp_path, protector, store):
    store.save("ok", SecretStr(KEY_A), "u")
    other = CredentialStore(tmp_path / "credentials.dat", FakeProtector())   # otro "usuario de Windows"
    other.save("foreign", SecretStr(KEY_B), "u2")
    assert store.load("ok").api_key.reveal() == KEY_A
    with pytest.raises(CredentialUnreadableError):
        store.load("foreign")
    assert [a for a, _ in store.iter_credentials()] == ["ok"]


def test_garbage_blob_is_unreadable(tmp_path, store):
    p = tmp_path / "credentials.dat"
    p.write_text(json.dumps({"format": 1, "entries": {"x": {"blob": "!!!no-base64!!!"}}}))
    with pytest.raises(CredentialUnreadableError):
        store.load("x")


def test_atomic_write_keeps_old_file_on_failure(tmp_path, store, monkeypatch):
    store.save("a1", SecretStr(KEY_A), "user-A")
    before = (tmp_path / "credentials.dat").read_bytes()

    def boom(*a, **k):
        raise OSError("disco lleno")
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        store.save("a1", SecretStr(KEY_B), "user-B")
    monkeypatch.undo()
    assert (tmp_path / "credentials.dat").read_bytes() == before
    assert store.load("a1").api_key.reveal() == KEY_A
    assert [p.name for p in tmp_path.iterdir()] == ["credentials.dat"]    # sin temporales


def test_purge_orphans(store):
    store.save("keep", SecretStr(KEY_A), None)
    store.save("orphan", SecretStr(KEY_B), None)
    assert store.purge_orphans({"keep"}) == ["orphan"]
    assert store.ids() == {"keep"}

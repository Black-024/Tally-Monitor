"""Protector del llavero (Linux/macOS): referencia opaca en credentials.dat y secreto solo en el llavero."""
import json
import sys

import pytest

from tally_monitor.core import config
from tally_monitor.core.errors import CredentialUnreadableError, ProtectionUnavailableError
from tally_monitor.core.secret import SecretStr
from tally_monitor.security.credential_store import CredentialStore
from tally_monitor.security.keyring_protector import KeyringProtector

KEY = "tly-ABCDEFGHIJKLMNOP1234"


class FakeKeyring:
    """Llavero en memoria con la misma interfaz que `keyring` (solo para pruebas)."""

    def __init__(self):
        self.items = {}

    def set_password(self, service, user, value):
        self.items[(service, user)] = value

    def get_password(self, service, user):
        return self.items.get((service, user))

    def delete_password(self, service, user):
        del self.items[(service, user)]


def test_roundtrip_and_blob_is_only_a_reference():
    kr = FakeKeyring()
    p = KeyringProtector(kr)
    blob = p.protect(KEY.encode())
    assert KEY.encode() not in blob and blob.startswith(b"TMKR1:")
    assert p.unprotect(blob) == KEY.encode()


def test_missing_entry_is_unreadable_not_a_crash():
    p = KeyringProtector(FakeKeyring())
    blob = p.protect(b"x")
    p.discard(blob)
    with pytest.raises(CredentialUnreadableError):
        p.unprotect(blob)
    with pytest.raises(CredentialUnreadableError):
        p.unprotect(b"otra-cosa")


def test_backend_failures_do_not_leak_details():
    class Broken(FakeKeyring):
        def set_password(self, *a):
            raise RuntimeError("detalle interno con " + KEY)

    with pytest.raises(ProtectionUnavailableError) as e:
        KeyringProtector(Broken()).protect(b"x")
    assert KEY not in str(e.value) and e.value.__cause__ is not None


def test_store_with_keyring_keeps_key_out_of_file_and_cleans_up(tmp_path):
    kr = FakeKeyring()
    store = CredentialStore(tmp_path / "credentials.dat", KeyringProtector(kr))
    store.save("a1", SecretStr(KEY), "u1")
    assert KEY not in (tmp_path / "credentials.dat").read_text()
    assert store.load("a1").api_key.reveal() == KEY and len(kr.items) == 1
    store.save("a1", SecretStr(KEY + "2"), "u1")                 # reemplazar: no quedan restos del anterior
    assert len(kr.items) == 1 and store.load("a1").api_key.reveal() == KEY + "2"
    store.save("a2", SecretStr(KEY + "3"), None)
    assert store.purge_orphans({"a2"}) == ["a1"] and len(kr.items) == 1
    store.delete("a2")
    assert kr.items == {} and not json.loads((tmp_path / "credentials.dat").read_text())["entries"]


@pytest.mark.skipif(sys.platform == "win32", reason="en Windows se usa DPAPI")
def test_default_protector_refuses_when_no_secure_keyring():
    from tally_monitor.security.protector import default_protector
    try:
        import keyring  # noqa: F401
    except ImportError:
        with pytest.raises(ProtectionUnavailableError):
            default_protector()


def test_data_dir_follows_each_systems_convention(monkeypatch, tmp_path):
    monkeypatch.delenv(config.ENV_HOME, raising=False)
    monkeypatch.setattr(config.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert config.resolve_paths().home == tmp_path / "xdg" / "TallyMonitor"
    monkeypatch.setenv("XDG_DATA_HOME", "relativa")                # XDG exige ruta absoluta
    assert config.resolve_paths().home.name == "TallyMonitor" and "relativa" not in str(config.resolve_paths().home)
    monkeypatch.setattr(config.sys, "platform", "darwin")
    assert config.resolve_paths().home.as_posix().endswith("Library/Application Support/TallyMonitor")

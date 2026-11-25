import hashlib
import sqlite3
from contextlib import closing

import pytest

from support.fixtures import core, make_core, paths, protector, clock, tally  # noqa: F401,E402
from support.shared import KEY_A
from tally_monitor.core.errors import DatabaseTooNewError
from tally_monitor.core.secret import SecretStr


def user_version(path):
    with closing(sqlite3.connect(path)) as c:
        return c.execute("PRAGMA user_version").fetchone()[0]


def test_first_run_creates_both_databases(make_core, paths):
    c = make_core()
    rep = c.startup.run()
    assert rep.library_ok and not rep.needs_restore and not rep.cache_recreated
    assert paths.library_db.exists() and paths.cache_db.exists()
    assert user_version(paths.library_db) == 3
    assert user_version(paths.cache_db) == 1
    assert rep.daily_backup_created                         # primer arranque: backup automático


def test_daily_backup_once_per_24h(make_core, clock):
    c = make_core()
    assert c.startup.run().daily_backup_created
    assert not make_core().startup.run().daily_backup_created
    clock.advance(hours=23)
    assert not make_core().startup.run().daily_backup_created
    clock.advance(hours=2)
    assert make_core().startup.run().daily_backup_created
    assert len([b for b in c.backups.list_backups() if b.reason == "auto"]) == 2


def test_auto_backup_can_be_disabled(make_core):
    c = make_core()
    c.startup.run()
    c.settings.set("auto_backup", "0")
    for b in c.backups.list_backups():
        c.backups.delete(b.filename)
    assert not make_core().startup.run().daily_backup_created


def test_corrupt_library_asks_for_restore_and_is_not_touched(make_core, paths):
    c = make_core()
    c.startup.run()
    good = c.backups.create_manual()
    for s in ("", "-wal", "-shm"):
        p = paths.home / f"library.db{s}"
        p.unlink(missing_ok=True)
    paths.library_db.write_bytes(b"no soy sqlite" * 200)
    rep = make_core().startup.run()
    assert rep.needs_restore and not rep.library_ok
    assert paths.library_db.read_bytes() == b"no soy sqlite" * 200
    c.backups.restore(good.filename)                      # y se puede recuperar
    assert make_core().startup.run().library_ok


def test_library_from_newer_version_is_refused_untouched(make_core, paths):
    c = make_core()
    c.startup.run()
    conn = sqlite3.connect(paths.library_db)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("PRAGMA user_version = 99")
    conn.close()
    before = hashlib.sha256(paths.library_db.read_bytes()).hexdigest()
    with pytest.raises(DatabaseTooNewError):
        make_core().startup.run()
    assert hashlib.sha256(paths.library_db.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("how", ["corrupt", "newer"])
def test_cache_is_discarded_and_rebuilt(make_core, paths, how):
    make_core().startup.run()
    if how == "corrupt":
        for s in ("-wal", "-shm"):
            (paths.home / f"cache.db{s}").unlink(missing_ok=True)
        paths.cache_db.write_bytes(b"basura" * 100)
    else:
        conn = sqlite3.connect(paths.cache_db)
        conn.execute("PRAGMA user_version = 50")
        conn.close()
    rep = make_core().startup.run()
    assert rep.cache_recreated
    assert user_version(paths.cache_db) == 1


def test_cache_is_never_in_backups(make_core, paths):
    c = make_core()
    c.startup.run()
    assert all(b.filename.startswith("library_") for b in c.backups.list_backups())
    assert not [p for p in paths.backups_dir.iterdir() if "cache" in p.name]


def test_quarantined_credentials_reported(make_core, paths):
    c = make_core()
    c.startup.run()
    c.accounts.add_account("Uno", SecretStr(KEY_A))
    paths.credentials.write_text("roto")
    rep = make_core().startup.run()
    assert rep.credentials_quarantined and rep.marked_no_credential
    assert list(paths.home.glob("credentials.dat.corrupt-*"))


def test_real_migration_with_pre_backup_via_composition(make_core, paths, monkeypatch):
    """Una v4 hipotética: se migra con copia previa 'pre_migracion' y se conservan los datos."""
    from tally_monitor.storage import migrations as mig
    c = make_core()
    c.startup.run()
    c.accounts.add_account("Uno", SecretStr(KEY_A))
    real = mig.load_migrations
    extra = mig.Migration(4, "agrega_nota", "ALTER TABLE data_account ADD COLUMN note TEXT;")
    monkeypatch.setattr("tally_monitor.app.load_migrations",
                        lambda kind: real(kind) + ([extra] if kind == "library" else []))
    c2 = make_core()
    rep = c2.startup.run()
    assert rep.library_migrated_from == 3
    pre = [b for b in c2.backups.list_backups() if b.reason == "pre_migracion"]
    assert len(pre) == 1 and pre[0].schema_version == 3
    assert [a.name for a in c2.accounts.list_accounts()] == ["Uno"]

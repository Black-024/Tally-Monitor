import sqlite3
import threading

import pytest

from support.shared import FakeClock
from tally_monitor.core.errors import BackupError, BackupTooNewError, RestoreFailedError
from tally_monitor.storage.backup import BackupManager
from tally_monitor.storage.database import Database
from tally_monitor.storage.migrations import Migration, MigrationRunner

M1 = Migration(1, "inicial", "CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT);")
M2 = Migration(2, "extra", "ALTER TABLE t ADD COLUMN e TEXT;")


@pytest.fixture
def env(tmp_path):
    clock = FakeClock()
    db = Database(tmp_path / "library.db")
    MigrationRunner(db, [M1], app_version="t").migrate()
    with db.transaction() as c:
        c.execute("INSERT INTO t(v) VALUES ('uno')")
    mgr = BackupManager(db, tmp_path / "backups", clock=clock)
    return db, mgr, clock, tmp_path


def values(db):
    with db.connection() as c:
        return [r[0] for r in c.execute("SELECT v FROM t ORDER BY id")]


def test_create_is_consistent_and_named(env):
    db, mgr, clock, tmp = env
    info = mgr.create("manual")
    assert info.filename == "library_20261111_120000_manual_v1.db" and info.schema_version == 1
    assert mgr.verify(info) == 1
    b = sqlite3.connect(info.path)
    assert [r[0] for r in b.execute("SELECT v FROM t")] == ["uno"]
    assert b.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    b.close()
    assert sorted(p.name for p in (tmp / "backups").iterdir()) == [info.filename]   # sin temporales ni -wal


def test_same_second_does_not_overwrite(env):
    _, mgr, _, _ = env
    a, b = mgr.create("manual"), mgr.create("manual")
    assert a.filename != b.filename and len(mgr.list()) == 2


def test_backup_while_writing_is_consistent(env):
    db, mgr, _, _ = env
    stop = threading.Event()

    def writer():
        i = 0
        while not stop.is_set():
            with db.transaction() as c:
                c.execute("INSERT INTO t(v) VALUES (?)", (f"w{i}",))
            i += 1
    t = threading.Thread(target=writer)
    t.start()
    try:
        infos = [mgr.create("manual") for _ in range(5)]
    finally:
        stop.set()
        t.join()
    assert all(mgr.verify(i) == 1 for i in infos)


def test_retention_per_reason(env):
    _, mgr, clock, _ = env
    for _ in range(9):
        mgr.create("auto")
        clock.advance(minutes=1)
    for _ in range(3):
        mgr.create("manual")
        clock.advance(minutes=1)
    removed = mgr.apply_retention()
    left = mgr.list()
    assert len(removed) == 2
    assert sum(i.reason == "auto" for i in left) == 7 and sum(i.reason == "manual" for i in left) == 3
    newest_auto = max(i.created_at for i in left if i.reason == "auto")
    assert newest_auto.minute == 8                       # se borraron las más viejas


def test_delete_rejects_paths(env):
    _, mgr, _, tmp = env
    (tmp / "secreto.db").write_text("x")
    for bad in ("../secreto.db", "secreto.db", "..\\x.db", "/etc/passwd", "library_x.db"):
        with pytest.raises(BackupError):
            mgr.delete(bad)
    assert (tmp / "secreto.db").exists()


def test_restore_ok_and_safety_copy(env):
    db, mgr, clock, _ = env
    good = mgr.create("manual")
    with db.transaction() as c:
        c.execute("INSERT INTO t(v) VALUES ('dos')")
    clock.advance(minutes=5)
    mgr.restore(good.filename, latest_version=1)
    assert values(db) == ["uno"]
    assert any(i.reason == "pre_restauracion" for i in mgr.list())
    pre = next(i for i in mgr.list() if i.reason == "pre_restauracion")
    b = sqlite3.connect(pre.path)
    assert [r[0] for r in b.execute("SELECT v FROM t ORDER BY id")] == ["uno", "dos"]
    b.close()


def test_restore_failure_rolls_back(env):
    db, mgr, clock, _ = env
    good = mgr.create("manual")
    with db.transaction() as c:
        c.execute("INSERT INTO t(v) VALUES ('dos')")
    clock.advance(minutes=5)

    def fail():
        raise RuntimeError("migración rota")
    with pytest.raises(RestoreFailedError):
        mgr.restore(good.filename, latest_version=1, post_restore=fail)
    assert values(db) == ["uno", "dos"]                 # volvió al estado previo


def test_restore_older_backup_runs_post_restore_migration(env):
    db, mgr, clock, _ = env
    old = mgr.create("manual")                          # esquema v1
    MigrationRunner(db, [M1, M2], app_version="t").migrate()
    clock.advance(minutes=1)
    runner = MigrationRunner(db, [M1, M2], app_version="t")
    mgr.restore(old.filename, latest_version=2, post_restore=runner.migrate)
    assert db.user_version() == 2 and values(db) == ["uno"]


def test_restore_newer_schema_rejected_before_touching(env):
    db, mgr, clock, _ = env
    MigrationRunner(db, [M1, M2], app_version="t").migrate()
    newer = mgr.create("manual")                        # v2
    with pytest.raises(BackupTooNewError):
        mgr.restore(newer.filename, latest_version=1)
    assert not any(i.reason == "pre_restauracion" for i in mgr.list())


def test_corrupt_backup_rejected(env):
    db, mgr, clock, tmp = env
    info = mgr.create("manual")
    info.path.write_bytes(b"basura" * 100)
    with pytest.raises(BackupError):
        mgr.restore(info.filename, latest_version=1)
    assert values(db) == ["uno"]


def test_restore_when_current_db_is_corrupt_keeps_aside_copy(env):
    db, mgr, clock, tmp = env
    good = mgr.create("manual")
    for s in ("", "-wal", "-shm"):
        p = tmp / f"library.db{s}"
        if p.exists():
            p.unlink()
    (tmp / "library.db").write_bytes(b"no soy sqlite" * 50)
    clock.advance(minutes=1)
    mgr.restore(good.filename, latest_version=1)
    assert values(db) == ["uno"]
    assert list(tmp.glob("library.db.corrupt-*"))

import hashlib
import sqlite3

import pytest

from tally_monitor.core.errors import DatabaseTooNewError, MigrationError
from tally_monitor.storage.database import Database
from tally_monitor.storage.migrations import (Migration, MigrationRunner, load_migrations,
                                              split_statements)

M1 = Migration(1, "inicial", "CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT);")
M2 = Migration(2, "agrega_col", "ALTER TABLE t ADD COLUMN extra TEXT DEFAULT 'x';")
M3_BAD = Migration(3, "mala", "CREATE TABLE ok3(a); INSERT INTO no_existe VALUES (1);")


def runner(db, migs, **kw):
    return MigrationRunner(db, migs, app_version="0.0.test", **kw)


def test_packaged_migrations_create_schema(tmp_path):
    for kind, table in (("library", "data_account"), ("cache", "cache_meta")):
        db = Database(tmp_path / f"{kind}.db")
        migs = load_migrations(kind)
        expected = [1, 2, 3] if kind == "library" else [1]
        assert [m.version for m in migs] == expected
        res = MigrationRunner(db, migs, app_version="t").migrate()
        assert (res.from_version, res.to_version) == (0, expected[-1])
        with db.connection() as c:
            names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert table in names
        if kind == "library":
            assert {"state_setting", "app_migration_log", "raw_submission", "data_submission", "data_answer",
                    "state_user_number", "state_favorite", "state_sync"} <= names


def test_library_schema_has_no_credential_columns(tmp_path):
    db = Database(tmp_path / "l.db")
    MigrationRunner(db, load_migrations("library"), app_version="t").migrate()
    with db.connection() as c:
        cols = {r["name"] for r in c.execute("PRAGMA table_info(data_account)")}
    assert not {"api_key", "key", "token", "tally_user_id", "secret"} & cols


def test_idempotent_and_wal(tmp_path):
    db = Database(tmp_path / "l.db")
    r = runner(db, [M1, M2])
    assert r.migrate().applied == (1, 2)
    assert r.migrate().applied == ()
    with db.connection() as c:
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_failed_migration_rolls_back_completely(tmp_path):
    db = Database(tmp_path / "l.db")
    runner(db, [M1, M2]).migrate()
    with db.transaction() as c:
        c.execute("INSERT INTO t(v) VALUES ('dato')")
    with pytest.raises(MigrationError):
        runner(db, [M1, M2, M3_BAD]).migrate()
    assert db.user_version() == 2                      # no avanzó
    with db.connection() as c:
        names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "ok3" not in names                      # la tabla creada antes del fallo se deshizo
        assert c.execute("SELECT v FROM t").fetchone()[0] == "dato"


def test_newer_database_refused_and_untouched(tmp_path):
    db = Database(tmp_path / "l.db")
    runner(db, [M1, M2]).migrate()
    digest = lambda: hashlib.sha256(db.path.read_bytes()).hexdigest()  # noqa: E731
    with db.connection() as c:
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before = digest()
    with pytest.raises(DatabaseTooNewError):
        runner(db, [M1]).migrate()
    with db.connection() as c:
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    assert db.user_version() == 2 and digest() == before


def test_alter_table_migration_keeps_data(tmp_path):
    db = Database(tmp_path / "l.db")
    runner(db, [M1]).migrate()
    with db.transaction() as c:
        c.execute("INSERT INTO t(v) VALUES ('a'),('b')")
    runner(db, [M1, M2]).migrate()
    with db.connection() as c:
        assert [tuple(r) for r in c.execute("SELECT v, extra FROM t ORDER BY v")] == [("a", "x"), ("b", "x")]


def test_before_migrate_only_for_existing_db(tmp_path):
    db = Database(tmp_path / "l.db")
    calls = []
    runner(db, [M1], before_migrate=lambda a, b: calls.append((a, b))).migrate()
    assert calls == []                                  # base nueva: nada que respaldar
    runner(db, [M1, M2], before_migrate=lambda a, b: calls.append((a, b))).migrate()
    assert calls == [(1, 2)]


def test_failed_pre_backup_aborts_migration(tmp_path):
    db = Database(tmp_path / "l.db")
    runner(db, [M1]).migrate()

    def fail(a, b):
        raise RuntimeError("sin espacio")
    with pytest.raises(RuntimeError):
        runner(db, [M1, M2], before_migrate=fail).migrate()
    assert db.user_version() == 1


def test_non_consecutive_rejected(tmp_path):
    with pytest.raises(MigrationError):
        runner(Database(tmp_path / "l.db"), [M1, Migration(3, "x", "SELECT 1;")])


def test_split_statements_handles_triggers_and_comments():
    sql = """-- comentario; con punto y coma
    CREATE TABLE a(x);
    CREATE TRIGGER tr AFTER INSERT ON a BEGIN
      UPDATE a SET x = 1; INSERT INTO a VALUES (2);
    END;
    INSERT INTO a VALUES ('un;texto');
    """
    st = split_statements(sql)
    assert len(st) == 3 and st[1].startswith("CREATE TRIGGER") and "un;texto" in st[2]
    with pytest.raises(MigrationError):
        split_statements("CREATE TABLE b(x")


def test_missing_migration_folder_gives_clear_error(monkeypatch):
    from tally_monitor.core.errors import MigrationError
    from tally_monitor.storage import migrations as mig
    monkeypatch.setattr(mig.resources, "files", lambda pkg: __import__("pathlib").Path("/no/existe"))
    with pytest.raises(MigrationError):
        mig.load_migrations("library")

"""Migraciones versionadas con PRAGMA user_version."""
from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from importlib import resources
from typing import Callable

from ..core.clock import Clock
from ..core.errors import DatabaseTooNewError, MigrationError
from ..core.language import pick as _t
from .database import Database

log = logging.getLogger(__name__)
_FILE_RE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str


@dataclass(frozen=True)
class MigrationResult:
    from_version: int
    to_version: int
    applied: tuple[int, ...]


def load_migrations(kind: str) -> list[Migration]:
    """Lee los .sql empaquetados de migrations_sql/<kind>/."""
    folder = resources.files("tally_monitor.storage") / "migrations_sql" / kind
    if not folder.is_dir():
        raise MigrationError(_t("Faltan los archivos de migración de la base de datos (instalación incompleta).", "The database migration files are missing (incomplete installation)."))
    found = []
    for entry in folder.iterdir():
        m = _FILE_RE.match(entry.name)
        if m:
            found.append(Migration(int(m.group(1)), m.group(2), entry.read_text(encoding="utf-8")))
    return sorted(found, key=lambda x: x.version)


def split_statements(sql: str) -> list[str]:
    """Separa un script en sentencias completas (respeta triggers, comentarios y cadenas)."""
    out, buf = [], ""
    for line in sql.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            if buf.strip():
                out.append(buf.strip())
            buf = ""
    if buf.strip() and not all(l.strip().startswith("--") or not l.strip() for l in buf.splitlines()):
        raise MigrationError(_t("Migración con una sentencia incompleta.", "Migration with an incomplete statement."))
    return out


class MigrationRunner:
    def __init__(self, db: Database, migrations: list[Migration], *, app_version: str,
                 clock: Clock | None = None,
                 before_migrate: Callable[[int, int], None] | None = None) -> None:
        versions = [m.version for m in migrations]
        if versions != list(range(1, len(versions) + 1)):
            raise MigrationError(_t("Las migraciones deben ser consecutivas desde 1.", "Migrations must be consecutive starting at 1."))
        self._db, self._migrations = db, migrations
        self._app_version = app_version
        self._clock = clock or Clock()
        self._before = before_migrate

    @property
    def latest(self) -> int:
        return len(self._migrations)

    def migrate(self) -> MigrationResult:
        current = self._db.user_version()
        if current > self.latest:
            raise DatabaseTooNewError()
        pending = [m for m in self._migrations if m.version > current]
        if not pending:
            return MigrationResult(current, current, ())
        if self._before is not None and current > 0:
            # Si la copia previa falla, no se migra.
            self._before(current, self.latest)
        applied = []
        for m in pending:
            try:
                self._apply(m)
            except Exception as exc:
                log.error("Migración %s falló: %s", m.version, type(exc).__name__)
                raise MigrationError() from exc
            applied.append(m.version)
            log.info("Migración %s (%s) aplicada", m.version, m.name)
        return MigrationResult(current, self.latest, tuple(applied))

    def _apply(self, m: Migration) -> None:
        statements = split_statements(m.sql)
        with self._db.transaction() as conn:
            for st in statements:
                conn.execute(st)
            has_log = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='app_migration_log'").fetchone()
            if has_log:
                conn.execute(
                    "INSERT INTO app_migration_log(version, name, applied_at, app_version) VALUES (?,?,?,?)",
                    (m.version, m.name, self._clock.iso(), self._app_version))
            conn.execute(f"PRAGMA user_version = {int(m.version)}")

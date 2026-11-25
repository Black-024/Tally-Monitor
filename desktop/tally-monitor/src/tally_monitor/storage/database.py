"""Acceso a SQLite: una conexión nueva por operación, serializada con un candado."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class Database:
    """Representa un archivo SQLite. Cada `connection()` abre una conexión nueva,
    en modo autocommit; `transaction()` agrupa operaciones con BEGIN IMMEDIATE.
    El candado (reentrante) serializa el acceso y permite que restaurar un backup
    garantice que nadie más usa el archivo."""

    def __init__(self, path: Path, *, synchronous: str = "FULL") -> None:
        if synchronous not in ("FULL", "NORMAL"):
            raise ValueError("synchronous inválido")
        self.path = Path(path)
        self._synchronous = synchronous
        self.lock = threading.RLock()

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, isolation_level=None, timeout=5.0)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(f"PRAGMA synchronous={self._synchronous}")
        except BaseException:
            conn.close()          # p. ej. archivo que no es una base de datos
            raise
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        with self.lock:
            conn = self._open()
            try:
                yield conn
            finally:
                conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")

    def user_version(self) -> int:
        with self.connection() as conn:
            return int(conn.execute("PRAGMA user_version").fetchone()[0])

    def quick_check(self) -> list[str]:
        """Devuelve [] si está sano; si no, descripciones del problema."""
        try:
            with self.connection() as conn:
                rows = [r[0] for r in conn.execute("PRAGMA quick_check").fetchall()]
        except sqlite3.DatabaseError as exc:
            return [f"{type(exc).__name__}"]
        return [] if rows == ["ok"] else rows[:5]

    def remove_files(self) -> None:
        """Elimina el archivo y sus -wal/-shm (solo para cache.db)."""
        with self.lock:
            for suffix in ("", "-wal", "-shm"):
                p = Path(str(self.path) + suffix)
                if p.exists():
                    p.unlink()

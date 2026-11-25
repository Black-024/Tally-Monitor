"""Acceso a la tabla data_account. Nunca maneja claves."""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass

from ..core.clock import Clock
from ..core.errors import AccountNameTakenError, AccountNotFoundError
from .database import Database

STATUSES = ("unverified", "active", "key_rejected", "check_failed", "no_credential")


@dataclass(frozen=True)
class Account:
    account_id: str
    name: str
    status: str
    last_check_result: str | None
    last_checked_at: str | None
    last_validated_at: str | None
    created_at: str
    updated_at: str


_FIELDS = ("account_id", "name", "status", "last_check_result", "last_checked_at",
           "last_validated_at", "created_at", "updated_at")


def _row(r: sqlite3.Row) -> Account:
    # Tolera columnas que agreguen migraciones futuras.
    return Account(**{k: r[k] for k in _FIELDS})


class AccountsRepository:
    def __init__(self, db: Database, clock: Clock | None = None) -> None:
        self._db = db
        self._clock = clock or Clock()

    def add(self, name: str, *, status: str = "unverified", last_check_result: str | None = None,
            validated: bool = False, account_id: str | None = None) -> Account:
        now = self._clock.iso()
        aid = account_id or str(uuid.uuid4())
        try:
            with self._db.transaction() as c:
                c.execute(
                    "INSERT INTO data_account(account_id,name,status,last_check_result,last_checked_at,"
                    "last_validated_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (aid, name, status, last_check_result, now if last_check_result else None,
                     now if validated else None, now, now))
        except sqlite3.IntegrityError as exc:
            if "name" in str(exc):
                raise AccountNameTakenError() from exc
            raise
        return self.get(aid)

    def get(self, account_id: str) -> Account:
        with self._db.connection() as c:
            r = c.execute("SELECT * FROM data_account WHERE account_id=?", (account_id,)).fetchone()
        if r is None:
            raise AccountNotFoundError()
        return _row(r)

    def list(self) -> list[Account]:
        with self._db.connection() as c:
            rows = c.execute("SELECT * FROM data_account ORDER BY created_at, rowid").fetchall()
        return [_row(r) for r in rows]

    def name_exists(self, name: str, *, exclude_id: str | None = None) -> bool:
        with self._db.connection() as c:
            r = c.execute("SELECT account_id FROM data_account WHERE name=? COLLATE NOCASE",
                          (name,)).fetchone()
        return r is not None and r["account_id"] != exclude_id

    def rename(self, account_id: str, name: str) -> Account:
        try:
            with self._db.transaction() as c:
                cur = c.execute("UPDATE data_account SET name=?, updated_at=? WHERE account_id=?",
                                (name, self._clock.iso(), account_id))
                if cur.rowcount == 0:
                    raise AccountNotFoundError()
        except sqlite3.IntegrityError as exc:
            raise AccountNameTakenError() from exc
        return self.get(account_id)

    def set_check(self, account_id: str, *, status: str, result: str) -> Account:
        """Registra el resultado de una comprobación. `last_validated_at` solo avanza si result == 'ok'."""
        if status not in STATUSES:
            raise ValueError("estado inválido")
        now = self._clock.iso()
        with self._db.transaction() as c:
            cur = c.execute(
                "UPDATE data_account SET status=?, last_check_result=?, last_checked_at=?, "
                "last_validated_at=CASE WHEN ?='ok' THEN ? ELSE last_validated_at END, updated_at=? "
                "WHERE account_id=?", (status, result, now, result, now, now, account_id))
            if cur.rowcount == 0:
                raise AccountNotFoundError()
        return self.get(account_id)

    def set_status(self, account_id: str, status: str) -> Account:
        if status not in STATUSES:
            raise ValueError("estado inválido")
        with self._db.transaction() as c:
            cur = c.execute("UPDATE data_account SET status=?, updated_at=? WHERE account_id=?",
                            (status, self._clock.iso(), account_id))
            if cur.rowcount == 0:
                raise AccountNotFoundError()
        return self.get(account_id)

    def delete(self, account_id: str) -> None:
        with self._db.transaction() as c:
            cur = c.execute("DELETE FROM data_account WHERE account_id=?", (account_id,))
            if cur.rowcount == 0:
                raise AccountNotFoundError()

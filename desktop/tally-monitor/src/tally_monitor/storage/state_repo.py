"""Estado persistente que no se puede reconstruir: favoritos, recientes y marca de sincronización."""
from __future__ import annotations

from dataclasses import dataclass

from ..core.clock import Clock
from .database import Database

MAX_RECENTS = 10


@dataclass(frozen=True)
class SyncState:
    newest_submitted_at: str | None
    newest_submission_id: str | None
    last_sync_at: str | None
    last_full_reconcile_at: str | None
    last_error: str | None


class StateRepository:
    def __init__(self, db: Database, clock: Clock | None = None) -> None:
        self._db, self._clock = db, clock or Clock()

    # favoritos
    def set_favorite(self, account_id: str, form_id: str, value: bool) -> None:
        with self._db.transaction() as c:
            if value:
                c.execute("INSERT OR IGNORE INTO state_favorite(account_id,form_id) VALUES (?,?)",
                          (account_id, form_id))
            else:
                c.execute("DELETE FROM state_favorite WHERE account_id=? AND form_id=?", (account_id, form_id))

    def favorites(self, account_id: str) -> set[str]:
        with self._db.connection() as c:
            return {r[0] for r in c.execute("SELECT form_id FROM state_favorite WHERE account_id=?", (account_id,))}

    # recientes
    def touch_recent(self, account_id: str, form_id: str) -> None:
        with self._db.transaction() as c:
            c.execute("INSERT INTO state_recent(account_id,form_id,opened_at) VALUES (?,?,?) "
                      "ON CONFLICT(account_id,form_id) DO UPDATE SET opened_at=excluded.opened_at",
                      (account_id, form_id, self._clock.iso()))
            c.execute("DELETE FROM state_recent WHERE account_id=? AND form_id NOT IN ("
                      "SELECT form_id FROM state_recent WHERE account_id=? ORDER BY opened_at DESC, rowid DESC LIMIT ?)",
                      (account_id, account_id, MAX_RECENTS))

    def recents(self, account_id: str) -> list[str]:
        with self._db.connection() as c:
            return [r[0] for r in c.execute("SELECT form_id FROM state_recent WHERE account_id=? "
                                            "ORDER BY opened_at DESC, rowid DESC", (account_id,))]

    # sincronización
    def get_sync(self, account_id: str, form_id: str) -> SyncState | None:
        with self._db.connection() as c:
            r = c.execute("SELECT * FROM state_sync WHERE account_id=? AND form_id=?", (account_id, form_id)).fetchone()
        return SyncState(r["newest_submitted_at"], r["newest_submission_id"], r["last_sync_at"],
                         r["last_full_reconcile_at"], r["last_error"]) if r else None

    def save_sync_ok(self, account_id: str, form_id: str, *, newest_at: str | None, newest_id: str | None,
                     full: bool) -> None:
        now = self._clock.iso()
        with self._db.transaction() as c:
            c.execute("INSERT INTO state_sync(account_id,form_id,newest_submitted_at,newest_submission_id,"
                      "last_sync_at,last_full_reconcile_at,last_error) VALUES (?,?,?,?,?,?,NULL) "
                      "ON CONFLICT(account_id,form_id) DO UPDATE SET newest_submitted_at=excluded.newest_submitted_at,"
                      "newest_submission_id=excluded.newest_submission_id,last_sync_at=excluded.last_sync_at,"
                      "last_full_reconcile_at=COALESCE(excluded.last_full_reconcile_at,last_full_reconcile_at),"
                      "last_error=NULL",
                      (account_id, form_id, newest_at, newest_id, now, now if full else None))

    def save_sync_error(self, account_id: str, form_id: str, category: str) -> None:
        with self._db.transaction() as c:
            c.execute("INSERT INTO state_sync(account_id,form_id,last_error) VALUES (?,?,?) "
                      "ON CONFLICT(account_id,form_id) DO UPDATE SET last_error=excluded.last_error",
                      (account_id, form_id, category))

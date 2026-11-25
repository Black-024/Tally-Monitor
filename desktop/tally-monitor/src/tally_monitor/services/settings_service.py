"""Preferencias simples (tabla state_setting)."""
from __future__ import annotations

from ..core.clock import Clock
from ..storage.database import Database

_ALLOWED = {"log_level": ("DEBUG", "INFO", "WARNING", "ERROR"),
            "auto_backup": ("1", "0"),
            "sync_mode": ("manual", "auto"),
            "update_check": ("1", "0"),
            "theme": ("dark", "light"),
            "notify_mode": ("off", "on"),
            "tray_hint_shown": ("0", "1"),
            "notify_interval_min": ("15", "30", "60", "360")}
_DEFAULTS = {"log_level": "INFO", "auto_backup": "1", "sync_mode": "manual", "update_check": "0", "theme": "dark",
             "notify_mode": "off", "tray_hint_shown": "0", "notify_interval_min": "60", "notified_new_total": "0"}
_VALIDATORS = {"notified_new_total": lambda v: v.isascii() and v.isdigit() and len(v) <= 9}


class SettingsService:
    def __init__(self, db: Database, clock: Clock | None = None) -> None:
        self._db, self._clock = db, clock or Clock()

    def get(self, key: str) -> str:
        if key not in _DEFAULTS:
            raise KeyError(key)
        with self._db.connection() as c:
            r = c.execute("SELECT value FROM state_setting WHERE key=?", (key,)).fetchone()
        return r["value"] if r else _DEFAULTS[key]

    def set(self, key: str, value: str) -> None:
        if key in _VALIDATORS:
            ok = isinstance(value, str) and _VALIDATORS[key](value)
        else:
            ok = key in _ALLOWED and value in _ALLOWED[key]
        if not ok:
            raise ValueError("Preferencia inválida")
        with self._db.transaction() as c:
            c.execute("INSERT INTO state_setting(key,value,updated_at) VALUES (?,?,?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                      (key, value, self._clock.iso()))

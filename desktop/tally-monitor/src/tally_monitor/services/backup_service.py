"""Backups de library.db: automático diario, manual, listado, restauración."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Callable

from ..core.clock import Clock
from ..storage.backup import BackupInfo, BackupManager  # noqa: F401  (BackupInfo se re-exporta a la interfaz)

log = logging.getLogger(__name__)
AUTO_INTERVAL = timedelta(hours=24)


class BackupService:
    def __init__(self, manager: BackupManager, *, latest_schema: int,
                 migrate: Callable[[], None] | None = None, clock: Clock | None = None,
                 on_restored: Callable[[], None] | None = None) -> None:
        self._m, self._latest, self._migrate = manager, latest_schema, migrate
        self._on_restored = on_restored
        self._clock = clock or Clock()

    def list_backups(self) -> list[BackupInfo]:
        return self._m.list()

    def create_manual(self) -> BackupInfo:
        return self._m.create("manual")

    def ensure_daily_backup(self) -> BackupInfo | None:
        """Crea un backup 'auto' si el último tiene más de 24 h (o no hay ninguno)."""
        autos = [i for i in self._m.list() if i.reason == "auto"]
        if autos and self._clock.now() - autos[0].created_at < AUTO_INTERVAL:
            return None
        info = self._m.create("auto")
        self._m.apply_retention()
        return info

    def create_pre_reconciliation(self) -> BackupInfo:
        """Copia de seguridad previa a una reconciliación completa."""
        info = self._m.create("pre_reconciliacion")
        self._m.apply_retention()
        return info

    def verify(self, filename: str) -> int:
        return self._m.verify(self._m.find(filename))

    def restore(self, filename: str) -> BackupInfo:
        info = self._m.restore(filename, latest_version=self._latest, post_restore=self._migrate)
        if self._on_restored is not None:
            self._on_restored()      # p. ej. marcar cuentas que quedaron sin clave
        return info

    def delete(self, filename: str) -> None:
        self._m.delete(filename)

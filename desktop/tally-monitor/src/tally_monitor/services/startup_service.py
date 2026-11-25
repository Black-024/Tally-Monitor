"""Arranque: bases, migraciones, integridad, backup diario y coherencia de credenciales."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..core.errors import BackupError
from ..core.language import pick as _t
from ..storage.database import Database
from ..storage.migrations import MigrationRunner
from .account_service import AccountService
from .backup_service import BackupService
from .settings_service import SettingsService

log = logging.getLogger(__name__)


@dataclass
class StartupReport:
    library_ok: bool = True
    needs_restore: bool = False                 # library.db dañada: ofrecer restaurar un backup
    library_migrated_from: int | None = None
    cache_recreated: bool = False
    daily_backup_created: bool = False
    daily_backup_error: str | None = None
    orphans_removed: list[str] = field(default_factory=list)
    marked_no_credential: list[str] = field(default_factory=list)
    credentials_quarantined: str | None = None  # nombre del archivo ilegible apartado
    messages: list[str] = field(default_factory=list)


class StartupService:
    def __init__(self, *, library: Database, cache: Database, library_runner: MigrationRunner,
                 cache_runner: MigrationRunner, backups: BackupService, accounts: AccountService,
                 settings: SettingsService, store) -> None:
        self._library, self._cache = library, cache
        self._lib_runner, self._cache_runner = library_runner, cache_runner
        self._backups, self._accounts, self._settings, self._store = backups, accounts, settings, store

    def run(self) -> StartupReport:
        """Puede lanzar DatabaseTooNewError o MigrationError (la interfaz los muestra y no continúa)."""
        rep = StartupReport()
        self._prepare_cache(rep)

        # 1) integridad ANTES de tocar nada
        if self._library.path.exists() and self._library.quick_check():
            rep.library_ok, rep.needs_restore = False, True
            rep.messages.append(_t("La base de datos de la biblioteca está dañada. Restaurá una copia de seguridad.", "The library database is damaged. Restore a backup."))
            return rep

        # 2) migraciones (con backup previo automático)
        result = self._lib_runner.migrate()
        if result.applied:
            rep.library_migrated_from = result.from_version

        # 3) backup diario
        if self._settings.get("auto_backup") == "1":
            try:
                rep.daily_backup_created = self._backups.ensure_daily_backup() is not None
            except BackupError as exc:
                rep.daily_backup_error = exc.user_message
                rep.messages.append(_t("No se pudo crear la copia de seguridad diaria.", "The daily backup could not be created."))

        # 4) coherencia con el almacén de credenciales
        rec = self._accounts.reconcile_credentials()
        rep.orphans_removed, rep.marked_no_credential = rec["orphans_removed"], rec["marked_no_credential"]
        if self._store.last_quarantine is not None:
            rep.credentials_quarantined = self._store.last_quarantine.name
            rep.messages.append(_t("El archivo de credenciales estaba dañado y se apartó; reingresá las claves.", "The credentials file was damaged and has been set aside; re-enter your keys."))
        if rep.marked_no_credential:
            rep.messages.append(_t("Hay cuentas sin clave guardada: usá «Reemplazar clave».", "Some accounts have no saved key: use \"Replace key\"."))
        return rep

    def _prepare_cache(self, rep: StartupReport) -> None:
        """cache.db es descartable: si es ilegible, más nueva que la app o falla, se recrea."""
        try:
            if self._cache.path.exists() and (self._cache.quick_check()
                                              or self._cache.user_version() > self._cache_runner.latest):
                raise ValueError("cache incompatible")
            self._cache_runner.migrate()
        except Exception as exc:
            log.warning("cache.db se recreará (%s)", type(exc).__name__)
            self._cache.remove_files()
            self._cache_runner.migrate()
            rep.cache_recreated = True

"""Estado final de la aplicación para el informe del modo prueba."""
from __future__ import annotations

from ..core.config import AppPaths
from ..security.credential_store import CredentialStore
from ..storage.accounts_repo import AccountsRepository
from ..storage.diagnostics_repo import DiagnosticsRepository
from .backup_service import BackupService
from .diagnostic_report import build_report
from .settings_service import SettingsService


class DiagnosticsService:
    def __init__(self, repo: DiagnosticsRepository, accounts: AccountsRepository, store: CredentialStore,
                 backups: BackupService, settings: SettingsService, paths: AppPaths) -> None:
        self._repo, self._accounts, self._store = repo, accounts, store
        self._backups, self._settings, self._paths = backups, settings, paths

    def snapshot(self) -> dict:
        out = self._repo.snapshot()
        ids = {a.account_id for a in self._accounts.list()}
        stored = self._store.ids()
        out["credenciales"] = {"guardadas": len(stored), "cuentas": len(ids),
                               "coinciden_con_cuentas": stored == ids,
                               "archivo_existe": self._paths.credentials.exists()}
        by_reason: dict[str, int] = {}
        for b in self._backups.list_backups():
            by_reason[b.reason] = by_reason.get(b.reason, 0) + 1
        out["copias_de_seguridad"] = {"total": sum(by_reason.values()), "por_motivo": by_reason}
        out["ajustes"] = {k: self._settings.get(k) for k in ("log_level", "auto_backup", "sync_mode")}
        return out

    def report(self, version: str) -> str:
        """Texto seguro para copiar: nunca falla (si algo no se puede leer, lo dice)."""
        try:
            snap = self.snapshot()
        except Exception:  # noqa: BLE001 - el informe debe poder generarse con la base dañada
            snap = None
        return build_report(version, snap, self._paths.logs_dir)

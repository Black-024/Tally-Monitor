"""Lo que la interfaz recibe al arrancar: solo servicios y datos de presentación."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..services.account_service import AccountService
from ..services.backup_service import BackupService
from ..services.analysis_service import AnalysisService
from ..services.export_service import ExportService
from ..services.notify_service import NewResponsesChecker
from ..services.settings_service import SettingsService
from ..services.survey_service import FavoritesService, SurveyService
from ..services.sync_service import SyncService
from ..services.update_service import UpdateService


@dataclass
class AppContext:
    accounts: AccountService
    backups: BackupService
    settings: SettingsService
    data_dir: str
    logs_dir: str
    app_version: str
    startup_messages: list[str] = field(default_factory=list)
    degraded: bool = False          # base dañada: solo se permite restaurar una copia
    test_mode: bool = False         # modo prueba: se muestra un aviso y se registra la sesión
    sync: SyncService | None = None
    surveys: SurveyService | None = None
    favorites: FavoritesService | None = None
    analysis: AnalysisService | None = None
    export: ExportService | None = None
    apply_theme: Callable[[str], None] = lambda name: None    # cambia el tema de toda la aplicación en vivo
    updates: UpdateService | None = None
    notifier: NewResponsesChecker | None = None      # avisos de respuestas nuevas (lógica sin Qt)
    diagnostic_report: Callable[[], str] | None = None
    note: Callable[..., None] = lambda *a, **k: None    # registro de eventos de pantalla (no-op fuera del modo prueba)

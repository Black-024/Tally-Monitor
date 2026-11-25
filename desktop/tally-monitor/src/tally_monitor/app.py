"""Raíz de composición: construye el núcleo y lo entrega a quien lo use (la interfaz, más adelante)."""
from __future__ import annotations

from dataclasses import dataclass

from ._version import RELEASES_REPO, __version__
from .api.client import TallyClient
from .core.clock import Clock
from .core.config import AppPaths, resolve_paths
from .core.logging_setup import setup_logging
from .security.credential_store import CredentialStore
from .security.protector import CredentialProtector, default_protector
from .services.account_service import AccountService
from .services.backup_service import BackupService
from .services.analysis_service import AnalysisService
from .services.export_service import ExportService
from .api.update_client import UpdateClient
from .services.update_service import UpdateService
from .services.diagnostics_service import DiagnosticsService
from .services.instrumentation import instrument
from .services.notify_service import NewResponsesChecker
from .services.settings_service import SettingsService
from .services.survey_service import FavoritesService, SurveyService
from .services.sync_service import SyncService
from .services.startup_service import StartupService
from .storage.accounts_repo import AccountsRepository
from .storage.backup import BackupManager
from .storage.analytics_repo import AnalyticsRepository
from .storage.database import Database
from .storage.diagnostics_repo import DiagnosticsRepository
from .storage.state_repo import StateRepository
from .storage.submissions_repo import SubmissionsRepository
from .storage.surveys_repo import SurveysRepository
from .storage.meta_repo import MetaRepository
from .storage.migrations import MigrationRunner, load_migrations


@dataclass
class Core:
    paths: AppPaths
    accounts: AccountService
    backups: BackupService
    settings: SettingsService
    startup: StartupService
    sync: SyncService
    surveys: SurveyService
    favorites: FavoritesService
    diagnostics: DiagnosticsService
    analysis: AnalysisService
    export: ExportService
    updates: UpdateService | None = None
    notifier: NewResponsesChecker | None = None


def build_core(*, paths: AppPaths | None = None, protector: CredentialProtector | None = None,
               client: TallyClient | None = None, clock: Clock | None = None,
               configure_logging: bool = True, recorder=None,
               update_client: UpdateClient | None = None) -> Core:
    """`recorder` (solo modo prueba): registra cada llamada a los servicios y cada solicitud a Tally."""
    paths = paths or resolve_paths()
    paths.ensure()
    clock = clock or Clock()
    if configure_logging:
        setup_logging(paths.logs_dir)
    protector = protector or default_protector()     # en no-Windows lanza: no hay clave sin cifrar
    client = client or TallyClient(on_event=recorder.request if recorder else None)

    library = Database(paths.library_db, synchronous="FULL")
    cache = Database(paths.cache_db, synchronous="NORMAL")
    lib_migrations, cache_migrations = load_migrations("library"), load_migrations("cache")

    manager = BackupManager(library, paths.backups_dir, clock=clock)
    lib_runner = MigrationRunner(
        library, lib_migrations, app_version=__version__, clock=clock,
        before_migrate=lambda cur, new: manager.create("pre_migracion"))
    cache_runner = MigrationRunner(cache, cache_migrations, app_version=__version__, clock=clock)

    store = CredentialStore(paths.credentials, protector, clock)
    repo = AccountsRepository(library, clock)
    accounts = AccountService(repo, store, client, clock)
    backups = BackupService(manager, latest_schema=lib_runner.latest, migrate=lib_runner.migrate, clock=clock,
                            on_restored=accounts.reconcile_credentials)
    settings = SettingsService(library, clock)
    startup = StartupService(library=library, cache=cache, library_runner=lib_runner,
                             cache_runner=cache_runner, backups=backups, accounts=accounts,
                             settings=settings, store=store)
    surveys_repo, subs_repo, state_repo = (SurveysRepository(library, clock), SubmissionsRepository(library, clock),
                                           StateRepository(library, clock))
    sync = SyncService(surveys_repo, subs_repo, state_repo, store, client, clock,
                       before_reconcile=backups.create_pre_reconciliation)
    surveys = SurveyService(surveys_repo, subs_repo, state_repo, MetaRepository(library), clock)
    favorites = FavoritesService(state_repo)
    diagnostics = DiagnosticsService(DiagnosticsRepository(library, cache), repo, store, backups, settings, paths)
    analysis = AnalysisService(AnalyticsRepository(library), surveys_repo, clock)
    analytics_repo = AnalyticsRepository(library)
    export = ExportService(analysis, analytics_repo, surveys_repo, clock)
    updates = UpdateService(update_client or UpdateClient(), settings, __version__, RELEASES_REPO)
    core = Core(paths, accounts, backups, settings, startup, sync, surveys, favorites, diagnostics, analysis, export, updates,
                NewResponsesChecker(accounts, sync, surveys, settings, clock))
    if recorder is not None:
        for name in ("accounts", "backups", "settings", "startup", "sync", "surveys", "favorites", "analysis", "export"):
            setattr(core, name, instrument(getattr(core, name), name, recorder))
    return core

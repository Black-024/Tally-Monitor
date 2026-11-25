"""Punto de entrada: py -m tally_monitor   (con PYTHONPATH=src o instalado con pip install -e .)"""
import logging
import sys

from ._version import __version__
from .app import build_core
from .core.errors import TallyMonitorError
from .core.language import pick


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--self-check" in args:
        from . import selfcheck
        return selfcheck.run()
    if "--version" in args:
        sys.stdout and sys.stdout.write(f"{__version__}\n")
        return 0
    test_mode = "--test" in args
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError:
        sys.stderr.write(pick("Falta PySide6. Instalalo con:  py -m pip install PySide6\n", "PySide6 is missing. Install it with:  py -m pip install PySide6\n"))
        return 2
    from .ui import strings as S
    from .ui.context import AppContext
    from .ui.main_window import MainWindow
    from .ui.theme.qss import build_qss
    from .ui.workers import TaskRunner

    app = QApplication(sys.argv[:1])
    app.setApplicationName(S.APP_NAME)
    app.setDesktopFileName("tally-monitor")     # Linux: une la ventana con su lanzador (.desktop) y su ícono
    app.setStyle("Fusion")
    from .core.windows_shell import set_app_user_model_id
    from .ui import branding
    from .ui.theme import current as theme
    set_app_user_model_id()
    icon = branding.app_icon()
    if icon is not None:
        app.setWindowIcon(icon)              # barra de tareas y ventanas
    app.setStyleSheet(build_qss(theme.colors()))

    def apply_theme(name: str) -> None:
        theme.set_name(name)
        app.setStyleSheet(build_qss(theme.colors()))
        win = getattr(app, "_tm_window", None)
        if win is not None:
            win.refresh_theme()

    from .core.config import resolve_paths
    from .core.singleton import SingleInstance
    lock = SingleInstance(resolve_paths().home / "tally_monitor.lock")
    if not lock.acquire():
        QMessageBox.information(None, S.APP_NAME, S.ALREADY_RUNNING)
        return 0
    recorder = None
    if test_mode:
        from . import testmode
        recorder = testmode.create_recorder(resolve_paths(), __version__)

    def fatal(text: str, exc: BaseException | None = None) -> int:
        if recorder is not None:
            recorder.finish("error_de_arranque", error=exc)
        QMessageBox.critical(None, S.APP_NAME, text)
        return 1

    try:
        core = build_core(recorder=recorder)
    except TallyMonitorError as exc:                 # incluye ProtectionUnavailableError
        return fatal(exc.user_message, exc)
    if recorder is not None:
        testmode.attach(recorder, core)
    try:
        report = core.startup.run()
    except TallyMonitorError as exc:                 # incluye DatabaseTooNewError y MigrationError
        return fatal(exc.user_message, exc)

    try:
        level = core.settings.get("log_level")
        logging.getLogger("tally_monitor").setLevel(getattr(logging, level, logging.INFO))
    except Exception:  # noqa: BLE001 - el nivel de log nunca debe impedir arrancar
        pass

    if not report.needs_restore:
        try:
            apply_theme(core.settings.get("theme"))
        except Exception:  # noqa: BLE001 - el tema nunca debe impedir arrancar
            pass
    ctx = AppContext(core.accounts, core.backups, core.settings, str(core.paths.home), str(core.paths.logs_dir),
                     __version__, startup_messages=report.messages, degraded=report.needs_restore,
                     sync=core.sync, surveys=core.surveys, favorites=core.favorites, analysis=core.analysis, export=core.export,
                     updates=core.updates, notifier=core.notifier, apply_theme=apply_theme,
                     diagnostic_report=lambda: core.diagnostics.report(__version__),
                     test_mode=test_mode, note=(recorder.event if recorder else (lambda *a, **k: None)))
    runner = TaskRunner()
    window = MainWindow(ctx, runner)
    app._tm_window = window
    window.refresh_theme()
    window.show()
    window.validate_all_in_background()
    window.check_updates_in_background()
    code = app.exec()
    lock.release()
    if recorder is not None:
        path = recorder.finish("normal")
        QMessageBox.information(None, S.APP_NAME, S.TEST_REPORT_SAVED.format(path=path))
        sys.stdout and sys.stdout.write(pick("Informe guardado en: ", "Report saved to: ") + f"{path}\n")
    return code


if __name__ == "__main__":
    sys.exit(main())

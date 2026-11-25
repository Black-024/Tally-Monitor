"""Modo prueba: arranca el registro de la sesión y engancha los errores no capturados.
Se activa con `py -m tally_monitor --test`. Al cerrar, deja un informe JSON en la carpeta informes-prueba."""
from __future__ import annotations

import atexit
import logging
import sys
import threading

from .core.logging_setup import RedactingFilter
from .core.session_report import SessionRecorder, current_frozen, describe_exception, scrub_text


class _RecorderHandler(logging.Handler):
    def __init__(self, recorder: SessionRecorder) -> None:
        super().__init__(level=logging.INFO)
        self._rec = recorder
        self.addFilter(RedactingFilter())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._rec.log(record.levelname, record.name.replace("tally_monitor.", ""), record.getMessage())
            if record.exc_text:
                self._rec.log(record.levelname, record.name, record.exc_text)
        except Exception:  # noqa: BLE001
            pass


def create_recorder(paths, app_version: str) -> SessionRecorder:
    return SessionRecorder(paths.reports_dir, app_version=app_version, frozen=current_frozen())


def attach(recorder: SessionRecorder, core) -> None:
    """Conecta el registrador con el núcleo ya construido y con los errores del programa."""
    recorder.set_state_provider(core.diagnostics.snapshot)
    logging.getLogger("tally_monitor").addHandler(_RecorderHandler(recorder))
    _install_hooks(recorder)
    atexit.register(lambda: recorder.finish("salida_inesperada"))      # no hace nada si ya se cerró bien
    recorder.event("inicio", modo="prueba")


def _install_hooks(recorder: SessionRecorder) -> None:
    prev_hook = sys.excepthook

    def excepthook(tp, exc, tb):
        try:
            if exc is not None and exc.__traceback__ is None:
                exc = exc.with_traceback(tb)
            recorder.event("excepcion", donde="hilo principal", detalle=describe_exception(exc))
        finally:
            prev_hook(tp, exc, tb)

    sys.excepthook = excepthook

    prev_thread = threading.excepthook

    def thread_hook(args):
        try:
            recorder.event("excepcion", donde="hilo de trabajo", detalle=describe_exception(args.exc_value))
        finally:
            prev_thread(args)

    threading.excepthook = thread_hook

    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    except ImportError:
        return
    names = {QtMsgType.QtWarningMsg: "aviso", QtMsgType.QtCriticalMsg: "critico", QtMsgType.QtFatalMsg: "fatal"}

    def qt_handler(kind, _ctx, message):
        if kind in names:
            recorder.event("qt", nivel=names[kind], mensaje=scrub_text(message))

    qInstallMessageHandler(qt_handler)

"""Ejecuta servicios fuera del hilo de la interfaz y entrega el resultado en el hilo principal."""
from __future__ import annotations

import logging
import threading
from typing import Callable

from PySide6.QtCore import QObject, Signal, Slot

from ..core.errors import TallyMonitorError
from . import strings as S

log = logging.getLogger(__name__)


class TaskRunner(QObject):
    """run(fn, on_ok, on_error): fn corre en un hilo; on_ok(resultado) y on_error(error)
    se llaman en el hilo de la interfaz. `error` tiene siempre `.user_message`."""

    _done = Signal(int, object, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._callbacks: dict[int, tuple[Callable | None, Callable | None]] = {}
        self._next = 0
        self._lock = threading.Lock()
        self._done.connect(self._dispatch)

    def run(self, fn: Callable[[], object], on_ok: Callable | None = None,
            on_error: Callable | None = None) -> None:
        with self._lock:
            tid = self._next
            self._next += 1
        self._callbacks[tid] = (on_ok, on_error)

        def target() -> None:
            try:
                result, error = fn(), None
            except TallyMonitorError as exc:
                result, error = None, exc
            except Exception as exc:  # noqa: BLE001 - nunca romper la interfaz
                log.error("Error inesperado en tarea: %s", type(exc).__name__)
                result, error = None, _Unexpected()
            self._done.emit(tid, result, error)

        threading.Thread(target=target, daemon=True).start()

    @Slot(int, object, object)
    def _dispatch(self, tid: int, result, error) -> None:
        on_ok, on_error = self._callbacks.pop(tid, (None, None))
        try:
            if error is None:
                if on_ok:
                    on_ok(result)
            elif on_error:
                on_error(error)
        except Exception as exc:  # noqa: BLE001
            log.error("Error en el manejador de resultado: %s", type(exc).__name__)


class _Unexpected:
    user_message = S.GENERIC_ERROR
    category = "unexpected"

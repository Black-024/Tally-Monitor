"""Espacio de una encuesta: encabezado, «Actualizar» y tres pestañas (Resumen, Respuestas, Exportar)."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from .. import strings as S
from ..context import AppContext
from ..workers import TaskRunner
from .analysis import AnalysisPage
from .exports import ExportsPage
from .survey_detail import SurveyDetailPage

# nombre que usa el modo prueba para «qué pantalla se abrió»
_SCREEN_NOTE = {"resumen": "analisis", "respuestas": "respuestas", "exportar": "exportaciones"}


class SurveyWorkspace(QWidget):
    back_requested = Signal()
    changed = Signal()

    def __init__(self, ctx: AppContext, runner: TaskRunner, parent=None) -> None:
        super().__init__(parent)
        self._ctx = ctx
        self.detail = SurveyDetailPage(ctx, runner)          # Respuestas (y dueña de la sincronización)
        self.analysis = AnalysisPage(ctx, runner)            # Resumen
        self.exports = ExportsPage(ctx, runner, self.analysis.period)
        self.detail.back_requested.connect(self.back_requested.emit)
        self.detail.changed.connect(self._synced)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 8, 32, 16)
        outer.setSpacing(10)
        outer.addWidget(self.detail.head)
        outer.addWidget(self.detail.sync_bar)

        tabs = QHBoxLayout()
        tabs.setSpacing(26)
        self.tab_buttons: dict[str, QPushButton] = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        for key, label in S.TABS:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setProperty("tab", "true")
            b.clicked.connect(lambda _c=False, k=key: self.show_tab(k))
            group.addButton(b)
            tabs.addWidget(b)
            self.tab_buttons[key] = b
        tabs.addStretch(1)
        outer.addLayout(tabs)
        line = QFrame()
        line.setFixedHeight(1)
        line.setProperty("divider", "true")
        outer.addWidget(line)

        self.stack = QStackedWidget()
        self.pages = {"resumen": self.analysis, "respuestas": self.detail, "exportar": self.exports}
        for w in self.pages.values():
            self.stack.addWidget(w)
        outer.addWidget(self.stack, 1)
        self.tab_buttons["resumen"].setChecked(True)
        self.stack.setCurrentWidget(self.analysis)
        self.current_tab = "resumen"

    def open_survey(self, account_id: str, form_id: str) -> None:
        self.detail.open_survey(account_id, form_id)
        self.analysis.open_survey(account_id, form_id)
        self.exports.open_survey(account_id, form_id)
        self.show_tab("resumen")

    def show_tab(self, key: str) -> None:
        self.current_tab = key
        self.tab_buttons[key].setChecked(True)
        self.stack.setCurrentWidget(self.pages[key])
        if key == "exportar":
            self.exports.refresh()
        self._ctx.note("pantalla", pantalla=_SCREEN_NOTE[key])

    def _synced(self) -> None:
        self.analysis.refresh()
        self.exports.refresh()
        self.changed.emit()

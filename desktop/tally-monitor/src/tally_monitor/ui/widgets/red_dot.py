"""Círculo rojo que marca algo pendiente (respuestas sin actualizar). Se dibuja a mano: no depende de estilos."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from .. import strings as S

RED = "#E53935"


class RedDot(QWidget):
    def __init__(self, size: int = 10, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAccessibleName(S.RED_DOT_NAME)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(RED))
        p.drawEllipse(self.rect())
        p.end()

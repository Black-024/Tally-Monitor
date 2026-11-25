"""Etiqueta de estado: el texto siempre acompaña al color. El aspecto sale de la hoja de estilos (propiedad «tone»)."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel

from .. import strings as S
from ..presenters import status_view


class StatusBadge(QLabel):
    def __init__(self, status: str, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("badge", "true")
        self.set_status(status)

    def set_status(self, status: str) -> None:
        label, tone = status_view(status)
        self.setText(label)
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)
        self.setAccessibleName(S.STATUS_ACCESSIBLE.format(label=label))

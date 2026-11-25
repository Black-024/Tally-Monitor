"""Ventana de solo lectura para mostrar textos largos (licencias, privacidad) dentro de la aplicación."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from .. import strings as S


class TextDialog(QDialog):
    def __init__(self, title: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 560)
        lay = QVBoxLayout(self)
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setPlainText(text)
        lay.addWidget(self.view)
        row = QHBoxLayout()
        row.addStretch(1)
        close = QPushButton(S.BTN_CLOSE)
        close.setProperty("variant", "primary")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)

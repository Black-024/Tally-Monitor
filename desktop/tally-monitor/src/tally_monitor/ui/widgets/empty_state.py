"""Estado vacío: título, texto y una acción opcional."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class EmptyState(QWidget):
    action_clicked = Signal()

    def __init__(self, title: str, text: str, action_text: str | None = None, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(10)
        t = QLabel(title)
        t.setProperty("role", "section")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d = QLabel(text)
        d.setProperty("role", "muted")
        d.setWordWrap(True)
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d.setMaximumWidth(460)
        lay.addWidget(t, alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(d, alignment=Qt.AlignmentFlag.AlignCenter)
        if action_text:
            b = QPushButton(action_text)
            b.setProperty("variant", "primary")
            b.clicked.connect(self.action_clicked.emit)
            lay.addWidget(b, alignment=Qt.AlignmentFlag.AlignCenter)

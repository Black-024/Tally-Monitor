"""Barra de meta: «124 de 200 (62 %)», barra de progreso y la estimación. Solo muestra lo que le dan."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from .. import presenters as P


class GoalBar(QWidget):
    def __init__(self, local: int, goal: int, projection, *, show_eta: bool = True, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.line = QLabel(P.goal_line(local, goal, projection))
        self.line.setProperty("role", "muted")
        lay.addWidget(self.line)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(projection.pct)
        self.bar.setTextVisible(False)
        self.bar.setAccessibleName(P.goal_line(local, goal, projection))
        lay.addWidget(self.bar)
        self.eta = QLabel(P.goal_eta_text(projection))
        self.eta.setProperty("role", "meta")
        self.eta.setWordWrap(True)
        self.eta.setVisible(show_eta)
        lay.addWidget(self.eta)

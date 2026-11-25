"""Barras horizontales dibujadas con QPainter (sin dependencias de gráficos). Siempre muestran el número al lado."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QTextOption
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import strings as S
from ..presenters import bar_value_text
from ..theme import current

ROW_H = 32


class BarChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, int, float]] = []
        self._show_pct = True
        self.palette_override: dict | None = None          # para exportar con otro estilo distinto del de la ventana
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _value_text(self, count: int, frac: float) -> str:
        return bar_value_text(count, frac) if self._show_pct else str(count)

    def set_rows(self, rows: list[tuple[str, int, float]], show_pct: bool = True) -> None:
        """rows: (texto, cantidad, fracción 0..1: largo de la barra). show_pct=False muestra solo la cantidad
        (para gráficos donde la fracción es respecto del máximo y no un porcentaje)."""
        self._rows = list(rows)
        self._show_pct = show_pct
        self.setFixedHeight(max(ROW_H, ROW_H * len(self._rows)))
        self.setAccessibleName(S.BAR_CHART_NAME)
        self.setAccessibleDescription("; ".join(f"{t}: {self._value_text(n, f)}" for t, n, f in self._rows))
        self.update()

    def rows(self) -> list[tuple[str, int, float]]:
        return list(self._rows)

    def sizeHint(self) -> QSize:
        return QSize(420, max(ROW_H, ROW_H * len(self._rows)))

    def paintEvent(self, _event) -> None:
        c = self.palette_override or current.colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fm = QFontMetrics(self.font())
        w = self.width()
        label_w = max(120, int(w * 0.34))
        value_w = 110
        bar_x = label_w + 8
        bar_w = max(20, w - bar_x - value_w - 8)
        left = QTextOption(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        right = QTextOption(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        for i, (text, count, frac) in enumerate(self._rows):
            y = i * ROW_H
            p.setPen(QColor(c["text"]))
            p.drawText(QRectF(0, y, label_w, ROW_H), fm.elidedText(text, Qt.TextElideMode.ElideRight, label_w), left)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(c["surface2"]))
            p.drawRoundedRect(QRectF(bar_x, y + 8, bar_w, ROW_H - 16), 7, 7)
            if count > 0 and frac > 0:
                p.setBrush(QColor(c["accent"]))
                p.drawRoundedRect(QRectF(bar_x, y + 8, max(4.0, bar_w * min(1.0, frac)), ROW_H - 16), 7, 7)
            p.setPen(QColor(c["muted"]))
            p.drawText(QRectF(bar_x + bar_w + 8, y, value_w, ROW_H), self._value_text(count, frac), right)
        p.end()

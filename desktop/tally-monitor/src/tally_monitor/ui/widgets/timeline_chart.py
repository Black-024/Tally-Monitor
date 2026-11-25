"""Barras verticales de respuestas en el tiempo, dibujadas con QPainter."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QTextOption
from PySide6.QtWidgets import QSizePolicy, QWidget

from .. import strings as S
from ..theme import current


class TimelineChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._series: list[tuple[str, int]] = []
        self.palette_override: dict | None = None          # para exportar con otro estilo distinto del de la ventana
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_series(self, series: list[tuple[str, int]]) -> None:
        """series: (etiqueta, cantidad) en orden cronológico."""
        self._series = list(series)
        total = sum(n for _, n in self._series)
        self.setAccessibleName(S.TIMELINE_NAME)
        self.setAccessibleDescription(S.TIMELINE_DESC.format(total=total, n=len(self._series)))
        self.update()

    def series(self) -> list[tuple[str, int]]:
        return list(self._series)

    def sizeHint(self) -> QSize:
        return QSize(520, 190)

    def paintEvent(self, _event) -> None:
        c = self.palette_override or current.colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = len(self._series)
        left, right, top, bottom = 36, 8, 8, 24
        w, h = self.width() - left - right, self.height() - top - bottom
        center = QTextOption(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        right_al = QTextOption(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        p.setPen(QPen(QColor(c["border"]), 1))
        p.drawLine(left, top + h, left + w, top + h)
        if n == 0 or w <= 0 or h <= 0:
            p.end()
            return
        peak = max(1, max(c for _, c in self._series))
        p.setPen(QColor(c["muted"]))
        p.drawText(QRectF(0, top - 4, left - 4, 16), str(peak), right_al)
        p.drawText(QRectF(0, top + h - 12, left - 4, 16), "0", right_al)
        slot = w / n
        bar_w = max(1.0, min(28.0, slot * 0.7))
        p.setPen(Qt.PenStyle.NoPen)
        for i, (_label, count) in enumerate(self._series):
            if count <= 0:
                continue
            bh = max(2.0, h * count / peak)
            p.setBrush(QColor(c["accent"]))
            p.drawRoundedRect(QRectF(left + i * slot + (slot - bar_w) / 2, top + h - bh, bar_w, bh), 4, 4)
        p.setPen(QColor(c["muted"]))
        picks = sorted({0, n // 2, n - 1})
        for i in picks:
            label = self._series[i][0]
            x = left + i * slot + slot / 2 - 40
            x = min(max(x, 0), self.width() - 80)
            p.drawText(QRectF(x, top + h + 4, 80, 18), label, center)
        p.end()

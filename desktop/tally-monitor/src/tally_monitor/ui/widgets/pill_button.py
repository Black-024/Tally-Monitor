"""Botón en forma de píldora dibujado a mano (siempre completamente redondeado, sin depender de estilos).

kind="pill": selector del menú superior (seleccionado = relleno de color de acción).
kind="chip": filtro chico (seleccionado = contorno de acento sobre fondo suave).
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QPushButton

from ..theme import current

_SIZES = {"pill": (36, 22), "chip": (34, 16)}       # (alto, relleno horizontal)


class PillButton(QPushButton):
    def __init__(self, text: str = "", kind: str = "pill", parent=None) -> None:
        super().__init__(text, parent)
        self.kind = kind
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setProperty("pillkind", kind)
        self._badge = False

    def set_badge(self, on: bool) -> None:
        """Muestra u oculta un círculo rojo a la derecha del texto (algo pendiente)."""
        if on != self._badge:
            self._badge = on
            self.updateGeometry()
            self.update()

    def sizeHint(self) -> QSize:
        h, pad = _SIZES[self.kind]
        f = self.font()
        f.setBold(True)                                        # se mide en negrita para que no cambie de ancho al seleccionarse
        return QSize(QFontMetrics(f).horizontalAdvance(self.text()) + 2 * pad + (14 if self._badge else 0), h)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, _event) -> None:
        c = current.colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        radius = rect.height() / 2
        enabled, checked = self.isEnabled(), self.isChecked()
        hover = self.underMouse()
        if self.kind == "pill":
            if checked:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(c["action"]))
                p.drawRoundedRect(rect, radius, radius)
                text_color = c["action_text"]
            else:
                text_color = c["text"] if hover else c["muted"]
        else:
            p.setBrush(QColor(c["surface2"]) if checked else Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(c["accent"] if (checked or hover) else c["border"]), 1.5 if checked else 1))
            p.drawRoundedRect(rect, radius, radius)
            text_color = c["text"] if (checked or hover) else c["muted"]
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(c["accent"]), 2))
            p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)
        f = self.font()
        f.setBold(True if (checked or self.kind == "pill") else False)
        p.setFont(f)
        p.setPen(QColor(text_color if enabled else c["dim"]))
        if self._badge:
            tw = QFontMetrics(f).horizontalAdvance(self.text())
            x0 = (self.width() - (tw + 14)) / 2
            p.drawText(QRectF(x0, 0, tw, self.height()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#E53935"))
            p.drawEllipse(QRectF(x0 + tw + 5, self.height() / 2 - 4.5, 9, 9))
        else:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()

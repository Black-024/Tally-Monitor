"""Ícono de la bandeja del sistema para los avisos (solo Qt; la lógica de cuándo avisar vive en services/notify_service)."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from . import branding
from . import strings as S


def tray_available() -> bool:
    return bool(QSystemTrayIcon.isSystemTrayAvailable())


class TrayController(QObject):
    open_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._tray = None
        self._menu = None

    def _build(self) -> None:
        icon = branding.app_icon()
        if icon is None or icon.isNull():
            icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip(S.NOTIFY_TRAY_TOOLTIP)
        self._menu = QMenu()
        self._menu.addAction(S.NOTIFY_TRAY_OPEN).triggered.connect(lambda _c=False: self.open_requested.emit())
        self._menu.addAction(S.NOTIFY_TRAY_QUIT).triggered.connect(lambda _c=False: self.quit_requested.emit())
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._activated)
        self._tray.messageClicked.connect(self.open_requested.emit)

    def _activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.open_requested.emit()

    def show(self) -> None:
        if self._tray is None:
            self._build()
        self._tray.show()

    def hide(self) -> None:
        if self._tray is not None:
            self._tray.hide()

    def is_visible(self) -> bool:
        return self._tray is not None and bool(self._tray.isVisible())

    def notify(self, title: str, body: str) -> None:
        if self._tray is not None:
            self._tray.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 10000)

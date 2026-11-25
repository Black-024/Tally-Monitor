"""Logo e ícono de la aplicación (opcionales: si no hay archivos de logo, se omiten sin error)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

from ..core.assets import find_icon, find_logo


def app_icon() -> QIcon | None:
    path = find_icon()
    return QIcon(str(path)) if path else None


def logo_pixmap(size: int, style: str) -> QPixmap | None:
    path = find_logo(style)
    if not path:
        return None
    pix = QPixmap(str(path))
    if pix.isNull():
        return None
    return pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

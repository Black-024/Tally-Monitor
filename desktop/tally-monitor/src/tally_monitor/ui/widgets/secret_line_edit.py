"""Campo para la API Key: siempre enmascarado, sin botón de mostrar."""
from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLineEdit

from ...core.secret import SecretStr
from .. import strings as S


class SecretLineEdit(QLineEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)   # el texto no se muestra ni se puede copiar
        self.setMaxLength(200)
        self.setPlaceholderText("tly-…")
        self.setAccessibleName(S.API_KEY_FIELD)

    def secret(self) -> SecretStr:
        return SecretStr(self.text().strip())

    def clear_secret(self) -> None:
        """Vacía el campo y, si el portapapeles todavía contiene la clave, también lo vacía."""
        value = self.text().strip()
        if value:
            clip = QGuiApplication.clipboard()
            if clip is not None and clip.text().strip() == value:
                clip.clear()
        self.clear()

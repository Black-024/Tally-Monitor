"""Diálogos simples de confirmación y de texto."""
from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox, QWidget

from .. import strings as S


def ask_new_name(parent: QWidget, current: str) -> str | None:
    text, ok = QInputDialog.getText(parent, S.RENAME_TITLE, S.RENAME_LABEL, QLineEdit.EchoMode.Normal, current)
    return text.strip() if ok else None


def confirm_destructive(parent: QWidget, title: str, text: str, confirm_label: str) -> bool:
    """Confirmación con «Cancelar» como opción por defecto."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    confirm = box.addButton(confirm_label, QMessageBox.ButtonRole.DestructiveRole)
    cancel = box.addButton(S.BTN_CANCEL, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel)
    box.setEscapeButton(cancel)
    box.exec()
    return box.clickedButton() is confirm


def show_info(parent: QWidget, title: str, text: str) -> None:
    QMessageBox.information(parent, title, text)


def show_error(parent: QWidget, title: str, text: str) -> None:
    QMessageBox.critical(parent, title, text)

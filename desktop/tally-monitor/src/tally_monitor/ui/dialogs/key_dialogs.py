"""Diálogos para ingresar una API Key: agregar cuenta y reemplazar clave."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
                               QVBoxLayout)

from ...core.keyformat import looks_like_api_key
from .. import strings as S
from ..context import AppContext
from ..widgets.secret_line_edit import SecretLineEdit
from ..workers import TaskRunner


class _KeyDialog(QDialog):
    """Base: campo de clave oculto, estado, progreso. El diálogo no se puede cerrar mientras valida."""

    def __init__(self, ctx: AppContext, runner: TaskRunner, title: str, help_text: str, ok_text: str,
                 parent=None, *, suggested_name: str = "", account_id: str = "") -> None:
        super().__init__(parent)
        self._ctx, self._runner = ctx, runner
        self._suggested, self._account_id = suggested_name, account_id
        self._busy = False
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        self._lay = QVBoxLayout(self)
        self._lay.setSpacing(10)
        help_lbl = QLabel(help_text)
        help_lbl.setWordWrap(True)
        help_lbl.setProperty("role", "muted")
        self._lay.addWidget(help_lbl)

        self._extra_fields()

        self._lay.addWidget(QLabel(S.FIELD_KEY))
        self.key_edit = SecretLineEdit()
        self.key_edit.returnPressed.connect(self._submit)
        self.key_edit.textChanged.connect(self._clear_error)
        self._lay.addWidget(self.key_edit)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setProperty("role", "error")
        self._lay.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)           # indeterminada
        self.progress.setTextVisible(False)
        self.progress.hide()
        self._lay.addWidget(self.progress)

        row = QHBoxLayout()
        row.addStretch(1)
        self.cancel_btn = QPushButton(S.BTN_CANCEL)
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton(ok_text)
        self.ok_btn.setProperty("variant", "primary")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._submit)
        row.addWidget(self.cancel_btn)
        row.addWidget(self.ok_btn)
        self._lay.addLayout(row)
        self.key_edit.setFocus()

    # --- a sobrescribir ---
    def _extra_fields(self) -> None: ...
    def _start(self, key):  # pragma: no cover
        raise NotImplementedError
    def _validate_extra(self) -> str | None:
        return None

    # --- común ---
    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.progress.setVisible(busy)
        for w in (self.ok_btn, self.cancel_btn, self.key_edit):
            w.setEnabled(not busy)
        if busy:
            self.status.setProperty("role", "muted")
            self.status.setText(S.VALIDATING)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _show_error(self, message: str) -> None:
        self.status.setProperty("role", "error")
        self.status.setText(message)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _clear_error(self, *_a) -> None:
        if not self._busy:
            self.status.setText("")

    def _submit(self) -> None:
        if self._busy:
            return
        problem = self._validate_extra()
        if problem:
            self._show_error(problem)
            return
        key = self.key_edit.secret()
        if not looks_like_api_key(key.reveal()):
            self._show_error(S.KEY_FORMAT_ERROR)
            return
        self._set_busy(True)
        self._start(key)

    def _failed(self, error) -> None:
        self._set_busy(False)
        self._show_error(error.user_message)
        self.key_edit.setFocus()
        self.key_edit.selectAll()

    def reject(self) -> None:
        if not self._busy:
            super().reject()

    def done(self, result: int) -> None:
        if not self._busy:
            self.key_edit.clear_secret()
            super().done(result)


class AddAccountDialog(_KeyDialog):
    def __init__(self, ctx, runner, suggested_name: str, parent=None) -> None:
        super().__init__(ctx, runner, S.ADD_TITLE, S.ADD_HELP, S.BTN_SAVE_VALIDATE, parent,
                         suggested_name=suggested_name)
        self.account = None

    def _extra_fields(self) -> None:
        self._lay.addWidget(QLabel(S.FIELD_NAME))
        self.name_edit = QLineEdit(self._suggested)
        self.name_edit.setMaxLength(60)
        self.name_edit.setAccessibleName(S.FIELD_NAME)
        self._lay.addWidget(self.name_edit)

    def _validate_extra(self) -> str | None:
        return None if 1 <= len(self.name_edit.text().strip()) <= 60 else S.NAME_LENGTH_ERROR

    def _start(self, key) -> None:
        name = self.name_edit.text()
        self._runner.run(lambda: self._ctx.accounts.add_account(name, key), self._saved, self._failed)

    def _saved(self, account) -> None:
        self.account = account
        self._set_busy(False)
        self.accept()


class ReplaceKeyDialog(_KeyDialog):
    def __init__(self, ctx, runner, account_id: str, account_name: str, parent=None) -> None:
        super().__init__(ctx, runner, f"{S.REPLACE_TITLE} — {account_name}", S.REPLACE_HELP, S.BTN_REPLACE_OK,
                         parent, account_id=account_id)
        self.result_info = None

    def _start(self, key) -> None:
        aid = self._account_id
        self._runner.run(lambda: self._ctx.accounts.replace_key(aid, key), self._replaced, self._failed)

    def _replaced(self, result) -> None:
        self.result_info = result
        self._set_busy(False)
        self.accept()

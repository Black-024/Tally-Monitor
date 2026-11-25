"""Página Cuentas: lista y acciones. Solo usa servicios (a través del TaskRunner)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from .. import presenters as P
from .. import strings as S
from ..context import AppContext
from ..dialogs.key_dialogs import AddAccountDialog, ReplaceKeyDialog
from ..dialogs.simple_dialogs import ask_new_name, confirm_destructive
from ..widgets.empty_state import EmptyState
from ..widgets.status_badge import StatusBadge
from ..workers import TaskRunner


class AccountCard(QFrame):
    def __init__(self, account, page: "AccountsPage") -> None:
        super().__init__()
        self.setObjectName("Card")
        self.account = account
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        top = QHBoxLayout()
        name = QLabel(account.name)
        name.setProperty("role", "section")
        top.addWidget(name)
        top.addWidget(StatusBadge(account.status))
        top.addStretch(1)
        lay.addLayout(top)
        sub = QLabel(P.account_subtitle(account))
        sub.setProperty("role", "muted")
        sub.setWordWrap(True)
        lay.addWidget(sub)
        hint = P.account_help(account)
        if hint:
            h = QLabel(hint)
            h.setWordWrap(True)
            lay.addWidget(h)
        row = QHBoxLayout()
        self.buttons: list[QPushButton] = []
        aid = account.account_id
        for text, handler, variant in (
                (S.BTN_VALIDATE, lambda: page.validate(aid), None),
                (S.BTN_RENAME, lambda: page.rename(account), None),
                (S.BTN_REPLACE, lambda: page.replace_key(account), None),
                (S.BTN_DELETE, lambda: page.delete(account), "danger")):
            b = QPushButton(text)
            if variant:
                b.setProperty("variant", variant)
            b.clicked.connect(handler)
            row.addWidget(b)
            self.buttons.append(b)
        row.addStretch(1)
        lay.addLayout(row)


class AccountsPage(QWidget):
    changed = Signal()      # avisa a otras páginas (Inicio) que las cuentas cambiaron

    def __init__(self, ctx: AppContext, runner: TaskRunner, parent=None) -> None:
        super().__init__(parent)
        self._ctx, self._runner = ctx, runner
        self._accounts: list = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        head = QHBoxLayout()
        title = QLabel(S.ACCOUNTS_TITLE)
        title.setProperty("role", "title")
        head.addWidget(title)
        head.addStretch(1)
        self.add_btn = QPushButton(S.ADD_ACCOUNT)
        self.add_btn.setProperty("variant", "primary")
        self.add_btn.clicked.connect(self.open_add_dialog)
        head.addWidget(self.add_btn)
        outer.addLayout(head)

        self.notice = QLabel("")
        self.notice.setProperty("role", "notice")
        self.notice.setWordWrap(True)
        self.notice.hide()
        outer.addWidget(self.notice)

        self._body = QWidget()
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(0, 8, 0, 0)
        self._body_lay.setSpacing(12)
        self._body_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._body)
        outer.addWidget(scroll, 1)

    # ---------- datos ----------
    def refresh(self) -> None:
        self._runner.run(self._ctx.accounts.list_accounts, self._render, self._on_error)

    def _render(self, accounts) -> None:
        self._accounts = accounts
        while self._body_lay.count():
            item = self._body_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not accounts:
            empty = EmptyState(S.NO_ACCOUNTS_TITLE, S.NO_ACCOUNTS_TEXT, S.ADD_FIRST)
            empty.action_clicked.connect(self.open_add_dialog)
            self._body_lay.addWidget(empty)
        for a in accounts:
            self._body_lay.addWidget(AccountCard(a, self))
        self.changed.emit()

    def _on_error(self, error) -> None:
        self.say(error.user_message)

    def say(self, message: str) -> None:
        self.notice.setText(message)
        self.notice.setVisible(bool(message))

    def _set_busy(self, busy: bool) -> None:
        self.add_btn.setEnabled(not busy)
        for i in range(self._body_lay.count()):
            w = self._body_lay.itemAt(i).widget()
            if isinstance(w, AccountCard):
                for b in w.buttons:
                    b.setEnabled(not busy)
        if busy:
            self.say(S.BUSY)

    # ---------- acciones ----------
    def open_add_dialog(self) -> None:
        dlg = AddAccountDialog(self._ctx, self._runner, P.suggest_account_name([a.name for a in self._accounts]), self)
        if dlg.exec() and dlg.account is not None:
            self.say(S.ACCOUNT_ADDED.format(name=dlg.account.name))
        self.refresh()

    def validate(self, account_id: str) -> None:
        self._set_busy(True)
        self._runner.run(lambda: self._ctx.accounts.validate_account(account_id),
                         lambda out: self._after(S.ACCOUNT_VALIDATE_RESULT.format(name=out.account.name, message=out.message)),
                         lambda e: self._after(e.user_message))

    def _after(self, message: str) -> None:
        self._set_busy(False)
        self.say(message)
        self.refresh()

    def rename(self, account) -> None:
        new = ask_new_name(self, account.name)
        if new is None or new == account.name:
            return
        self._set_busy(True)
        aid = account.account_id
        self._runner.run(lambda: self._ctx.accounts.rename_account(aid, new),
                         lambda a: self._after(S.ACCOUNT_RENAMED.format(name=a.name)),
                         lambda e: self._after(e.user_message))

    def replace_key(self, account) -> None:
        dlg = ReplaceKeyDialog(self._ctx, self._runner, account.account_id, account.name, self)
        if dlg.exec() and dlg.result_info is not None:
            self.say(S.KEY_REPLACED if dlg.result_info.identity_verified
                     else f"{S.KEY_REPLACED} {S.IDENTITY_NOT_VERIFIED}")
        self.refresh()

    def delete(self, account) -> None:
        if not confirm_destructive(self, S.DELETE_TITLE, S.DELETE_TEXT.format(name=account.name), S.DELETE_CONFIRM):
            return
        self._set_busy(True)
        aid = account.account_id
        self._runner.run(lambda: self._ctx.accounts.delete_account(aid),
                         lambda _r: self._after(S.ACCOUNT_DELETED.format(name=account.name)),
                         lambda e: self._after(e.user_message))

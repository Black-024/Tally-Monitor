"""Configuración: datos y copias de seguridad, logs, acerca de."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QFrame, QHBoxLayout, QHeaderView,
                               QLabel, QMessageBox, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from ...core import language
from .. import presenters as P
from .. import strings as S
from ..context import AppContext
from ..dialogs.simple_dialogs import confirm_destructive, show_info
from ..dialogs.text_dialog import TextDialog
from ..theme import current as theme
from ..tray import tray_available
from ..widgets.pill_button import PillButton
from ..workers import TaskRunner

_ROLE_FILE = Qt.ItemDataRole.UserRole


def _section(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("role", "section")
    return lbl


def _card() -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("Card")
    v = QVBoxLayout(f)
    v.setContentsMargins(16, 14, 16, 14)
    v.setSpacing(8)
    return f, v


class SettingsPage(QWidget):
    def __init__(self, ctx: AppContext, runner: TaskRunner, on_restored=None, parent=None,
                 on_notify_changed=None) -> None:
        super().__init__(parent)
        self._ctx, self._runner, self._on_restored = ctx, runner, on_restored
        self._on_notify_changed = on_notify_changed
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        title = QLabel(S.SETTINGS_TITLE)
        title.setProperty("role", "title")
        outer.addWidget(title)
        self.notice = QLabel("")
        self.notice.setProperty("role", "notice")
        self.notice.setWordWrap(True)
        self.notice.hide()
        outer.addWidget(self.notice)
        if ctx.degraded:
            b = QLabel(S.DEGRADED)
            b.setProperty("role", "banner")
            b.setWordWrap(True)
            outer.addWidget(b)

        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setSpacing(14)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self._build_appearance())
        lay.addWidget(self._build_language())
        lay.addWidget(self._build_data())
        lay.addWidget(self._build_sync())
        lay.addWidget(self._build_notify())
        lay.addWidget(self._build_logs())
        lay.addWidget(self._build_updates())
        lay.addWidget(self._build_about())
        lay.addWidget(self._build_footer())
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

    # ---------- apariencia ----------
    def _build_appearance(self) -> QFrame:
        card, v = _card()
        v.addWidget(_section(S.SEC_APPEARANCE))
        row = QHBoxLayout()
        self.theme_buttons: dict[str, PillButton] = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        for key, label in (("dark", S.THEME_DARK), ("light", S.THEME_LIGHT)):
            b = PillButton(label, "chip")
            b.setAccessibleName(S.THEME_ACCESSIBLE.format(label=label))
            b.clicked.connect(lambda _c=False, k=key: self.set_theme(k))
            group.addButton(b)
            row.addWidget(b)
            self.theme_buttons[key] = b
        row.addStretch(1)
        v.addLayout(row)
        self.theme_buttons[theme.name()].setChecked(True)
        note = QLabel(S.THEME_NOTE)
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        v.addWidget(note)
        return card

    def set_theme(self, name: str) -> None:
        self.theme_buttons[name].setChecked(True)
        self._ctx.apply_theme(name)
        if not self._ctx.degraded:
            self._runner.run(lambda: self._ctx.settings.set("theme", name), None, self._error)

    # ---------- idioma ----------
    def _build_language(self) -> QFrame:
        card, v = _card()
        v.addWidget(_section(S.SEC_LANGUAGE))
        row = QHBoxLayout()
        row.addWidget(QLabel(S.LANGUAGE_LABEL))
        self.language_combo = QComboBox()
        for code, name in S.LANGUAGE_NAMES:
            self.language_combo.addItem(name, code)
        self.language_combo.setAccessibleName(S.LANGUAGE_LABEL)
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(language.current())))
        self.language_combo.currentIndexChanged.connect(self._language_changed)     # después de fijar el valor inicial
        row.addWidget(self.language_combo)
        row.addStretch(1)
        v.addLayout(row)
        return card

    def _language_changed(self, _index: int = 0) -> None:
        """Guarda la preferencia (language.txt); se aplica al reiniciar, porque los textos se cargan al arrancar."""
        code = self.language_combo.currentData()
        if code not in language.SUPPORTED:
            return
        if code == language.current():
            self.say("")
            return
        try:
            language.set_language(code, self._ctx.data_dir)
        except (OSError, ValueError):
            self.say(S.GENERIC_ERROR)
            return
        self.say(S.LANGUAGE_RESTART)

    # ---------- datos y backups ----------
    def _build_data(self) -> QFrame:
        card, v = _card()
        v.addWidget(_section(S.SEC_DATA))
        row = QHBoxLayout()
        lbl = QLabel(f"{S.DATA_FOLDER} {self._ctx.data_dir}")
        lbl.setProperty("role", "muted")
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(lbl, 1)
        open_btn = QPushButton(S.OPEN_FOLDER)
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self._ctx.data_dir)))
        row.addWidget(open_btn)
        v.addLayout(row)

        self.auto_chk = QCheckBox(S.AUTO_BACKUP)
        self.auto_chk.toggled.connect(self._auto_toggled)
        v.addWidget(self.auto_chk)

        self.table = QTableWidget(0, len(S.BACKUP_HEADERS))
        self.table.setHorizontalHeaderLabels(S.BACKUP_HEADERS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(180)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        v.addWidget(self.table)

        btns = QHBoxLayout()
        self.create_btn = QPushButton(S.BACKUP_NOW)
        self.create_btn.clicked.connect(self._create_backup)
        self.restore_btn = QPushButton(S.BACKUP_RESTORE)
        self.restore_btn.clicked.connect(self._restore)
        self.delete_btn = QPushButton(S.BACKUP_DELETE)
        self.delete_btn.setProperty("variant", "danger")
        self.delete_btn.clicked.connect(self._delete_backup)
        for b in (self.create_btn, self.restore_btn, self.delete_btn):
            btns.addWidget(b)
        btns.addStretch(1)
        v.addLayout(btns)
        note = QLabel(S.BACKUP_NOTE)
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        v.addWidget(note)
        self._selection_changed()
        return card

    def refresh(self) -> None:
        self._runner.run(self._ctx.backups.list_backups, self._fill_table, self._error)
        if self._ctx.degraded:          # base dañada: las preferencias no se pueden leer
            return
        self._runner.run(lambda: self._ctx.settings.get("auto_backup"), self._set_auto, self._error)
        self._runner.run(lambda: self._ctx.settings.get("log_level"), self._set_level, self._error)
        self._runner.run(lambda: self._ctx.settings.get("sync_mode"), self._set_sync_mode, self._error)
        self._runner.run(lambda: self._ctx.settings.get("update_check") == "1", self._set_update_enabled, self._error)
        self._runner.run(lambda: (self._ctx.settings.get("notify_mode"), self._ctx.settings.get("notify_interval_min")),
                         lambda res: self._set_notify(*res), self._error)

    def _set_auto(self, value: str) -> None:
        self.auto_chk.blockSignals(True)
        self.auto_chk.setChecked(value == "1")
        self.auto_chk.blockSignals(False)

    def _auto_toggled(self, checked: bool) -> None:
        self._runner.run(lambda: self._ctx.settings.set("auto_backup", "1" if checked else "0"), None, self._error)

    def _fill_table(self, backups) -> None:
        self.table.setRowCount(len(backups))
        for r, b in enumerate(backups):
            cells = [P.format_dt_local(b.created_at), P.reason_label(b.reason), f"v{b.schema_version}",
                     P.format_size(b.size_bytes)]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setData(_ROLE_FILE, b.filename)
                self.table.setItem(r, c, item)
        self._selection_changed()

    def _selected(self) -> tuple[str, str] | None:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        return item.data(_ROLE_FILE), item.text()

    def _selection_changed(self) -> None:
        has = self._selected() is not None
        self.restore_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    def say(self, message: str) -> None:
        self.notice.setText(message)
        self.notice.setVisible(bool(message))

    def _error(self, error) -> None:
        self._busy(False)
        self.say(error.user_message)

    def _busy(self, busy: bool) -> None:
        for b in (self.create_btn, self.restore_btn, self.delete_btn):
            b.setEnabled(not busy)
        if not busy:
            self._selection_changed()

    def _create_backup(self) -> None:
        self._busy(True)
        self._runner.run(self._ctx.backups.create_manual, lambda _i: self._done(S.BACKUP_CREATED), self._error)

    def _done(self, message: str) -> None:
        self._busy(False)
        self.say(message)
        self.refresh()

    def _delete_backup(self) -> None:
        sel = self._selected()
        if sel is None:
            return
        filename, date = sel
        if not confirm_destructive(self, S.BACKUP_DELETE, S.DELETE_BACKUP_TEXT.format(date=date), S.DELETE_CONFIRM):
            return
        self._busy(True)
        self._runner.run(lambda: self._ctx.backups.delete(filename), lambda _r: self._done(S.BACKUP_DELETED), self._error)

    def _restore(self) -> None:
        sel = self._selected()
        if sel is None:
            return
        filename, date = sel
        if not confirm_destructive(self, S.RESTORE_TITLE, S.RESTORE_TEXT.format(date=date), S.BACKUP_RESTORE):
            return
        self._busy(True)
        self._runner.run(lambda: self._ctx.backups.restore(filename), lambda _i: self._restored(), self._error)

    def _restored(self) -> None:
        self._busy(False)
        if self._ctx.degraded:
            show_info(self, S.RESTORE_TITLE, S.RESTORE_RESTART)
            if self._on_restored:
                self._on_restored(quit_app=True)
            return
        self.say(S.RESTORE_OK)
        self.refresh()
        if self._on_restored:
            self._on_restored(quit_app=False)

    # ---------- sincronización ----------
    def _build_sync(self) -> QFrame:
        card, v = _card()
        v.addWidget(_section(S.SEC_SYNC))
        row = QHBoxLayout()
        row.addWidget(QLabel(S.SYNC_MODE_LABEL))
        self.sync_combo = QComboBox()
        self.sync_combo.setAccessibleName(S.SYNC_MODE_LABEL)
        for key, label in S.SYNC_MODES:
            self.sync_combo.addItem(label, key)
        self.sync_combo.currentIndexChanged.connect(self._sync_mode_changed)
        row.addWidget(self.sync_combo)
        row.addStretch(1)
        v.addLayout(row)
        note = QLabel(S.SYNC_MODE_NOTE)
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        v.addWidget(note)
        return card

    def _set_sync_mode(self, value: str) -> None:
        idx = self.sync_combo.findData(value)
        self.sync_combo.blockSignals(True)
        self.sync_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.sync_combo.blockSignals(False)

    def _sync_mode_changed(self, _index: int) -> None:
        value = self.sync_combo.currentData()
        if value in ("manual", "auto"):
            self._runner.run(lambda: self._ctx.settings.set("sync_mode", value), None, self._error)

    # ---------- avisos ----------
    def _build_notify(self) -> QFrame:
        card, v = _card()
        v.addWidget(_section(S.SEC_NOTIFY))
        self._tray_ok = tray_available()
        self.notify_chk = QCheckBox(S.NOTIFY_CHECK)
        self.notify_chk.setEnabled(self._tray_ok)
        self.notify_chk.toggled.connect(self._notify_toggled)
        v.addWidget(self.notify_chk)
        row = QHBoxLayout()
        row.addWidget(QLabel(S.NOTIFY_INTERVAL_LABEL))
        self.notify_combo = QComboBox()
        self.notify_combo.setAccessibleName(S.NOTIFY_INTERVAL_LABEL)
        for key, label in S.NOTIFY_INTERVALS:
            self.notify_combo.addItem(label, key)
        self.notify_combo.setEnabled(self._tray_ok)
        self.notify_combo.currentIndexChanged.connect(self._notify_interval_changed)
        row.addWidget(self.notify_combo)
        row.addStretch(1)
        v.addLayout(row)
        self.notify_status = QLabel(S.NOTIFY_NO_TRAY if not self._tray_ok else "")
        self.notify_status.setProperty("role", "notice")
        self.notify_status.setVisible(not self._tray_ok)
        v.addWidget(self.notify_status)
        note = QLabel(S.NOTIFY_NOTE)
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        v.addWidget(note)
        return card

    def _set_notify(self, mode: str, interval: str) -> None:
        self.notify_chk.blockSignals(True)
        self.notify_combo.blockSignals(True)
        self.notify_chk.setChecked(mode == "on" and self._tray_ok)       # sin bandeja se muestra apagado y desactivado
        idx = self.notify_combo.findData(interval)
        self.notify_combo.setCurrentIndex(idx if idx >= 0 else self.notify_combo.findData("60"))
        self.notify_chk.blockSignals(False)
        self.notify_combo.blockSignals(False)

    def _notify_saved(self, _r=None) -> None:
        if self._on_notify_changed:
            self._on_notify_changed()

    def _notify_toggled(self, on: bool) -> None:
        notifier = self._ctx.notifier
        if notifier is not None:
            self._runner.run(lambda: notifier.set_enabled(on), self._notify_saved, self._error)

    def _notify_interval_changed(self, _index: int) -> None:
        notifier, value = self._ctx.notifier, self.notify_combo.currentData()
        if notifier is not None and value:
            self._runner.run(lambda: notifier.set_interval(int(value)), self._notify_saved, self._error)

    def _copy_diagnostics(self) -> None:
        make = self._ctx.diagnostic_report
        if make is None:
            return
        self._runner.run(make, self._diag_ready, self._error)

    def _diag_ready(self, text: str) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self.say(S.DIAG_COPIED)

    # ---------- logs ----------
    def _build_logs(self) -> QFrame:
        card, v = _card()
        v.addWidget(_section(S.SEC_LOGS))
        row = QHBoxLayout()
        row.addWidget(QLabel(S.LOG_LEVEL))
        self.level = QComboBox()
        self.level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.level.setAccessibleName(S.LOG_LEVEL)
        self.level.currentTextChanged.connect(self._level_changed)
        row.addWidget(self.level)
        open_btn = QPushButton(S.LOGS_FOLDER)
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self._ctx.logs_dir)))
        row.addWidget(open_btn)
        diag_btn = QPushButton(S.COPY_DIAG)
        diag_btn.clicked.connect(self._copy_diagnostics)
        row.addWidget(diag_btn)
        row.addStretch(1)
        v.addLayout(row)
        note = QLabel(S.LOG_NOTE)
        note.setProperty("role", "muted")
        v.addWidget(note)
        return card

    def _set_level(self, value: str) -> None:
        self.level.blockSignals(True)
        self.level.setCurrentText(value)
        self.level.blockSignals(False)

    def _level_changed(self, value: str) -> None:
        logging.getLogger("tally_monitor").setLevel(getattr(logging, value, logging.INFO))
        self._runner.run(lambda: self._ctx.settings.set("log_level", value), None, self._error)

    # ---------- actualizaciones ----------
    def _build_updates(self) -> QFrame:
        card, v = _card()
        v.addWidget(_section(S.SEC_UPDATES))
        self.update_chk = QCheckBox(S.UPDATE_CHECK)
        self.update_chk.toggled.connect(self._update_toggled)
        v.addWidget(self.update_chk)
        row = QHBoxLayout()
        self.update_now_btn = QPushButton(S.UPDATE_NOW)
        self.update_now_btn.clicked.connect(self._update_now)
        row.addWidget(self.update_now_btn)
        self.update_open_btn = QPushButton(S.UPDATE_OPEN)
        self.update_open_btn.clicked.connect(self._update_open)
        self.update_open_btn.hide()
        row.addWidget(self.update_open_btn)
        row.addStretch(1)
        v.addLayout(row)
        self.update_label = QLabel("")
        self.update_label.setProperty("role", "muted")
        self.update_label.setWordWrap(True)
        v.addWidget(self.update_label)
        note = QLabel(S.UPDATE_NOTE)
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        v.addWidget(note)
        self._update_url = ""
        return card

    def _update_toggled(self, on: bool) -> None:
        up = self._ctx.updates
        if up is not None:
            self._runner.run(lambda: up.set_enabled(on), None, self._error)

    def _update_now(self) -> None:
        up = self._ctx.updates
        if up is None:
            return
        self.update_now_btn.setEnabled(False)
        self._runner.run(lambda: up.check(force=True), self._update_result, self._error)

    def _update_result(self, status) -> None:
        self.update_now_btn.setEnabled(True)
        self._update_url = status.url or ""
        self.update_open_btn.setVisible(status.state == "available" and bool(status.url))
        if status.state == "available":
            self.update_label.setText(S.UPDATE_AVAILABLE.format(version=status.latest))
        else:
            self.update_label.setText(S.UPDATE_STATES.get(status.state, ""))

    def _update_open(self) -> None:
        if self._update_url:
            QDesktopServices.openUrl(QUrl(self._update_url))

    def _set_update_enabled(self, value: bool) -> None:
        self.update_chk.blockSignals(True)
        self.update_chk.setChecked(value)
        self.update_chk.blockSignals(False)

    # ---------- acerca de ----------
    def _build_about(self) -> QFrame:
        card, v = _card()
        v.addWidget(_section(S.SEC_ABOUT))
        text = QLabel(S.ABOUT_TEXT.format(version=self._ctx.app_version))
        text.setWordWrap(True)
        v.addWidget(text)
        row = QHBoxLayout()
        for label, filename in ((S.ABOUT_LICENSE, "THIRD_PARTY_LICENSES.md"), (S.ABOUT_PRIVACY, "PRIVACIDAD.md")):
            b = QPushButton(label)
            b.clicked.connect(lambda _c=False, f=filename: self._open_doc(f))
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        return card

    def _build_footer(self) -> QLabel:
        from ...core.platform_info import os_name
        foot = QLabel(S.FOOTER.format(platform=os_name(), version=self._ctx.app_version))
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        foot.setProperty("role", "muted")
        return foot

    def _open_doc(self, filename: str) -> None:
        """Muestra el texto dentro de la aplicación (no depende de que haya un programa asociado a .md)."""
        from ...core.assets import read_legal
        if filename.startswith("THIRD"):
            parts = [read_legal("LICENSE"), read_legal("THIRD_PARTY_LICENSES.md")]
            text = "\n\n".join(p for p in parts if p) or (S.LICENSES_TEXT)
            title = S.LICENSES
        else:
            # PRIVACIDAD.md está en español: en inglés se muestra el resumen traducido
            text = (read_legal("PRIVACIDAD.md") if language.current() == "es" else None) or S.PRIVACY_SUMMARY
            title = S.PRIVACY_TITLE
        TextDialog(title, text, self).exec()

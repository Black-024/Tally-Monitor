"""Diálogo «Editar encuesta»: meta, nota y etiquetas (datos propios, locales). Solo usa servicios."""
from __future__ import annotations

import re

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout,
                               QWidget)

from ...core.errors import TallyMonitorError
from .. import strings as S
from ..context import AppContext
from ..workers import TaskRunner

_THOUSANDS = re.compile(r"^\d{1,3}(\.\d{3})+$")


class EditSurveyDialog(QDialog):
    """`survey` es un SurveySummary. Al guardar con éxito el diálogo se cierra con accept() y deja `saved` con el
    resumen nuevo. Las reglas de validación viven en el servicio (aquí solo se muestran sus mensajes)."""

    def __init__(self, ctx: AppContext, runner: TaskRunner, account_id: str, survey, parent=None) -> None:
        super().__init__(parent)
        self._ctx, self._runner = ctx, runner
        self._account_id, self._form_id = account_id, survey.form_id
        self._tags: list[str] = list(survey.tags)
        self._busy = False
        self.saved = None
        self.setWindowTitle(S.EDIT_TITLE)
        self.setModal(True)
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        name = QLabel(survey.name)
        name.setProperty("role", "section")
        name.setWordWrap(True)
        lay.addWidget(name)

        lay.addWidget(QLabel(S.EDIT_GOAL_LABEL))
        self.goal_edit = QLineEdit(str(survey.goal) if survey.goal else "")
        self.goal_edit.setPlaceholderText(S.EDIT_GOAL_PLACEHOLDER)
        self.goal_edit.setAccessibleName(S.EDIT_GOAL_LABEL)
        lay.addWidget(self.goal_edit)
        lay.addWidget(self._hint(S.EDIT_GOAL_HELP))

        lay.addWidget(QLabel(S.EDIT_NOTE_LABEL))
        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlainText(survey.note)
        self.note_edit.setAccessibleName(S.EDIT_NOTE_LABEL)
        self.note_edit.setFixedHeight(90)
        lay.addWidget(self.note_edit)
        lay.addWidget(self._hint(S.EDIT_NOTE_HELP))

        lay.addWidget(QLabel(S.EDIT_TAGS_LABEL))
        row = QHBoxLayout()
        self.tag_edit = QLineEdit()
        self.tag_edit.setPlaceholderText(S.EDIT_TAG_PLACEHOLDER)
        self.tag_edit.setAccessibleName(S.EDIT_TAGS_LABEL)
        self.tag_edit.returnPressed.connect(self._add_tag)
        row.addWidget(self.tag_edit, 1)
        self.tag_add_btn = QPushButton(S.EDIT_TAG_ADD)
        self.tag_add_btn.clicked.connect(self._add_tag)
        row.addWidget(self.tag_add_btn)
        lay.addLayout(row)
        self.chips_holder = QWidget()
        self.chips_lay = QHBoxLayout(self.chips_holder)
        self.chips_lay.setContentsMargins(0, 0, 0, 0)
        self.chips_lay.setSpacing(6)
        lay.addWidget(self.chips_holder)
        lay.addWidget(self._hint(S.EDIT_TAGS_HELP))
        self._chip_buttons: list = []
        self._render_chips()

        self.status = QLabel("")
        self.status.setProperty("role", "error")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.cancel_btn = QPushButton(S.BTN_CANCEL)
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton(S.EDIT_SAVE)
        self.ok_btn.setProperty("variant", "primary")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._submit)
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.ok_btn)
        lay.addLayout(btns)

    @staticmethod
    def _hint(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("role", "muted")
        lbl.setWordWrap(True)
        return lbl

    # ---------- etiquetas ----------
    def tags(self) -> list[str]:
        return list(self._tags)

    def _render_chips(self) -> None:
        while self.chips_lay.count():
            item = self.chips_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._chip_buttons = []
        for t in self._tags:
            b = QPushButton(f"{t}  ×")
            b.setProperty("variant", "link")
            b.setAccessibleName(S.EDIT_TAG_REMOVE.format(tag=t))
            b.setToolTip(S.EDIT_TAG_REMOVE.format(tag=t))
            b.clicked.connect(lambda _c=False, tag=t: self.remove_tag(tag))
            self.chips_lay.addWidget(b)
            self._chip_buttons.append(b)
        self.chips_lay.addStretch(1)

    def _add_tag(self) -> None:
        text = self.tag_edit.text()
        if not text.strip():
            return
        try:
            self._tags = self._ctx.surveys.normalize_tags(self._tags + [text])   # mismas reglas que al guardar
        except TallyMonitorError as exc:
            self._show_error(exc.user_message)
            return
        self.tag_edit.setText("")
        self._show_error("")
        self._render_chips()

    def remove_tag(self, tag: str) -> None:
        self._tags = [t for t in self._tags if t != tag]
        self._show_error("")
        self._render_chips()

    # ---------- guardar ----------
    def _show_error(self, message: str) -> None:
        self.status.setText(message)

    def _goal_value(self):
        """None si está vacío; ValueError si no es un entero."""
        text = self.goal_edit.text().strip()
        if not text:
            return None
        if _THOUSANDS.match(text):                     # «1.000» o «1.000.000» (puntos de miles es-AR)
            text = text.replace(".", "")
        if not text.isascii() or not text.isdigit():
            raise ValueError(text)
        return int(text)

    def _submit(self) -> None:
        if self._busy:
            return
        pending = self.tag_edit.text().strip()
        tags = list(self._tags)
        if pending:                                    # lo escrito y no agregado todavía también se guarda
            tags.append(pending)
        try:
            goal = self._goal_value()
        except ValueError:
            self._show_error(S.EDIT_GOAL_NOT_NUMBER)
            return
        note = self.note_edit.toPlainText()
        aid, fid = self._account_id, self._form_id
        self._busy = True
        self.ok_btn.setEnabled(False)

        def ok(summary):
            self._busy = False
            self.saved = summary
            self.accept()

        def fail(error):
            self._busy = False
            self.ok_btn.setEnabled(True)
            self._show_error(error.user_message)

        self._runner.run(lambda: self._ctx.surveys.set_survey_meta(aid, fid, goal, note, tags), ok, fail)

    def reject(self) -> None:
        if not self._busy:
            super().reject()

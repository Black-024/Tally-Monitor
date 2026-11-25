"""Detalle de una encuesta: sincronización y respuestas individuales («Usuario NNN»). Solo usa servicios."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QProgressBar, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from ...core.errors import SyncCancelled
from .. import presenters as P
from .. import strings as S
from ..context import AppContext
from ..dialogs.edit_survey_dialog import EditSurveyDialog
from ..dialogs.simple_dialogs import confirm_destructive
from ..widgets.empty_state import EmptyState
from ..workers import TaskRunner

PAGE_SIZE = 200


class SurveyDetailPage(QWidget):
    back_requested = Signal()
    changed = Signal()                       # la lista de encuestas debería refrescarse
    _progress = Signal(str, int, object)     # se emite desde el hilo de trabajo; Qt lo entrega en el hilo de la interfaz

    def __init__(self, ctx: AppContext, runner: TaskRunner, parent=None) -> None:
        super().__init__(parent)
        self._ctx, self._runner = ctx, runner
        self._account_id: str | None = None
        self._form_id: str | None = None
        self._views: list = []            # respuestas cargadas (ResponseView)
        self._total = 0
        self._syncing = False
        self._cancel = False
        self._token = 0                   # invalida resultados de una encuesta anterior
        self._survey = None               # último SurveySummary mostrado
        self._progress.connect(self._show_progress)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        # Encabezado y barra de sincronización: son widgets sueltos; el «espacio de la encuesta» los coloca arriba
        # (así «Actualizar» se ve en todas las pestañas).
        self.head = QWidget()
        hv = QVBoxLayout(self.head)
        hv.setContentsMargins(0, 0, 0, 0)
        hv.setSpacing(2)
        self.back_btn = QPushButton(S.BACK_TO_SURVEYS)
        self.back_btn.setProperty("variant", "link")
        self.back_btn.clicked.connect(self.back_requested.emit)
        top_row = QHBoxLayout()
        top_row.addWidget(self.back_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        top_row.addStretch(1)
        self.edit_btn = QPushButton(S.BTN_EDIT)
        self.edit_btn.setAccessibleName(S.EDIT_TITLE)
        self.edit_btn.clicked.connect(self.open_edit)
        top_row.addWidget(self.edit_btn)
        hv.addLayout(top_row)
        self.title = QLabel("")
        self.title.setProperty("role", "title")
        self.title.setWordWrap(True)
        hv.addWidget(self.title)
        self.subtitle = QLabel("")
        self.subtitle.setProperty("role", "muted")
        self.subtitle.setWordWrap(True)
        hv.addWidget(self.subtitle)
        self.note_label = QLabel("")                 # la nota propia, bajo el título
        self.note_label.setWordWrap(True)
        self.note_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.note_label.hide()
        hv.addWidget(self.note_label)

        self.sync_bar = QWidget()
        sv = QVBoxLayout(self.sync_bar)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(6)
        bar = QHBoxLayout()
        self.sync_btn = QPushButton(S.BTN_SYNC)
        self.sync_btn.setProperty("variant", "primary")
        self.sync_btn.clicked.connect(lambda: self.sync(full=False))
        self.full_btn = QPushButton(S.BTN_SYNC_FULL)
        self.full_btn.setProperty("variant", "link")
        self.full_btn.clicked.connect(self._ask_full)
        self.cancel_btn = QPushButton(S.BTN_CANCEL_SYNC)
        self.cancel_btn.clicked.connect(self._request_cancel)
        self.cancel_btn.hide()
        for b in (self.sync_btn, self.full_btn, self.cancel_btn):
            bar.addWidget(b)
        bar.addStretch(1)
        sv.addLayout(bar)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        sv.addWidget(self.progress)
        self.notice = QLabel("")
        self.notice.setProperty("role", "notice")
        self.notice.setWordWrap(True)
        self.notice.hide()
        sv.addWidget(self.notice)

        privacy = QLabel(S.PRIVACY_NOTICE)
        privacy.setProperty("role", "banner")
        privacy.setWordWrap(True)
        outer.addWidget(privacy)

        # cuerpo: lista de usuarios a la izquierda, respuesta a la derecha
        self.body = QWidget()
        body = QHBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(14)
        left = QVBoxLayout()
        head = QLabel(S.RESPONSES_HEADER)
        head.setProperty("role", "section")
        left.addWidget(head)
        self.search = QLineEdit()
        self.search.setPlaceholderText(S.RESPONSES_SEARCH)
        self.search.setAccessibleName(S.RESPONSES_SEARCH)
        self.search.textChanged.connect(self._apply_filter)
        left.addWidget(self.search)
        self.user_list = QListWidget()
        self.user_list.setAccessibleName(S.RESPONSES_HEADER)
        self.user_list.currentRowChanged.connect(self._row_changed)
        left.addWidget(self.user_list, 1)
        self.count_label = QLabel("")
        self.count_label.setProperty("role", "meta")
        left.addWidget(self.count_label)
        self.more_btn = QPushButton(S.LOAD_MORE)
        self.more_btn.clicked.connect(self._load_more)
        self.more_btn.hide()
        left.addWidget(self.more_btn)
        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setFixedWidth(270)
        body.addWidget(left_w)

        self.detail_area = QScrollArea()
        self.detail_area.setWidgetResizable(True)
        self.detail_holder = QWidget()
        self.detail_lay = QVBoxLayout(self.detail_holder)
        self.detail_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.detail_lay.setSpacing(12)
        self.detail_area.setWidget(self.detail_holder)
        body.addWidget(self.detail_area, 1)
        outer.addWidget(self.body, 1)

        self.empty_unsynced = EmptyState(S.NO_RESPONSES_TITLE, S.NO_RESPONSES_TEXT)
        self.empty_zero = EmptyState(S.NO_RESPONSES_EMPTY_SURVEY, "")
        for w in (self.empty_unsynced, self.empty_zero):
            w.hide()
            outer.addWidget(w, 1)
        self._visible: list = []          # respuestas visibles tras el filtro (misma orden que la lista)

    # ---------- apertura y carga ----------
    def open_survey(self, account_id: str, form_id: str) -> None:
        self._token += 1
        self._account_id, self._form_id = account_id, form_id
        self._views, self._total, self._visible = [], 0, []
        self.search.setText("")
        self._say("")
        self._set_syncing(False)
        self._ctx.note("encuesta_abierta", form_id=form_id)
        aid, fid = account_id, form_id
        self._runner.run(lambda: self._ctx.favorites.touch_recent(aid, fid), None, None)
        self._load(first=True, then_auto=True)

    def _load(self, *, first: bool = False, then_auto: bool = False) -> None:
        """first=True recarga desde el principio (conservando lo ya cargado); False agrega la página siguiente."""
        aid, fid, token = self._account_id, self._form_id, self._token
        offset = 0 if first else len(self._views)
        limit = max(PAGE_SIZE, len(self._views)) if first else PAGE_SIZE

        def work():
            survey = self._ctx.surveys.get_survey(aid, fid)
            views = self._ctx.surveys.responses(aid, fid, offset=offset, limit=limit)
            mode = self._ctx.settings.get("sync_mode")
            return survey, views, mode

        def ok(res):
            if token != self._token:
                return
            survey, views, mode = res
            self._render(survey, views, replace=first)
            if then_auto and mode == "auto":
                self.sync(full=False)

        self._runner.run(work, ok, self._on_error)

    def _render(self, survey, views, *, replace: bool) -> None:
        self._survey = survey
        self.title.setText(survey.name)
        self.note_label.setText(survey.note)
        self.note_label.setVisible(bool(survey.note))
        self.subtitle.setText(f"{P.survey_status_text(survey)} · {P.survey_counts_text(survey)}"
                              + (f" · {S.NEW_IN_TALLY}" if survey.has_new_hint else ""))
        if replace:
            self._views = list(views)
        else:
            self._views += list(views)
        self._total = survey.local_submissions
        has_any = bool(self._views)
        none_in_tally = survey.reported_submissions == 0 and not survey.never_synced
        self.body.setVisible(has_any)
        self.empty_unsynced.setVisible(not has_any and not none_in_tally)
        self.empty_zero.setVisible(not has_any and none_in_tally)
        self._apply_filter()

    def _apply_filter(self, *_args) -> None:
        current = self._current_number()
        q = self.search.text()
        self._visible = [v for v in self._views if P.response_matches(v, q)]
        self.user_list.blockSignals(True)
        self.user_list.clear()
        for v in self._visible:
            self.user_list.addItem(v.label + ("  ·  " + S.INCOMPLETE_RESPONSE if not v.is_completed else ""))
        self.user_list.blockSignals(False)
        self.count_label.setText(S.SHOWING_COUNT.format(shown=len(self._views), total=self._total))
        self.more_btn.setVisible(len(self._views) < self._total)
        row = next((i for i, v in enumerate(self._visible) if v.number == current), 0 if self._visible else -1)
        if row >= 0:
            self.user_list.setCurrentRow(row)
        self._show_response(self._visible[row] if row >= 0 else None)

    def _load_more(self) -> None:
        self._load(first=False)

    def _current_number(self) -> int | None:
        row = self.user_list.currentRow()
        return self._visible[row].number if 0 <= row < len(self._visible) else None

    def _row_changed(self, row: int) -> None:
        self._show_response(self._visible[row] if 0 <= row < len(self._visible) else None)

    # ---------- respuesta individual ----------
    def _show_response(self, view) -> None:
        while self.detail_lay.count():
            item = self.detail_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if view is None:
            hint = QLabel(S.USER_NOT_FOUND if self.search.text().strip() else S.SELECT_A_USER)
            hint.setProperty("role", "muted")
            self.detail_lay.addWidget(hint)
            return
        head = QFrame()
        head.setObjectName("Card")
        hl = QVBoxLayout(head)
        hl.setContentsMargins(16, 14, 16, 14)
        ident = QLabel(view.label)
        ident.setProperty("role", "user-id")           # el identificador, bien visible
        hl.addWidget(ident)
        when = QLabel(S.SUBMITTED_AT.format(when=P.format_local_seconds(view.submitted_at))
                      + (f" · {S.INCOMPLETE_RESPONSE}" if not view.is_completed else ""))
        when.setProperty("role", "meta")               # fecha y hora: más chicas y atenuadas
        hl.addWidget(when)
        self.detail_lay.addWidget(head)
        for a in view.answers:
            card = QFrame()
            card.setObjectName("Card")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)
            cl.setSpacing(4)
            q = QLabel(a.question_title)
            q.setProperty("role", "question")
            q.setWordWrap(True)
            cl.addWidget(q)
            for line in P.answer_lines(a):
                t = QLabel(line)
                t.setProperty("role", "answer")
                t.setWordWrap(True)
                t.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                cl.addWidget(t)
            self.detail_lay.addWidget(card)

    # ---------- sincronización ----------
    def _set_syncing(self, on: bool) -> None:
        self._syncing = on
        self.sync_btn.setEnabled(not on)
        self.full_btn.setEnabled(not on)
        self.back_btn.setEnabled(True)
        self.cancel_btn.setVisible(on)
        self.progress.setVisible(on)
        if on:
            self._cancel = False

    def _ask_full(self) -> None:
        if confirm_destructive(self, S.SYNC_FULL_TITLE, S.SYNC_FULL_TEXT, S.SYNC_FULL_CONFIRM):
            self.sync(full=True)

    def _request_cancel(self) -> None:
        self._cancel = True
        self.cancel_btn.setEnabled(False)

    def sync(self, *, full: bool) -> None:
        if self._syncing or not self._account_id:
            return
        aid, fid, token = self._account_id, self._form_id, self._token
        self._set_syncing(True)
        self.cancel_btn.setEnabled(True)
        self._say(S.SYNCING)
        self._ctx.note("sync_pedida", form_id=fid, completa=full)

        def work():
            return self._ctx.sync.sync_form(aid, fid, full=full, cancel=lambda: self._cancel,
                                            progress=lambda ph, n, t: self._progress.emit(ph, n, t))

        def ok(result):
            if token != self._token:
                return
            self._set_syncing(False)
            self._say(P.sync_result_text(result))
            self._load(first=True)
            self.changed.emit()

        def fail(error):
            if token != self._token:
                return
            self._set_syncing(False)
            if isinstance(error, SyncCancelled):
                self._say(S.SYNC_CANCELLED)
            else:
                extra = f" {S.OFFLINE_SHOWING_SAVED}" if getattr(error, "category", "") == "network" else ""
                self._say(error.user_message + extra)
            self._load(first=True)
            self.changed.emit()

        self._runner.run(work, ok, fail)

    def _show_progress(self, phase: str, done: int, total) -> None:
        if not self._syncing:
            return
        label = S.SYNC_PHASES.get(phase, S.SYNCING)
        self._say((S.SYNC_PROGRESS_OF.format(label=label, done=done, total=total) if isinstance(total, int) and total
                   else S.SYNC_PROGRESS.format(label=label, done=done)))

    # ---------- editar meta, nota y etiquetas ----------
    def make_edit_dialog(self):
        return EditSurveyDialog(self._ctx, self._runner, self._account_id, self._survey, self)

    def open_edit(self) -> None:
        if self._survey is None or not self._account_id:
            return
        dlg = self.make_edit_dialog()
        dlg.exec()
        if getattr(dlg, "saved", None) is not None:
            self._say(S.EDIT_SAVED)
            self._load(first=True)
            self.changed.emit()

    # ---------- varios ----------
    def _on_error(self, error) -> None:
        self._say(error.user_message)

    def _say(self, message: str) -> None:
        self.notice.setText(message)
        self.notice.setVisible(bool(message))

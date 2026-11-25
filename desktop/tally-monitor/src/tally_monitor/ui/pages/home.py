"""Página Inicio: saludo según fecha y hora, mini resumen de las encuestas y aviso de respuestas sin actualizar.
Solo usa servicios y lee lo ya guardado; en modo de sincronización «automática» además actualiza la lista de encuestas."""
from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ...core.errors import TallyMonitorError
from .. import presenters as P
from .. import strings as S
from ..context import AppContext
from ..greeting import greeting_for
from ..widgets.empty_state import EmptyState
from ..widgets.goal_bar import GoalBar
from ..widgets.red_dot import RedDot
from ..workers import TaskRunner

_AUTO_EVERY_SECONDS = 120


class _TopRow(QFrame):
    """Fila de «Cómo les va»: tocarla abre la encuesta."""

    def __init__(self, account_id: str, survey, on_open) -> None:
        super().__init__()
        self.setObjectName("SurveyCard")
        self._aid, self._fid, self._on_open = account_id, survey.form_id, on_open
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"{survey.name}. {P.survey_counts_text(survey)}. {S.OPEN_SUFFIX}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14)
        col = QVBoxLayout()
        col.setSpacing(2)
        name = QLabel(survey.name)
        name.setProperty("role", "section")
        name.setWordWrap(True)
        col.addWidget(name)
        meta = QLabel(S.HOME_TOP_META.format(status=P.survey_status_text(survey), when=P.format_local(survey.last_submission_at)))
        meta.setProperty("role", "muted")
        col.addWidget(meta)
        lay.addLayout(col, 1)
        if survey.has_new_hint:
            lay.addWidget(RedDot(10), alignment=Qt.AlignmentFlag.AlignVCenter)
        count = QLabel("—" if survey.never_synced else str(survey.local_submissions))
        count.setProperty("role", "big-number")
        lay.addWidget(count)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_open(self._aid, self._fid)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._on_open(self._aid, self._fid)
        else:
            super().keyPressEvent(event)


class _GoalRow(QFrame):
    """Fila de «Metas»: nombre, barra de progreso y estimación. Tocarla abre la encuesta."""

    def __init__(self, account_id: str, survey, projection, on_open) -> None:
        super().__init__()
        self.setObjectName("SurveyCard")
        self._aid, self._fid, self._on_open = account_id, survey.form_id, on_open
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"{survey.name}. {P.goal_line(survey.local_submissions, survey.goal, projection)}. {S.OPEN_SUFFIX}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(6)
        name = QLabel(survey.name)
        name.setProperty("role", "section")
        name.setWordWrap(True)
        lay.addWidget(name)
        self.goal_bar = GoalBar(survey.local_submissions, survey.goal, projection)
        lay.addWidget(self.goal_bar)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_open(self._aid, self._fid)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._on_open(self._aid, self._fid)
        else:
            super().keyPressEvent(event)


class HomePage(QWidget):
    pending_changed = Signal(bool)            # hay (o ya no hay) encuestas con respuestas sin actualizar

    def __init__(self, ctx: AppContext, runner: TaskRunner, on_open_accounts, on_open_surveys, on_open_survey, parent=None) -> None:
        super().__init__(parent)
        self._ctx, self._runner = ctx, runner
        self._on_open_accounts, self._on_open_surveys, self._on_open_survey = on_open_accounts, on_open_surveys, on_open_survey
        self._token = 0
        self._syncing = False
        self._last_auto = 0.0
        self._sync_error = ""
        self._goal_items: list = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._body = QWidget()
        self._lay = QVBoxLayout(self._body)
        self._lay.setContentsMargins(32, 12, 32, 24)
        self._lay.setSpacing(14)
        self._lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._body)
        outer.addWidget(scroll)
        self._render_empty_shell()

    # ---------- carga ----------
    def refresh(self) -> None:
        token = self._token = self._token + 1

        def work():
            accounts = [a for a in self._ctx.accounts.list_accounts() if a.status != "no_credential"]
            per = [(a.account_id, self._ctx.surveys.list_surveys(a.account_id)) for a in accounts]
            goals = [(a.account_id, self._ctx.surveys.goals(a.account_id)) for a in accounts]
            return accounts, per, self._ctx.settings.get("sync_mode"), goals

        def ok(res):
            if token != self._token:
                return
            accounts, per, mode, goals = res
            overview = P.home_overview(per)
            self._goal_items = P.goal_items(per, goals)
            self._render(bool(accounts), overview)
            self.pending_changed.emit(bool(overview.pending))
            if (mode == "auto" and accounts and not self._syncing
                    and time.monotonic() - self._last_auto > _AUTO_EVERY_SECONDS):
                self._auto_sync([a.account_id for a in accounts])

        self._runner.run(work, ok, lambda e: self._say_error(e.user_message))

    def _auto_sync(self, account_ids: list[str]) -> None:
        """Modo automático: trae la lista de encuestas de cada cuenta (en segundo plano; lo que falle se avisa sin interrumpir)."""
        self._syncing = True
        self._last_auto = time.monotonic()

        def work():
            first_error = ""
            for aid in account_ids:
                try:
                    self._ctx.sync.sync_forms(aid)
                except TallyMonitorError as exc:
                    first_error = first_error or exc.user_message
            return first_error

        def done(msg):
            self._syncing = False
            self._sync_error = msg or ""
            self.refresh()

        def failed(error):
            self._syncing = False
            self._sync_error = error.user_message
            self.refresh()

        self._runner.run(work, done, failed)

    def _say_error(self, text: str) -> None:
        self._sync_error = text
        self._render_empty_shell()

    # ---------- dibujo ----------
    def _clear(self) -> None:
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _header(self) -> None:
        title, sub = greeting_for(datetime.now())
        t = QLabel(title)
        t.setProperty("role", "title")
        t.setWordWrap(True)
        self._lay.addWidget(t)
        s = QLabel(sub)
        s.setProperty("role", "muted")
        s.setWordWrap(True)
        self._lay.addWidget(s)
        if self._sync_error:
            n = QLabel(self._sync_error)
            n.setProperty("role", "notice")
            n.setWordWrap(True)
            self._lay.addWidget(n)

    def _render_empty_shell(self) -> None:
        self._clear()
        self._header()

    def _render(self, has_accounts: bool, ov: P.HomeOverview) -> None:
        self._clear()
        self._header()
        if not has_accounts:
            empty = EmptyState(S.HOME_NO_ACCOUNTS_TITLE, S.HOME_NO_ACCOUNTS_TEXT, S.SURVEYS_NO_ACCOUNTS_ACTION)
            empty.action_clicked.connect(self._on_open_accounts)
            self._lay.addWidget(empty)
            return
        if ov.pending:
            self._lay.addWidget(self._pending_card(ov))
        if ov.survey_count == 0:
            empty = EmptyState(S.HOME_NO_SURVEYS_TITLE, S.HOME_NO_SURVEYS_TEXT, S.HOME_PENDING_ACTION)
            empty.action_clicked.connect(lambda: self._on_open_surveys(None))
            self._lay.addWidget(empty)
            return
        tiles = QHBoxLayout()
        tiles.setSpacing(16)
        for value, label in ((ov.survey_count, S.HOME_TILE_SURVEYS), (ov.response_total, S.HOME_TILE_RESPONSES),
                             (ov.open_count, S.HOME_TILE_OPEN)):
            tiles.addWidget(self._tile(str(value), label))
        self._lay.addLayout(tiles)
        last = QLabel(S.HOME_LAST.format(when=P.format_local(ov.last_at)))
        last.setProperty("role", "muted")
        self._lay.addWidget(last)
        if self._goal_items:                         # «Metas»: solo encuestas con meta y no archivadas
            goals_title = QLabel(S.GOAL_SECTION)
            goals_title.setProperty("role", "section")
            self._lay.addWidget(goals_title)
            for aid, survey, projection in self._goal_items:
                self._lay.addWidget(_GoalRow(aid, survey, projection, self._on_open_survey))
        top = QLabel(S.HOME_TOP_TITLE)
        top.setProperty("role", "section")
        self._lay.addWidget(top)
        for aid, survey in ov.top:
            self._lay.addWidget(_TopRow(aid, survey, self._on_open_survey))

    def _tile(self, value: str, label: str) -> QFrame:
        f = QFrame()
        f.setObjectName("Card")
        l = QVBoxLayout(f)
        l.setContentsMargins(20, 14, 20, 14)
        l.setSpacing(0)
        v = QLabel(value)
        v.setProperty("role", "tile-number")
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c = QLabel(label)
        c.setProperty("role", "muted")
        c.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(v)
        l.addWidget(c)
        return f

    def _pending_card(self, ov: P.HomeOverview) -> QFrame:
        f = QFrame()
        f.setObjectName("Card")
        l = QVBoxLayout(f)
        l.setContentsMargins(20, 16, 20, 16)
        l.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(RedDot(12), alignment=Qt.AlignmentFlag.AlignVCenter)
        title = QLabel(S.HOME_PENDING_TITLE)
        title.setProperty("role", "section")
        head.addWidget(title)
        head.addStretch(1)
        l.addLayout(head)
        text = (S.HOME_PENDING_TEXT.format(n=ov.new_count, s=len(ov.pending)) if ov.new_count > 0 else S.HOME_PENDING_TEXT_NOCOUNT)
        body = QLabel(text)
        body.setProperty("role", "muted")
        body.setWordWrap(True)
        l.addWidget(body)
        btn = QPushButton(S.HOME_PENDING_ACTION)
        btn.setProperty("variant", "primary")
        btn.clicked.connect(lambda _c=False: self._on_open_surveys(ov.pending[0][0]))
        row = QHBoxLayout()
        row.addWidget(btn)
        row.addStretch(1)
        l.addLayout(row)
        return f

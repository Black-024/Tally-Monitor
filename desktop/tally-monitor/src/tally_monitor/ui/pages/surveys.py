"""Página Encuestas: lista (guardada, disponible sin conexión) y detalle. Solo usa servicios."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
                               QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from .. import presenters as P
from .. import strings as S
from ..context import AppContext
from ..dialogs.edit_survey_dialog import EditSurveyDialog
from ..widgets.empty_state import EmptyState
from ..widgets.goal_bar import GoalBar
from ..widgets.pill_button import PillButton
from ..widgets.red_dot import RedDot
from ..workers import TaskRunner
from .survey_workspace import SurveyWorkspace


class SurveyCard(QFrame):
    """Tarjeta de la «pared»: el número de respuestas bien grande; tocar la tarjeta abre la encuesta."""

    def __init__(self, survey, page: "SurveysPage", goal=None) -> None:
        super().__init__()
        self.setObjectName("SurveyCard")
        self.survey = survey
        self._page = page
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"{survey.name}. {P.survey_counts_text(survey)}. {S.OPEN_SUFFIX}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(4)
        top = QHBoxLayout()
        self.number = QLabel("—" if survey.never_synced else str(survey.local_submissions))
        self.number.setProperty("role", "big-number")
        top.addWidget(self.number)
        top.addStretch(1)
        fid = survey.form_id
        self.fav_btn = QPushButton(S.FAV_ON if survey.is_favorite else S.FAV_OFF)
        self.fav_btn.setProperty("variant", "link")
        self.fav_btn.setCheckable(True)
        self.fav_btn.setChecked(survey.is_favorite)
        self.fav_btn.setAccessibleName(S.FAV_ON if survey.is_favorite else S.FAV_OFF)
        self.fav_btn.setToolTip(S.FAV_ON if survey.is_favorite else S.FAV_OFF)
        self.fav_btn.clicked.connect(lambda checked=False: page.set_favorite(fid, not survey.is_favorite))
        top.addWidget(self.fav_btn, alignment=Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        n = survey.local_submissions
        unit = S.CARD_NEVER if survey.never_synced else (S.CARD_RESPONSES_ONE if n == 1 else S.CARD_RESPONSES)
        name_row = QHBoxLayout()
        name = QLabel(survey.name)
        name.setProperty("role", "section")
        name.setWordWrap(True)
        name_row.addWidget(name, 1)
        if survey.has_new_hint and not survey.archived:
            dot = RedDot(10)
            name_row.addWidget(dot, alignment=Qt.AlignmentFlag.AlignTop)
            tag = QLabel(S.CARD_NEW)
            tag.setProperty("role", "tag")
            name_row.addWidget(tag, alignment=Qt.AlignmentFlag.AlignTop)
        lay.addLayout(name_row)
        meta = QLabel(f"{unit} · {P.survey_status_text(survey)}")
        meta.setProperty("role", "muted")
        lay.addWidget(meta)
        sync = QLabel(P.survey_counts_text(survey))
        sync.setProperty("role", "meta")
        sync.setWordWrap(True)
        lay.addWidget(sync)
        self.tag_labels: list = []
        if survey.archived or survey.tags:                      # etiquetas como chips chicos (solo lectura)
            chips = QHBoxLayout()
            chips.setSpacing(6)
            for text in ([S.ARCHIVED_TAG] if survey.archived else []) + list(survey.tags):
                chip = QLabel(text)
                chip.setProperty("role", "tag")
                chips.addWidget(chip)
                self.tag_labels.append(chip)
            chips.addStretch(1)
            lay.addLayout(chips)
        self.goal_bar = None
        if goal is not None and survey.goal:
            self.goal_bar = GoalBar(survey.local_submissions, survey.goal, goal, show_eta=False)
            lay.addWidget(self.goal_bar)
        actions = QHBoxLayout()
        self.archive_btn = QPushButton(S.UNARCHIVE if survey.archived else S.ARCHIVE)
        self.archive_btn.setProperty("variant", "link")
        self.archive_btn.setAccessibleName(f"{self.archive_btn.text()}: {survey.name}")
        self.archive_btn.clicked.connect(lambda _c=False: page.set_archived(fid, not survey.archived))
        actions.addStretch(1)
        actions.addWidget(self.archive_btn)
        lay.addLayout(actions)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._page.open_survey(self.survey.form_id)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._page.open_survey(self.survey.form_id)
        else:
            super().keyPressEvent(event)


class SurveysPage(QWidget):
    saved_loaded = Signal()                  # se leyó la lista guardada (puede haber cambiado lo pendiente)

    def __init__(self, ctx: AppContext, runner: TaskRunner, on_open_accounts, parent=None) -> None:
        super().__init__(parent)
        self._ctx, self._runner, self._on_open_accounts = ctx, runner, on_open_accounts
        self._account_id: str | None = None
        self._accounts: list = []
        self._surveys: list = []
        self._recents: list[str] = []
        self._auto_done: set[str] = set()     # cuentas ya actualizadas automáticamente en esta sesión
        self._listing = False
        self._token = 0
        self._mode = "manual"
        self._goals: dict = {}
        self._tag: str | None = None          # etiqueta elegida para filtrar (una a la vez)
        self._show_archived = False

        self.stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.stack)

        # --- lista ---
        self.list_page = QWidget()
        lay = QVBoxLayout(self.list_page)
        lay.setContentsMargins(32, 8, 32, 20)
        head = QHBoxLayout()
        title = QLabel(S.SURVEYS_TITLE)
        title.setProperty("role", "title")
        head.addWidget(title)
        head.addStretch(1)
        self.refresh_btn = QPushButton(S.SURVEYS_REFRESH)
        self.refresh_btn.setProperty("variant", "primary")
        self.refresh_btn.clicked.connect(self.sync_list)
        head.addWidget(self.refresh_btn)
        lay.addLayout(head)
        subtitle = QLabel(S.WALL_SUBTITLE)
        subtitle.setProperty("role", "muted")
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)

        filt = QHBoxLayout()
        filt.addWidget(QLabel(S.SURVEYS_ACCOUNT))
        self.account_combo = QComboBox()
        self.account_combo.setAccessibleName(S.SURVEYS_ACCOUNT)
        self.account_combo.currentIndexChanged.connect(self._account_changed)
        filt.addWidget(self.account_combo)
        self.search = QLineEdit()
        self.search.setPlaceholderText(S.SURVEYS_SEARCH)
        self.search.setAccessibleName(S.SURVEYS_SEARCH)
        self.search.textChanged.connect(self._render_list)
        filt.addWidget(self.search, 1)
        self.filter_combo = QComboBox()
        self.filter_combo.setAccessibleName("Filtro")
        for key, label in S.SURVEYS_FILTERS:
            self.filter_combo.addItem(label, key)
        self.filter_combo.currentIndexChanged.connect(self._render_list)
        filt.addWidget(self.filter_combo)
        lay.addLayout(filt)

        self.tags_row_holder = QWidget()                     # fila de chips: «Todas» + una por etiqueta en uso
        self.tags_row = QHBoxLayout(self.tags_row_holder)
        self.tags_row.setContentsMargins(0, 0, 0, 0)
        self.tags_row.setSpacing(8)
        self.tag_chips: dict = {}
        lay.addWidget(self.tags_row_holder)
        self.archived_chip = PillButton(S.SHOW_ARCHIVED, "chip")
        self.archived_chip.setAccessibleName(S.SHOW_ARCHIVED)
        self.archived_chip.toggled.connect(self._archived_toggled)

        self.notice = QLabel("")
        self.notice.setProperty("role", "notice")
        self.notice.setWordWrap(True)
        self.notice.hide()
        lay.addWidget(self.notice)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        lay.addWidget(self.progress)

        self._body = QWidget()
        self._body_lay = QGridLayout(self._body)
        self._body_lay.setContentsMargins(0, 8, 6, 0)
        self._body_lay.setSpacing(16)
        self._body_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._cols = 0
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._body)
        lay.addWidget(scroll, 1)
        self.stack.addWidget(self.list_page)

        # --- detalle ---
        self.workspace = SurveyWorkspace(ctx, runner)
        self.detail = self.workspace.detail                 # (las pruebas y el resto lo siguen usando por este nombre)
        self.workspace.back_requested.connect(self.show_list)
        self.workspace.changed.connect(self._reload_saved)
        self.stack.addWidget(self.workspace)

    # ---------- carga: siempre primero lo guardado ----------
    def refresh(self) -> None:
        token = self._token = self._token + 1

        def work():
            accounts = [a for a in self._ctx.accounts.list_accounts() if a.status != "no_credential"]
            return accounts, self._ctx.settings.get("sync_mode")

        def ok(res):
            if token != self._token:
                return
            accounts, mode = res
            self._fill_accounts(accounts)
            self._mode = mode
            self._reload_saved(auto=(mode == "auto"))

        self._runner.run(work, ok, self._on_error)

    def _fill_accounts(self, accounts) -> None:
        self._accounts = accounts
        ids = [a.account_id for a in accounts]
        if self._account_id not in ids:
            self._account_id = ids[0] if ids else None
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        for a in accounts:
            self.account_combo.addItem(a.name, a.account_id)
        if self._account_id in ids:
            self.account_combo.setCurrentIndex(ids.index(self._account_id))
        self.account_combo.blockSignals(False)
        self.account_combo.setVisible(len(accounts) > 1)
        self.refresh_btn.setEnabled(bool(accounts) and not self._listing)

    def _account_changed(self, index: int) -> None:
        data = self.account_combo.itemData(index)
        if data and data != self._account_id:
            self._account_id = data
            self._say("")
            self._reload_saved(auto=self._mode == "auto")

    def _reload_saved(self, auto: bool = False) -> None:
        aid = self._account_id
        if aid is None:
            self._surveys, self._recents, self._goals = [], [], {}
            self._render_list()
            return
        token = self._token

        def work():
            return (self._ctx.surveys.list_surveys(aid), self._ctx.favorites.recents(aid),
                    self._ctx.surveys.goals(aid))

        def ok(res):
            if token != self._token or aid != self._account_id:
                return
            self._surveys, self._recents, self._goals = res
            self._render_list()
            self.saved_loaded.emit()
            if auto and aid not in self._auto_done:
                self._auto_done.add(aid)
                self.sync_list()

        self._runner.run(work, ok, self._on_error)

    # ---------- dibujo ----------
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cols = self._columns()
        if cols != self._cols and self._accounts and self._surveys:
            self._render_list()

    def _columns(self) -> int:
        width = self.width()
        width = width if isinstance(width, int) else 1100
        return max(1, min(4, (max(width, 400) - 64) // 340))

    def _render_list(self, *_args) -> None:
        while self._body_lay.count():
            item = self._body_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cols = cols = self._columns()
        if not self._accounts:
            empty = EmptyState(S.SURVEYS_NO_ACCOUNTS_TITLE, S.SURVEYS_NO_ACCOUNTS_TEXT, S.SURVEYS_NO_ACCOUNTS_ACTION)
            empty.action_clicked.connect(self._on_open_accounts)
            self._body_lay.addWidget(empty, 0, 0, 1, cols)
            return
        self._fill_tag_chips()
        shown = P.filter_surveys(self._surveys, text=self.search.text(),
                                 mode=self.filter_combo.currentData() or "all", recents=self._recents,
                                 tag=self._tag, show_archived=self._show_archived)
        if not shown:
            msg = S.SURVEYS_EMPTY_FILTER if self._surveys else S.SURVEYS_EMPTY_TEXT
            if self._surveys and not self._show_archived and P.has_archived(self._surveys):
                msg += " " + S.SURVEYS_EMPTY_ARCHIVED_HINT
            title = S.SURVEYS_EMPTY_TITLE if not self._surveys else ""
            self._body_lay.addWidget(EmptyState(title or S.SURVEYS_TITLE, msg), 0, 0, 1, cols)
            return
        for i, sv in enumerate(shown):
            self._body_lay.addWidget(SurveyCard(sv, self, self._goals.get(sv.form_id)), i // cols, i % cols)
        for c in range(cols):
            self._body_lay.setColumnStretch(c, 1)

    def _fill_tag_chips(self) -> None:
        """Rehace la fila «Todas · etiqueta · … · Mostrar archivadas». Si la etiqueta elegida ya no existe, vuelve a «Todas»."""
        tags = P.all_tags(self._surveys, show_archived=self._show_archived)
        if self._tag and self._tag.casefold() not in {t.casefold() for t in tags}:
            self._tag = None
        while self.tags_row.count():
            item = self.tags_row.takeAt(0)
            w = item.widget()
            if w is not None and w is not self.archived_chip:
                w.deleteLater()
        self.tag_chips = {}
        group = QButtonGroup(self.tags_row_holder)
        group.setExclusive(True)
        for key, label in [(None, S.TAG_ALL)] + [(t, t) for t in tags]:
            chip = PillButton(label, "chip")
            chip.setAccessibleName(S.TAG_FILTER_LABEL.format(tag=label))
            chip.setChecked(key == self._tag or (key is not None and self._tag is not None
                                                 and key.casefold() == self._tag.casefold()))
            chip.clicked.connect(lambda _c=False, k=key: self.set_tag(k))
            group.addButton(chip)
            self.tags_row.addWidget(chip)
            self.tag_chips[key] = chip
        self.tags_row.addStretch(1)
        self.archived_chip.blockSignals(True)
        self.archived_chip.setChecked(self._show_archived)
        self.archived_chip.blockSignals(False)
        self.tags_row.addWidget(self.archived_chip)
        self.archived_chip.setVisible(P.has_archived(self._surveys) or self._show_archived)
        self.tags_row_holder.setVisible(bool(tags) or self.archived_chip.isVisible())

    def set_tag(self, tag: str | None) -> None:
        self._tag = tag
        self._render_list()

    def _archived_toggled(self, on: bool) -> None:
        self._show_archived = bool(on)
        self._render_list()

    def set_archived(self, form_id: str, value: bool) -> None:
        aid = self._account_id
        if aid is None:
            return

        def ok(_r):
            self._say(S.ARCHIVE_DONE if value else S.UNARCHIVE_DONE)
            self._reload_saved()

        self._runner.run(lambda: self._ctx.surveys.set_archived(aid, form_id, value), ok, self._on_error)

    # ---------- acciones ----------
    def sync_list(self) -> None:
        aid = self._account_id
        if aid is None or self._listing:
            return
        self._listing = True
        self.refresh_btn.setEnabled(False)
        self.progress.show()
        self._say(S.SURVEYS_LISTING)
        self._ctx.note("lista_encuestas_pedida")

        def ok(res):
            self._listing = False
            self.progress.hide()
            self.refresh_btn.setEnabled(True)
            self._say(S.SURVEYS_LISTED.format(n=res.count))
            self._reload_saved()

        def fail(error):
            self._listing = False
            self.progress.hide()
            self.refresh_btn.setEnabled(True)
            extra = f" {S.OFFLINE_SHOWING_SAVED}" if getattr(error, "category", "") == "network" else ""
            self._say(error.user_message + extra)
            self._reload_saved()

        self._runner.run(lambda: self._ctx.sync.sync_forms(aid), ok, fail)

    def open_survey(self, form_id: str) -> None:
        if self._account_id is None:
            return
        self.stack.setCurrentWidget(self.workspace)
        self.workspace.open_survey(self._account_id, form_id)

    def focus_account(self, account_id: str) -> None:
        """Deja elegida esta cuenta; la próxima carga (navegar a Encuestas) la usa."""
        self._account_id = account_id

    def reset(self) -> None:
        """Tras restaurar una copia: vuelve a la lista y relee todo."""
        self.stack.setCurrentWidget(self.list_page)
        self.refresh()

    def show_list(self) -> None:
        self.stack.setCurrentWidget(self.list_page)
        self._reload_saved()

    def set_favorite(self, form_id: str, value: bool) -> None:
        aid = self._account_id
        if aid is None:
            return
        self._runner.run(lambda: self._ctx.favorites.set_favorite(aid, form_id, value),
                         lambda _r: self._reload_saved(), self._on_error)

    def _on_error(self, error) -> None:
        self._say(error.user_message)

    def _say(self, message: str) -> None:
        self.notice.setText(message)
        self.notice.setVisible(bool(message))

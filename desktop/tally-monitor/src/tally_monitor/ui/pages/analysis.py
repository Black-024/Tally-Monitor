"""Resumen (análisis) de una encuesta: tarjetas, gráfico en el tiempo y estadísticas por pregunta. Solo usa servicios."""
from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDateEdit, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from .. import presenters as P
from .. import strings as S
from ...services.analysis_service import AnswerFilter
from ..context import AppContext
from ..widgets.bar_chart import BarChart
from ..widgets.goal_bar import GoalBar
from ..widgets.pill_button import PillButton
from ..widgets.timeline_chart import TimelineChart
from ..workers import TaskRunner


def _card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(20, 16, 20, 16)
    lay.setSpacing(8)
    return frame, lay


class AnalysisPage(QWidget):
    """Vive dentro del espacio de una encuesta: la encuesta la elige quien lo abre (`open_survey`)."""

    def __init__(self, ctx: AppContext, runner: TaskRunner, parent=None) -> None:
        super().__init__(parent)
        self._ctx, self._runner = ctx, runner
        self._token = 0
        self._account_id: str | None = None
        self._form_id: str | None = None
        self._kind = "all"
        self.result = None                      # último SurveyAnalysis mostrado
        self._cross: AnswerFilter | None = None  # cruce de preguntas activo (se reinicia al cambiar de encuesta)
        self._cross_questions: list = []         # CrossQuestion de la encuesta abierta
        self._cross_sel: tuple[str, str] | None = None     # lo elegido en los selectores (aunque no se haya aplicado)
        self.cross_question_combo = None
        self.cross_option_combo = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.chips: dict[str, QPushButton] = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        for key, label in S.ANALYSIS_CHIPS:
            b = PillButton(label, "chip")
            b.setAccessibleName(S.PERIOD_LABEL.format(label=label))
            b.clicked.connect(lambda _c=False, k=key: self.set_filter(k))
            group.addButton(b)
            bar.addWidget(b)
            self.chips[key] = b
        self.chips["all"].setChecked(True)
        bar.addStretch(1)
        self.incomplete_btn = PillButton(S.ANALYSIS_WITH_INCOMPLETE, "chip")
        self.incomplete_btn.setChecked(True)
        self.incomplete_btn.setAccessibleName(S.ANALYSIS_INCLUDE_INCOMPLETE)
        self.incomplete_btn.toggled.connect(self._incomplete_toggled)
        bar.addWidget(self.incomplete_btn)
        outer.addLayout(bar)

        self.custom_row = QWidget()
        crow = QHBoxLayout(self.custom_row)
        crow.setContentsMargins(0, 0, 0, 0)
        today = QDate.currentDate()
        self.from_edit, self.to_edit = QDateEdit(today.addDays(-7)), QDateEdit(today)
        for edit, label in ((self.from_edit, S.ANALYSIS_FROM), (self.to_edit, S.ANALYSIS_TO)):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat(S.QT_DATE_FMT)
            edit.setAccessibleName(label)
            edit.dateChanged.connect(self._reload)
            crow.addWidget(QLabel(label))
            crow.addWidget(edit)
        crow.addStretch(1)
        self.custom_row.hide()
        outer.addWidget(self.custom_row)

        self.notice = QLabel("")
        self.notice.setProperty("role", "notice")
        self.notice.setWordWrap(True)
        self.notice.hide()
        outer.addWidget(self.notice)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.holder = QWidget()
        self.body = QVBoxLayout(self.holder)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.body.setContentsMargins(0, 0, 6, 0)
        self.body.setSpacing(14)
        self.scroll.setWidget(self.holder)
        outer.addWidget(self.scroll, 1)

    # ---------- apertura y filtros ----------
    def open_survey(self, account_id: str, form_id: str) -> None:
        self._account_id, self._form_id = account_id, form_id
        self._cross, self._cross_sel, self._cross_questions = None, None, []      # el filtro no pasa a otra encuesta
        self._reload()

    def refresh(self) -> None:
        if self._account_id and self._form_id:
            self._reload()

    def set_filter(self, kind: str) -> None:
        self._kind = kind
        self.chips[kind].setChecked(True)
        self.custom_row.setVisible(kind == "custom")
        self._ctx.note("filtro_analisis", filtro=kind)
        self._reload()

    def period(self):
        """(tipo, desde, hasta, con_incompletos, texto) del período elegido: lo usa la pestaña Exportar."""
        kind = self._kind
        start = end = None
        if kind == "custom":
            start, end = self.from_edit.date().toPython(), self.to_edit.date().toPython()
        label = dict((k, v) for k, v in S.ANALYSIS_FILTERS).get(kind, "")
        if kind == "custom":
            label = S.CUSTOM_RANGE.format(start=start.strftime(S.DATE_FMT), end=end.strftime(S.DATE_FMT))
        incl = self.incomplete_btn.isChecked()
        return kind, start, end, incl, (S.PERIOD_WITH_INCOMPLETE if incl else S.PERIOD_WITHOUT_INCOMPLETE).format(label=label)

    def _incomplete_toggled(self, on: bool) -> None:
        self.incomplete_btn.setText(S.ANALYSIS_WITH_INCOMPLETE if on else S.ANALYSIS_WITHOUT_INCOMPLETE)
        self._reload()

    def _reload(self, *_args) -> None:
        aid, fid, kind = self._account_id, self._form_id, self._kind
        if not aid or not fid:
            return
        start = end = None
        if kind == "custom":
            start, end = self.from_edit.date().toPython(), self.to_edit.date().toPython()
            if start > end:
                self._say(S.ANALYSIS_INVALID_RANGE)
                return
        include = self.incomplete_btn.isChecked()
        self._say("")
        token = self._token = self._token + 1

        cross = self._cross

        def work():
            analysis = self._ctx.analysis.analyze(aid, fid, kind, include_incomplete=include,
                                                  start_date=start, end_date=end, answer_filter=cross)
            survey = self._ctx.surveys.get_survey(aid, fid)
            goal = self._ctx.surveys.goals(aid).get(fid) if survey.goal else None
            return analysis, survey, goal, self._ctx.analysis.cross_questions(aid, fid)

        def ok(res):
            if token != self._token:           # llegó tarde: ya se pidió otra cosa
                return
            self._render(*res)

        self._runner.run(work, ok, lambda e: token == self._token and self._on_error(e))

    def _clear(self) -> None:
        while self.body.count():
            item = self.body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render(self, a, survey, goal=None, cross_questions=()) -> None:
        self.result = a
        self._cross_questions = list(cross_questions)
        self._clear()
        self._ctx.note("analisis_mostrado", filtro=a.filter.kind, respuestas=a.overview.total)
        when = P.format_relative(survey.last_synced_at) if survey.last_synced_at else "—"
        meta = QLabel(S.ANALYSIS_DATA_FROM.format(when=when))
        meta.setProperty("role", "meta")
        meta.setWordWrap(True)
        self.body.addWidget(meta)
        for w in a.warnings:
            text = {"tipos_no_interpretados": S.ANALYSIS_WARN_NOT_INTERPRETED,
                    "preguntas_agregadas_despues": S.ANALYSIS_WARN_LATER_QUESTIONS}.get(w)
            if text:
                banner = QLabel(text)
                banner.setProperty("role", "banner")
                banner.setWordWrap(True)
                self.body.addWidget(banner)

        if survey.goal and goal is not None:               # bloque de meta (usa todas las respuestas guardadas)
            card, lay = _card()
            head = QLabel(S.GOAL_BLOCK_TITLE)
            head.setProperty("role", "section")
            lay.addWidget(head)
            self.goal_bar = GoalBar(survey.local_submissions, survey.goal, goal)
            lay.addWidget(self.goal_bar)
            self.body.addWidget(card)

        if a.answer_filter is not None:                    # cinta del cruce activo
            self.body.addWidget(self._cross_ribbon(a))

        # resumen
        tiles = QHBoxLayout()
        for label, value in P.overview_tiles(a.overview):
            card, lay = _card()
            num = QLabel(value)
            num.setProperty("role", "tile-number")
            cap = QLabel(label)
            cap.setProperty("role", "muted")
            lay.addWidget(num)
            lay.addWidget(cap)
            tiles.addWidget(card)
        holder = QWidget()
        holder.setLayout(tiles)
        tiles.setContentsMargins(0, 0, 0, 0)
        self.body.addWidget(holder)
        span = P.span_text(a.overview)
        if span:
            lbl = QLabel(span)
            lbl.setProperty("role", "meta")
            self.body.addWidget(lbl)

        if a.overview.total == 0:
            if a.answer_filter is not None:
                empty = QLabel(S.CROSS_NOBODY)
            else:
                empty = QLabel(S.ANALYSIS_EMPTY_PERIOD if a.filter.kind != "all" else S.ANALYSIS_NOTHING_SAVED)
            empty.setProperty("role", "notice")
            empty.setWordWrap(True)
            self.body.addWidget(empty)
            if a.answer_filter is not None:
                self.body.addWidget(self._cross_card())          # para poder quitar o cambiar el filtro
            return

        # línea de tiempo
        card, lay = _card()
        head = QLabel(f"{S.ANALYSIS_TIMELINE} · {S.ANALYSIS_BUCKETS.get(a.timeline.bucket, '')}")
        head.setProperty("role", "section")
        lay.addWidget(head)
        self.timeline_chart = TimelineChart()
        self.timeline_chart.set_series(P.timeline_series(a.timeline))
        lay.addWidget(self.timeline_chart)
        self.body.addWidget(card)

        self.body.addWidget(self._rhythm_card(a))
        if self._cross_questions or a.answer_filter is not None:
            self.body.addWidget(self._cross_card())

        # preguntas
        sec = QLabel(S.ANALYSIS_QUESTIONS)
        sec.setProperty("role", "section")
        self.body.addWidget(sec)
        for i, q in enumerate(a.questions, 1):
            self.body.addWidget(self._question_card(q, i))

    # ---------- ritmo ----------
    def _rhythm_card(self, a) -> QFrame:
        t = a.trends
        card, lay = _card()
        head = QLabel(S.RHYTHM_TITLE)
        head.setProperty("role", "section")
        lay.addWidget(head)
        self.rhythm_week = QLabel(P.rhythm_week_text(t))
        self.rhythm_week.setProperty("role", "section")
        lay.addWidget(self.rhythm_week)
        note = QLabel(S.RHYTHM_WEEK_NOTE)
        note.setProperty("role", "meta")
        note.setWordWrap(True)
        lay.addWidget(note)
        self.rhythm_peak = QLabel(P.rhythm_peak_text(t))
        lay.addWidget(self.rhythm_peak)
        comp = P.rhythm_completion_text(t)
        self.rhythm_completion = QLabel(comp)
        self.rhythm_completion.setVisible(bool(comp))
        lay.addWidget(self.rhythm_completion)
        sub = QLabel(S.RHYTHM_WEEKDAYS_TITLE)
        sub.setProperty("role", "muted")
        lay.addWidget(sub)
        self.weekday_chart = BarChart()
        self.weekday_chart.set_rows(P.weekday_rows(t), show_pct=False)
        lay.addWidget(self.weekday_chart)
        sub2 = QLabel(S.RHYTHM_HOURS_TITLE)
        sub2.setProperty("role", "muted")
        lay.addWidget(sub2)
        self.hour_chart = TimelineChart()
        self.hour_chart.set_series(P.hour_series(t))
        lay.addWidget(self.hour_chart)
        return card

    # ---------- cruzar preguntas ----------
    def _cross_title(self, question_id: str) -> str:
        return next((q.title for q in self._cross_questions if q.question_id == question_id), question_id)

    def _cross_ribbon(self, a) -> QFrame:
        card, lay = _card()
        text = QLabel(P.cross_ribbon_text(a, self._cross_title(a.answer_filter.question_id)))
        text.setProperty("role", "section")
        text.setWordWrap(True)
        lay.addWidget(text)
        self.cross_ribbon_label = text
        for note in (S.CROSS_EXPORT_NOTE, S.CROSS_SELF_NOTE):
            lbl = QLabel(note)
            lbl.setProperty("role", "meta")
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
        clear = QPushButton(S.CROSS_CLEAR)
        clear.clicked.connect(self.clear_cross)
        row = QHBoxLayout()
        row.addWidget(clear)
        row.addStretch(1)
        lay.addLayout(row)
        self.cross_clear_btn = clear
        return card

    def _cross_card(self) -> QFrame:
        card, lay = _card()
        head = QLabel(S.CROSS_TITLE)
        head.setProperty("role", "section")
        lay.addWidget(head)
        if not self._cross_questions:
            lbl = QLabel(S.CROSS_NO_QUESTIONS)
            lbl.setProperty("role", "muted")
            lay.addWidget(lbl)
            return card
        help_lbl = QLabel(S.CROSS_HELP)
        help_lbl.setProperty("role", "muted")
        help_lbl.setWordWrap(True)
        lay.addWidget(help_lbl)
        row = QHBoxLayout()
        row.addWidget(QLabel(S.CROSS_QUESTION))
        self.cross_question_combo = QComboBox()
        self.cross_question_combo.setAccessibleName(S.CROSS_QUESTION)
        for q in self._cross_questions:
            self.cross_question_combo.addItem(q.title or q.question_id, q.question_id)
        row.addWidget(self.cross_question_combo, 1)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel(S.CROSS_OPTION))
        self.cross_option_combo = QComboBox()
        self.cross_option_combo.setAccessibleName(S.CROSS_OPTION)
        row2.addWidget(self.cross_option_combo, 1)
        lay.addLayout(row2)
        sel_q = (self._cross_sel or (None, None))[0] or (self._cross.question_id if self._cross else None)
        idx = self.cross_question_combo.findData(sel_q) if sel_q else 0
        self.cross_question_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._fill_cross_options()
        self.cross_question_combo.currentIndexChanged.connect(self._cross_question_changed)
        buttons = QHBoxLayout()
        self.cross_apply_btn = QPushButton(S.CROSS_APPLY)
        self.cross_apply_btn.setProperty("variant", "primary")
        self.cross_apply_btn.clicked.connect(self.apply_cross)
        buttons.addWidget(self.cross_apply_btn)
        buttons.addStretch(1)
        lay.addLayout(buttons)
        return card

    def _fill_cross_options(self) -> None:
        qid = self.cross_question_combo.currentData()
        q = next((x for x in self._cross_questions if x.question_id == qid), None)
        self.cross_option_combo.clear()
        for opt in (q.options if q else ()):
            self.cross_option_combo.addItem(opt, opt)
        wanted = (self._cross_sel[1] if self._cross_sel and self._cross_sel[0] == qid else None)
        idx = self.cross_option_combo.findData(wanted) if wanted else -1
        if idx >= 0:
            self.cross_option_combo.setCurrentIndex(idx)

    def _cross_question_changed(self, _index: int) -> None:
        self._cross_sel = None
        self._fill_cross_options()

    def apply_cross(self) -> None:
        if self.cross_question_combo is None or self.cross_option_combo is None:
            return
        qid, opt = self.cross_question_combo.currentData(), self.cross_option_combo.currentData()
        if not qid or opt is None:
            return
        self._cross, self._cross_sel = AnswerFilter(qid, opt), (qid, opt)
        self._ctx.note("cruce_aplicado")
        self._reload()

    def clear_cross(self) -> None:
        self._cross = None
        self._ctx.note("cruce_quitado")
        self._reload()

    def _question_card(self, q, number: int) -> QFrame:
        card, lay = _card()
        title = QLabel(f"{number}. {q.title or S.ANALYSIS_DELETED_QUESTION}" + (
            f" {S.ANALYSIS_DELETED_QUESTION}" if q.is_deleted and q.title else ""))
        title.setWordWrap(True)
        title.setProperty("role", "section")
        lay.addWidget(title)
        counts = QLabel(P.question_counts_text(q))
        counts.setProperty("role", "meta")
        counts.setWordWrap(True)
        lay.addWidget(counts)
        if q.kind in ("single", "multi"):
            chart = BarChart()
            chart.set_rows(P.bar_rows(q))
            lay.addWidget(chart)
            extra = P.other_values_text(q)
            if extra:
                lbl = QLabel(extra)
                lbl.setProperty("role", "muted")
                lbl.setWordWrap(True)
                lay.addWidget(lbl)
        elif q.kind == "text":
            lbl = QLabel(S.ANALYSIS_TEXT_STATS.format(avg=P.format_decimal(q.avg_len, 0), max=q.max_len or 0))
            lbl.setProperty("role", "muted")
            lay.addWidget(lbl)
            hint = QLabel(S.ANALYSIS_TEXT_HINT)
            hint.setProperty("role", "meta")
            lay.addWidget(hint)
        else:
            lbl = QLabel(S.ANALYSIS_NOT_INTERPRETED.format(type=q.type))
            lbl.setProperty("role", "muted")
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
        return card

    def _on_error(self, error) -> None:
        self._say(error.user_message)

    def _say(self, message: str) -> None:
        self.notice.setText(message)
        self.notice.setVisible(bool(message))

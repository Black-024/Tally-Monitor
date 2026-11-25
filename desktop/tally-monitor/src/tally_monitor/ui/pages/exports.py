"""Exportar (Excel, PDF, PNG): resumen de la encuesta o respuestas individuales. Solo usa servicios."""
from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QVBoxLayout, QWidget)

from ...services.export_service import ExportOptions
from .. import presenters as P
from .. import strings as S
from ..context import AppContext
from ..dialogs.simple_dialogs import confirm_destructive
from ...core.assets import find_logo
from ..theme import current as theme
from ..theme.qss import build_qss
from ..theme.tokens import FONT_FAMILIES, palette
from ..widgets.pill_button import PillButton
from ..widgets.bar_chart import BarChart
from ..widgets.timeline_chart import TimelineChart
from ..workers import TaskRunner

MAX_PNG_PEOPLE = 40
BIG_PDF_PEOPLE = 3000          # desde acá el PDF individual avisa que puede tardar (no hay tope: se puede igual)
IMAGE_WIDTH = 900


def add_watermark(pixmap, style: str = "dark") -> None:
    """Marquita «Tally Monitor» (con el logo, si hay) en la esquina inferior derecha de la imagen."""
    c = palette(style)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setOpacity(0.85)
    font = QFont(list(FONT_FAMILIES), 10)
    font.setBold(True)
    p.setFont(font)
    text = S.APP_NAME
    w = p.fontMetrics().horizontalAdvance(text)
    x, y = pixmap.width() - 20 - w, pixmap.height() - 18
    p.setPen(QColor(c["muted"]))
    p.drawText(x, y, text)
    logo_path = find_logo(style)
    logo = QPixmap(str(logo_path)) if logo_path else None
    if logo is not None and not logo.isNull():
        size = 20
        p.drawPixmap(x - size - 8, y - 15, logo.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.SmoothTransformation))
    else:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(c["action"]))
        p.drawRoundedRect(QRectF(x - 26, y - 14, 18, 18), 5, 5)
    p.end()


def pixmap_to_png(pix) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pix.save(buf, "PNG")
    data = bytes(QByteArray(buf.data()))
    buf.close()
    return data


def _render(card: QWidget, style: str) -> bytes:
    card.setStyleSheet(build_qss(palette(style)))              # el estilo del archivo no depende del de la ventana
    for kind in (BarChart, TimelineChart):                     # PySide6 no acepta una tupla de tipos
        for chart in card.findChildren(kind):
            chart.palette_override = palette(style)
    card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    card.setFixedWidth(IMAGE_WIDTH)
    card.ensurePolished()
    for child in card.findChildren(QWidget):               # estilos aplicados antes de medir (sin mostrar la ventana)
        child.ensurePolished()
    lay = card.layout()
    lay.activate()
    height = max(lay.sizeHint().height(), lay.heightForWidth(IMAGE_WIDTH) if lay.hasHeightForWidth() else 0, 200)
    card.resize(IMAGE_WIDTH, height + 40)                        # +40: espacio para la marquita
    pix = card.grab()
    add_watermark(pix, style)
    data = pixmap_to_png(pix)
    card.deleteLater()
    return data


def _canvas() -> tuple[QWidget, QVBoxLayout]:
    card = QWidget()
    lay = QVBoxLayout(card)
    lay.setContentsMargins(28, 24, 28, 24)
    lay.setSpacing(8)
    return card, lay


def render_summary_png(survey_name: str, analysis, style: str = "dark") -> bytes:
    """Los mismos gráficos de la pestaña Resumen, en una imagen."""
    card, lay = _canvas()
    title = QLabel(survey_name)
    title.setProperty("role", "title")
    title.setWordWrap(True)
    lay.addWidget(title)
    sub = QLabel(S.EXPORT_PNG_SUBTITLE.format(label=analysis.filter.label, n=analysis.overview.total))
    sub.setProperty("role", "muted")
    lay.addWidget(sub)
    head = QLabel(f"{S.ANALYSIS_TIMELINE} · {S.ANALYSIS_BUCKETS.get(analysis.timeline.bucket, '')}")
    head.setProperty("role", "section")
    lay.addWidget(head)
    tl = TimelineChart()
    tl.set_series(P.timeline_series(analysis.timeline))
    lay.addWidget(tl)
    for i, q in enumerate(analysis.questions, 1):
        if q.kind not in ("single", "multi"):
            continue
        t = QLabel(f"{i}. {q.title or S.ANALYSIS_DELETED_QUESTION}")
        t.setWordWrap(True)
        t.setProperty("role", "section")
        lay.addSpacing(8)
        lay.addWidget(t)
        c = QLabel(P.question_counts_text(q))
        c.setProperty("role", "meta")
        lay.addWidget(c)
        chart = BarChart()
        chart.set_rows(P.bar_rows(q))
        lay.addWidget(chart)
    return _render(card, style)


def render_individual_png(survey_name: str, period: str, cards, style: str = "dark") -> bytes:
    """Una ficha por persona, con el diseño de la aplicación."""
    card, lay = _canvas()
    title = QLabel(survey_name)
    title.setProperty("role", "title")
    title.setWordWrap(True)
    lay.addWidget(title)
    sub = QLabel(S.EXPORT_PNG_IND_SUBTITLE.format(n=len(cards), period=period))
    sub.setProperty("role", "muted")
    lay.addWidget(sub)
    for c in cards:
        frame = QFrame()
        frame.setObjectName("Card")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(18, 14, 18, 14)
        fl.setSpacing(4)
        who = QLabel(c.label)
        who.setProperty("role", "section")
        fl.addWidget(who)
        when = QLabel(P.format_local_naive(c.when) + ("" if c.is_completed else S.EXPORT_PNG_INCOMPLETE))
        when.setProperty("role", "meta")
        fl.addWidget(when)
        for it in c.items:
            q = QLabel(f"{it.number}. {it.title}")
            q.setProperty("role", "question")
            q.setWordWrap(True)
            fl.addWidget(q)
            box = QFrame()
            box.setObjectName("AnswerBox")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(12, 6, 12, 6)
            a = QLabel(it.text)
            a.setProperty("role", "muted" if it.is_note else "answer")
            a.setWordWrap(True)
            bl.addWidget(a)
            fl.addWidget(box)
        lay.addSpacing(6)
        lay.addWidget(frame)
    return _render(card, style)


class ExportsPage(QWidget):
    def __init__(self, ctx: AppContext, runner: TaskRunner, get_period, parent=None) -> None:
        """`get_period()` devuelve (tipo, desde, hasta, con_incompletos, texto) del período elegido en Resumen."""
        super().__init__(parent)
        self._ctx, self._runner, self._get_period = ctx, runner, get_period
        self._account_id: str | None = None
        self._form_id: str | None = None
        self._busy = False
        self._scope = "summary"
        self.ask_path = self._ask_path          # reemplazable en pruebas
        self.confirm_png_individual = lambda: confirm_destructive(
            self, S.EXPORT_PNG_IND_TITLE, S.EXPORT_PNG_IND_TEXT, S.EXPORT_PNG_IND_CONFIRM)
        self.confirm_big_pdf = lambda n: confirm_destructive(
            self, S.EXPORT_BIG_PDF_TITLE, S.EXPORT_BIG_PDF_TEXT.format(n=P.format_count(n), est=P.format_duration(n * 0.0015)),
            S.EXPORT_BIG_PDF_CONFIRM)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        scope_row = QHBoxLayout()
        self.scope_buttons: dict[str, QPushButton] = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        for key, label in (("summary", S.EXPORT_SCOPE_SUMMARY), ("individual", S.EXPORT_SCOPE_INDIVIDUAL)):
            b = PillButton(label, "chip")
            b.clicked.connect(lambda _c=False, k=key: self.set_scope(k))
            group.addButton(b)
            scope_row.addWidget(b)
            self.scope_buttons[key] = b
        self.scope_buttons["summary"].setChecked(True)
        scope_row.addStretch(1)
        outer.addLayout(scope_row)
        self.scope_hint = QLabel(S.EXPORT_SUMMARY_HINT)
        self.scope_hint.setProperty("role", "muted")
        self.scope_hint.setWordWrap(True)
        outer.addWidget(self.scope_hint)
        self.period_label = QLabel("")
        self.period_label.setProperty("role", "meta")
        outer.addWidget(self.period_label)

        # estilo visual de PDF e imagen (Excel no lleva diseño)
        style_row = QHBoxLayout()
        style_lbl = QLabel(S.EXPORT_STYLE_LABEL)
        style_lbl.setProperty("role", "muted")
        style_row.addWidget(style_lbl)
        self.style_buttons: dict[str, PillButton] = {}
        sg = QButtonGroup(self)
        sg.setExclusive(True)
        for key, label in (("dark", S.EXPORT_STYLE_DARK), ("light", S.EXPORT_STYLE_LIGHT)):
            b = PillButton(label, "chip")
            b.clicked.connect(lambda _c=False, k=key: self.set_style(k))
            sg.addButton(b)
            style_row.addWidget(b)
            self.style_buttons[key] = b
        style_row.addStretch(1)
        outer.addLayout(style_row)
        self._style = theme.name()                    # por defecto, el mismo estilo que tiene la ventana
        self.style_buttons[self._style].setChecked(True)

        # quién (solo en individuales)
        self.who_row = QWidget()
        wr = QHBoxLayout(self.who_row)
        wr.setContentsMargins(0, 0, 0, 0)
        self.who_all = PillButton(S.EXPORT_WHO_ALL, "chip")
        self.who_one = PillButton(S.EXPORT_WHO_ONE, "chip")
        wg = QButtonGroup(self)
        wg.setExclusive(True)
        for b in (self.who_all, self.who_one):
            wg.addButton(b)
            wr.addWidget(b)
        self.who_all.setChecked(True)
        self.who_one.toggled.connect(lambda on: self.who_edit.setVisible(on))
        self.who_edit = QLineEdit()
        self.who_edit.setPlaceholderText(S.EXPORT_WHO_PLACEHOLDER)
        self.who_edit.setAccessibleName(S.EXPORT_WHO_ONE)
        self.who_edit.setMaximumWidth(260)
        self.who_edit.hide()
        wr.addWidget(self.who_edit)
        wr.addStretch(1)
        self.who_row.hide()
        outer.addWidget(self.who_row)

        big = QHBoxLayout()
        big.setSpacing(14)
        self.xlsx_btn = QPushButton(S.EXPORT_BIG_XLSX)
        self.pdf_btn = QPushButton(S.EXPORT_BIG_PDF)
        self.png_btn = QPushButton(S.EXPORT_BIG_PNG)
        for b, fmt in ((self.xlsx_btn, "xlsx"), (self.pdf_btn, "pdf"), (self.png_btn, "png")):
            b.setProperty("big", "true")
            b.setMinimumHeight(110)
            b.clicked.connect(lambda _c=False, f=fmt: self.export(f))
            big.addWidget(b)
        outer.addLayout(big)

        self.text_box = QCheckBox(S.EXPORT_INCLUDE_TEXT)
        self.text_box.toggled.connect(self._text_toggled)
        outer.addWidget(self.text_box)
        self.mask_box = QCheckBox(S.EXPORT_MASK)
        self.mask_box.setChecked(True)
        self.mask_box.setEnabled(False)
        outer.addWidget(self.mask_box)
        self.text_warning = QLabel(S.EXPORT_TEXT_WARNING)
        self.text_warning.setProperty("role", "banner")
        self.text_warning.setWordWrap(True)
        self.text_warning.hide()
        outer.addWidget(self.text_warning)

        self.notice = QLabel("")
        self.notice.setProperty("role", "notice")
        self.notice.setWordWrap(True)
        self.notice.hide()
        outer.addWidget(self.notice)
        outer.addStretch(1)

    # ---------- apertura ----------
    def open_survey(self, account_id: str, form_id: str) -> None:
        self._account_id, self._form_id = account_id, form_id
        self._say("")
        self.refresh()

    def refresh(self) -> None:
        self.period_label.setText(S.PERIOD_LABEL.format(label=self._get_period()[4]))

    def set_scope(self, scope: str) -> None:
        self._scope = scope
        self.scope_buttons[scope].setChecked(True)
        individual = scope == "individual"
        self.who_row.setVisible(individual)
        self.scope_hint.setText(S.EXPORT_INDIVIDUAL_HINT if individual else S.EXPORT_SUMMARY_HINT)
        self.png_btn.setText(S.EXPORT_BIG_PNG_IND if individual else S.EXPORT_BIG_PNG)
        self.pdf_btn.setText(S.EXPORT_BIG_PDF_IND if individual else S.EXPORT_BIG_PDF)
        self.text_box.setChecked(individual)          # en individuales el texto es lo importante: viene tildado

    def set_style(self, style: str) -> None:
        self._style = style if style in self.style_buttons else "dark"
        self.style_buttons[self._style].setChecked(True)

    def follow_theme(self) -> None:
        """Al cambiar el tema de la ventana, el estilo de exportación acompaña (se puede volver a cambiar)."""
        self.set_style(theme.name())

    def _text_toggled(self, on: bool) -> None:
        self.mask_box.setEnabled(on)
        self.text_warning.setVisible(on)

    # ---------- exportar ----------
    def options(self, only_number: int | None = None) -> ExportOptions:
        kind, start, end, include_incomplete, _label = self._get_period()
        return ExportOptions(kind=kind, start_date=start, end_date=end, include_incomplete=include_incomplete,
                             include_text=self.text_box.isChecked(), mask_personal=self.mask_box.isChecked(),
                             scope=self._scope, only_number=only_number, style=self._style)

    def _ask_path(self, suggested: str, fmt: str) -> str | None:
        path, _ = QFileDialog.getSaveFileName(self, S.EXPORT_SAVE_TITLE, suggested, S.EXPORT_FILTERS[fmt])
        return path or None

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for b in (self.xlsx_btn, self.pdf_btn, self.png_btn):
            b.setEnabled(not busy)
        if busy:
            self._say(S.EXPORT_BUSY)

    def export(self, fmt: str) -> None:
        aid, fid = self._account_id, self._form_id
        if self._busy or not aid or not fid:
            return
        if self._scope == "individual" and fmt == "png" and not self.confirm_png_individual():
            return                                           # no es recomendable: solo sigue si lo confirma
        self._say("")
        wanted = self.who_edit.text().strip() if (self._scope == "individual" and self.who_one.isChecked()) else ""

        def prepare():
            number = None
            if self._scope == "individual" and self.who_one.isChecked():
                found = self._ctx.surveys.find_by_label(aid, fid, wanted)
                if found is None:
                    return None, None, 0
                number = found.number
            count = 0
            if self._scope == "individual" and fmt == "pdf" and number is None:
                survey = self._ctx.surveys.get_survey(aid, fid)
                count = survey.local_submissions if survey else 0
            return number, self._ctx.export.suggested_name(aid, fid, fmt, self._scope), count

        def got(res):
            number, name, count = res
            if name is None:
                self._say(S.EXPORT_WHO_NOT_FOUND)
                return
            if count >= BIG_PDF_PEOPLE and not self.confirm_big_pdf(count):
                return                                       # no es recomendable: solo sigue si lo confirma
            path = self.ask_path(name, fmt)
            if not path:
                return                                       # canceló el diálogo: no pasa nada
            self._start(fmt, aid, fid, path, self.options(number))

        self._runner.run(prepare, got, self._on_error)

    def _start(self, fmt: str, aid: str, fid: str, path: str, opts: ExportOptions) -> None:
        self._set_busy(True)
        self._ctx.note("exportar_pedida", formato=fmt, filtro=opts.kind, texto=opts.include_text, alcance=opts.scope)
        if fmt == "png":
            self._start_png(aid, fid, path, opts)
            return
        call = self._ctx.export.export_xlsx if fmt == "xlsx" else self._ctx.export.export_pdf
        # el diálogo nativo ya preguntó si se reemplaza un archivo existente
        self._runner.run(lambda: call(aid, fid, path, opts, overwrite=True), self._done, self._failed)

    def _start_png(self, aid: str, fid: str, path: str, opts: ExportOptions) -> None:
        if opts.scope == "individual":
            def work():
                return self._ctx.export.individual_cards(aid, fid, opts)

            def render(res):
                name, period, cards = res
                if len(cards) > MAX_PNG_PEOPLE:
                    self._set_busy(False)
                    self._say(S.EXPORT_PNG_IND_TOO_MANY.format(n=len(cards), max=MAX_PNG_PEOPLE))
                    return
                if not cards:
                    self._set_busy(False)
                    self._say(S.EXPORT_NOTHING)
                    return
                data = render_individual_png(name, period, cards, opts.style)
                self._runner.run(lambda: self._ctx.export.save_png(path, data, overwrite=True), self._done, self._failed)

            self._runner.run(work, render, self._failed)
            return

        def work2():
            analysis = self._ctx.analysis.analyze(aid, fid, opts.kind, include_incomplete=opts.include_incomplete,
                                                  start_date=opts.start_date, end_date=opts.end_date)
            return analysis, self._ctx.surveys.get_survey(aid, fid).name

        def render2(res):
            analysis, name = res
            if analysis.overview.total == 0:
                self._set_busy(False)
                self._say(S.EXPORT_NOTHING)
                return
            data = render_summary_png(name, analysis, opts.style)
            self._runner.run(lambda: self._ctx.export.save_png(path, data, overwrite=True), self._done, self._failed)

        self._runner.run(work2, render2, self._failed)

    def _done(self, result) -> None:
        self._set_busy(False)
        msg = S.EXPORT_DONE.format(path=result.path)
        if result.text_included:
            msg += S.EXPORT_DONE_EXTRA_TEXT.format(masked=S.EXPORT_MASKED if result.masked else S.EXPORT_UNMASKED)
        self._say(msg)
        self._ctx.note("exportar_hecha", formato=result.format)

    def _failed(self, error) -> None:
        self._set_busy(False)
        self._on_error(error)

    def _on_error(self, error) -> None:
        self._say(error.user_message)

    def _say(self, message: str) -> None:
        self.notice.setText(message)
        self.notice.setVisible(bool(message))

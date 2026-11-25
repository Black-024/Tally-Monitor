"""Informes PDF con el diseño de Tally Monitor, en estilo oscuro (negro, violeta, dorado) o claro (blanco, aqua, café), con la marca en una esquina.
Lógica pura: solo usa reportlab, `core` y los modelos de `analysis`."""
from __future__ import annotations

from datetime import datetime, timezone, tzinfo

from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..core.assets import find_logo
from ..core.language import pick as _t
from ..core.palette import palette
from . import format as F
from .individual import build_cards
from .xlsx_writer import PRIVACY_NOTE

WIDTH = A4[0] - 40 * mm
BRAND = "Tally Monitor"


class Pal:
    """Colores del PDF según el estilo elegido («dark» o «light»), tomados de `core.palette`."""

    def __init__(self, style: str) -> None:
        c = palette(style)
        self.style = style if style in ("dark", "light") else "dark"
        h = colors.HexColor
        self.bg, self.card, self.card2, self.line = h(c["bg"]), h(c["surface"]), h(c["surface2"]), h(c["border"])
        self.tx, self.mu, self.dim = h(c["text"]), h(c["muted"]), h(c["dim"])
        self.accent, self.action = h(c["accent"]), h(c["action"])




def _txt(s: str) -> str:
    """Helvetica solo cubre WinAnsi: lo demás (emojis, etc.) se reemplaza por «?»."""
    return (s or "").replace("‑", "-").encode("cp1252", errors="replace").decode("cp1252")


def _esc(s: str) -> str:
    return _txt(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bars_drawing(rows: list[tuple[str, int, float]], pal: Pal) -> Drawing:
    """rows: (texto, cantidad, fracción 0..1). Barras horizontales con el número siempre visible."""
    row_h = 18
    d = Drawing(WIDTH, max(row_h, row_h * len(rows)))
    label_w, value_w = WIDTH * 0.36, 78
    bar_x, bar_w = label_w + 8, WIDTH - label_w - value_w - 16
    for i, (text, count, frac) in enumerate(rows):
        y = (len(rows) - 1 - i) * row_h
        label = _txt(text)
        shown = label
        while len(shown) > 3 and len(shown) * 4.7 > label_w:
            shown = shown[:-2]
        d.add(String(0, y + 5, shown if shown == label else shown.rstrip() + "…", fontName="Helvetica", fontSize=8.5, fillColor=pal.tx))
        d.add(Rect(bar_x, y + 3, bar_w, 10, rx=5, ry=5, fillColor=pal.card2, strokeColor=None))
        if count > 0 and frac > 0:
            d.add(Rect(bar_x, y + 3, max(3.0, bar_w * min(1.0, frac)), 10, rx=5, ry=5, fillColor=pal.accent, strokeColor=None))
        d.add(String(WIDTH, y + 5, f"{count} · {F.pct(frac * 100)}", fontName="Helvetica", fontSize=8.5,
                     textAnchor="end", fillColor=pal.mu))
    return d


def timeline_drawing(series: list[tuple[str, int]], pal: Pal) -> Drawing:
    h, left, bottom = 130, 26, 18
    d = Drawing(WIDTH, h)
    plot_w, plot_h = WIDTH - left - 4, h - bottom - 8
    d.add(Line(left, bottom, left + plot_w, bottom, strokeColor=pal.line, strokeWidth=0.8))
    if not series:
        return d
    peak = max(1, max(c for _l, c in series))
    d.add(String(left - 4, h - 12, str(peak), fontName="Helvetica", fontSize=7, textAnchor="end", fillColor=pal.dim))
    d.add(String(left - 4, bottom - 2, "0", fontName="Helvetica", fontSize=7, textAnchor="end", fillColor=pal.dim))
    n = len(series)
    slot = plot_w / n
    bw = max(1.5, min(20.0, slot * 0.7))
    for i, (_l, c) in enumerate(series):
        if c > 0:
            bh = max(2.0, plot_h * c / peak)
            x = left + i * slot + (slot - bw) / 2
            d.add(Rect(x, bottom, bw, bh, rx=min(3.0, bw / 2), ry=min(3.0, bw / 2), fillColor=pal.accent, strokeColor=None))
    for i in sorted({0, n // 2, n - 1}):
        d.add(String(left + i * slot + slot / 2, 5, series[i][0], fontName="Helvetica", fontSize=7,
                     textAnchor="middle", fillColor=pal.dim))
    return d


def timeline_series(t) -> list[tuple[str, int]]:
    fmt = {"hour": _t("%d/%m %H:00", "%m/%d %H:00"), "month": "%m/%Y"}.get(t.bucket, _t("%d/%m", "%m/%d"))
    return [(p.start.strftime(fmt), p.count) for p in t.points]


def bar_rows(q) -> list[tuple[str, int, float]]:
    base = q.answered or 0
    f = (lambda n: n / base) if base else (lambda n: 0.0)
    rows = [(o.text, o.count, f(o.count)) for o in q.options]
    if q.other_count:
        rows.append((_t("Otro (texto escrito)", "Other (written text)"), q.other_count, f(q.other_count)))
    if q.orphan_count:
        rows.append((_t("Opciones que ya no existen", "Options that no longer exist"), q.orphan_count, f(q.orphan_count)))
    return rows


def _styles(pal: Pal):
    tx, mu, dim = pal.tx, pal.mu, pal.dim
    base = dict(fontName="Helvetica", textColor=tx)
    return {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=tx, spaceAfter=2),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=tx, spaceBefore=14, spaceAfter=6),
        "h3": ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=tx, spaceBefore=10, spaceAfter=2),
        "body": ParagraphStyle("body", fontSize=9.5, leading=13, **base),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=11, textColor=mu),
        "q": ParagraphStyle("q", fontName="Helvetica", fontSize=8, leading=10.5, textColor=mu),
        "a": ParagraphStyle("a", fontName="Helvetica", fontSize=10, leading=13.5, textColor=tx),
        "note": ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=9, leading=12, textColor=dim),
        "who": ParagraphStyle("who", fontName="Helvetica-Bold", fontSize=12.5, leading=15, textColor=pal.action),
        "when": ParagraphStyle("when", fontName="Helvetica", fontSize=8, leading=11, textColor=dim, alignment=2),
    }


def _page_fn(pal: Pal):
    """Fondo, franja de color arriba, número de página y la marquita «Tally Monitor» (con el logo, si hay) en la esquina."""
    logo = find_logo(pal.style)

    def _page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(pal.bg)
        canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
        canvas.setFillColor(pal.action)
        canvas.rect(0, A4[1] - 2.4 * mm, A4[0], 2.4 * mm, stroke=0, fill=1)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(pal.dim)
        canvas.drawString(20 * mm, 10 * mm, _t(f"Página {doc.page}", f"Page {doc.page}"))
        canvas.setFillAlpha(0.85)                                    # marca de agua discreta, abajo a la derecha
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(pal.mu)
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, BRAND)
        tw = canvas.stringWidth(BRAND, "Helvetica-Bold", 9)
        x = A4[0] - 20 * mm - tw - 6.5 * mm
        drawn = False
        if logo is not None:
            try:
                canvas.drawImage(str(logo), x, 8.8 * mm, 5 * mm, 5 * mm, mask="auto", preserveAspectRatio=True)
                drawn = True
            except Exception:  # noqa: BLE001 - un logo ilegible no debe impedir exportar
                drawn = False
        if not drawn:
            canvas.setFillColor(pal.action)
            canvas.roundRect(x, 9.2 * mm, 4 * mm, 4 * mm, 1.2 * mm, stroke=0, fill=1)
        canvas.restoreState()
    return _page


def _doc(path: str, title: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(path, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                             bottomMargin=20 * mm, title=_txt(title), author=BRAND)


def _tiles(values: list[tuple[str, str]], pal: Pal) -> Table:
    t = Table([[v for v, _l in values], [l for _v, l in values]], colWidths=[WIDTH / len(values)] * len(values))
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 20),
                           ("TEXTCOLOR", (0, 0), (-1, 0), pal.tx), ("FONTSIZE", (0, 1), (-1, 1), 8),
                           ("TEXTCOLOR", (0, 1), (-1, 1), pal.mu), ("BACKGROUND", (0, 0), (-1, -1), pal.card),
                           ("ROUNDEDCORNERS", [10, 10, 10, 10]), ("INNERGRID", (0, 0), (-1, -1), 0.6, pal.line),
                           ("LEADING", (0, 0), (-1, 0), 26), ("LEADING", (0, 1), (-1, 1), 11),
                           ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 0), (-1, 0), 10),
                           ("BOTTOMPADDING", (0, 1), (-1, 1), 10)]))
    return t


def write_pdf(path: str, *, survey_name: str, analysis, rows, tz: tzinfo, options, generated_at_local: datetime,
              label_for=None) -> None:
    if getattr(options, "scope", "summary") == "individual":
        return write_individual_pdf(path, survey_name=survey_name, analysis=analysis, rows=rows, tz=tz,
                                    options=options, generated_at_local=generated_at_local, label_for=label_for)
    pal = Pal(getattr(options, "style", "dark"))
    st = _styles(pal)
    o = analysis.overview
    sub = _t(f"{analysis.filter.label} · envíos incompletos {'incluidos' if options.include_incomplete else 'excluidos'}"
             f" · generado el {F.dt(generated_at_local)}",
             f"{analysis.filter.label} · incomplete submissions {'included' if options.include_incomplete else 'excluded'}"
             f" · generated on {F.dt(generated_at_local)}")
    story = [Paragraph(_esc(survey_name), st["title"]), Paragraph(_esc(sub), st["small"]), Spacer(1, 10),
             _tiles([(str(o.total), _t("Respuestas", "Responses")), (str(o.completed), _t("Completas", "Complete")), (str(o.partial), _t("Incompletas", "Incomplete")),
                     (F.dec(o.per_day, 2), _t("Promedio por día", "Average per day"))], pal)]
    if o.first_at:
        story.append(Spacer(1, 4))
        story.append(Paragraph(_esc(_t(f"Primera respuesta: {F.dt(_local(o.first_at, tz))} · Última: {F.dt(_local(o.last_at, tz))}", f"First response: {F.dt(_local(o.first_at, tz))} · Last: {F.dt(_local(o.last_at, tz))}")), st["small"]))
    if o.total == 0:
        story.append(Paragraph(_t("No hay respuestas en este período.", "There are no responses in this period."), st["body"]))
        _doc(path, _t(f"Informe — {survey_name}", f"Report — {survey_name}")).build(story, onFirstPage=_page_fn(pal), onLaterPages=_page_fn(pal))
        return
    bucket = {"hour": _t("por hora", "by hour"), "day": _t("por día", "by day"), "month": _t("por mes", "by month")}.get(analysis.timeline.bucket, "")
    story += [Paragraph(_t(f"Respuestas en el tiempo · {bucket}", f"Responses over time · {bucket}"), st["h2"]), timeline_drawing(timeline_series(analysis.timeline), pal),
              Paragraph(_t("Preguntas", "Questions"), st["h2"])]
    by_q: dict = {}
    for r in rows:
        for qid, cell in r.cells.items():
            by_q.setdefault(qid, []).append(cell)
    from .xlsx_writer import cell_text
    for number, q in enumerate(analysis.questions, 1):
        head = f"{number}. {q.title or _t('(sin título)', '(untitled)')}" + (_t(" (eliminada)", " (deleted)") if q.is_deleted else "")
        counts = (_t(f"{q.answered} respondieron · {q.blank} sin respuesta", f"{q.answered} answered · {q.blank} blank")
                  + (_t(f" · {q.not_asked} no la vieron", f" · {q.not_asked} did not see it") if q.not_asked else ""))
        block = [Paragraph(_esc(head), st["h3"]), Paragraph(_esc(counts), st["small"]), Spacer(1, 4)]
        if q.kind in ("single", "multi"):
            block.append(bars_drawing(bar_rows(q), pal))
            story.append(KeepTogether(block))
        elif q.kind == "text":
            avg = F.dec(q.avg_len, 0) if q.avg_len is not None else "—"
            block.append(Paragraph(_t(f"Largo promedio: {avg} caracteres · máximo: {q.max_len or 0}", f"Average length: {avg} characters · maximum: {q.max_len or 0}"), st["body"]))
            story.append(KeepTogether(block))
            if options.include_text:
                texts = [cell_text(c, include_text=True, mask=options.mask_personal) for c in by_q.get(q.question_id, [])]
                texts = [t for t in texts if t]
                for t in texts[:200]:
                    story.append(Paragraph("• " + _esc(t[:600]), st["body"]))
                if len(texts) > 200:
                    story.append(Paragraph(_t(f"… y {len(texts) - 200} más (están en el Excel).", f"… and {len(texts) - 200} more (they are in the Excel file)."), st["small"]))
        else:
            block.append(Paragraph(_t(f"Tipo de pregunta sin análisis propio ({_esc(q.type)}).", f"Question type without its own analysis ({_esc(q.type)})."), st["small"]))
            story.append(KeepTogether(block))
    if options.include_text:
        story += [Spacer(1, 10), Paragraph(_esc(PRIVACY_NOTE), st["small"])]
    _doc(path, _t(f"Informe — {survey_name}", f"Report — {survey_name}")).build(story, onFirstPage=_page_fn(pal), onLaterPages=_page_fn(pal))


def _local(iso: str, tz: tzinfo) -> datetime:
    return datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(tz).replace(tzinfo=None)


def _card_table(card, st, pal: Pal) -> Table:
    """Ficha de una persona: encabezado + (pregunta chica, respuesta en recuadro con borde de acento)."""
    when = F.dt(card.when) + ("" if card.is_completed else _t(" · incompleta", " · incomplete"))
    data = [[Paragraph(_esc(card.label), st["who"]), Paragraph(_esc(when), st["when"])]]
    style = [("BACKGROUND", (0, 0), (-1, -1), pal.card), ("ROUNDEDCORNERS", [12, 12, 12, 12]),
             ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
             ("TOPPADDING", (0, 0), (-1, 0), 10), ("BOTTOMPADDING", (0, 0), (-1, 0), 4), ("VALIGN", (0, 0), (-1, 0), "MIDDLE")]
    r = 1
    for it in card.items:
        data.append([Paragraph(_esc(f"{it.number}. {it.title}"), st["q"]), ""])
        style += [("SPAN", (0, r), (1, r)), ("TOPPADDING", (0, r), (-1, r), 6), ("BOTTOMPADDING", (0, r), (-1, r), 1)]
        data.append([Paragraph(_esc(it.text), st["note"] if it.is_note else st["a"]), ""])
        style += [("SPAN", (0, r + 1), (1, r + 1)), ("BACKGROUND", (0, r + 1), (1, r + 1), pal.card2),
                  ("LINEBEFORE", (0, r + 1), (0, r + 1), 3, pal.accent),
                  ("TOPPADDING", (0, r + 1), (-1, r + 1), 6), ("BOTTOMPADDING", (0, r + 1), (-1, r + 1), 6)]
        r += 2
    if not card.items:
        data.append([Paragraph(_t("Sin respuestas registradas.", "No responses recorded."), st["note"]), ""])
        style.append(("SPAN", (0, 1), (1, 1)))
    style.append(("BOTTOMPADDING", (0, len(data) - 1), (-1, len(data) - 1), 10))
    t = Table(data, colWidths=[WIDTH * 0.62, WIDTH * 0.38], splitByRow=1)
    t.setStyle(TableStyle(style))
    return t


def write_individual_pdf(path: str, *, survey_name: str, analysis, rows, tz: tzinfo, options, generated_at_local: datetime,
                         label_for) -> None:
    pal = Pal(getattr(options, "style", "dark"))
    st = _styles(pal)
    cards = build_cards(analysis, rows, tz, label_for, include_text=options.include_text, mask=options.mask_personal)
    span = ""
    if cards:
        first, last = min(c.when for c in cards), max(c.when for c in cards)
        span = _t(f" · del {F.dt(first)} al {F.dt(last)}", f" · from {F.dt(first)} to {F.dt(last)}")
    story = [Paragraph(_esc(survey_name), st["title"]),
             Paragraph(_esc(_t(f"{len(cards)} respuestas individuales{span} · {analysis.filter.label} · generado el {F.dt(generated_at_local)}", f"{len(cards)} individual responses{span} · {analysis.filter.label} · generated on {F.dt(generated_at_local)}")),
                       st["small"])]
    if options.include_text:
        story.append(Spacer(1, 4))
        story.append(Paragraph(_esc(PRIVACY_NOTE), st["small"]))
    story.append(Spacer(1, 10))
    if not cards:
        story.append(Paragraph(_t("No hay respuestas en este período.", "There are no responses in this period."), st["body"]))
    for card in cards:
        t = _card_table(card, st, pal)
        story.append(KeepTogether([t]) if len(card.items) <= 10 else t)
        story.append(Spacer(1, 10))
    _doc(path, _t(f"Respuestas — {survey_name}", f"Responses — {survey_name}")).build(story, onFirstPage=_page_fn(pal), onLaterPages=_page_fn(pal))

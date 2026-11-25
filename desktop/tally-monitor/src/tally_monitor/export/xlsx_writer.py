"""Escribe el libro de Excel (.xlsx). Lógica pura; el servicio decide dónde y cuándo guardarlo."""
from __future__ import annotations

from datetime import datetime, timezone, tzinfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from ..core.language import pick as _t
from .masking import mask_text

PRIVACY_NOTE = _t("Las respuestas de texto libre pueden contener datos personales escritos voluntariamente por las "
                  "personas. El enmascarado automático ayuda, pero no garantiza ocultar todo: revisá el archivo antes "
                  "de compartirlo.",
                  "Free-text responses may contain personal data that people wrote voluntarily. Automatic masking helps "
                  "but does not guarantee that everything is hidden: review the file before sharing it.")
_XL_DT = _t("dd/mm/yyyy hh:mm", "mm/dd/yyyy hh:mm")
_XL_D = _t("dd/mm/yyyy", "mm/dd/yyyy")
_UNTITLED = _t("(sin título)", "(untitled)")
_DELETED = _t(" (eliminada)", " (deleted)")
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
_HEAD_FILL = PatternFill("solid", fgColor="DDE1F5")


def _local(iso: str, tz: tzinfo) -> datetime:
    dt = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).replace(tzinfo=None)


def _put(ws, row: int, col: int, value, *, fmt: str | None = None, bold: bool = False):
    """Escribe una celda. Un texto que empieza con = + - @ se guarda como TEXTO (nunca como fórmula)."""
    cell = ws.cell(row=row, column=col, value=value)
    if isinstance(value, str):
        cell.data_type = "s"
        if value.startswith(_FORMULA_START):
            cell.quotePrefix = True                            # Excel lo trata como texto, nunca como fórmula
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    if fmt:
        cell.number_format = fmt
    if bold:
        cell.font = Font(bold=True)
    return cell


def _header(ws, row: int, titles: list[str]) -> None:
    for i, t in enumerate(titles, 1):
        c = _put(ws, row, i, t, bold=True)
        c.fill = _HEAD_FILL


def _widths(ws, widths: list[int]) -> None:
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def cell_text(cell, *, include_text: bool, mask: bool) -> str | None:
    """Texto de una respuesta para una celda (None = vacía)."""
    if cell is None:
        return None
    kind, is_blank, text, choices = cell
    if is_blank:
        return None
    if kind in ("single", "multi"):
        return " | ".join(t for t, _o in choices) or None
    if kind == "text":
        if not include_text or text is None:
            return None
        return mask_text(text) if mask else text
    return None


def write_xlsx(path: str, *, survey_name: str, analysis, rows, label_for, tz: tzinfo, options,
               generated_at_local: datetime) -> None:
    wb = Workbook()
    individual = getattr(options, "scope", "summary") == "individual"

    # ---- Resumen ----
    ws = wb.active
    ws.title = _t("Resumen", "Summary")
    o = analysis.overview
    _put(ws, 1, 1, _t("Tally Monitor — exportación", "Tally Monitor — export"), bold=True)
    items = [
        (_t("Encuesta", "Survey"), survey_name),
        (_t("Período", "Period"), analysis.filter.label),
        (_t("Envíos incompletos", "Incomplete submissions"), _t("incluidos", "included") if options.include_incomplete else _t("excluidos", "excluded")),
        (_t("Generado", "Generated"), generated_at_local),
        (_t("Respuestas", "Responses"), o.total), (_t("Completas", "Complete"), o.completed), (_t("Incompletas", "Incomplete"), o.partial),
        (_t("Promedio por día", "Average per day"), round(o.per_day, 2) if o.per_day is not None else None),
        (_t("Primera respuesta", "First response"), _local(o.first_at, tz) if o.first_at else None),
        (_t("Última respuesta", "Last response"), _local(o.last_at, tz) if o.last_at else None),
        (_t("Respuestas de texto", "Text responses"), (_t("incluidas", "included") + (_t(", con datos personales enmascarados", ", with personal data masked") if options.mask_personal
                                                else _t(", SIN enmascarar", ", NOT masked"))) if options.include_text else _t("no incluidas", "not included")),
    ]
    for i, (k, v) in enumerate(items, 3):
        _put(ws, i, 1, k, bold=True)
        _put(ws, i, 2, v, fmt=_XL_DT if isinstance(v, datetime) else None)
    note = _put(ws, len(items) + 4, 1, PRIVACY_NOTE)
    ws.merge_cells(start_row=len(items) + 4, start_column=1, end_row=len(items) + 4, end_column=2)
    note.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[len(items) + 4].height = 62
    _widths(ws, [26, 60])

    # ---- Estadísticas ----
    if individual:
        return _individual_sheets(wb, path, analysis=analysis, rows=rows, label_for=label_for, tz=tz, options=options)
    ws = wb.create_sheet(_t("Estadísticas", "Statistics"))
    _header(ws, 1, [_t("N.º", "No."), _t("Pregunta", "Question"), _t("Opción", "Option"), _t("Cantidad", "Count"), _t("% de quienes respondieron", "% of respondents")])
    r = 2
    for number, q in enumerate(analysis.questions, 1):
        title = (q.title or _UNTITLED) + (_DELETED if q.is_deleted else "")
        _put(ws, r, 1, number)
        _put(ws, r, 2, title, bold=True)
        _put(ws, r, 3, _t(f"Respondieron {q.answered} · sin respuesta {q.blank}", f"Answered {q.answered} · blank {q.blank}")
             + (_t(f" · no la vieron {q.not_asked}", f" · did not see it {q.not_asked}") if q.not_asked else ""))
        r += 1
        if q.kind in ("single", "multi"):
            for opt in q.options:
                _put(ws, r, 3, opt.text)
                _put(ws, r, 4, opt.count)
                _put(ws, r, 5, opt.pct / 100.0, fmt="0.0%")
                r += 1
            for label, n in ((_t("Otro (texto escrito)", "Other (written text)"), q.other_count), (_t("Opciones que ya no existen", "Options that no longer exist"), q.orphan_count)):
                if n:
                    _put(ws, r, 3, label)
                    _put(ws, r, 4, n)
                    _put(ws, r, 5, (n / q.answered) if q.answered else 0.0, fmt="0.0%")
                    r += 1
        elif q.kind == "text":
            _put(ws, r, 3, _t("Largo promedio (caracteres)", "Average length (characters)"))
            _put(ws, r, 4, round(q.avg_len, 1) if q.avg_len is not None else None)
            r += 1
        else:
            _put(ws, r, 3, _t("Tipo de pregunta sin análisis propio", "Question type without its own analysis"))
            r += 1
    _widths(ws, [6, 50, 42, 12, 24])
    ws.freeze_panes = "A2"

    # ---- Línea de tiempo ----
    ws = wb.create_sheet(_t("En el tiempo", "Over time"))
    _header(ws, 1, [_t("Intervalo (hora local)", "Interval (local time)"), _t("Respuestas", "Responses")])
    fmt = {"hour": _XL_DT, "day": _XL_D, "month": "mm/yyyy"}.get(analysis.timeline.bucket, _XL_D)
    for i, p in enumerate(analysis.timeline.points, 2):
        _put(ws, i, 1, p.start.replace(tzinfo=None) if hasattr(p.start, "replace") else p.start, fmt=fmt)
        _put(ws, i, 2, p.count)
    _widths(ws, [24, 14])
    ws.freeze_panes = "A2"

    # ---- Respuestas individuales ----
    ws = wb.create_sheet(_t("Respuestas", "Responses"))
    shown = [q for q in analysis.questions if not (q.kind == "text" and not options.include_text)]
    _header(ws, 1, [_t("Usuario", "User"), _t("Fecha y hora (local)", "Date and time (local)"), _t("Estado", "Status")] +
            [f"{analysis.questions.index(q) + 1}. {q.title or _UNTITLED}" + (_DELETED if q.is_deleted else "") for q in shown])
    for i, row in enumerate(rows, 2):
        _put(ws, i, 1, label_for(row.key))
        _put(ws, i, 2, _local(row.submitted_at, tz), fmt=_XL_DT)
        _put(ws, i, 3, _t("Completa", "Complete") if row.is_completed else _t("Incompleta", "Incomplete"))
        for j, q in enumerate(shown, 4):
            v = cell_text(row.cells.get(q.question_id), include_text=options.include_text, mask=options.mask_personal)
            if v is not None:
                _put(ws, i, j, v)
    _widths(ws, [14, 20, 12] + [32] * len(shown))
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(path)


def _individual_sheets(wb, path: str, *, analysis, rows, label_for, tz: tzinfo, options) -> None:
    """Respuestas individuales: tabla ancha (una fila por persona) y «Detalle» (una fila por respuesta)."""
    from .individual import build_cards
    cards = build_cards(analysis, rows, tz, label_for, include_text=options.include_text, mask=options.mask_personal)
    ws = wb.create_sheet(_t("Respuestas", "Responses"))
    shown = [q for q in analysis.questions if not (q.kind == "text" and not options.include_text)]
    _header(ws, 1, [_t("Usuario", "User"), _t("Fecha y hora (local)", "Date and time (local)"), _t("Estado", "Status")] +
            [f"{analysis.questions.index(q) + 1}. {q.title or _UNTITLED}" + (_DELETED if q.is_deleted else "")
             for q in shown])
    for i, row in enumerate(rows, 2):
        _put(ws, i, 1, label_for(row.key))
        _put(ws, i, 2, _local(row.submitted_at, tz), fmt=_XL_DT)
        _put(ws, i, 3, _t("Completa", "Complete") if row.is_completed else _t("Incompleta", "Incomplete"))
        for j, q in enumerate(shown, 4):
            v = cell_text(row.cells.get(q.question_id), include_text=options.include_text, mask=options.mask_personal)
            if v is not None:
                _put(ws, i, j, v)
    _widths(ws, [14, 20, 12] + [32] * len(shown))
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    ws = wb.create_sheet(_t("Detalle", "Detail"))
    _header(ws, 1, [_t("Usuario", "User"), _t("Fecha y hora (local)", "Date and time (local)"), _t("N.º", "No."), _t("Pregunta", "Question"), _t("Respuesta", "Response")])
    r = 2
    for c in cards:
        for it in c.items:
            _put(ws, r, 1, c.label)
            _put(ws, r, 2, c.when, fmt=_XL_DT)
            _put(ws, r, 3, it.number)
            _put(ws, r, 4, it.title)
            _put(ws, r, 5, it.text)
            r += 1
    _widths(ws, [14, 20, 6, 48, 60])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(path)

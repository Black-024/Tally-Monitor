"""Fichas de respuestas individuales («Usuario NNN»), compartidas por PDF, Excel y la imagen PNG."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo

from ..core.language import pick as _t
from .masking import mask_text

NOTE_TEXT_OMITTED = _t("Respuesta de texto no incluida en esta exportación.", "Text response not included in this export.")


@dataclass(frozen=True)
class AnswerItem:
    number: int                    # n.º de pregunta (1…n, en el orden de la encuesta)
    title: str
    text: str
    is_note: bool = False          # True: no es una respuesta sino un aviso (p. ej. texto no incluido)


@dataclass(frozen=True)
class ResponseCard:
    key: int
    label: str                     # «Usuario 001»
    when: datetime                 # hora local, sin zona
    is_completed: bool
    items: tuple[AnswerItem, ...]


def _local(iso: str, tz: tzinfo) -> datetime:
    dt = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).replace(tzinfo=None)


def build_cards(analysis, rows, tz: tzinfo, label_for, *, include_text: bool, mask: bool) -> list[ResponseCard]:
    """Solo se muestran las preguntas que la persona respondió (las saltadas u opcionales sin respuesta no aparecen)."""
    cards = []
    for row in rows:
        items = []
        for number, q in enumerate(analysis.questions, 1):
            cell = row.cells.get(q.question_id)
            if cell is None:
                continue
            kind, is_blank, text, choices = cell
            if is_blank:
                continue
            title = (q.title or _t("(sin título)", "(untitled)")) + (_t(" (pregunta eliminada)", " (deleted question)") if q.is_deleted else "")
            if kind in ("single", "multi"):
                value = ", ".join(t for t, _o in choices)
                if value:
                    items.append(AnswerItem(number, title, value))
            elif kind == "text":
                if include_text and text:
                    items.append(AnswerItem(number, title, mask_text(text) if mask else text))
                else:
                    items.append(AnswerItem(number, title, NOTE_TEXT_OMITTED, is_note=True))
        cards.append(ResponseCard(row.key, label_for(row.key), _local(row.submitted_at, tz), row.is_completed,
                                  tuple(items)))
    return cards

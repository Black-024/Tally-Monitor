"""Cruce de preguntas: qué envíos eligieron una opción. Función pura."""
from __future__ import annotations

from typing import Iterable

from .models import AnswerFilter, AnswerPoint, QuestionInfo

FILTERABLE_TYPES = ("MULTIPLE_CHOICE", "CHECKBOXES")      # los que el análisis interpreta como opción única / múltiple


def norm(text: str) -> str:
    """Normaliza espacios (recorta y colapsa) para comparar opciones."""
    return " ".join((text or "").split())


def filterable_questions(questions: Iterable[QuestionInfo]) -> list[QuestionInfo]:
    return [q for q in questions if q.type in FILTERABLE_TYPES and not q.is_deleted]


def is_filterable(question: QuestionInfo | None) -> bool:
    return question is not None and question.type in FILTERABLE_TYPES


def matching_keys(answers: Iterable[AnswerPoint], flt: AnswerFilter) -> set[int]:
    """Claves de los envíos cuya respuesta a flt.question_id incluye la opción (comparación tras normalizar
    espacios; en selección múltiple basta con que esté entre las elegidas). Solo cuentan las opciones declaradas:
    un texto escrito en «Otro» no es esa opción."""
    wanted = norm(flt.option_text)
    out: set[int] = set()
    for a in answers:
        if a.question_id != flt.question_id or a.is_blank:
            continue
        if any(origin == "declared" and norm(text) == wanted for text, origin in a.choices):
            out.add(a.key)
    return out

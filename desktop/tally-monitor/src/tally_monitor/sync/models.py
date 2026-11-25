"""Filas normalizadas (sin dependencias de base de datos ni de red)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FormRow:
    form_id: str
    name: str
    status: str
    is_closed: bool
    workspace_id: str | None
    reported_submissions: int | None
    created_at: str | None
    updated_at: str | None


@dataclass(frozen=True)
class QuestionRow:
    question_id: str
    position: int
    type: str
    title: str
    reported_responses: int | None
    group_uuid: str | None
    has_other_option: bool
    is_deleted: bool
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChoiceRow:
    option_text: str
    origin: str                      # declared | other | unmatched


@dataclass(frozen=True)
class AnswerRow:
    question_id: str
    kind: str                        # text | single | multi | raw
    text_value: str | None
    is_blank: bool
    raw_json: str
    choices: tuple[ChoiceRow, ...] = ()


@dataclass(frozen=True)
class SubmissionRow:
    submission_id: str
    form_id: str
    submitted_at: str
    is_completed: bool
    created_at: str | None
    updated_at: str | None
    answers: tuple[AnswerRow, ...] = field(default_factory=tuple)

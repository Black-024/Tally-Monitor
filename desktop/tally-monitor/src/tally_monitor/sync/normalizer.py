"""Del JSON sanitizado a filas normalizadas. Reconstruible: solo depende del JSON sanitizado."""
from __future__ import annotations

import json

from .models import AnswerRow, ChoiceRow, FormRow, QuestionRow, SubmissionRow

# Tipos de pregunta VERIFICADOS con datos reales. El resto se guarda como 'raw' sin interpretarlo.
SINGLE_TYPES = {"MULTIPLE_CHOICE"}
MULTI_TYPES = {"CHECKBOXES"}
TEXT_TYPES = {"TEXTAREA"}
_OPTION_BLOCK_TYPES = {"CHECKBOX"}


def form_row(data: dict) -> FormRow:
    n = data.get("numberOfSubmissions")
    return FormRow(
        form_id=str(data["id"]), name=str(data.get("name") or ""), status=str(data.get("status") or ""),
        is_closed=bool(data.get("isClosed")), workspace_id=data.get("workspaceId"),
        reported_submissions=n if isinstance(n, int) else None,
        created_at=data.get("createdAt"), updated_at=data.get("updatedAt"))


def _is_option_block(b: dict) -> bool:
    t = str(b.get("type") or "")
    return t.endswith("_OPTION") or t in _OPTION_BLOCK_TYPES


def question_rows(detail: dict | None, questions: dict) -> list[QuestionRow]:
    """Une las preguntas con sus opciones: pregunta.fields[].blockGroupUuid == bloque.groupUuid."""
    blocks = [b for b in (detail or {}).get("blocks") or [] if isinstance(b, dict)]
    order: dict[str, int] = {}
    for i, b in enumerate(blocks):
        order.setdefault(str(b.get("groupUuid")), i)
    rows = []
    for idx, q in enumerate(questions.get("questions") or []):
        fields = q.get("fields") or []
        group = fields[0].get("blockGroupUuid") if fields else None
        opts, other = [], False
        for b in blocks:
            if group and b.get("groupUuid") == group:
                p = b.get("payload") or {}
                if _is_option_block(b) and isinstance(p.get("text"), str):
                    opts.append((p.get("index") if isinstance(p.get("index"), int) else len(opts), p["text"]))
                if p.get("hasOtherOption") or p.get("isOtherOption"):
                    other = True
        opts.sort(key=lambda t: t[0])
        rows.append(QuestionRow(
            question_id=str(q["id"]), position=order.get(str(group), 10_000 + idx), type=str(q.get("type") or ""),
            title=str(q.get("title") or ""), reported_responses=q.get("numberOfResponses")
            if isinstance(q.get("numberOfResponses"), int) else None,
            group_uuid=group, has_other_option=other, is_deleted=bool(q.get("isDeleted")),
            options=tuple(t for _, t in opts)))
    rows.sort(key=lambda r: (r.position, r.question_id))
    return [QuestionRow(**{**r.__dict__, "position": i}) for i, r in enumerate(rows)]


def _blank(answer) -> bool:
    if answer is None:
        return True
    if isinstance(answer, str):
        return answer.strip() == ""
    if isinstance(answer, (list, tuple)):
        return all(_blank(a) for a in answer)
    return False


def _human(answer) -> str:
    if answer is None:
        return ""
    if isinstance(answer, str):
        return answer
    if isinstance(answer, (list, tuple)):
        return ", ".join(_human(a) for a in answer if not _blank(a))
    return json.dumps(answer, ensure_ascii=False)


def answer_row(response: dict, question: QuestionRow | None) -> AnswerRow:
    answer = response.get("answer")
    qid = str(response.get("questionId"))
    raw = json.dumps(answer, ensure_ascii=False)
    blank = _blank(answer)
    qtype = question.type if question else None
    if qtype in TEXT_TYPES and (answer is None or isinstance(answer, str)):
        return AnswerRow(qid, "text", answer if isinstance(answer, str) else None, blank, raw)
    if qtype in SINGLE_TYPES | MULTI_TYPES and (answer is None or (
            isinstance(answer, list) and all(isinstance(a, str) for a in answer))):
        labels = [a for a in (answer or []) if a.strip()]
        choices = []
        for lab in labels:
            if lab in question.options:
                origin = "declared"
            else:
                origin = "other" if question.has_other_option else "unmatched"
            choices.append(ChoiceRow(lab, origin))
        kind = "single" if qtype in SINGLE_TYPES else "multi"
        return AnswerRow(qid, kind, _human(labels) or None, blank, raw, tuple(choices))
    return AnswerRow(qid, "raw", _human(answer) or None, blank, raw)


def submission_row(sub: dict, questions: dict[str, QuestionRow]) -> SubmissionRow:
    answers = tuple(answer_row(r, questions.get(str(r.get("questionId"))))
                    for r in sub.get("responses") or [] if isinstance(r, dict))
    return SubmissionRow(
        submission_id=str(sub["id"]), form_id=str(sub.get("formId") or ""),
        submitted_at=str(sub.get("submittedAt") or sub.get("createdAt") or ""),
        is_completed=bool(sub.get("isCompleted")), created_at=sub.get("createdAt"),
        updated_at=sub.get("updatedAt"), answers=answers)

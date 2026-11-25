"""Lista blanca de campos («JSON original sanitizado»). Lo que no figura en la lista NO se guarda.

De lo descartado y desconocido solo se informa el NOMBRE del campo (nunca su valor), para detectar
cambios de la API sin guardar datos inesperados.
"""
from __future__ import annotations

from dataclasses import dataclass

SANITIZER_VERSION = 2   # v2: se conserva isOtherOption (opción «Otro») y se descarta isFolded (solo aspecto)

# Campos conocidos que se descartan a propósito (no se informan como «desconocidos»).
_FORM_KEEP = {"id", "name", "status", "isClosed", "numberOfSubmissions", "createdAt", "updatedAt", "workspaceId"}
_FORM_DROP = {"createdByUserId", "organizationId", "folderId", "index", "isNameModifiedByUser",
              "hasDraftBlocks", "settings", "blocks"}
_BLOCK_KEEP = {"type", "groupType", "uuid", "groupUuid"}
_BLOCK_DROP = set()
_PAYLOAD_KEEP = {"text", "index", "isHidden", "isRequired", "hasOtherOption", "isFirst", "isLast",
                 "logicalOperator", "conditionals", "actions", "updateUuid", "isOtherOption"}
_PAYLOAD_DROP = {"safeHTMLSchema", "placeholder", "button", "logo", "title", "isFolded"}
_Q_KEEP = {"id", "type", "title", "numberOfResponses", "isDeleted", "fields"}
_Q_DROP = {"formId", "createdAt", "updatedAt", "isTitleModifiedByUser"}
_FIELD_KEEP = {"blockGroupUuid", "questionType", "type", "uuid"}
_FIELD_DROP = {"title"}
_SUB_KEEP = {"id", "formId", "isCompleted", "submittedAt", "createdAt", "updatedAt", "responses"}
_SUB_DROP = {"respondentId", "previewUrl", "pdfUrl", "locale"}
_RESP_KEEP = {"questionId", "answer"}
_RESP_DROP = {"id", "formId", "respondentId", "submissionId", "sessionUuid", "createdAt", "updatedAt"}


@dataclass(frozen=True)
class Sanitized:
    data: dict
    unknown_fields: tuple[str, ...] = ()


def _unknown(raw: dict, keep: set, drop: set, where: str) -> list[str]:
    return [f"{where}.{k}" for k in raw if k not in keep and k not in drop]


def _pick(raw: dict, keep: set) -> dict:
    return {k: raw[k] for k in keep if k in raw}


def sanitize_form(raw: dict) -> Sanitized:
    """Resumen de formulario (de /forms) o detalle (de /forms/{id}, con bloques)."""
    unknown = _unknown(raw, _FORM_KEEP, _FORM_DROP, "form")
    out = _pick(raw, _FORM_KEEP)
    if isinstance(raw.get("blocks"), list):
        blocks = []
        for b in raw["blocks"]:
            if isinstance(b, dict):
                sb, u = _sanitize_block(b)
                blocks.append(sb)
                unknown += u
        out["blocks"] = blocks
    return Sanitized(out, tuple(dict.fromkeys(unknown)))


def _sanitize_block(b: dict) -> tuple[dict, list[str]]:
    unknown = _unknown(b, _BLOCK_KEEP | {"payload"}, _BLOCK_DROP, "block")
    out = _pick(b, _BLOCK_KEEP)
    payload = b.get("payload")
    if isinstance(payload, dict):
        unknown += _unknown(payload, _PAYLOAD_KEEP, _PAYLOAD_DROP, "block.payload")
        p = _pick(payload, _PAYLOAD_KEEP)
        if "conditionals" in p:
            p["conditionals"] = _sanitize_conditionals(p["conditionals"])
        if "actions" in p:
            p["actions"] = _sanitize_actions(p["actions"])
        out["payload"] = p
    return out, unknown


def _sanitize_conditionals(items) -> list:
    out = []
    for c in items if isinstance(items, list) else []:
        if not isinstance(c, dict):
            continue
        p = c.get("payload") if isinstance(c.get("payload"), dict) else {}
        field = p.get("field") if isinstance(p.get("field"), dict) else {}
        value = p.get("value")
        out.append({"type": c.get("type"), "uuid": c.get("uuid"),
                    "payload": {"comparison": p.get("comparison"),
                                "value": value if isinstance(value, str) and len(value) <= 200 else None,
                                "field": _pick(field, {"blockGroupUuid", "questionType", "type", "uuid"})}})
    return out


def _sanitize_actions(items) -> list:
    out = []
    for a in items if isinstance(items, list) else []:
        if isinstance(a, dict):
            p = a.get("payload") if isinstance(a.get("payload"), dict) else {}
            blocks = p.get("showBlocks")
            out.append({"type": a.get("type"),
                        "payload": {"showBlocks": [x for x in blocks if isinstance(x, str)]
                                    if isinstance(blocks, list) else []}})
    return out


def sanitize_questions(raw: dict) -> Sanitized:
    unknown = _unknown(raw, {"questions", "hasResponses"}, set(), "questions")
    questions = []
    for q in raw.get("questions") or []:
        if not isinstance(q, dict):
            continue
        unknown += _unknown(q, _Q_KEEP, _Q_DROP, "question")
        sq = _pick(q, _Q_KEEP)
        sq["fields"] = []
        for f in q.get("fields") or []:
            if isinstance(f, dict):
                unknown += _unknown(f, _FIELD_KEEP, _FIELD_DROP, "question.field")
                sq["fields"].append(_pick(f, _FIELD_KEEP))
        questions.append(sq)
    out = {"questions": questions}
    if "hasResponses" in raw:
        out["hasResponses"] = bool(raw["hasResponses"])
    return Sanitized(out, tuple(dict.fromkeys(unknown)))


def sanitize_submission(raw: dict) -> Sanitized:
    unknown = _unknown(raw, _SUB_KEEP, _SUB_DROP, "submission")
    out = _pick(raw, _SUB_KEEP - {"responses"})
    responses = []
    for r in raw.get("responses") or []:
        if isinstance(r, dict):
            unknown += _unknown(r, _RESP_KEEP, _RESP_DROP, "response")
            responses.append(_pick(r, _RESP_KEEP))
    out["responses"] = responses
    return Sanitized(out, tuple(dict.fromkeys(unknown)))

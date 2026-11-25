"""Segundo camino de cálculo, INDEPENDIENTE del normalizador: parte del «JSON original sanitizado» y cuenta a su manera.
Sirve para comprobar que las estadísticas (calculadas desde las tablas normalizadas) coinciden con los datos originales."""
from __future__ import annotations

from .models import QuestionStats

_SINGLE, _MULTI, _TEXT = "MULTIPLE_CHOICE", "CHECKBOXES", "TEXTAREA"


def _nonblank(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip() != ""
    if isinstance(v, (list, tuple)):
        return any(_nonblank(x) for x in v)
    return True


def raw_counts(questions_raw: dict, submissions: list[dict]) -> dict[str, dict]:
    """{question_id: {"type", "asked", "answered", "labels": {texto: personas}}} calculado solo desde el JSON crudo."""
    types = {str(q["id"]): q.get("type") for q in (questions_raw or {}).get("questions", [])}
    out = {qid: {"type": t, "asked": 0, "answered": 0, "labels": {}} for qid, t in types.items()}
    for sub in submissions:
        seen: set[str] = set()
        for r in sub.get("responses", []):
            qid = str(r.get("questionId"))
            if qid not in out or qid in seen:
                continue
            seen.add(qid)
            entry, ans = out[qid], r.get("answer")
            entry["asked"] += 1
            if _nonblank(ans):
                entry["answered"] += 1
                if entry["type"] in (_SINGLE, _MULTI) and isinstance(ans, list):
                    for label in {x for x in ans if isinstance(x, str) and x.strip()}:
                        entry["labels"][label] = entry["labels"].get(label, 0) + 1
    return out


def compare(stats: tuple[QuestionStats, ...], raw: dict[str, dict], *, total: int, completed: int,
            raw_total: int, raw_completed: int) -> list[str]:
    """Lista de diferencias (vacía = todo coincide). Los mensajes no incluyen textos de personas."""
    problems: list[str] = []
    if total != raw_total or completed != raw_completed:
        problems.append(f"totales: calculado {total}/{completed} vs original {raw_total}/{raw_completed}")
    for q in stats:
        r = raw.get(q.question_id)
        if r is None:
            problems.append(f"pregunta {q.position + 1}: no está en los datos originales")
            continue
        if (q.asked, q.answered) != (r["asked"], r["answered"]):
            problems.append(f"pregunta {q.position + 1}: traían/respondieron {q.asked}/{q.answered} "
                            f"vs original {r['asked']}/{r['answered']}")
        if q.kind in ("single", "multi") and q.interpreted:
            known = {o.text for o in q.options}
            for o in q.options:
                if o.count != r["labels"].get(o.text, 0):
                    problems.append(f"pregunta {q.position + 1}: opción «{o.text[:30]}» {o.count} vs "
                                    f"{r['labels'].get(o.text, 0)}")
            rest = sum(n for t, n in r["labels"].items() if t not in known)
            if q.other_count + q.orphan_count != rest:
                problems.append(f"pregunta {q.position + 1}: «otro»+huérfanas {q.other_count + q.orphan_count} vs {rest}")
    return problems

"""Encuestas y preguntas (raw_form, raw_questions, data_form, data_question, data_option)."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from ..core.clock import Clock
from ..sync.models import FormRow, QuestionRow
from ..sync.sanitizer import SANITIZER_VERSION
from .database import Database


@dataclass(frozen=True)
class FormRecord:
    form_id: str
    name: str
    status: str
    is_closed: bool
    reported_submissions: int | None
    created_at: str | None
    updated_at: str | None
    last_submission_at: str | None
    last_synced_at: str | None
    local_submissions: int          # envíos completos y numerados (sin los desaparecidos del origen)


@dataclass(frozen=True)
class QuestionRecord:
    question_id: str
    position: int
    type: str
    title: str
    has_other_option: bool
    is_deleted: bool
    options: tuple[str, ...]


_LIST_SQL = """
SELECT f.*, (SELECT COUNT(*) FROM data_submission s JOIN state_user_number n ON n.account_id=s.account_id
             AND n.submission_id=s.submission_id WHERE s.account_id=f.account_id AND s.form_id=f.form_id
             AND s.missing_at_source_at IS NULL) AS local_n
FROM data_form f WHERE f.account_id=?"""


def _record(r: sqlite3.Row) -> FormRecord:
    return FormRecord(r["form_id"], r["name"], r["status"], bool(r["is_closed"]), r["reported_submissions"],
                      r["created_at"], r["updated_at"], r["last_submission_at"], r["last_synced_at"], r["local_n"])


class SurveysRepository:
    def __init__(self, db: Database, clock: Clock | None = None) -> None:
        self._db, self._clock = db, clock or Clock()

    # ---------- escritura ----------
    @staticmethod
    def _upsert_form(c, account_id: str, f: FormRow) -> None:
        c.execute(
            "INSERT INTO data_form(account_id,form_id,name,status,is_closed,workspace_id,reported_submissions,"
            "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(account_id,form_id) DO UPDATE SET name=excluded.name,status=excluded.status,"
            "is_closed=excluded.is_closed,workspace_id=excluded.workspace_id,"
            "reported_submissions=COALESCE(excluded.reported_submissions,reported_submissions),"
            "created_at=excluded.created_at,updated_at=excluded.updated_at",
            (account_id, f.form_id, f.name, f.status, int(f.is_closed), f.workspace_id,
             f.reported_submissions, f.created_at, f.updated_at))

    def _merge_raw(self, c, account_id: str, form_id: str, key: str, value: dict) -> None:
        r = c.execute("SELECT sanitized_json FROM raw_form WHERE account_id=? AND form_id=?",
                      (account_id, form_id)).fetchone()
        cur = json.loads(r["sanitized_json"]) if r else {"summary": None, "detail": None}
        cur[key] = value
        c.execute("INSERT INTO raw_form(account_id,form_id,sanitized_json,sanitizer_version,fetched_at) "
                  "VALUES (?,?,?,?,?) ON CONFLICT(account_id,form_id) DO UPDATE SET "
                  "sanitized_json=excluded.sanitized_json,sanitizer_version=excluded.sanitizer_version,"
                  "fetched_at=excluded.fetched_at",
                  (account_id, form_id, json.dumps(cur, ensure_ascii=False), SANITIZER_VERSION, self._clock.iso()))

    def save_summaries(self, account_id: str, items: list[tuple[FormRow, dict]]) -> None:
        """Resultado de /forms: una transacción para toda la lista."""
        with self._db.transaction() as c:
            for row, sanitized in items:
                self._upsert_form(c, account_id, row)
                self._merge_raw(c, account_id, row.form_id, "summary", sanitized)

    def save_detail(self, account_id: str, form: FormRow, detail: dict, questions_raw: dict,
                    questions: list[QuestionRow]) -> None:
        with self._db.transaction() as c:
            self._upsert_form(c, account_id, form)
            self._merge_raw(c, account_id, form.form_id, "detail", detail)
            c.execute("INSERT INTO raw_questions(account_id,form_id,sanitized_json,sanitizer_version,fetched_at) "
                      "VALUES (?,?,?,?,?) ON CONFLICT(account_id,form_id) DO UPDATE SET "
                      "sanitized_json=excluded.sanitized_json,sanitizer_version=excluded.sanitizer_version,"
                      "fetched_at=excluded.fetched_at",
                      (account_id, form.form_id, json.dumps(questions_raw, ensure_ascii=False),
                       SANITIZER_VERSION, self._clock.iso()))
            self._replace_questions(c, account_id, form.form_id, questions)

    @staticmethod
    def _replace_questions(c, account_id: str, form_id: str, questions: list[QuestionRow]) -> None:
        c.execute("DELETE FROM data_option WHERE account_id=? AND form_id=?", (account_id, form_id))
        c.execute("DELETE FROM data_question WHERE account_id=? AND form_id=?", (account_id, form_id))
        for q in questions:
            c.execute("INSERT INTO data_question(account_id,form_id,question_id,position,type,title,"
                      "reported_responses,group_uuid,has_other_option,is_deleted) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (account_id, form_id, q.question_id, q.position, q.type, q.title, q.reported_responses,
                       q.group_uuid, int(q.has_other_option), int(q.is_deleted)))
            for i, text in enumerate(dict.fromkeys(q.options)):
                c.execute("INSERT INTO data_option(account_id,form_id,question_id,option_text,position) "
                          "VALUES (?,?,?,?,?)", (account_id, form_id, q.question_id, text, i))

    def mark_synced(self, account_id: str, form_id: str, *, last_submission_at: str | None) -> None:
        with self._db.transaction() as c:
            c.execute("UPDATE data_form SET last_synced_at=?, last_submission_at=? "
                      "WHERE account_id=? AND form_id=?",
                      (self._clock.iso(), last_submission_at, account_id, form_id))

    def set_reported(self, account_id: str, form_id: str, n: int) -> None:
        with self._db.transaction() as c:
            c.execute("UPDATE data_form SET reported_submissions=? WHERE account_id=? AND form_id=?",
                      (n, account_id, form_id))

    # ---------- lectura ----------
    def list_forms(self, account_id: str) -> list[FormRecord]:
        with self._db.connection() as c:
            rows = c.execute(_LIST_SQL + " ORDER BY f.updated_at DESC, f.name COLLATE NOCASE",
                             (account_id,)).fetchall()
        return [_record(r) for r in rows]

    def get_form(self, account_id: str, form_id: str) -> FormRecord | None:
        with self._db.connection() as c:
            r = c.execute(_LIST_SQL + " AND f.form_id=?", (account_id, form_id)).fetchone()
        return _record(r) if r else None

    def get_questions(self, account_id: str, form_id: str) -> list[QuestionRecord]:
        with self._db.connection() as c:
            qs = c.execute("SELECT * FROM data_question WHERE account_id=? AND form_id=? ORDER BY position",
                           (account_id, form_id)).fetchall()
            opts = c.execute("SELECT question_id, option_text FROM data_option WHERE account_id=? AND form_id=? "
                             "ORDER BY position", (account_id, form_id)).fetchall()
        by_q: dict[str, list[str]] = {}
        for o in opts:
            by_q.setdefault(o["question_id"], []).append(o["option_text"])
        return [QuestionRecord(q["question_id"], q["position"], q["type"], q["title"],
                               bool(q["has_other_option"]), bool(q["is_deleted"]),
                               tuple(by_q.get(q["question_id"], ()))) for q in qs]

    def raw_structure(self, account_id: str, form_id: str) -> tuple[dict | None, dict | None]:
        """(detalle sanitizado, preguntas sanitizadas) tal como se guardaron."""
        with self._db.connection() as c:
            f = c.execute("SELECT sanitized_json FROM raw_form WHERE account_id=? AND form_id=?",
                          (account_id, form_id)).fetchone()
            q = c.execute("SELECT sanitized_json FROM raw_questions WHERE account_id=? AND form_id=?",
                          (account_id, form_id)).fetchone()
        detail = json.loads(f["sanitized_json"]).get("detail") if f else None
        return detail, (json.loads(q["sanitized_json"]) if q else None)

    def replace_questions(self, account_id: str, form_id: str, questions: list[QuestionRow]) -> None:
        with self._db.transaction() as c:
            self._replace_questions(c, account_id, form_id, questions)

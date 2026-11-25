"""Envíos y respuestas (raw_submission, data_submission, data_answer, data_choice, state_user_number)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..core.clock import Clock
from ..sync.models import SubmissionRow
from ..sync.sanitizer import SANITIZER_VERSION
from .database import Database


@dataclass(frozen=True)
class AnswerRecord:
    question_id: str
    kind: str
    text_value: str | None
    is_blank: bool
    choices: tuple[tuple[str, str], ...] = ()      # (texto de la opción, origen)


@dataclass(frozen=True)
class SubmissionRecord:
    number: int | None
    submitted_at: str
    is_completed: bool
    answers: tuple[AnswerRecord, ...] = field(default_factory=tuple)


class SubmissionsRepository:
    def __init__(self, db: Database, clock: Clock | None = None) -> None:
        self._db, self._clock = db, clock or Clock()

    # ---------- escritura ----------
    @staticmethod
    def _write_normalized(c, account_id: str, s: SubmissionRow) -> None:
        c.execute(
            "INSERT INTO data_submission(account_id,submission_id,form_id,submitted_at,is_completed,created_at,"
            "updated_at,missing_at_source_at) VALUES (?,?,?,?,?,?,?,NULL) "
            "ON CONFLICT(account_id,submission_id) DO UPDATE SET form_id=excluded.form_id,"
            "submitted_at=excluded.submitted_at,is_completed=excluded.is_completed,created_at=excluded.created_at,"
            "updated_at=excluded.updated_at,missing_at_source_at=NULL",
            (account_id, s.submission_id, s.form_id, s.submitted_at, int(s.is_completed), s.created_at, s.updated_at))
        c.execute("DELETE FROM data_choice WHERE account_id=? AND submission_id=?", (account_id, s.submission_id))
        c.execute("DELETE FROM data_answer WHERE account_id=? AND submission_id=?", (account_id, s.submission_id))
        for a in s.answers:
            c.execute("INSERT OR REPLACE INTO data_answer(account_id,submission_id,question_id,kind,text_value,"
                      "is_blank,raw_json) VALUES (?,?,?,?,?,?,?)",
                      (account_id, s.submission_id, a.question_id, a.kind, a.text_value, int(a.is_blank), a.raw_json))
            for ch in a.choices:
                c.execute("INSERT OR IGNORE INTO data_choice(account_id,submission_id,question_id,option_text,origin)"
                          " VALUES (?,?,?,?,?)", (account_id, s.submission_id, a.question_id, ch.option_text, ch.origin))

    def upsert_page(self, account_id: str, items: list[tuple[SubmissionRow, dict]]) -> tuple[int, int]:
        """Guarda una página en una sola transacción. Devuelve (nuevos, actualizados)."""
        now, new, upd = self._clock.iso(), 0, 0
        with self._db.transaction() as c:
            for row, sanitized in items:
                exists = c.execute("SELECT 1 FROM raw_submission WHERE account_id=? AND submission_id=?",
                                   (account_id, row.submission_id)).fetchone()
                c.execute(
                    "INSERT INTO raw_submission(account_id,submission_id,form_id,sanitized_json,sanitizer_version,"
                    "first_seen_at,last_seen_at,missing_at_source_at) VALUES (?,?,?,?,?,?,?,NULL) "
                    "ON CONFLICT(account_id,submission_id) DO UPDATE SET sanitized_json=excluded.sanitized_json,"
                    "sanitizer_version=excluded.sanitizer_version,last_seen_at=excluded.last_seen_at,"
                    "missing_at_source_at=NULL",
                    (account_id, row.submission_id, row.form_id, json.dumps(sanitized, ensure_ascii=False),
                     SANITIZER_VERSION, now, now))
                self._write_normalized(c, account_id, row)
                if exists:
                    upd += 1
                else:
                    new += 1
        return new, upd

    def count_present(self, account_id: str, form_id: str) -> int:
        with self._db.connection() as c:
            return c.execute("SELECT COUNT(*) FROM data_submission WHERE account_id=? AND form_id=? "
                             "AND missing_at_source_at IS NULL", (account_id, form_id)).fetchone()[0]

    def recent_counts(self, account_id: str, start_iso: str, end_iso: str) -> dict[str, int]:
        """form_id -> envíos guardados y numerados con start <= submitted_at <= end (ISO UTC de igual formato)."""
        with self._db.connection() as c:
            return {r[0]: r[1] for r in c.execute(
                "SELECT s.form_id, COUNT(*) FROM data_submission s JOIN state_user_number n "
                "ON n.account_id=s.account_id AND n.submission_id=s.submission_id "
                "WHERE s.account_id=? AND s.missing_at_source_at IS NULL AND s.submitted_at >= ? AND s.submitted_at <= ? "
                "GROUP BY s.form_id", (account_id, start_iso, end_iso))}

    def newest_submitted_at(self, account_id: str, form_id: str) -> str | None:
        with self._db.connection() as c:
            return c.execute("SELECT MAX(submitted_at) FROM data_submission WHERE account_id=? AND form_id=? "
                             "AND missing_at_source_at IS NULL", (account_id, form_id)).fetchone()[0]

    def mark_missing(self, account_id: str, form_id: str, seen: set[str]) -> int:
        """Tras un recorrido completo: marca como «desaparecidos del origen» (sin borrar) los que no vinieron."""
        now = self._clock.iso()
        with self._db.transaction() as c:
            ids = [r[0] for r in c.execute(
                "SELECT submission_id FROM data_submission WHERE account_id=? AND form_id=? "
                "AND missing_at_source_at IS NULL", (account_id, form_id))]
            gone = [i for i in ids if i not in seen]
            for i in gone:
                for t in ("data_submission", "raw_submission"):
                    c.execute(f"UPDATE {t} SET missing_at_source_at=? WHERE account_id=? AND submission_id=?",
                              (now, account_id, i))
        return len(gone)

    def assign_numbers(self, account_id: str, form_id: str) -> int:
        """Numera los envíos sin número por fecha ascendente (empate: ID). Nunca renumera ni reutiliza."""
        with self._db.transaction() as c:
            rows = c.execute(
                "SELECT s.submission_id FROM data_submission s LEFT JOIN state_user_number n "
                "ON n.account_id=s.account_id AND n.submission_id=s.submission_id "
                "WHERE s.account_id=? AND s.form_id=? AND n.number IS NULL "
                "ORDER BY s.submitted_at ASC, s.submission_id ASC", (account_id, form_id)).fetchall()
            if not rows:
                return 0
            r = c.execute("SELECT next_number FROM state_form_counter WHERE account_id=? AND form_id=?",
                          (account_id, form_id)).fetchone()
            nxt = r["next_number"] if r else 1
            for row in rows:
                c.execute("INSERT INTO state_user_number(account_id,form_id,submission_id,number) VALUES (?,?,?,?)",
                          (account_id, form_id, row["submission_id"], nxt))
                nxt += 1
            c.execute("INSERT INTO state_form_counter(account_id,form_id,next_number) VALUES (?,?,?) "
                      "ON CONFLICT(account_id,form_id) DO UPDATE SET next_number=excluded.next_number",
                      (account_id, form_id, nxt))
            return len(rows)

    def raw_submissions(self, account_id: str, form_id: str) -> list[dict]:
        with self._db.connection() as c:
            rows = c.execute("SELECT sanitized_json FROM raw_submission WHERE account_id=? AND form_id=?",
                             (account_id, form_id)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def rewrite_normalized(self, account_id: str, rows: list[SubmissionRow]) -> None:
        with self._db.transaction() as c:
            for s in rows:
                prev = c.execute("SELECT missing_at_source_at FROM data_submission WHERE account_id=? "
                                 "AND submission_id=?", (account_id, s.submission_id)).fetchone()
                self._write_normalized(c, account_id, s)
                if prev and prev[0]:
                    c.execute("UPDATE data_submission SET missing_at_source_at=? WHERE account_id=? "
                              "AND submission_id=?", (prev[0], account_id, s.submission_id))

    # ---------- lectura ----------
    def _load(self, c, account_id: str, rows) -> list[SubmissionRecord]:
        out = []
        for r in rows:
            sid = r["submission_id"]
            answers = []
            for a in c.execute("SELECT a.* FROM data_answer a LEFT JOIN data_question q ON q.account_id=a.account_id "
                               "AND q.question_id=a.question_id AND q.form_id=? WHERE a.account_id=? "
                               "AND a.submission_id=? ORDER BY COALESCE(q.position, 1000000), a.question_id",
                               (r["form_id"], account_id, sid)):
                ch = tuple((x["option_text"], x["origin"]) for x in c.execute(
                    "SELECT option_text, origin FROM data_choice WHERE account_id=? AND submission_id=? "
                    "AND question_id=? ORDER BY option_text", (account_id, sid, a["question_id"])))
                answers.append(AnswerRecord(a["question_id"], a["kind"], a["text_value"], bool(a["is_blank"]), ch))
            out.append(SubmissionRecord(r["number"], r["submitted_at"], bool(r["is_completed"]), tuple(answers)))
        return out

    _BASE = ("SELECT s.submission_id, s.form_id, s.submitted_at, s.is_completed, n.number FROM data_submission s "
             "LEFT JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id "
             "WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL AND n.number IS NOT NULL")

    def list_page(self, account_id: str, form_id: str, *, offset: int = 0, limit: int = 50) -> list[SubmissionRecord]:
        with self._db.connection() as c:
            rows = c.execute(self._BASE + " ORDER BY n.number, s.submitted_at LIMIT ? OFFSET ?",
                             (account_id, form_id, max(1, limit), max(0, offset))).fetchall()
            return self._load(c, account_id, rows)

    def get_by_number(self, account_id: str, form_id: str, number: int) -> SubmissionRecord | None:
        with self._db.connection() as c:
            rows = c.execute(self._BASE + " AND n.number=?", (account_id, form_id, number)).fetchall()
            got = self._load(c, account_id, rows)
        return got[0] if got else None

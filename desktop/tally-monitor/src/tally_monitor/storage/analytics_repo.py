"""Lectura de solo lectura para el análisis: envíos, respuestas y preguntas, con filtro de fechas aplicado en SQL."""
from __future__ import annotations

import json
from collections import defaultdict

from ..analysis.models import AnswerPoint, QuestionInfo, ResponseRow, SubmissionPoint
from .database import Database

_FROM = ("FROM data_submission s JOIN state_user_number n ON n.account_id=s.account_id "
         "AND n.submission_id=s.submission_id WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL")


class AnalyticsRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    @staticmethod
    def _where(start_iso, end_iso, include_incomplete) -> tuple[str, list]:
        sql, args = "", []
        if start_iso:
            sql += " AND s.submitted_at >= ?"
            args.append(start_iso)
        if end_iso:
            sql += " AND s.submitted_at < ?"
            args.append(end_iso)
        if not include_incomplete:
            sql += " AND s.is_completed = 1"
        return sql, args

    def load(self, account_id: str, form_id: str, *, start_iso: str | None = None, end_iso: str | None = None,
             include_incomplete: bool = True):
        extra, args = self._where(start_iso, end_iso, include_incomplete)
        base = [account_id, form_id] + args
        with self._db.connection() as c:
            subs = [SubmissionPoint(r[0], r[1], bool(r[2])) for r in c.execute(
                f"SELECT n.number, s.submitted_at, s.is_completed {_FROM}{extra} ORDER BY n.number", base)]
            choices: dict[tuple[int, str], list] = defaultdict(list)
            for r in c.execute(
                    f"SELECT n.number, ch.question_id, ch.option_text, ch.origin FROM data_choice ch "
                    f"JOIN data_submission s ON s.account_id=ch.account_id AND s.submission_id=ch.submission_id "
                    f"JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id "
                    f"WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL{extra}", base):
                choices[(r[0], r[1])].append((r[2], r[3]))
            answers = [AnswerPoint(r[0], r[1], r[2], bool(r[3]), r[4], tuple(sorted(choices.get((r[0], r[1]), ()))))
                       for r in c.execute(
                f"SELECT n.number, a.question_id, a.kind, a.is_blank, "
                f"CASE WHEN a.kind='text' THEN length(a.text_value) END FROM data_answer a "
                f"JOIN data_submission s ON s.account_id=a.account_id AND s.submission_id=a.submission_id "
                f"JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id "
                f"WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL{extra}", base)]
            opts: dict[str, list[str]] = defaultdict(list)
            for r in c.execute("SELECT question_id, option_text FROM data_option WHERE account_id=? AND form_id=? "
                               "ORDER BY position", (account_id, form_id)):
                opts[r[0]].append(r[1])
            questions = [QuestionInfo(r["question_id"], r["position"], r["type"], r["title"],
                                      tuple(opts.get(r["question_id"], ())), bool(r["has_other_option"]),
                                      bool(r["is_deleted"]))
                         for r in c.execute("SELECT * FROM data_question WHERE account_id=? AND form_id=? "
                                            "ORDER BY position", (account_id, form_id))]
        return subs, answers, questions

    def all_submission_points(self, account_id: str, form_id: str) -> list[SubmissionPoint]:
        """Todos los envíos guardados y numerados (sin filtro de tiempo ni de completitud): para el ritmo semanal."""
        with self._db.connection() as c:
            return [SubmissionPoint(r[0], r[1], bool(r[2])) for r in c.execute(
                f"SELECT n.number, s.submitted_at, s.is_completed {_FROM} ORDER BY n.number", (account_id, form_id))]

    def question_answers(self, account_id: str, form_id: str, question_id: str) -> list[AnswerPoint]:
        """Respuestas de UNA pregunta en todos los envíos guardados (sin filtro de tiempo): para el cruce."""
        with self._db.connection() as c:
            choices: dict[int, list] = defaultdict(list)
            for r in c.execute(
                    "SELECT n.number, ch.option_text, ch.origin FROM data_choice ch "
                    "JOIN data_submission s ON s.account_id=ch.account_id AND s.submission_id=ch.submission_id "
                    "JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id "
                    "WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL AND ch.question_id=?",
                    (account_id, form_id, question_id)):
                choices[r[0]].append((r[1], r[2]))
            return [AnswerPoint(r[0], question_id, r[1], bool(r[2]), None, tuple(sorted(choices.get(r[0], ()))))
                    for r in c.execute(
                "SELECT n.number, a.kind, a.is_blank FROM data_answer a "
                "JOIN data_submission s ON s.account_id=a.account_id AND s.submission_id=a.submission_id "
                "JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id "
                "WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL AND a.question_id=?",
                (account_id, form_id, question_id))]

    def export_rows(self, account_id: str, form_id: str, *, start_iso: str | None = None, end_iso: str | None = None,
                    include_incomplete: bool = True, include_text: bool = True) -> list[ResponseRow]:
        extra, args = self._where(start_iso, end_iso, include_incomplete)
        base = [account_id, form_id] + args
        with self._db.connection() as c:
            rows = {r[0]: [r[1], bool(r[2]), {}] for r in c.execute(
                f"SELECT n.number, s.submitted_at, s.is_completed {_FROM}{extra} ORDER BY n.number", base)}
            choices: dict[tuple[int, str], list] = defaultdict(list)
            for r in c.execute(
                    f"SELECT n.number, ch.question_id, ch.option_text, ch.origin FROM data_choice ch "
                    f"JOIN data_submission s ON s.account_id=ch.account_id AND s.submission_id=ch.submission_id "
                    f"JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id "
                    f"WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL{extra}", base):
                choices[(r[0], r[1])].append((r[2], r[3]))
            for r in c.execute(
                    f"SELECT n.number, a.question_id, a.kind, a.is_blank, a.text_value FROM data_answer a "
                    f"JOIN data_submission s ON s.account_id=a.account_id AND s.submission_id=a.submission_id "
                    f"JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id "
                    f"WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL{extra}", base):
                if r[0] in rows:
                    text = r[4] if (r[2] == "text" and include_text) else None
                    rows[r[0]][2][r[1]] = (r[2], bool(r[3]), text, tuple(sorted(choices.get((r[0], r[1]), ()))))
        return [ResponseRow(k, v[0], v[1], v[2]) for k, v in sorted(rows.items())]

    def raw_present(self, account_id: str, form_id: str, *, include_incomplete: bool = True) -> list[dict]:
        """JSON original sanitizado de los mismos envíos que usa el análisis (presentes y numerados)."""
        extra = "" if include_incomplete else " AND s.is_completed = 1"
        with self._db.connection() as c:
            rows = c.execute(
                "SELECT r.sanitized_json FROM raw_submission r JOIN data_submission s ON s.account_id=r.account_id "
                "AND s.submission_id=r.submission_id JOIN state_user_number n ON n.account_id=s.account_id "
                "AND n.submission_id=s.submission_id WHERE s.account_id=? AND s.form_id=? "
                "AND s.missing_at_source_at IS NULL" + extra, (account_id, form_id)).fetchall()
        return [json.loads(r[0]) for r in rows]

"""Datos propios del usuario por encuesta: meta, nota, etiquetas y archivada (survey_meta, survey_tags).
Aquí NO se validan reglas de negocio (eso vive en services/survey_service.py); solo se guarda."""
from __future__ import annotations

from dataclasses import dataclass, field

from .database import Database


@dataclass(frozen=True)
class SurveyMeta:
    goal: int | None = None
    note: str = ""
    archived: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)


class MetaRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_all(self, account_id: str) -> dict[str, SurveyMeta]:
        """form_id -> SurveyMeta, solo de las encuestas que tienen algo guardado."""
        with self._db.connection() as c:
            metas = {r["form_id"]: r for r in c.execute(
                "SELECT form_id, goal, note, archived FROM survey_meta WHERE account_id=?", (account_id,))}
            tags: dict[str, list[str]] = {}
            for r in c.execute("SELECT form_id, tag FROM survey_tags WHERE account_id=? ORDER BY rowid",
                               (account_id,)):
                tags.setdefault(r["form_id"], []).append(r["tag"])
        out = {}
        for fid in set(metas) | set(tags):
            m = metas.get(fid)
            out[fid] = SurveyMeta(m["goal"] if m else None, m["note"] if m else "",
                                  bool(m["archived"]) if m else False, tuple(tags.get(fid, ())))
        return out

    def get(self, account_id: str, form_id: str) -> SurveyMeta:
        return self.get_all(account_id).get(form_id, SurveyMeta())

    def form_exists(self, account_id: str, form_id: str) -> bool:
        with self._db.connection() as c:
            return c.execute("SELECT 1 FROM data_form WHERE account_id=? AND form_id=?",
                             (account_id, form_id)).fetchone() is not None

    def save(self, account_id: str, form_id: str, goal: int | None, note: str, tags: list[str]) -> None:
        """Una sola transacción: conserva `archived`."""
        with self._db.transaction() as c:
            c.execute("INSERT INTO survey_meta(account_id,form_id,goal,note,archived) VALUES (?,?,?,?,0) "
                      "ON CONFLICT(account_id,form_id) DO UPDATE SET goal=excluded.goal, note=excluded.note",
                      (account_id, form_id, goal, note))
            c.execute("DELETE FROM survey_tags WHERE account_id=? AND form_id=?", (account_id, form_id))
            for t in tags:
                c.execute("INSERT INTO survey_tags(account_id,form_id,tag) VALUES (?,?,?)", (account_id, form_id, t))

    def set_archived(self, account_id: str, form_id: str, archived: bool) -> None:
        with self._db.transaction() as c:
            c.execute("INSERT INTO survey_meta(account_id,form_id,archived) VALUES (?,?,?) "
                      "ON CONFLICT(account_id,form_id) DO UPDATE SET archived=excluded.archived",
                      (account_id, form_id, int(archived)))

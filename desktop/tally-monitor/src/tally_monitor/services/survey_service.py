"""Lectura de encuestas y respuestas desde la copia local (nunca llama a la API)."""
from __future__ import annotations

from dataclasses import dataclass

import re
from datetime import timedelta

from ..analysis.goal import GoalProjection, goal_projection  # noqa: F401  (GoalProjection se re-exporta a la interfaz)
from ..analysis.timefilter import to_iso
from ..core.clock import Clock
from ..core.language import pick as _t
from ..core.errors import InvalidSurveyMetaError, SurveyNotFoundError
from ..storage.meta_repo import MetaRepository, SurveyMeta
from ..storage.state_repo import StateRepository
from ..storage.submissions_repo import SubmissionsRepository
from ..storage.surveys_repo import FormRecord, SurveysRepository
from ..sync.numbering import format_user_label, parse_user_label


GOAL_MIN, GOAL_MAX = 1, 1_000_000
NOTE_MAX = 500
TAG_MAX_LEN = 24
TAGS_MAX = 8
_SPACES = re.compile(r"\s+")


def validate_goal(goal) -> int | None:
    """Entero 1..1.000.000 o None (sin meta). Los booleanos y los decimales no valen."""
    if goal is None:
        return None
    if isinstance(goal, bool) or not isinstance(goal, int):
        raise InvalidSurveyMetaError(_t("La meta tiene que ser un número entero.", "The goal must be a whole number."))
    if not GOAL_MIN <= goal <= GOAL_MAX:
        raise InvalidSurveyMetaError(_t("La meta tiene que estar entre 1 y 1.000.000.", "The goal must be between 1 and 1,000,000."))
    return goal


def normalize_note(note) -> str:
    text = (note or "").strip() if isinstance(note, str) or note is None else None
    if text is None:
        raise InvalidSurveyMetaError(_t("La nota no es válida.", "The note is not valid."))
    if len(text) > NOTE_MAX:
        raise InvalidSurveyMetaError(_t(f"La nota puede tener hasta {NOTE_MAX} caracteres.", f"The note can have up to {NOTE_MAX} characters."))
    return text


def normalize_tag(tag: str) -> str:
    """strip + espacios internos colapsados; no vacía; hasta 24 caracteres."""
    if not isinstance(tag, str):
        raise InvalidSurveyMetaError(_t("La etiqueta no es válida.", "The tag is not valid."))
    t = _SPACES.sub(" ", tag.strip())
    if not t:
        raise InvalidSurveyMetaError(_t("La etiqueta no puede estar vacía.", "The tag cannot be empty."))
    if len(t) > TAG_MAX_LEN:
        raise InvalidSurveyMetaError(_t(f"Cada etiqueta puede tener hasta {TAG_MAX_LEN} caracteres.", f"Each tag can have up to {TAG_MAX_LEN} characters."))
    return t


def normalize_tags(tags) -> list[str]:
    """Normaliza todas; únicas sin distinguir mayúsculas (se conserva la primera grafía); máximo 8."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags or ():
        t = normalize_tag(raw)
        if t.casefold() in seen:
            continue
        seen.add(t.casefold())
        out.append(t)
    if len(out) > TAGS_MAX:
        raise InvalidSurveyMetaError(_t(f"Cada encuesta puede tener hasta {TAGS_MAX} etiquetas.", f"Each survey can have up to {TAGS_MAX} tags."))
    return out


@dataclass(frozen=True)
class SurveySummary:
    form_id: str
    name: str
    status: str
    is_closed: bool
    reported_submissions: int | None     # lo que informó Tally en la última sincronización
    local_submissions: int               # lo que hay guardado aquí
    last_submission_at: str | None
    last_synced_at: str | None
    has_new_hint: bool                   # Tally informa más envíos que los guardados
    is_favorite: bool
    never_synced: bool
    goal: int | None = None
    note: str = ""
    tags: tuple[str, ...] = ()
    archived: bool = False


@dataclass(frozen=True)
class OptionStat:
    text: str
    origin: str                          # declared | other | unmatched


@dataclass(frozen=True)
class QuestionView:
    question_id: str
    position: int
    type: str
    title: str
    options: tuple[str, ...]
    has_other_option: bool
    is_deleted: bool


@dataclass(frozen=True)
class AnswerView:
    question_title: str
    kind: str
    text: str | None
    is_blank: bool
    choices: tuple[OptionStat, ...]


@dataclass(frozen=True)
class ResponseView:
    number: int | None
    label: str                           # «Usuario 001»
    submitted_at: str                    # ISO UTC; la interfaz lo muestra en hora local, pequeño y atenuado
    is_completed: bool
    answers: tuple[AnswerView, ...]


class SurveyService:
    def __init__(self, surveys: SurveysRepository, submissions: SubmissionsRepository,
                 state: StateRepository, meta: MetaRepository | None = None, clock: Clock | None = None) -> None:
        self._surveys, self._subs, self._state, self._meta = surveys, submissions, state, meta
        self._clock = clock or Clock()

    def goals(self, account_id: str) -> dict[str, GoalProjection]:
        """Proyección de la meta de cada encuesta que tiene una (archivadas incluidas: quien muestra decide)."""
        now = self._clock.now().astimezone()
        recent = self._subs.recent_counts(account_id, to_iso(now - timedelta(days=7)), to_iso(now))
        out = {}
        for s in self.list_surveys(account_id):
            if s.goal:
                out[s.form_id] = goal_projection(s.local_submissions, s.goal, recent.get(s.form_id, 0), now)
        return out

    @staticmethod
    def normalize_tags(tags) -> list[str]:
        return normalize_tags(tags)

    def _summary(self, f: FormRecord, favs: set[str], meta: SurveyMeta | None = None) -> SurveySummary:
        m = meta or SurveyMeta()
        return SurveySummary(
            f.form_id, f.name, f.status, f.is_closed, f.reported_submissions, f.local_submissions,
            f.last_submission_at, f.last_synced_at,
            has_new_hint=f.reported_submissions is not None and f.reported_submissions > f.local_submissions,
            is_favorite=f.form_id in favs, never_synced=f.last_synced_at is None,
            goal=m.goal, note=m.note, tags=m.tags, archived=m.archived)

    def list_surveys(self, account_id: str) -> list[SurveySummary]:
        favs = self._state.favorites(account_id)
        metas = self._meta.get_all(account_id) if self._meta else {}
        return [self._summary(f, favs, metas.get(f.form_id)) for f in self._surveys.list_forms(account_id)]

    def get_survey(self, account_id: str, form_id: str) -> SurveySummary:
        f = self._surveys.get_form(account_id, form_id)
        if f is None:
            raise SurveyNotFoundError()
        return self._summary(f, self._state.favorites(account_id),
                             self._meta.get(account_id, form_id) if self._meta else None)

    # ---------- datos propios (meta, nota, etiquetas, archivada) ----------
    def set_survey_meta(self, account_id: str, form_id: str, goal, note, tags) -> SurveySummary:
        """Atómico: valida todo antes de escribir; si algo no vale no se toca nada."""
        goal_v, note_v, tags_v = validate_goal(goal), normalize_note(note), normalize_tags(tags)
        if self._meta is None or not self._meta.form_exists(account_id, form_id):
            raise SurveyNotFoundError()
        self._meta.save(account_id, form_id, goal_v, note_v, tags_v)
        return self.get_survey(account_id, form_id)

    def set_archived(self, account_id: str, form_id: str, archived: bool) -> None:
        if self._meta is None or not self._meta.form_exists(account_id, form_id):
            raise SurveyNotFoundError()
        self._meta.set_archived(account_id, form_id, bool(archived))

    def questions(self, account_id: str, form_id: str) -> list[QuestionView]:
        return [QuestionView(q.question_id, q.position, q.type, q.title, q.options, q.has_other_option, q.is_deleted)
                for q in self._surveys.get_questions(account_id, form_id)]

    def _view(self, rec, titles: dict[str, str]) -> ResponseView:
        answers = tuple(AnswerView(titles.get(a.question_id, _t("(pregunta eliminada)", "(deleted question)")), a.kind, a.text_value,
                                   a.is_blank, tuple(OptionStat(t, o) for t, o in a.choices))
                        for a in rec.answers)
        return ResponseView(rec.number, format_user_label(rec.number) if rec.number else _t("Usuario ?", "User ?"),
                            rec.submitted_at, rec.is_completed, answers)

    def responses(self, account_id: str, form_id: str, *, offset: int = 0, limit: int = 50) -> list[ResponseView]:
        titles = {q.question_id: q.title for q in self._surveys.get_questions(account_id, form_id)}
        return [self._view(r, titles) for r in self._subs.list_page(account_id, form_id, offset=offset, limit=limit)]

    def response_by_number(self, account_id: str, form_id: str, number: int) -> ResponseView | None:
        titles = {q.question_id: q.title for q in self._surveys.get_questions(account_id, form_id)}
        rec = self._subs.get_by_number(account_id, form_id, number)
        return self._view(rec, titles) if rec else None

    def find_by_label(self, account_id: str, form_id: str, text: str) -> ResponseView | None:
        """Busca «Usuario 012», «12» o «A001»."""
        n = parse_user_label(text)
        return self.response_by_number(account_id, form_id, n) if n else None


class FavoritesService:
    def __init__(self, state: StateRepository) -> None:
        self._state = state

    def set_favorite(self, account_id: str, form_id: str, value: bool) -> None:
        self._state.set_favorite(account_id, form_id, value)

    def favorites(self, account_id: str) -> set[str]:
        return self._state.favorites(account_id)

    def touch_recent(self, account_id: str, form_id: str) -> None:
        self._state.touch_recent(account_id, form_id)

    def recents(self, account_id: str) -> list[str]:
        return self._state.recents(account_id)

"""Estadísticas de una encuesta a partir de lo guardado (nunca llama a la API)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo

from ..analysis import answerfilter, stats, timefilter
from ..analysis import crosscheck as cc
from ..analysis.models import (AnswerFilter, OptionStat, QuestionInfo, Overview, QuestionStats, ResolvedFilter, SurveyAnalysis,  # noqa: F401
                               TimeBucket, Timeline)
from ..core.clock import Clock
from ..analysis.answerfilter import filterable_questions  # noqa: F401  (se re-exporta a la interfaz)
from ..analysis.trends import Trends, trends as compute_trends  # noqa: F401
from ..core.errors import InvalidFilterError, SurveyNotFoundError
from ..storage.analytics_repo import AnalyticsRepository
from ..storage.surveys_repo import SurveysRepository

FILTER_KINDS = timefilter.KINDS


@dataclass(frozen=True)
class CrossQuestion:
    question_id: str
    title: str
    options: tuple[str, ...]


class AnalysisService:
    def __init__(self, repo: AnalyticsRepository, surveys: SurveysRepository, clock: Clock | None = None,
                 tz: tzinfo | None = None) -> None:
        self._repo, self._surveys = repo, surveys
        self._clock = clock or Clock()
        self._tz = tz                       # None → hora local del equipo

    def _zone(self) -> tzinfo:
        return self._tz or datetime.now().astimezone().tzinfo

    def analyze(self, account_id: str, form_id: str, kind: str = "all", *, include_incomplete: bool = True,
                start_date: date | None = None, end_date: date | None = None,
                answer_filter: AnswerFilter | None = None) -> SurveyAnalysis:
        if self._surveys.get_form(account_id, form_id) is None:
            raise SurveyNotFoundError()
        now, tz = self._clock.now(), self._zone()
        flt = timefilter.resolve_filter(kind, now, tz, start_date=start_date, end_date=end_date)
        subs, answers, questions = self._repo.load(account_id, form_id, start_iso=flt.start_iso, end_iso=flt.end_iso,
                                                   include_incomplete=include_incomplete)
        all_points = self._repo.all_submission_points(account_id, form_id)
        matched = total_in_period = None
        if answer_filter is not None:
            question = next((q for q in questions if q.question_id == answer_filter.question_id), None)
            if not answerfilter.is_filterable(question):
                raise InvalidFilterError()
            keys_all = answerfilter.matching_keys(
                self._repo.question_answers(account_id, form_id, answer_filter.question_id), answer_filter)
            total_in_period = len(subs)
            subs = [s for s in subs if s.key in keys_all]
            answers = [a for a in answers if a.key in keys_all]
            all_points = [s for s in all_points if s.key in keys_all]
            matched = len(subs)
        tr = compute_trends([(s.submitted_at, s.is_completed) for s in subs], now, tz,
                            all_submissions=[(s.submitted_at, s.is_completed) for s in all_points])
        qstats = stats.all_question_stats(questions, answers, len(subs))
        axis_start, axis_end = (now - timedelta(hours=24), now) if kind == "24h" else (None, None)
        tl = stats.timeline(subs, tz, start=axis_start, end=axis_end)
        warnings = []
        if any(q.not_asked for q in qstats if not q.is_deleted):
            warnings.append("preguntas_agregadas_despues")
        if any(not q.interpreted for q in qstats):
            warnings.append("tipos_no_interpretados")
        return SurveyAnalysis(form_id, flt, include_incomplete, self._clock.iso(), stats.overview(subs, tz),
                              qstats, tl, tuple(warnings),
                              tr, answer_filter, matched, total_in_period)

    def cross_questions(self, account_id: str, form_id: str) -> list[CrossQuestion]:
        """Preguntas de opción con opciones: las que se pueden usar para «Cruzar preguntas»."""
        infos = [QuestionInfo(q.question_id, q.position, q.type, q.title, q.options, q.has_other_option, q.is_deleted)
                 for q in self._surveys.get_questions(account_id, form_id)]
        return [CrossQuestion(q.question_id, q.title, q.options) for q in filterable_questions(infos) if q.options]

    def crosscheck(self, account_id: str, form_id: str, *, include_incomplete: bool = True) -> list[str]:
        """Recalcula desde el JSON original sanitizado y devuelve las diferencias con las estadísticas (vacío = coincide)."""
        result = self.analyze(account_id, form_id, "all", include_incomplete=include_incomplete)
        _detail, questions_raw = self._surveys.raw_structure(account_id, form_id)
        raw_subs = self._repo.raw_present(account_id, form_id, include_incomplete=include_incomplete)
        raw = cc.raw_counts(questions_raw or {}, raw_subs)
        return cc.compare(result.questions, raw, total=result.overview.total, completed=result.overview.completed,
                          raw_total=len(raw_subs), raw_completed=sum(1 for s in raw_subs if s.get("isCompleted")))

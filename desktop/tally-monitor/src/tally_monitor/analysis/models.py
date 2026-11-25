"""Datos de entrada y resultados del análisis. Sin dependencias de Qt, SQLite ni red."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# ---------- entrada (filas simples que entrega el repositorio) ----------
@dataclass(frozen=True)
class SubmissionPoint:
    key: int                       # número de «Usuario»
    submitted_at: str              # ISO UTC (2026-11-10T12:00:00.000Z)
    is_completed: bool


@dataclass(frozen=True)
class AnswerPoint:
    key: int
    question_id: str
    kind: str                      # text | single | multi | raw
    is_blank: bool
    text_len: int | None = None
    choices: tuple[tuple[str, str], ...] = ()      # (texto, origen: declared|other|unmatched)


@dataclass(frozen=True)
class ResponseRow:
    """Una respuesta completa lista para exportar (el texto libre solo viaja si se pide)."""
    key: int
    submitted_at: str
    is_completed: bool
    cells: dict                    # question_id -> (kind, is_blank, texto|None, ((opción, origen), ...))


@dataclass(frozen=True)
class QuestionInfo:
    question_id: str
    position: int
    type: str
    title: str
    options: tuple[str, ...] = ()
    has_other_option: bool = False
    is_deleted: bool = False


# ---------- filtro de tiempo ----------
@dataclass(frozen=True)
class ResolvedFilter:
    kind: str                      # all | 24h | 7d | 30d | custom
    start_iso: str | None          # inclusivo
    end_iso: str | None            # exclusivo
    label: str


@dataclass(frozen=True)
class AnswerFilter:
    """Cruce de preguntas: conserva solo los envíos cuya respuesta a `question_id` incluye exactamente `option_text`."""
    question_id: str
    option_text: str


# ---------- resultados ----------
@dataclass(frozen=True)
class Overview:
    total: int
    completed: int
    partial: int
    first_at: str | None
    last_at: str | None
    span_days: int                 # días locales entre la primera y la última respuesta (inclusive); 0 si no hay
    per_day: float | None          # promedio de respuestas por día dentro de ese lapso


@dataclass(frozen=True)
class OptionStat:
    text: str
    count: int
    pct: float | None              # % sobre quienes respondieron la pregunta; None si nadie respondió


@dataclass(frozen=True)
class QuestionStats:
    question_id: str
    position: int
    type: str
    title: str
    kind: str                      # single | multi | text | raw
    interpreted: bool
    asked: int                     # envíos que traían esta pregunta (con respuesta, vacía o no)
    answered: int                  # respondieron (no vacía)
    blank: int                     # la traían pero vacía
    not_asked: int                 # envíos del filtro que no traían la pregunta (p. ej. agregada después)
    base_note: str                 # a qué se refiere el porcentaje
    options: tuple[OptionStat, ...] = ()
    other_count: int = 0
    other_values: tuple[tuple[str, int], ...] = ()
    orphan_count: int = 0
    orphan_values: tuple[tuple[str, int], ...] = ()
    avg_len: float | None = None
    max_len: int | None = None
    is_deleted: bool = False


@dataclass(frozen=True)
class TimeBucket:
    start: datetime                # inicio local (sin zona) del intervalo
    count: int


@dataclass(frozen=True)
class Timeline:
    bucket: str                    # hour | day | month
    points: tuple[TimeBucket, ...]
    total: int


@dataclass(frozen=True)
class SurveyAnalysis:
    form_id: str
    filter: ResolvedFilter
    include_incomplete: bool
    generated_at: str
    overview: Overview
    questions: tuple[QuestionStats, ...]
    timeline: Timeline
    warnings: tuple[str, ...] = field(default_factory=tuple)
    trends: object = None                      # analysis.trends.Trends del conjunto analizado
    answer_filter: AnswerFilter | None = None
    matched: int | None = None                 # con filtro: envíos del período que cumplen
    total_in_period: int | None = None         # con filtro: envíos del período antes de filtrar

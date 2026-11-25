package ar.tallymonitor.analysis

import java.time.LocalDateTime

/** Filas simples que entrega el almacenamiento al análisis. */
data class SubmissionPoint(val key: Int, val submittedAt: String, val isCompleted: Boolean)

/** kind: text | single | multi | raw. choices: (texto, origen declared|other|unmatched). */
data class AnswerPoint(
    val key: Int, val questionId: String, val kind: String, val isBlank: Boolean,
    val textLen: Int? = null, val choices: List<Pair<String, String>> = emptyList(),
)

/** Una celda de respuesta lista para exportar (el texto libre solo viaja si se pide). */
data class Cell(val kind: String, val isBlank: Boolean, val text: String?, val choices: List<Pair<String, String>>)

data class ResponseRow(val key: Int, val submittedAt: String, val isCompleted: Boolean, val cells: Map<String, Cell>)

data class QuestionInfo(
    val questionId: String, val position: Int, val type: String, val title: String,
    val options: List<String> = emptyList(), val hasOtherOption: Boolean = false, val isDeleted: Boolean = false,
)

/** Filtro ya resuelto: inicio inclusivo, fin exclusivo (ISO UTC). */
data class ResolvedFilter(val kind: String, val startIso: String?, val endIso: String?, val label: String)

data class Overview(
    val total: Int, val completed: Int, val partial: Int, val firstAt: String?, val lastAt: String?,
    val spanDays: Int, val perDay: Double?,
)

data class OptionStat(val text: String, val count: Int, val pct: Double?)

data class QuestionStats(
    val questionId: String, val position: Int, val type: String, val title: String, val kind: String,
    val interpreted: Boolean, val asked: Int, val answered: Int, val blank: Int, val notAsked: Int, val baseNote: String,
    val options: List<OptionStat> = emptyList(), val otherCount: Int = 0, val otherValues: List<Pair<String, Int>> = emptyList(),
    val orphanCount: Int = 0, val orphanValues: List<Pair<String, Int>> = emptyList(),
    val avgLen: Double? = null, val maxLen: Int? = null, val isDeleted: Boolean = false,
)

data class TimeBucket(val start: LocalDateTime, val count: Int)

/** bucket: hour | day | month. */
data class Timeline(val bucket: String, val points: List<TimeBucket>, val total: Int)

data class SurveyAnalysis(
    val formId: String, val filter: ResolvedFilter, val includeIncomplete: Boolean, val generatedAt: String,
    val overview: Overview, val questions: List<QuestionStats>, val timeline: Timeline, val warnings: List<String> = emptyList(),
    /** Ritmo (spec §2.2) y resultado del cruce de preguntas (null si no hay cruce). */
    val trends: Trends? = null, val answerFilter: AnswerFilterResult? = null,
)

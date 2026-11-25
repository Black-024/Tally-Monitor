package ar.tallymonitor.export

import ar.tallymonitor.analysis.ResponseRow
import ar.tallymonitor.analysis.SurveyAnalysis
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZoneOffset

const val NOTE_TEXT_OMITTED = "Respuesta de texto no incluida en esta exportación."

/** isNote = true: no es una respuesta sino un aviso (p. ej. texto no incluido). */
data class AnswerItem(val number: Int, val title: String, val text: String, val isNote: Boolean = false)

/** Ficha de una persona («Usuario 001»), compartida por PDF, Excel e imagen. */
data class ResponseCard(val key: Int, val label: String, val whenLocal: LocalDateTime, val isCompleted: Boolean, val items: List<AnswerItem>)

object Individual {
    fun localTime(iso: String, tz: ZoneId): LocalDateTime =
        LocalDateTime.parse(iso.substring(0, 19)).atOffset(ZoneOffset.UTC).atZoneSameInstant(tz).toLocalDateTime()

    /** Solo se muestran las preguntas que la persona respondió (las saltadas u opcionales sin respuesta no aparecen). */
    fun build(analysis: SurveyAnalysis, rows: List<ResponseRow>, tz: ZoneId, labelFor: (Int) -> String, includeText: Boolean, mask: Boolean): List<ResponseCard> =
        rows.map { row -> card(analysis, row, tz, labelFor, includeText, mask) }

    fun card(analysis: SurveyAnalysis, row: ResponseRow, tz: ZoneId, labelFor: (Int) -> String, includeText: Boolean, mask: Boolean): ResponseCard {
        val items = ArrayList<AnswerItem>()
        analysis.questions.forEachIndexed { idx, q ->
            val cell = row.cells[q.questionId] ?: return@forEachIndexed
            if (cell.isBlank) return@forEachIndexed
            val title = (q.title.ifEmpty { "(sin título)" }) + (if (q.isDeleted) " (pregunta eliminada)" else "")
            when (cell.kind) {
                "single", "multi" -> {
                    val value = cell.choices.joinToString(", ") { it.first }
                    if (value.isNotEmpty()) items += AnswerItem(idx + 1, title, value)
                }
                "text" -> {
                    val t = cell.text
                    if (includeText && !t.isNullOrEmpty()) items += AnswerItem(idx + 1, title, if (mask) Masking.maskText(t) else t)
                    else items += AnswerItem(idx + 1, title, NOTE_TEXT_OMITTED, isNote = true)
                }
            }
        }
        return ResponseCard(row.key, labelFor(row.key), localTime(row.submittedAt, tz), row.isCompleted, items)
    }
}

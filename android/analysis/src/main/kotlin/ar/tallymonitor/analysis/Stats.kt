package ar.tallymonitor.analysis

import java.time.Duration
import java.time.Instant
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.temporal.ChronoUnit

/**
 * Estadísticas puras. Reglas (docs/ESTADISTICAS.md):
 * «respondió» = respuesta no vacía; «sin respuesta» = vacía; «no traía la pregunta» se cuenta aparte;
 * porcentajes sobre quienes respondieron esa pregunta; en selección múltiple, de personas (puede superar 100 %);
 * los números internos son enteros y el redondeo es cosa de quien muestra.
 */
object Stats {
    private val BASE_NOTES = mapOf(
        "single" to "% sobre quienes respondieron esta pregunta",
        "multi" to "% de personas que respondieron esta pregunta (puede sumar más de 100 %)",
        "text" to "", "raw" to "",
    )
    private val KIND_BY_TYPE = mapOf("MULTIPLE_CHOICE" to "single", "CHECKBOXES" to "multi", "TEXTAREA" to "text")

    fun parseIso(iso: String): Instant = Instant.parse(iso)

    private fun localDate(iso: String, tz: ZoneId) = parseIso(iso).atZone(tz).toLocalDate()

    fun pct(count: Int, base: Int): Double? = if (base <= 0) null else count * 100.0 / base

    fun overview(submissions: Collection<SubmissionPoint>, tz: ZoneId): Overview {
        if (submissions.isEmpty()) return Overview(0, 0, 0, null, null, 0, null)
        val completed = submissions.count { it.isCompleted }
        val first = submissions.minOf { it.submittedAt }
        val last = submissions.maxOf { it.submittedAt }
        val span = ChronoUnit.DAYS.between(localDate(first, tz), localDate(last, tz)).toInt() + 1
        return Overview(submissions.size, completed, submissions.size - completed, first, last, span, submissions.size.toDouble() / span)
    }

    private fun ranked(m: Map<String, Int>): List<Pair<String, Int>> =
        m.entries.sortedWith(compareBy({ -it.value }, { it.key })).map { it.key to it.value }

    fun questionStats(q: QuestionInfo, answers: Collection<AnswerPoint>, totalSubmissions: Int): QuestionStats {
        val kind = KIND_BY_TYPE[q.type] ?: "raw"
        val rows = LinkedHashMap<Int, AnswerPoint>()
        for (a in answers) rows[a.key] = a                       // una respuesta por envío y pregunta
        val asked = rows.size
        val answeredRows = rows.values.filter { !it.isBlank }
        val answered = answeredRows.size
        val base = QuestionStats(
            questionId = q.questionId, position = q.position, type = q.type, title = q.title, kind = kind, interpreted = false,
            asked = asked, answered = answered, blank = asked - answered, notAsked = maxOf(0, totalSubmissions - asked),
            baseNote = BASE_NOTES.getValue(kind), isDeleted = q.isDeleted,
        )
        if (kind == "single" || kind == "multi") {
            val declared = HashMap<String, Int>()
            val other = HashMap<String, Int>()
            val orphan = HashMap<String, Int>()
            for (a in answeredRows) {
                val seen = HashSet<Pair<String, String>>()
                for ((text, origin) in a.choices) {
                    if (!seen.add(text to origin)) continue       // una persona cuenta una sola vez por opción
                    val target = when (origin) { "declared" -> declared; "other" -> other; else -> orphan }
                    target[text] = (target[text] ?: 0) + 1
                }
            }
            val options = q.options.map { OptionStat(it, declared[it] ?: 0, pct(declared[it] ?: 0, answered)) }
            val known = q.options.toSet()
            // opciones «declared» que ya no figuran en la pregunta: se muestran, nunca se pierden
            val extra = declared.entries.sortedBy { it.key }.filter { it.key !in known }.map { OptionStat(it.key, it.value, pct(it.value, answered)) }
            return base.copy(
                interpreted = true, options = options + extra,
                otherCount = other.values.sum(), otherValues = ranked(other),
                orphanCount = orphan.values.sum(), orphanValues = ranked(orphan),
            )
        }
        if (kind == "text") {
            val lens = answeredRows.map { it.textLen ?: 0 }
            return base.copy(interpreted = true, avgLen = if (lens.isEmpty()) null else lens.sum().toDouble() / lens.size, maxLen = lens.maxOrNull())
        }
        return base
    }

    fun allQuestionStats(questions: Collection<QuestionInfo>, answers: Collection<AnswerPoint>, totalSubmissions: Int): List<QuestionStats> {
        val byQ = answers.groupBy { it.questionId }
        return questions.sortedWith(compareBy({ it.position }, { it.questionId }))
            .map { questionStats(it, byQ[it.questionId] ?: emptyList(), totalSubmissions) }
    }

    // ---------- evolución en el tiempo ----------
    private fun floor(dt: LocalDateTime, bucket: String): LocalDateTime = when (bucket) {
        "hour" -> dt.truncatedTo(ChronoUnit.HOURS)
        "day" -> dt.truncatedTo(ChronoUnit.DAYS)
        else -> dt.truncatedTo(ChronoUnit.DAYS).withDayOfMonth(1)
    }

    private fun next(dt: LocalDateTime, bucket: String): LocalDateTime = when (bucket) {
        "hour" -> dt.plusHours(1)
        "day" -> dt.plusDays(1)
        else -> dt.plusMonths(1)
    }

    /** hour hasta 48 h, day hasta 400 días, month más allá. */
    fun chooseBucket(first: LocalDateTime, last: LocalDateTime): String {
        val span = Duration.between(first, last)
        return when {
            span <= Duration.ofHours(48) -> "hour"
            span <= Duration.ofDays(400) -> "day"
            else -> "month"
        }
    }

    /**
     * Cuenta por intervalo en hora local, rellenando con ceros. [start]/[end] fijan el eje (p. ej. las 24 h completas
     * aunque no haya respuestas); si faltan, va de la primera a la última respuesta.
     */
    fun timeline(submissions: Collection<SubmissionPoint>, tz: ZoneId, start: Instant? = null, end: Instant? = null): Timeline {
        val locs = submissions.map { parseIso(it.submittedAt).atZone(tz).toLocalDateTime() }
        if (locs.isEmpty() && (start == null || end == null)) return Timeline("day", emptyList(), 0)
        val lo = start?.atZone(tz)?.toLocalDateTime() ?: locs.min()
        var hi = end?.atZone(tz)?.toLocalDateTime() ?: locs.max()
        if (hi < lo) hi = lo
        val bucket = chooseBucket(lo, hi)
        val counts = HashMap<LocalDateTime, Int>()
        for (d in locs) counts.merge(floor(d, bucket), 1, Int::plus)
        val points = ArrayList<TimeBucket>()
        var cur = floor(lo, bucket)
        val last = floor(hi, bucket)
        while (cur <= last) {
            points.add(TimeBucket(cur, counts[cur] ?: 0))
            cur = next(cur, bucket)
        }
        return Timeline(bucket, points, locs.size)
    }
}

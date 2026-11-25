package ar.tallymonitor.verify

import ar.tallymonitor.analysis.*
import ar.tallymonitor.core.JObj
import ar.tallymonitor.core.QuestionRow
import ar.tallymonitor.sync.Normalizer
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

/** Comprobaciones de análisis y exportación contra los vectores golden. */
fun extraChecks(g: Golden): List<Pair<String, () -> List<String>>> = listOf(
    "estadísticas" to { statsCheck(g) },
    "filtros de tiempo" to { timeFilterCheck(g) },
    "enmascarado" to { maskingCheck(g) },
) + apiChecks() + syncChecks(g.dir.path) + credChecks() + archChecks(g.dir.parentFile.path) + listOf(
)

private val TZ = ZoneOffset.ofHours(-3)

@Suppress("UNCHECKED_CAST")
private fun statsCheck(g: Golden): List<String> {
    val out = ArrayList<String>()
    val san = g.obj("expected_sanitized.json")
    val form = san["form"] as JObj
    val qrows = Normalizer.questionRows(form, san["questions"] as JObj)
    val byId: Map<String, QuestionRow> = qrows.associateBy { it.questionId }
    val subs = (san["submissions"] as List<JObj>).map { Normalizer.submissionRow(it, byId) }
    val pts = ArrayList<SubmissionPoint>(); val answers = ArrayList<AnswerPoint>()
    subs.forEachIndexed { idx, r ->
        val i = idx + 1
        pts += SubmissionPoint(i, r.submittedAt, r.isCompleted)
        for (a in r.answers) answers += AnswerPoint(i, a.questionId, a.kind, a.isBlank,
            if (a.textValue != null && a.kind == "text") a.textValue!!.length else null, a.choices.map { it.optionText to it.origin })
    }
    val qinfo = qrows.map { QuestionInfo(it.questionId, it.position, it.type, it.title, it.options, it.hasOtherOption, it.isDeleted) }
    val exp = g.obj("expected_stats.json")
    g.diff("overview", overviewMap(Stats.overview(pts, TZ)), exp["overview"], out, 1e-9)
    g.diff("questions", Stats.allQuestionStats(qinfo, answers, pts.size).map { questionMap(it) }, exp["questions"], out, 1e-9)
    g.diff("timeline", timelineMap(Stats.timeline(pts, TZ)), exp["timeline"], out)
    return out
}

private fun overviewMap(o: Overview) = mapOf("total" to o.total, "completed" to o.completed, "partial" to o.partial,
    "first_at" to o.firstAt, "last_at" to o.lastAt, "span_days" to o.spanDays, "per_day" to o.perDay)

private fun questionMap(q: QuestionStats) = mapOf(
    "question_id" to q.questionId, "position" to q.position, "type" to q.type, "title" to q.title, "kind" to q.kind,
    "interpreted" to q.interpreted, "asked" to q.asked, "answered" to q.answered, "blank" to q.blank, "not_asked" to q.notAsked,
    "base_note" to q.baseNote, "options" to q.options.map { mapOf("text" to it.text, "count" to it.count, "pct" to it.pct) },
    "other_count" to q.otherCount, "other_values" to q.otherValues.map { listOf(it.first, it.second) },
    "orphan_count" to q.orphanCount, "orphan_values" to q.orphanValues.map { listOf(it.first, it.second) },
    "avg_len" to q.avgLen, "max_len" to q.maxLen, "is_deleted" to q.isDeleted)

private fun timelineMap(t: Timeline) = mapOf("bucket" to t.bucket, "total" to t.total,
    "points" to t.points.map { mapOf("start" to it.start.toString().replace("T", " ").let { s -> if (s.length == 16) "$s:00" else s }, "count" to it.count) })

@Suppress("UNCHECKED_CAST")
private fun timeFilterCheck(g: Golden): List<String> {
    val out = ArrayList<String>()
    val exp = g.obj("expected_timefilter.json")
    val now = Instant.parse("2026-11-10T15:00:00Z")
    for (c in exp["cases"] as List<JObj>) {
        val kind = c["kind"] as String
        val r = if (kind == "custom") TimeFilter.resolve(kind, now, TZ, LocalDate.parse(c["start"] as String), LocalDate.parse(c["end"] as String))
                else TimeFilter.resolve(kind, now, TZ)
        g.diff("filtro $kind", mapOf("kind" to r.kind, "start_iso" to r.startIso, "end_iso" to r.endIso, "label" to r.label), c["result"], out)
    }
    return out
}

@Suppress("UNCHECKED_CAST")
private fun maskingCheck(g: Golden): List<String> {
    val out = ArrayList<String>()
    for (c in g.read("masking.json") as List<Map<String, Any?>>) {
        val got = ar.tallymonitor.export.Masking.maskText(c["in"] as String)
        if (got != c["out"]) out += "«${c["in"]}»: «$got» ≠ «${c["out"]}»"
    }
    return out
}

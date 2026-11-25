package ar.tallymonitor.analysis

import ar.tallymonitor.core.JObj

/**
 * Segundo camino de cálculo, INDEPENDIENTE del normalizador: parte del «JSON original sanitizado» y cuenta a su manera.
 * Sirve para comprobar que las estadísticas coinciden con los datos originales.
 */
object Crosscheck {
    class RawQuestion(val type: String?, var asked: Int = 0, var answered: Int = 0, val labels: MutableMap<String, Int> = HashMap())

    private fun nonBlank(v: Any?): Boolean = when (v) {
        null -> false
        is String -> v.trim().isNotEmpty()
        is List<*> -> v.any { nonBlank(it) }
        else -> true
    }

    @Suppress("UNCHECKED_CAST")
    fun rawCounts(questionsRaw: JObj?, submissions: List<JObj>): Map<String, RawQuestion> {
        val out = LinkedHashMap<String, RawQuestion>()
        for (q in (questionsRaw?.get("questions") as? List<*>) ?: emptyList<Any?>()) {
            val qo = q as? Map<String, Any?> ?: continue
            out[qo["id"].toString()] = RawQuestion(qo["type"] as? String)
        }
        for (sub in submissions) {
            val seen = HashSet<String>()
            for (r in (sub["responses"] as? List<*>) ?: emptyList<Any?>()) {
                val ro = r as? Map<String, Any?> ?: continue
                val qid = ro["questionId"].toString()
                val entry = out[qid] ?: continue
                if (!seen.add(qid)) continue
                val ans = ro["answer"]
                entry.asked++
                if (nonBlank(ans)) {
                    entry.answered++
                    if ((entry.type == "MULTIPLE_CHOICE" || entry.type == "CHECKBOXES") && ans is List<*>) {
                        for (label in ans.filterIsInstance<String>().filter { it.trim().isNotEmpty() }.toSet()) {
                            entry.labels[label] = (entry.labels[label] ?: 0) + 1
                        }
                    }
                }
            }
        }
        return out
    }

    /** Lista de diferencias (vacía = todo coincide). Los mensajes no incluyen textos de personas. */
    fun compare(stats: List<QuestionStats>, raw: Map<String, RawQuestion>, total: Int, completed: Int, rawTotal: Int, rawCompleted: Int): List<String> {
        val problems = ArrayList<String>()
        if (total != rawTotal || completed != rawCompleted) problems += "totales: calculado $total/$completed vs original $rawTotal/$rawCompleted"
        for (q in stats) {
            val r = raw[q.questionId]
            if (r == null) { problems += "pregunta ${q.position + 1}: no está en los datos originales"; continue }
            if (q.asked != r.asked || q.answered != r.answered) {
                problems += "pregunta ${q.position + 1}: traían/respondieron ${q.asked}/${q.answered} vs original ${r.asked}/${r.answered}"
            }
            if ((q.kind == "single" || q.kind == "multi") && q.interpreted) {
                val known = q.options.map { it.text }.toSet()
                for (o in q.options) {
                    val exp = r.labels[o.text] ?: 0
                    if (o.count != exp) problems += "pregunta ${q.position + 1}: opción «${o.text.take(30)}» ${o.count} vs $exp"
                }
                val rest = r.labels.filterKeys { it !in known }.values.sum()
                if (q.otherCount + q.orphanCount != rest) problems += "pregunta ${q.position + 1}: «otro»+huérfanas ${q.otherCount + q.orphanCount} vs $rest"
            }
        }
        return problems
    }
}

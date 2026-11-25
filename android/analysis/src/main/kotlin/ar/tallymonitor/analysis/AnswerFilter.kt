package ar.tallymonitor.analysis

/** Cruce de preguntas (spec 1.1 §2.3): solo envíos cuya respuesta a [questionId] incluya exactamente [optionText] (espacios normalizados). */
data class AnswerFilter(val questionId: String, val optionText: String)

/** matched = personas que cumplen; totalInPeriod = personas del período antes de aplicar el cruce. */
data class AnswerFilterResult(val filter: AnswerFilter, val matched: Int, val totalInPeriod: Int)

object AnswerFilters {
    private val OPTION_TYPES = setOf("MULTIPLE_CHOICE", "CHECKBOXES")

    /** Recorta y junta espacios internos. */
    fun normalize(text: String): String {
        val sb = StringBuilder(); var pendingSpace = false
        for (ch in text) {
            if (ch.isWhitespace()) { pendingSpace = sb.isNotEmpty() } else { if (pendingSpace) sb.append(' '); pendingSpace = false; sb.append(ch) }
        }
        return sb.toString()
    }

    /** Solo las preguntas de opción que la app interpreta (única y múltiple). */
    fun isOptionQuestion(q: QuestionInfo): Boolean = q.type in OPTION_TYPES

    /** [choices]: pares (clave del envío, texto de la opción elegida) de ESA pregunta. Devuelve las claves que eligieron la opción. */
    fun matchingKeys(filter: AnswerFilter, choices: Collection<Pair<Int, String>>): Set<Int> {
        val wanted = normalize(filter.optionText)
        val out = HashSet<Int>()
        for ((key, text) in choices) if (normalize(text) == wanted) out.add(key)
        return out
    }
}

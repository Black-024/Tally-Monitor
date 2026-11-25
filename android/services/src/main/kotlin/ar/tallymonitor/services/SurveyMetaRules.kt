package ar.tallymonitor.services

import ar.tallymonitor.core.ErrorCode
import ar.tallymonitor.core.TallyMonitorException

/**
 * Reglas ÚNICAS de meta, nota y etiquetas (spec 1.1 §1). Código puro (sin Android): la interfaz las usa para validar mientras se
 * escribe y el backend las vuelve a aplicar antes de tocar la base. Los largos se cuentan en caracteres Unicode (code points).
 */
object SurveyMetaRules {
    const val MAX_GOAL = 1_000_000
    const val MAX_NOTE = 500
    const val MAX_TAG = 24
    const val MAX_TAGS = 8

    class Clean(val goal: Int?, val note: String, val tags: List<String>)

    private fun chars(s: String) = s.codePointCount(0, s.length)

    /** null = sin meta. Si no, entero de 1 a 1.000.000. */
    fun goal(goal: Int?): Int? {
        if (goal != null && goal !in 1..MAX_GOAL) throw TallyMonitorException(ErrorCode.INVALID_GOAL)
        return goal
    }

    /** Recorta los extremos; más de 500 caracteres es un error (no se corta en silencio). */
    fun note(note: String): String {
        val n = note.trim()
        if (chars(n) > MAX_NOTE) throw TallyMonitorException(ErrorCode.NOTE_TOO_LONG)
        return n
    }

    /** Recorta y junta los espacios internos. No valida largo ni vacío (eso lo hace [tags]). */
    fun normalizeTag(tag: String): String {
        val sb = StringBuilder(); var pending = false
        for (ch in tag) { if (ch.isWhitespace()) pending = sb.isNotEmpty() else { if (pending) sb.append(' '); pending = false; sb.append(ch) } }
        return sb.toString()
    }

    /**
     * Normaliza cada etiqueta; vacía o de más de 24 caracteres es un error; las repetidas (sin distinguir mayúsculas) se descartan
     * conservando la primera grafía; más de 8 distintas es un error. Conserva el orden de entrada.
     */
    fun tags(raw: List<String>): List<String> {
        val seen = HashSet<String>(); val out = ArrayList<String>()
        for (r in raw) {
            val t = normalizeTag(r)
            if (t.isEmpty() || chars(t) > MAX_TAG) throw TallyMonitorException(ErrorCode.INVALID_TAG)
            if (seen.add(t.lowercase())) out.add(t)
        }
        if (out.size > MAX_TAGS) throw TallyMonitorException(ErrorCode.TOO_MANY_TAGS)
        return out
    }

    /** Valida TODO antes de devolver: si algo falla, no se escribe nada. */
    fun clean(goal: Int?, note: String, tags: List<String>): Clean = Clean(goal(goal), note(note), tags(tags))
}

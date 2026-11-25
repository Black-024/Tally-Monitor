package ar.tallymonitor.export

/** Enmascarado de posibles datos personales en textos libres. Es una ayuda, NO una garantía. */
object Masking {
    const val MASK = "[oculto]"
    // (?U): \w, \d y \s en Unicode, como en Python.
    private val EMAIL = Regex("(?U)[\\w.+-]+@[\\w-]+(?:\\.[\\w-]+)+")
    private val URL = Regex("(?U)(?:https?://|www\\.)\\S+", RegexOption.IGNORE_CASE)
    private val HANDLE = Regex("(?U)(?<![\\w@])@\\w{3,}")
    private val NUMBERISH = Regex("(?U)(?<![\\w])\\+?\\d[\\d\\s().-]{5,}\\d(?![\\w])")
    private val DATE = Regex("(?U)^\\d{1,4}[-/.]\\d{1,2}[-/.]\\d{1,4}$")

    /** Oculta correos, direcciones web, usuarios (@nombre) y números largos (teléfonos, DNI, tarjetas). */
    fun maskText(text: String): String {
        if (text.isEmpty()) return text
        var out = EMAIL.replace(text, MASK)
        out = URL.replace(out, MASK)
        out = HANDLE.replace(out, MASK)
        return NUMBERISH.replace(out) { m ->
            val s = m.value.trim()
            if (DATE.containsMatchIn(s)) m.value else if (s.count { it.isDigit() } >= 7) MASK else m.value
        }
    }
}

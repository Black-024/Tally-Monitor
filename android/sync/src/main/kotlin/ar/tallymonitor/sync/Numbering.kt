package ar.tallymonitor.sync

/**
 * Etiquetas «Usuario NNN».
 * 1–9999 → Usuario 001 … Usuario 9999 (mínimo 3 dígitos); 10000+ → bloques de 9999 con letras:
 * Usuario A001 … A9999, B001 … Z9999, AA001 … El número interno siempre es un entero; la etiqueta es solo presentación.
 */
object Numbering {
    const val PER_BLOCK = 9999
    const val FIRST_LETTER_NUMBER = 10000

    private fun letters(index: Int): String {
        var i = index + 1
        val sb = StringBuilder()
        while (i > 0) {
            val rem = (i - 1) % 26
            i = (i - 1) / 26
            sb.insert(0, ('A'.code + rem).toChar())
        }
        return sb.toString()
    }

    private fun lettersIndex(letters: String): Int {
        var n = 0
        for (ch in letters) n = n * 26 + (ch.code - 64)
        return n - 1
    }

    fun formatUserLabel(number: Int): String {
        require(number >= 1) { "El número de usuario debe ser un entero positivo" }
        if (number < FIRST_LETTER_NUMBER) return "Usuario " + number.toString().padStart(3, '0')
        val k = number - FIRST_LETTER_NUMBER
        return "Usuario " + letters(k / PER_BLOCK) + (k % PER_BLOCK + 1).toString().padStart(3, '0')
    }

    private val NUM = Regex("^\\s*(?:usuario\\s+)?(\\d{1,4})\\s*$", RegexOption.IGNORE_CASE)
    private val LET = Regex("^\\s*(?:usuario\\s+)?([A-Za-z]{1,4})(\\d{3,4})\\s*$", RegexOption.IGNORE_CASE)

    /** Inversa de [formatUserLabel] (para buscar «Usuario 012» o «A001»). null si no es una etiqueta. */
    fun parseUserLabel(text: String): Int? {
        NUM.matchEntire(text)?.let { m ->
            val n = m.groupValues[1].toInt()
            return if (n in 1..PER_BLOCK) n else null
        }
        LET.matchEntire(text)?.let { m ->
            val within = m.groupValues[2].toInt()
            if (within !in 1..PER_BLOCK) return null
            return FIRST_LETTER_NUMBER + lettersIndex(m.groupValues[1].uppercase()) * PER_BLOCK + within - 1
        }
        return null
    }
}

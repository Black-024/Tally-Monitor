package ar.tallymonitor.core

/** Oculta cualquier clave de Tally («tly-…») y cabeceras «Bearer …» de un texto antes de registrarlo. */
object Redactor {
    private val KEY = Regex("tly-[A-Za-z0-9_\\-]{6,}")
    private val BEARER = Regex("(?i)bearer\\s+[A-Za-z0-9._\\-]{6,}")
    fun redact(text: String): String = BEARER.replace(KEY.replace(text, "tly-***"), "Bearer ***")
}

/** Único punto de salida de mensajes de diagnóstico. Todo pasa por [Redactor]. */
interface AppLogger {
    fun log(level: Level, message: String)
    enum class Level { DEBUG, INFO, WARN, ERROR }
    fun info(m: String) = log(Level.INFO, m)
    fun warn(m: String) = log(Level.WARN, m)
    fun error(m: String) = log(Level.ERROR, m)
    companion object { val NONE = object : AppLogger { override fun log(level: Level, message: String) {} } }
}

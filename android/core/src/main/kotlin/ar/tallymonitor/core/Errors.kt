package ar.tallymonitor.core

/**
 * Errores tipados. La interfaz los traduce a texto con [code]; el backend nunca incluye la clave, el cuerpo de una
 * respuesta de la API ni datos de encuestas en [message].
 */
open class TallyMonitorException(val code: ErrorCode, message: String? = null, cause: Throwable? = null) :
    RuntimeException(message ?: code.name, cause)

enum class ErrorCode {
    INVALID_KEY_FORMAT, KEY_REJECTED, FORBIDDEN, NETWORK, TIMEOUT, RATE_LIMITED, SERVER_ERROR, BAD_RESPONSE,
    RESPONSE_TOO_LARGE, NOT_FOUND, PROTECTION_UNAVAILABLE, CREDENTIAL_UNREADABLE, ACCOUNT_MISMATCH,
    DATABASE_TOO_NEW, MIGRATION_FAILED, BACKUP_FAILED, RESTORE_FAILED, SYNC_CANCELLED, EXPORT_FAILED,
    EXPORT_CANCELLED, INVALID_ID, NOT_FOUND_LOCAL, ALREADY_EXISTS, INTERNAL,
    INVALID_GOAL, NOTE_TOO_LONG, INVALID_TAG, TOO_MANY_TAGS, INVALID_FILTER
}

/** Ante 429/5xx/red caídas el cliente informa cuánto esperar (segundos) cuando la API lo indica. */
class ApiException(code: ErrorCode, val status: Int? = null, val retryAfterSeconds: Int? = null, cause: Throwable? = null) :
    TallyMonitorException(code, null, cause)

class SyncCancelledException : TallyMonitorException(ErrorCode.SYNC_CANCELLED)

/** Un identificador de Tally debe ser corto y alfanumérico antes de armar una ruta con él. */
object Ids {
    private val RE = Regex("^[A-Za-z0-9_-]{1,64}$")
    fun check(id: String): String {
        if (!RE.matches(id)) throw TallyMonitorException(ErrorCode.INVALID_ID)
        return id
    }
}

/** Reloj inyectable: las pruebas lo fijan; en producción usa la hora real. */
interface Clock {
    fun nowMillis(): Long
    fun nowIso(): String = Iso.format(nowMillis())
    companion object { val SYSTEM = object : Clock { override fun nowMillis() = System.currentTimeMillis() } }
}

/** Fechas ISO-8601 UTC con milisegundos («2026-11-10T12:00:00.000Z»), el formato de Tally. */
object Iso {
    private val FMT = java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'").withZone(java.time.ZoneOffset.UTC)
    fun format(millis: Long): String = FMT.format(java.time.Instant.ofEpochMilli(millis))
    fun parse(text: String): java.time.Instant = java.time.Instant.parse(text)
    fun parseOrNull(text: String?): java.time.Instant? = try { if (text == null) null else java.time.Instant.parse(text) } catch (e: Exception) { null }
}

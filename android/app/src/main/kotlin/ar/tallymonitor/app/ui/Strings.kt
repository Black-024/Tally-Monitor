package ar.tallymonitor.app.ui

import ar.tallymonitor.core.ApiException
import ar.tallymonitor.core.ErrorCode
import ar.tallymonitor.core.TallyMonitorException

/** Textos de error en español (Argentina) o inglés, según el idioma elegido. Nunca incluyen la clave, la URL ni el cuerpo de la respuesta. */
fun errorText(e: Throwable): String = when (e) {
    is TallyMonitorException -> when (e.code) {
        ErrorCode.INVALID_KEY_FORMAT -> tr("La clave no tiene el formato de una API Key de Tally (empieza con «tly-»). Revisá que esté completa y sin espacios.", "The key doesn't look like a Tally API Key (it starts with «tly-»). Check that it's complete and has no spaces.")
        ErrorCode.KEY_REJECTED -> tr("Tally rechazó la clave (401). Revisá que sea correcta y que no esté revocada.", "Tally rejected the key (401). Check that it's correct and hasn't been revoked.")
        ErrorCode.FORBIDDEN -> tr("La clave es válida pero no tiene permiso para esto (403).", "The key is valid but doesn't have permission for this (403).")
        ErrorCode.NETWORK -> tr("No se pudo conectar con Tally. Revisá tu conexión a Internet.", "Couldn't connect to Tally. Check your Internet connection.")
        ErrorCode.TIMEOUT -> tr("Tally tardó demasiado en responder. Probá de nuevo.", "Tally took too long to respond. Try again.")
        ErrorCode.RATE_LIMITED -> tr("Tally pidió esperar un poco (límite de solicitudes).", "Tally asked to wait a bit (rate limit).") + ((e as? ApiException)?.retryAfterSeconds?.let { tr(" Reintentá en $it s.", " Retry in $it s.") } ?: tr(" Reintentá en un minuto.", " Retry in a minute."))
        ErrorCode.SERVER_ERROR -> tr("Tally tiene un problema momentáneo. Probá más tarde.", "Tally is having a temporary problem. Try again later.")
        ErrorCode.BAD_RESPONSE, ErrorCode.RESPONSE_TOO_LARGE -> tr("Tally devolvió una respuesta inesperada.", "Tally returned an unexpected response.")
        ErrorCode.NOT_FOUND -> tr("Tally no encontró eso (¿se eliminó la encuesta?).", "Tally couldn't find that (was the survey deleted?).")
        ErrorCode.PROTECTION_UNAVAILABLE -> tr("Este dispositivo no pudo proteger la clave con su almacén seguro.", "This device couldn't protect the key with its secure storage.")
        ErrorCode.CREDENTIAL_UNREADABLE -> tr("No se puede leer la clave guardada de esta cuenta. Reemplazala desde Cuentas.", "The stored key for this account can't be read. Replace it from Accounts.")
        ErrorCode.ACCOUNT_MISMATCH -> tr("Esa clave pertenece a otro usuario de Tally. Se conservó la anterior.", "That key belongs to a different Tally user. The previous one was kept.")
        ErrorCode.DATABASE_TOO_NEW -> tr("Los datos fueron creados por una versión más nueva de la app.", "The data was created by a newer version of the app.")
        ErrorCode.MIGRATION_FAILED -> tr("No se pudieron actualizar los datos. Se restauró la copia anterior.", "The data couldn't be updated. The previous copy was restored.")
        ErrorCode.BACKUP_FAILED -> tr("No se pudo crear o leer la copia de seguridad.", "The backup couldn't be created or read.")
        ErrorCode.RESTORE_FAILED -> tr("No se pudo restaurar la copia. Se volvió al estado anterior.", "The backup couldn't be restored. Went back to the previous state.")
        ErrorCode.SYNC_CANCELLED -> tr("Sincronización cancelada.", "Sync cancelled.")
        ErrorCode.EXPORT_FAILED -> tr("No se pudo guardar el archivo.", "The file couldn't be saved.")
        ErrorCode.EXPORT_CANCELLED -> tr("Exportación cancelada.", "Export cancelled.")
        ErrorCode.INVALID_ID -> tr("Dato inválido (revisá el nombre: entre 1 y 60 caracteres).", "Invalid value (check the name: between 1 and 60 characters).")
        ErrorCode.NOT_FOUND_LOCAL -> tr("No se encontró ese dato en el teléfono.", "That item wasn't found on the phone.")
        ErrorCode.ALREADY_EXISTS -> tr("Ya existe una cuenta con ese nombre o con esa clave.", "An account with that name or key already exists.")
        ErrorCode.INTERNAL -> tr("Ocurrió un error inesperado.", "An unexpected error occurred.")
        ErrorCode.INVALID_GOAL -> tr("La meta tiene que ser un número entre 1 y 1.000.000.", "The goal must be a number between 1 and 1,000,000.")
        ErrorCode.NOTE_TOO_LONG -> tr("La nota puede tener hasta 500 caracteres.", "The note can have up to 500 characters.")
        ErrorCode.INVALID_TAG -> tr("Cada etiqueta debe tener entre 1 y 24 caracteres.", "Each tag must have between 1 and 24 characters.")
        ErrorCode.TOO_MANY_TAGS -> tr("Se pueden usar hasta 8 etiquetas por encuesta.", "Up to 8 tags can be used per survey.")
        ErrorCode.INVALID_FILTER -> tr("Ese cruce solo funciona con preguntas de opción.", "That cross-filter only works with choice questions.")
    }
    else -> tr("Ocurrió un error inesperado. ", "An unexpected error occurred. ") + where(e)
}

/** Pista técnica para diagnóstico: tipo de error y dónde ocurrió (nunca el mensaje, que podría tener datos). */
private fun where(e: Throwable): String {
    val f = e.stackTrace.firstOrNull { it.className.startsWith("ar.tallymonitor") } ?: e.stackTrace.firstOrNull()
    return "[" + e.javaClass.simpleName + (f?.let { tr(" en ", " in ") + "${it.className.substringAfterLast('.')}.${it.methodName}:${it.lineNumber}" } ?: "") + "]"
}

fun statusText(s: String) = when (s) {
    "active" -> tr("Activa", "Active"); "unverified" -> tr("Sin verificar", "Unverified"); "key_rejected" -> tr("Clave rechazada", "Key rejected")
    "check_failed" -> tr("No se pudo verificar", "Couldn't verify"); "no_credential" -> tr("Sin clave", "No key"); else -> s
}

/** Motivo de una copia de seguridad (valor interno del backend) en el idioma elegido. */
fun backupReasonText(r: String) = when (r) {
    "auto" -> tr("automática", "automatic"); "manual" -> tr("manual", "manual"); "pre_migracion" -> tr("antes de actualizar datos", "before data update")
    "pre_restauracion" -> tr("antes de restaurar", "before restore"); "pre_reconciliacion" -> tr("antes de conciliar", "before reconciling"); else -> r
}

/** Fecha ISO UTC → «dd/MM/yyyy HH:mm» (ES) o «MM/dd/yyyy h:mm a» (EN) en hora local. */
fun localTime(iso: String?, zone: java.time.ZoneId = java.time.ZoneId.systemDefault()): String =
    if (iso == null) "—" else try {
        java.time.format.DateTimeFormatter.ofPattern(if (I18n.current == Lang.EN) "MM/dd/yyyy h:mm a" else "dd/MM/yyyy HH:mm", I18n.locale).format(java.time.Instant.parse(iso).atZone(zone))
    } catch (e: Exception) { "—" }

fun pctText(p: Double?) = if (p == null) "—" else String.format(I18n.locale, "%.1f%%", p)

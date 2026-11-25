package ar.tallymonitor.services

import android.content.Context
import ar.tallymonitor.analysis.AnswerFilter
import ar.tallymonitor.analysis.SurveyAnalysis
import kotlinx.coroutines.flow.Flow
import java.io.OutputStream

/**
 * Contrato estable entre el backend y la interfaz.
 *
 * Convención de errores: todo fallo es una [ar.tallymonitor.core.TallyMonitorException] con un `code` tipado (la interfaz lo traduce a texto);
 * los errores de red de Tally son [ar.tallymonitor.core.ApiException] (con `status` y, si Tally lo informa, `retryAfterSeconds`). Ningún mensaje
 * contiene la clave, la URL ni el cuerpo de una respuesta. Toda función `suspend` es segura de llamar desde el hilo principal
 * (trabaja en Dispatchers.IO). Los `Flow` de sincronización se cancelan cancelando la corrutina que los recolecta.
 * La clave de API entra como [ar.tallymonitor.core.Secret] y NUNCA sale: no existe ninguna función que la devuelva.
 */
interface TallyMonitorBackend {
    val accounts: AccountService
    val surveys: SurveyService
    val sync: SyncService
    val analysis: AnalysisService
    val export: ExportService
    val backups: BackupService
    val settings: SettingsService
    val diagnostics: DiagnosticsService

    companion object {
        /** Crea el backend real (SQLite + Keystore + red). Llamar una sola vez, p. ej. desde la clase Application. */
        fun create(context: Context): TallyMonitorBackend = AndroidBackendFactory.create(context)
    }
}

interface AccountService {
    /** Emite la lista actual y vuelve a emitir tras cada cambio. */
    fun observeAccounts(): Flow<List<Account>>
    /** Valida con GET /users/me ANTES de guardar. Errores: INVALID_KEY_FORMAT, ALREADY_EXISTS (nombre o clave repetidos), KEY_REJECTED, FORBIDDEN, NETWORK, TIMEOUT, RATE_LIMITED, SERVER_ERROR. */
    suspend fun add(name: String, apiKey: ar.tallymonitor.core.Secret): Account
    /** Si la nueva falla la validación, pertenece a otra cuenta de Tally o ya está en otra cuenta local, se conserva la anterior. Devuelve si se pudo comprobar la identidad. */
    suspend fun replaceKey(id: String, newKey: ar.tallymonitor.core.Secret): Boolean
    suspend fun rename(id: String, name: String)
    /** Borra todos los datos de la cuenta y su credencial cifrada. */
    suspend fun remove(id: String)
    suspend fun verify(id: String): VerifyResult
}

interface SurveyService {
    /**
     * `query` busca en nombre, nota y etiquetas. `tag` deja solo las que tienen esa etiqueta (sin distinguir mayúsculas).
     * Las archivadas solo vienen con `includeArchived = true`.
     */
    fun observeSurveys(accountId: String, query: String? = null, onlyFavorites: Boolean = false, tag: String? = null, includeArchived: Boolean = false): Flow<List<SurveySummary>>
    suspend fun survey(accountId: String, formId: String): SurveyDetail
    suspend fun setFavorite(accountId: String, formId: String, on: Boolean)
    suspend fun markOpened(accountId: String, formId: String)
    /**
     * Guarda meta, nota y etiquetas de una encuesta (atómico: se valida todo antes de escribir; no cambia «archivada»).
     * Errores: INVALID_GOAL, NOTE_TOO_LONG, INVALID_TAG, TOO_MANY_TAGS, NOT_FOUND_LOCAL. Reglas en [SurveyMetaRules].
     */
    suspend fun setSurveyMeta(accountId: String, formId: String, goal: Int?, note: String, tags: List<String>)
    suspend fun setArchived(accountId: String, formId: String, archived: Boolean)
    fun observeRecents(accountId: String, limit: Int = 10): Flow<List<SurveySummary>>
}

interface SyncService {
    /** Trae la lista de encuestas de la cuenta. */
    fun syncForms(accountId: String): Flow<SyncEvent>
    /** Trae una encuesta (estructura + respuestas). `full` fuerza un recorrido completo. */
    fun syncForm(accountId: String, formId: String, full: Boolean = false): Flow<SyncEvent>
}

interface AnalysisService {
    /** `answerFilter` (cruce): todo el resultado se calcula solo con quienes eligieron esa opción. Error INVALID_FILTER si la pregunta no es de opción. No afecta a las exportaciones. */
    suspend fun analyze(accountId: String, formId: String, filter: TimeFilterSpec, answerFilter: AnswerFilter? = null): SurveyAnalysis
    /** Respuestas guardadas en los últimos 7×24 h por encuesta de la cuenta (formId → cantidad); alimenta las metas. */
    suspend fun recentCounts(accountId: String): Map<String, Int>
    /** Recalcula desde el JSON original sanitizado; lista vacía = coincide. */
    suspend fun crosscheck(accountId: String, formId: String, includeIncomplete: Boolean = true): List<String>
    /** Paginado por desplazamiento (offset/limit). */
    suspend fun responses(accountId: String, formId: String, offset: Int, limit: Int, descending: Boolean = false): List<ResponseView>
    /** Acepta «Usuario 012», «12» o «A001». */
    suspend fun findByLabel(accountId: String, formId: String, text: String): ResponseView?
    suspend fun response(accountId: String, formId: String, userNumber: Int): ResponseView
    fun userLabel(number: Int): String
}

interface ExportService {
    /** Nombre sugerido para el archivo («Encuesta - 2026-11-10.xlsx»). `format`: xlsx | pdf | png. */
    suspend fun suggestedName(accountId: String, formId: String, format: String, individual: Boolean = false): String
    /** Escribe en el flujo que abre la interfaz (SAF). Escritura atómica: primero a un temporal, recién al final se copia. */
    suspend fun exportXlsx(accountId: String, formId: String, request: ExportRequest, out: () -> OutputStream): ExportOutcome
    suspend fun exportPdf(accountId: String, formId: String, request: ExportRequest, out: () -> OutputStream): ExportOutcome
    /** Guarda los bytes de una imagen PNG que dibujó la interfaz. */
    suspend fun savePng(bytes: ByteArray, out: () -> OutputStream): ExportOutcome
    /** Datos para dibujar las fichas individuales como imagen (no escribe archivos). */
    suspend fun individualCards(accountId: String, formId: String, request: ExportRequest): Triple<String, String, List<ar.tallymonitor.export.ResponseCard>>
}

interface BackupService {
    suspend fun list(): List<BackupItem>
    suspend fun create(): BackupItem
    suspend fun restore(filename: String)
    suspend fun delete(filename: String)
}

interface SettingsService {
    /** Claves: theme (dark|light), auto_backup (1|0), sync_mode (manual|auto), log_level, update_check (1|0), notify_mode (off|on), notify_interval_min (15|30|60|360), notified_new_total (entero, lo usa el chequeo de avisos). */
    suspend fun get(key: String): String
    suspend fun set(key: String, value: String)
    fun observe(key: String): Flow<String>
}

interface DiagnosticsService {
    /** Solo conteos y estados: jamás claves, textos de respuestas ni nombres de cuentas o encuestas. */
    suspend fun snapshot(): Diagnostics
    suspend fun report(): String
}

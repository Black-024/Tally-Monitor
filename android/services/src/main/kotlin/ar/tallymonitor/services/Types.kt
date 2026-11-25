package ar.tallymonitor.services

import ar.tallymonitor.analysis.SurveyAnalysis
import java.time.LocalDate

/** Modelos que ve la interfaz. Inmutables; ninguno contiene la clave ni tipos de SQLite/HTTP. */
data class Account(val id: String, val name: String, val status: String, val lastCheckResult: String?, val lastCheckedAt: String?, val lastValidatedAt: String?)

/** result: ok | auth | forbidden | network | timeout | rate_limit | server | unexpected | no_credential */
data class VerifyResult(val account: Account, val result: String)

data class SurveySummary(val formId: String, val name: String, val status: String, val isClosed: Boolean, val reportedSubmissions: Int?, val localSubmissions: Int,
                         val lastSubmissionAt: String?, val lastSyncedAt: String?, val hasNewHint: Boolean, val isFavorite: Boolean, val neverSynced: Boolean,
                         /** Datos propios del usuario (spec 1.1 §1): meta de respuestas (null = sin meta), nota, etiquetas y si está archivada. */
                         val goal: Int? = null, val note: String = "", val tags: List<String> = emptyList(), val archived: Boolean = false)

data class QuestionView(val questionId: String, val position: Int, val type: String, val title: String, val options: List<String>, val hasOtherOption: Boolean, val isDeleted: Boolean)
data class SurveyDetail(val summary: SurveySummary, val questions: List<QuestionView>)

data class ChoiceView(val text: String, val origin: String)
data class AnswerView(val questionTitle: String, val kind: String, val text: String?, val isBlank: Boolean, val choices: List<ChoiceView>)
data class ResponseView(val number: Int, val label: String, val submittedAt: String, val isCompleted: Boolean, val answers: List<AnswerView>)

/** kind: all | 24h | 7d | 30d | custom. */
data class TimeFilterSpec(val kind: String = "all", val startDate: LocalDate? = null, val endDate: LocalDate? = null, val includeIncomplete: Boolean = true)

sealed class SyncEvent {
    data class Progress(val stage: String, val done: Int, val total: Int?) : SyncEvent()
    data class FormsDone(val count: Int, val unknownFields: List<String>) : SyncEvent()
    data class FormDone(val mode: String, val new: Int, val updated: Int, val missing: Int, val remoteTotal: Int?, val localTotal: Int, val warnings: List<String>, val unknownFields: List<String>) : SyncEvent()
}


data class BackupItem(val filename: String, val createdAtIso: String, val reason: String, val schemaVersion: Int, val sizeBytes: Long)

data class Diagnostics(val schemaVersion: Int, val dbHealthy: Boolean, val accounts: Int, val credentialsStored: Int, val credentialsMatchAccounts: Boolean,
                       val surveys: Int, val submissions: Int, val backupsByReason: Map<String, Int>, val settings: Map<String, String>, val lastErrors: List<String>)

/** Opciones de exportación que elige la interfaz (formatos: xlsx | pdf | png lo arma la UI). */
data class ExportRequest(val filter: TimeFilterSpec = TimeFilterSpec(), val includeText: Boolean = false, val maskPersonal: Boolean = true,
                         val individual: Boolean = false, val style: String = "dark", val onlyNumber: Int? = null)

data class ExportOutcome(val format: String, val responses: Int, val questions: Int, val textIncluded: Boolean, val masked: Boolean)

package ar.tallymonitor.testing

import ar.tallymonitor.analysis.*
import ar.tallymonitor.core.Secret
import ar.tallymonitor.core.TallyMonitorException
import ar.tallymonitor.core.ErrorCode
import ar.tallymonitor.export.ResponseCard
import ar.tallymonitor.services.*
import ar.tallymonitor.sync.Numbering
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.map
import java.io.OutputStream
import java.time.LocalDateTime

/**
 * Backend de ejemplo, todo en memoria (sin red, sin disco, sin Keystore). Sirve para desarrollar y probar la interfaz
 * (previews de Compose, pruebas de pantalla) sin depender del backend real. Los datos son inventados.
 */
class FakeTallyMonitorBackend : TallyMonitorBackend {
    private val accountsState = MutableStateFlow(listOf(Account("a1", "Cuenta de ejemplo", "active", "ok", "2026-03-01T10:00:00.000Z", "2026-03-01T10:00:00.000Z")))
    private val favorites = MutableStateFlow(setOf("f1"))
    private val survey0 = SurveySummary("f1", "Encuesta de satisfacción", "PUBLISHED", false, 60, 60, "2026-03-20T12:00:00.000Z", "2026-03-20T12:05:00.000Z", false, true, false)
    private val survey20 = SurveySummary("f2", "Inscripción al taller", "PUBLISHED", false, 12, 12, "2026-03-10T09:00:00.000Z", "2026-03-10T09:01:00.000Z", false, false, false)
    /** Meta, nota, etiquetas y archivada de cada encuesta de ejemplo (en memoria). */
    private val metas = MutableStateFlow(mapOf("f1" to Triple<Int?, String, List<String>>(100, "Encuesta de ejemplo", listOf("Taller")), "f2" to Triple<Int?, String, List<String>>(null, "", emptyList())))
    private val archived = MutableStateFlow(emptySet<String>())
    private fun withMeta(s: SurveySummary, m: Map<String, Triple<Int?, String, List<String>>>, a: Set<String>): SurveySummary =
        m[s.formId]?.let { s.copy(goal = it.first, note = it.second, tags = it.third, archived = s.formId in a) } ?: s.copy(archived = s.formId in a)
    private val survey get() = withMeta(survey0, metas.value, archived.value)
    private val survey2 get() = withMeta(survey20, metas.value, archived.value)
    private val questions = listOf(QuestionView("q1", 0, "MULTIPLE_CHOICE", "¿Cómo te enteraste?", listOf("Redes", "Amigos", "Otro"), false, false), QuestionView("q2", 1, "TEXTAREA", "Comentarios", emptyList(), false, false))

    private fun sample(): SurveyAnalysis {
        val opts = listOf(OptionStat("Redes", 30, 50.0), OptionStat("Amigos", 20, 33.3), OptionStat("Otro", 10, 16.7))
        val qs = listOf(QuestionStats("q1", 0, "MULTIPLE_CHOICE", "¿Cómo te enteraste?", "single", true, 60, 60, 0, 0, "", options = opts),
            QuestionStats("q2", 1, "TEXTAREA", "Comentarios", "text", true, 60, 55, 5, 0, "", avgLen = 42.0, maxLen = 120))
        val tl = Timeline("day", (1..7).map { TimeBucket(LocalDateTime.of(2026, 3, it, 0, 0), it * 2) }, 28)
        return SurveyAnalysis("f1", ResolvedFilter("all", null, null, "Todo el período"), true, "2026-03-20T12:00:00.000Z",
            Overview(60, 54, 6, "2026-03-01T10:00:00.000Z", "2026-03-20T12:00:00.000Z", 20, 3.0), qs, tl)
    }

    override val accounts = object : AccountService {
        override fun observeAccounts() = accountsState
        override suspend fun add(name: String, apiKey: Secret): Account { val a = Account("a${accountsState.value.size + 1}", name, "active", "ok", null, null); accountsState.value += a; return a }
        override suspend fun replaceKey(id: String, newKey: Secret) = true
        override suspend fun rename(id: String, name: String) { accountsState.value = accountsState.value.map { if (it.id == id) it.copy(name = name) else it } }
        override suspend fun remove(id: String) { accountsState.value = accountsState.value.filter { it.id != id } }
        override suspend fun verify(id: String) = VerifyResult(accountsState.value.first { it.id == id }, "ok")
    }
    override val surveys = object : SurveyService {
        override fun observeSurveys(accountId: String, query: String?, onlyFavorites: Boolean, tag: String?, includeArchived: Boolean): Flow<List<SurveySummary>> =
            combine(favorites, metas, archived) { favs, m, a ->
                listOf(survey0, survey20).map { withMeta(it, m, a).copy(isFavorite = it.formId in favs) }.filter { s ->
                    (includeArchived || !s.archived) && (!onlyFavorites || s.isFavorite) && (tag == null || s.tags.any { it.equals(tag, true) }) &&
                        (query.isNullOrBlank() || s.name.contains(query, true) || s.note.contains(query, true) || s.tags.any { it.contains(query, true) })
                }
            }
        override suspend fun survey(accountId: String, formId: String) = SurveyDetail(listOf(survey, survey2).first { it.formId == formId }, questions)
        override suspend fun setFavorite(accountId: String, formId: String, on: Boolean) { favorites.value = if (on) favorites.value + formId else favorites.value - formId }
        override suspend fun markOpened(accountId: String, formId: String) {}
        override suspend fun setSurveyMeta(accountId: String, formId: String, goal: Int?, note: String, tags: List<String>) {
            val c = SurveyMetaRules.clean(goal, note, tags); metas.value = metas.value + (formId to Triple(c.goal, c.note, c.tags))
        }
        override suspend fun setArchived(accountId: String, formId: String, archived: Boolean) { this@FakeTallyMonitorBackend.archived.value = if (archived) this@FakeTallyMonitorBackend.archived.value + formId else this@FakeTallyMonitorBackend.archived.value - formId }
        override fun observeRecents(accountId: String, limit: Int) = observeSurveys(accountId, null, false)
    }
    override val sync = object : SyncService {
        override fun syncForms(accountId: String): Flow<SyncEvent> = flow { emit(SyncEvent.Progress("encuestas", 1, 2)); emit(SyncEvent.FormsDone(2, emptyList())) }
        override fun syncForm(accountId: String, formId: String, full: Boolean): Flow<SyncEvent> = flow { emit(SyncEvent.Progress("respuestas", 30, 60)); emit(SyncEvent.FormDone("incremental", 5, 0, 0, 60, 60, emptyList(), emptyList())) }
    }
    private fun response(n: Int) = ResponseView(n, Numbering.formatUserLabel(n), "2026-03-%02dT10:00:00.000Z".format(1 + n % 20), n % 7 != 0,
        listOf(AnswerView("¿Cómo te enteraste?", "single", null, false, listOf(ChoiceView(if (n % 2 == 0) "Redes" else "Amigos", "declared"))), AnswerView("Comentarios", "text", "Comentario de ejemplo $n", false, emptyList())))
    override val analysis = object : AnalysisService {
        override suspend fun analyze(accountId: String, formId: String, filter: TimeFilterSpec, answerFilter: AnswerFilter?): SurveyAnalysis {
            val base = sample()
            val t = trends(listOf(SubmissionPoint(1, "2026-03-19T18:00:00.000Z", true), SubmissionPoint(2, "2026-03-18T10:00:00.000Z", false)), java.time.Instant.parse("2026-03-20T12:00:00Z"), java.time.ZoneOffset.UTC)
            return base.copy(trends = t, answerFilter = answerFilter?.let { AnswerFilterResult(it, 30, 60) })
        }
        override suspend fun recentCounts(accountId: String): Map<String, Int> = mapOf("f1" to 14, "f2" to 3)
        override suspend fun crosscheck(accountId: String, formId: String, includeIncomplete: Boolean) = emptyList<String>()
        override suspend fun responses(accountId: String, formId: String, offset: Int, limit: Int, descending: Boolean) =
            (1..60).toList().let { if (descending) it.reversed() else it }.drop(offset).take(limit).map(::response)
        override suspend fun findByLabel(accountId: String, formId: String, text: String) = Numbering.parseUserLabel(text)?.takeIf { it in 1..60 }?.let(::response)
        override suspend fun response(accountId: String, formId: String, userNumber: Int) = response(userNumber)
        override fun userLabel(number: Int) = Numbering.formatUserLabel(number)
    }
    override val export = object : ExportService {
        override suspend fun suggestedName(accountId: String, formId: String, format: String, individual: Boolean) = "Encuesta de ejemplo.$format"
        override suspend fun exportXlsx(accountId: String, formId: String, request: ExportRequest, out: () -> OutputStream) = ExportOutcome("xlsx", 60, 2, request.includeText, request.maskPersonal)
        override suspend fun exportPdf(accountId: String, formId: String, request: ExportRequest, out: () -> OutputStream) = ExportOutcome("pdf", 60, 2, request.includeText, request.maskPersonal)
        override suspend fun savePng(bytes: ByteArray, out: () -> OutputStream) = ExportOutcome("png", 0, 0, false, false)
        override suspend fun individualCards(accountId: String, formId: String, request: ExportRequest): Triple<String, String, List<ResponseCard>> = Triple("Encuesta de ejemplo", "Todo el período", emptyList())
    }
    override val backups = object : BackupService {
        override suspend fun list() = emptyList<BackupItem>()
        override suspend fun create() = BackupItem("library_20260301_100000_manual_v3.db", "2026-03-01T10:00:00.000Z", "manual", 3, 1024)
        override suspend fun restore(filename: String) {}
        override suspend fun delete(filename: String) {}
    }
    private val prefs = MutableStateFlow(mapOf("theme" to "dark", "auto_backup" to "1", "sync_mode" to "manual", "log_level" to "INFO", "update_check" to "0",
        "notify_mode" to "off", "notify_interval_min" to "60", "notified_new_total" to "0"))
    override val settings = object : SettingsService {
        override suspend fun get(key: String) = prefs.value[key] ?: throw TallyMonitorException(ErrorCode.INTERNAL)
        override suspend fun set(key: String, value: String) { prefs.value = prefs.value + (key to value) }
        override fun observe(key: String) = prefs.map { it[key] ?: "" }
    }
    override val diagnostics = object : DiagnosticsService {
        override suspend fun snapshot() = Diagnostics(3, true, 1, 1, true, 2, 60, emptyMap(), prefs.value, emptyList())
        override suspend fun report() = "Tally Monitor (datos de ejemplo)"
    }
}

package ar.tallymonitor.services

import ar.tallymonitor.analysis.AnswerFilter
import ar.tallymonitor.analysis.AnswerFilterResult
import ar.tallymonitor.analysis.AnswerFilters
import ar.tallymonitor.analysis.Crosscheck
import ar.tallymonitor.analysis.Stats
import ar.tallymonitor.analysis.SurveyAnalysis
import ar.tallymonitor.analysis.TimeFilter
import ar.tallymonitor.analysis.trends
import ar.tallymonitor.api.BASE_URL
import ar.tallymonitor.api.TallyClient
import ar.tallymonitor.core.*
import ar.tallymonitor.credentials.Credential
import ar.tallymonitor.credentials.CredentialProtector
import ar.tallymonitor.credentials.CredentialStore
import ar.tallymonitor.export.*
import ar.tallymonitor.storage.*
import ar.tallymonitor.sync.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.channels.trySendBlocking
import kotlinx.coroutines.withContext
import java.io.File
import java.io.OutputStream
import java.time.ZoneId
import java.time.Instant
import kotlin.coroutines.coroutineContext

class BackendPaths(val dataDir: File, val credentialsFile: File, val backupsDir: File, val cacheDir: File)

/** Entrega el logo ya decodificado para el PDF (la plataforma decodifica el PNG). */
fun interface LogoProvider { fun logo(style: String): PdfImage? }

private const val MAX_NAME = 60

/** Implementación real: une almacenamiento, credenciales cifradas, red, motor de sincronización, análisis y exportación. */
class RealBackend(
    private val paths: BackendPaths, protector: CredentialProtector, private val logos: LogoProvider, private val appVersion: String,
    baseUrl: String = BASE_URL, private val clock: Clock = Clock.SYSTEM, private val zone: () -> ZoneId = { ZoneId.systemDefault() },
    private val sleep: (Long) -> Unit = { Thread.sleep(it) },
) : TallyMonitorBackend {

    // ---- capas ----
    private val db = Db(File(paths.dataDir, "library.db"))
    private val store = CredentialStore(paths.credentialsFile, protector)
    private val client = TallyClient(baseUrl, minIntervalMs = 650, sleep = sleep)          // ~92 solicitudes/min: bajo el límite de 100
    private val backupMgr = BackupManager(db, paths.backupsDir, clock)
    private val accountsRepo = AccountsRepository(db, clock)
    private val surveysRepo = SurveysRepository(db, SANITIZER_VERSION, clock)
    private val subsRepo = SubmissionsRepository(db, SANITIZER_VERSION, clock)
    private val stateRepo = StateRepository(db, clock)
    private val settingsRepo = SettingsRepository(db, clock)
    private val metaRepo = SurveyMetaRepository(db)
    private val analytics = AnalyticsRepository(db)
    private val engine = SyncEngine(object : RemoteSource {
        override fun listForms(key: Secret, page: Int) = client.listForms(key, page)
        override fun getForm(key: Secret, formId: String) = client.getForm(key, formId)
        override fun getQuestions(key: Secret, formId: String) = client.getQuestions(key, formId)
        override fun listSubmissions(key: Secret, formId: String, page: Int, limit: Int, startDate: String?) = client.listSubmissions(key, formId, page, limit, startDate)
    }, SqliteSyncStore(surveysRepo, subsRepo, stateRepo), beforeReconcile = { runCatching { backupMgr.create("pre_reconciliacion"); backupMgr.applyRetention() } })

    /** Se incrementa con cada cambio: los Flow de observación vuelven a leer. */
    private val changes = MutableStateFlow(0)
    private fun changed() { changes.value++ }
    private suspend fun <T> io(block: () -> T): T = withContext(Dispatchers.IO) { block() }

    private val migrations = MigrationSql.load("library", listOf("0001_initial.sql", "0002_surveys.sql", "0003_survey_meta.sql"))
    private val preMigrationBackup: (Int, Int) -> Unit = { _, _ -> backupMgr.create("pre_migracion") }

    /** Aplica las migraciones pendientes. Tras restaurar una copia vieja (sin las tablas nuevas) se corre sin copia previa: ya existe la de «pre_restauracion». */
    private fun runMigrations(backupFirst: Boolean) {
        MigrationRunner(db, migrations, appVersion, clock, if (backupFirst) preMigrationBackup else null).migrate()
    }

    init {
        paths.dataDir.mkdirs(); paths.cacheDir.mkdirs()
        try {
            runMigrations(true)
        } catch (e: TallyMonitorException) {
            if (e.code == ErrorCode.MIGRATION_FAILED) backupMgr.list().firstOrNull { it.reason == "pre_migracion" }?.let { runCatching { backupMgr.restore(it.filename, migrations.size) } }
            throw e
        }
        runCatching { reconcileCredentials() }
        runCatching { autoBackupIfDue() }
    }

    private fun autoBackupIfDue() {
        if (settingsRepo.get("auto_backup") != "1") return
        val last = backupMgr.list().firstOrNull { it.reason == "auto" }
        if (last == null || clock.nowMillis() - last.createdAt.toEpochMilli() > 24 * 3600_000L) { backupMgr.create("auto"); backupMgr.applyRetention() }
    }

    /** Claves sin cuenta → se eliminan. Cuentas sin clave legible → «Sin credencial». */
    private fun reconcileCredentials() {
        val accs = accountsRepo.list()
        store.purgeOrphans(accs.map { it.accountId }.toSet())
        for (a in accs) {
            val ok = try { store.load(a.accountId) != null } catch (e: TallyMonitorException) { false }
            if (!ok && a.status != "no_credential") accountsRepo.setStatus(a.accountId, "no_credential")
        }
    }

    private fun toAccount(a: AccountRecord) = Account(a.accountId, a.name, a.status, a.lastCheckResult, a.lastCheckedAt, a.lastValidatedAt)
    private fun keyOf(accountId: String): Secret = (try { store.load(accountId) } catch (e: TallyMonitorException) { null })?.apiKey ?: throw TallyMonitorException(ErrorCode.CREDENTIAL_UNREADABLE)

    private fun category(e: ApiException): Pair<String, String> = when (e.code) {                // (resultado guardado, estado de la cuenta)
        ErrorCode.KEY_REJECTED, ErrorCode.FORBIDDEN -> "auth" to "key_rejected"
        ErrorCode.NETWORK, ErrorCode.TIMEOUT -> "network" to "check_failed"
        ErrorCode.RATE_LIMITED -> "rate_limit" to "check_failed"
        ErrorCode.SERVER_ERROR -> "server" to "check_failed"
        else -> "unexpected" to "check_failed"
    }

    // ================= cuentas =================
    override val accounts = object : AccountService {
        override fun observeAccounts(): Flow<List<Account>> = changes.map { io { accountsRepo.list().map(::toAccount) } }

        private fun cleanName(n: String): String { val t = n.trim(); if (t.length !in 1..MAX_NAME) throw TallyMonitorException(ErrorCode.INVALID_ID); return t }
        private fun checkShape(k: Secret) { if (!k.hasTallyKeyShape()) throw TallyMonitorException(ErrorCode.INVALID_KEY_FORMAT) }
        private fun checkDuplicate(k: Secret, exclude: String?) { if (store.all().any { (id, c) -> id != exclude && c.apiKey == k }) throw TallyMonitorException(ErrorCode.ALREADY_EXISTS) }

        override suspend fun add(name: String, apiKey: Secret): Account = io {
            val n = cleanName(name); checkShape(apiKey)
            if (accountsRepo.nameExists(n)) throw TallyMonitorException(ErrorCode.ALREADY_EXISTS)
            checkDuplicate(apiKey, null)
            val user = client.getCurrentUser(apiKey)                                    // puede lanzar ApiException
            val acc = accountsRepo.add(n, status = "active", lastCheckResult = "ok", validated = true)
            try { store.save(acc.accountId, Credential(apiKey, user.tallyUserId)) } catch (e: Exception) { accountsRepo.delete(acc.accountId); throw e }
            changed(); toAccount(acc)
        }

        override suspend fun replaceKey(id: String, newKey: Secret): Boolean = io {
            accountsRepo.get(id); checkShape(newKey); checkDuplicate(newKey, id)
            val old = try { store.load(id) } catch (e: TallyMonitorException) { null }
            val user = client.getCurrentUser(newKey)                                    // si falla, no se toca nada
            var verified = false
            val oldId = old?.tallyUserId
            val newId = user.tallyUserId
            if (oldId != null && newId != null) {
                if (oldId != newId) throw TallyMonitorException(ErrorCode.ACCOUNT_MISMATCH)
                verified = true
            }
            store.save(id, Credential(newKey, user.tallyUserId ?: old?.tallyUserId))
            accountsRepo.setCheck(id, "active", "ok"); changed(); verified
        }

        override suspend fun rename(id: String, name: String) { io { accountsRepo.rename(id, cleanName(name)); changed() } }

        override suspend fun remove(id: String) { io { accountsRepo.get(id); store.delete(id); accountsRepo.delete(id); changed() } }

        override suspend fun verify(id: String): VerifyResult = io {
            accountsRepo.get(id)
            val cred = try { store.load(id) } catch (e: TallyMonitorException) { null }
            if (cred == null) { val a = accountsRepo.setStatus(id, "no_credential"); changed(); return@io VerifyResult(toAccount(a), "no_credential") }
            try {
                val user = client.getCurrentUser(cred.apiKey)
                if (cred.tallyUserId == null && user.tallyUserId != null) store.save(id, Credential(cred.apiKey, user.tallyUserId))
                val a = accountsRepo.setCheck(id, "active", "ok"); changed(); VerifyResult(toAccount(a), "ok")
            } catch (e: ApiException) {
                val (res, status) = category(e)
                val a = accountsRepo.setCheck(id, status, res); changed()
                VerifyResult(toAccount(a), if (e.code == ErrorCode.FORBIDDEN) "forbidden" else if (e.code == ErrorCode.TIMEOUT) "timeout" else res)
            }
        }
    }

    // ================= encuestas =================
    private fun summary(f: FormRecord, favs: Set<String>, meta: SurveyMetaRecord?): SurveySummary {
        val reported = f.reportedSubmissions
        val local = f.localSubmissions
        return SurveySummary(f.formId, f.name, f.status, f.isClosed, reported, local, f.lastSubmissionAt, f.lastSyncedAt,
            reported != null && reported > local, f.formId in favs, f.lastSyncedAt == null,
            meta?.goal, meta?.note ?: "", meta?.tags ?: emptyList(), meta?.archived ?: false)
    }

    override val surveys = object : SurveyService {
        override fun observeSurveys(accountId: String, query: String?, onlyFavorites: Boolean, tag: String?, includeArchived: Boolean): Flow<List<SurveySummary>> = changes.map {
            io {
                val favs = stateRepo.favorites(accountId); val q = query?.trim()?.lowercase().orEmpty(); val metas = metaRepo.all(accountId)
                surveysRepo.listForms(accountId).map { summary(it, favs, metas[it.formId]) }.filter { s ->
                    (includeArchived || !s.archived) && (!onlyFavorites || s.isFavorite) && (tag == null || s.tags.any { it.equals(tag, ignoreCase = true) }) &&
                        (q.isEmpty() || s.name.lowercase().contains(q) || s.note.lowercase().contains(q) || s.tags.any { it.lowercase().contains(q) })
                }
            }
        }
        override suspend fun survey(accountId: String, formId: String): SurveyDetail = io {
            val f = surveysRepo.getForm(accountId, formId) ?: throw TallyMonitorException(ErrorCode.NOT_FOUND_LOCAL)
            SurveyDetail(summary(f, stateRepo.favorites(accountId), metaRepo.get(accountId, formId)), surveysRepo.getQuestions(accountId, formId).map { QuestionView(it.questionId, it.position, it.type, it.title, it.options, it.hasOtherOption, it.isDeleted) })
        }
        override suspend fun setFavorite(accountId: String, formId: String, on: Boolean) { io { stateRepo.setFavorite(accountId, formId, on); changed() } }
        override suspend fun markOpened(accountId: String, formId: String) { io { stateRepo.touchRecent(accountId, formId); changed() } }
        override suspend fun setSurveyMeta(accountId: String, formId: String, goal: Int?, note: String, tags: List<String>) {
            io {
                val clean = SurveyMetaRules.clean(goal, note, tags)                     // valida todo ANTES de escribir
                if (surveysRepo.getForm(accountId, formId) == null) throw TallyMonitorException(ErrorCode.NOT_FOUND_LOCAL)
                metaRepo.save(accountId, formId, clean.goal, clean.note, clean.tags); changed()
            }
        }
        override suspend fun setArchived(accountId: String, formId: String, archived: Boolean) {
            io {
                if (surveysRepo.getForm(accountId, formId) == null) throw TallyMonitorException(ErrorCode.NOT_FOUND_LOCAL)
                metaRepo.setArchived(accountId, formId, archived); changed()
            }
        }
        override fun observeRecents(accountId: String, limit: Int): Flow<List<SurveySummary>> = changes.map {
            io {
                val favs = stateRepo.favorites(accountId); val byId = surveysRepo.listForms(accountId).associateBy { it.formId }; val metas = metaRepo.all(accountId)
                stateRepo.recents(accountId).mapNotNull { byId[it] }.take(limit).map { summary(it, favs, metas[it.formId]) }.filter { !it.archived }
            }
        }
    }

    // ================= sincronización =================
    override val sync = object : SyncService {
        override fun syncForms(accountId: String): Flow<SyncEvent> = channelFlowIo { send, cancelled ->
            val r = engine.syncForms(accountId, keyOf(accountId), cancelled) { s, d, t -> send(SyncEvent.Progress(s, d, t)) }
            changed(); send(SyncEvent.FormsDone(r.count, r.unknownFields))
        }
        override fun syncForm(accountId: String, formId: String, full: Boolean): Flow<SyncEvent> = channelFlowIo { send, cancelled ->
            try {
                val r = engine.syncForm(accountId, formId, keyOf(accountId), full, cancelled) { s, d, t -> send(SyncEvent.Progress(s, d, t)) }
                send(SyncEvent.FormDone(r.mode, r.new, r.updated, r.missing, r.remoteTotal, r.localTotal, r.warnings, r.unknownFields))
            } finally { changed() }
        }
    }

    /** Corre un bloque bloqueante en IO y lo conecta a un Flow; cancelar el Flow detiene la sincronización a la siguiente página. */
    private fun channelFlowIo(block: (send: (SyncEvent) -> Unit, cancelled: () -> Boolean) -> Unit): Flow<SyncEvent> = kotlinx.coroutines.flow.channelFlow {
        val job = coroutineContext[Job]
        withContext(Dispatchers.IO) { block({ trySendBlocking(it) }, { job?.isActive == false }) }
    }

    // ================= análisis =================
    private fun resolve(f: TimeFilterSpec) = TimeFilter.resolve(f.kind, Instant.ofEpochMilli(clock.nowMillis()), zone(), f.startDate, f.endDate)

    private fun viewOf(rec: SubmissionRecord, titles: Map<String, String>) = ResponseView(rec.number ?: 0, if (rec.number != null) Numbering.formatUserLabel(rec.number!!) else "Usuario ?", rec.submittedAt, rec.isCompleted,
        rec.answers.map { AnswerView(titles[it.questionId] ?: "(pregunta eliminada)", it.kind, it.textValue, it.isBlank, it.choices.map { c -> ChoiceView(c.first, c.second) }) })

    private fun analyzeBlocking(acc: String, form: String, f: TimeFilterSpec, answerFilter: AnswerFilter? = null): SurveyAnalysis {
        if (surveysRepo.getForm(acc, form) == null) throw TallyMonitorException(ErrorCode.NOT_FOUND_LOCAL)
        val now = Instant.ofEpochMilli(clock.nowMillis()); val tz = zone()
        val flt = TimeFilter.resolve(f.kind, now, tz, f.startDate, f.endDate)
        val (periodSubs, periodAnswers, questions) = analytics.load(acc, form, flt.startIso, flt.endIso, f.includeIncomplete)
        // Cruce de preguntas: se conservan solo los envíos que eligieron esa opción; todo lo demás se calcula sobre ese subconjunto.
        val keys: Set<Int>? = if (answerFilter == null) null else {
            val q = questions.firstOrNull { it.questionId == answerFilter.questionId }
            if (q == null || !AnswerFilters.isOptionQuestion(q)) throw TallyMonitorException(ErrorCode.INVALID_FILTER)
            AnswerFilters.matchingKeys(answerFilter, analytics.choicesFor(acc, form, answerFilter.questionId))
        }
        val subs = if (keys == null) periodSubs else periodSubs.filter { it.key in keys }
        val answers = if (keys == null) periodAnswers else periodAnswers.filter { it.key in keys }
        val filterResult = if (answerFilter == null) null else AnswerFilterResult(answerFilter, subs.size, periodSubs.size)
        val qstats = Stats.allQuestionStats(questions, answers, subs.size)
        val tl = if (f.kind == "24h") Stats.timeline(subs, tz, now.minusSeconds(24 * 3600), now) else Stats.timeline(subs, tz)
        val warnings = ArrayList<String>()
        if (qstats.any { it.notAsked > 0 && !it.isDeleted }) warnings += "preguntas_agregadas_despues"
        if (qstats.any { !it.interpreted }) warnings += "tipos_no_interpretados"
        // Ritmo: día/hora/finalización del período elegido; últimos 7 días contra los 7 anteriores con TODOS los envíos guardados.
        val allPoints = analytics.points(acc, form).let { p -> if (keys == null) p else p.filter { it.key in keys } }
        val rhythm = trends(subs, now, tz).withRecentFrom(trends(allPoints, now, tz))
        return SurveyAnalysis(form, flt, f.includeIncomplete, clock.nowIso(), Stats.overview(subs, tz), qstats, tl, warnings, rhythm, filterResult)
    }

    override val analysis = object : AnalysisService {
        override suspend fun analyze(accountId: String, formId: String, filter: TimeFilterSpec, answerFilter: AnswerFilter?): SurveyAnalysis = io { analyzeBlocking(accountId, formId, filter, answerFilter) }

        override suspend fun recentCounts(accountId: String): Map<String, Int> = io {
            val now = clock.nowMillis()
            analytics.countsBetween(accountId, Iso.format(now - 7L * 24 * 3600_000L), Iso.format(now))
        }

        override suspend fun crosscheck(accountId: String, formId: String, includeIncomplete: Boolean): List<String> = io {
            val r = analyzeBlocking(accountId, formId, TimeFilterSpec("all", includeIncomplete = includeIncomplete))
            val (_, qraw) = surveysRepo.rawStructure(accountId, formId)
            val raw = analytics.rawPresent(accountId, formId, includeIncomplete)
            Crosscheck.compare(r.questions, Crosscheck.rawCounts(qraw, raw), r.overview.total, r.overview.completed, raw.size, raw.count { Normalizer.truthy(it["isCompleted"]) })
        }

        private fun titles(acc: String, form: String) = surveysRepo.getQuestions(acc, form).associate { it.questionId to it.title }

        override suspend fun responses(accountId: String, formId: String, offset: Int, limit: Int, descending: Boolean): List<ResponseView> = io {
            val t = titles(accountId, formId); subsRepo.listPage(accountId, formId, offset, limit, descending).map { viewOf(it, t) }
        }
        override suspend fun findByLabel(accountId: String, formId: String, text: String): ResponseView? = io {
            val n = Numbering.parseUserLabel(text) ?: return@io null
            subsRepo.getByNumber(accountId, formId, n)?.let { viewOf(it, titles(accountId, formId)) }
        }
        override suspend fun response(accountId: String, formId: String, userNumber: Int): ResponseView = io {
            viewOf(subsRepo.getByNumber(accountId, formId, userNumber) ?: throw TallyMonitorException(ErrorCode.NOT_FOUND_LOCAL), titles(accountId, formId))
        }
        override fun userLabel(number: Int) = Numbering.formatUserLabel(number)
    }

    // ================= exportación =================
    private fun safeFilename(name: String): String = name.map { if (it in "<>:\"/\\|?*" || it.code < 32) '_' else it }.joinToString("").trim(' ', '.').take(80).ifEmpty { "encuesta" }

    private fun options(r: ExportRequest) = ExportOptions(r.filter.kind, r.filter.startDate, r.filter.endDate, r.filter.includeIncomplete, r.includeText, r.maskPersonal,
        if (r.individual) "individual" else "summary", r.style, r.onlyNumber)

    private class Prepared(val name: String, val analysis: SurveyAnalysis, val rows: List<ar.tallymonitor.analysis.ResponseRow>, val tz: ZoneId, val opts: ExportOptions)

    private fun prepare(acc: String, form: String, req: ExportRequest): Prepared {
        val f = surveysRepo.getForm(acc, form) ?: throw TallyMonitorException(ErrorCode.NOT_FOUND_LOCAL)
        val a = analyzeBlocking(acc, form, req.filter)
        val rows = analytics.exportRows(acc, form, a.filter.startIso, a.filter.endIso, req.filter.includeIncomplete, req.includeText, if (req.individual) req.onlyNumber else null)
        if (req.individual && req.onlyNumber != null && rows.isEmpty()) throw TallyMonitorException(ErrorCode.NOT_FOUND_LOCAL)
        return Prepared(f.name, a, rows, zone(), options(req))
    }

    /** Escribe a un temporal en la caché y, al terminar bien, copia al destino: nunca queda un archivo a medias. */
    private fun atomic(out: () -> OutputStream, suffix: String, write: (OutputStream) -> Unit) {
        val tmp = File.createTempFile("tally-", suffix, paths.cacheDir)
        try {
            tmp.outputStream().use { write(it) }
            out().use { o -> tmp.inputStream().use { it.copyTo(o) }; o.flush() }
        } catch (e: TallyMonitorException) { throw e
        } catch (e: java.io.IOException) { throw TallyMonitorException(ErrorCode.EXPORT_FAILED, cause = e)
        } finally { tmp.delete() }
    }

    override val export = object : ExportService {
        override suspend fun suggestedName(accountId: String, formId: String, format: String, individual: Boolean): String = io {
            val base = safeFilename(surveysRepo.getForm(accountId, formId)?.name ?: "")
            val date = Instant.ofEpochMilli(clock.nowMillis()).atZone(zone()).toLocalDate()
            "$base${if (individual) " - respuestas" else ""} - $date.$format"
        }
        override suspend fun exportXlsx(accountId: String, formId: String, request: ExportRequest, out: () -> OutputStream): ExportOutcome = io {
            val p = prepare(accountId, formId, request)
            val now = Instant.ofEpochMilli(clock.nowMillis()).atZone(p.tz).toLocalDateTime()
            atomic(out, ".xlsx") { XlsxExport.write(it, p.name, p.analysis, p.rows, Numbering::formatUserLabel, p.tz, p.opts, now, CancelCheck { false }) }
            ExportOutcome("xlsx", p.rows.size, p.analysis.questions.size, request.includeText, request.includeText && request.maskPersonal)
        }
        override suspend fun exportPdf(accountId: String, formId: String, request: ExportRequest, out: () -> OutputStream): ExportOutcome {
          val job = coroutineContext[Job]
          return io {
            val p = prepare(accountId, formId, request)
            val now = Instant.ofEpochMilli(clock.nowMillis()).atZone(p.tz).toLocalDateTime()
            atomic(out, ".pdf") { PdfExport.write(it, p.name, p.analysis, p.rows, Numbering::formatUserLabel, p.tz, p.opts, now, logos.logo(request.style), CancelCheck { job?.isActive == false }) }
            ExportOutcome("pdf", p.rows.size, p.analysis.questions.size, request.includeText, request.includeText && request.maskPersonal)
          }
        }
        override suspend fun savePng(bytes: ByteArray, out: () -> OutputStream): ExportOutcome = io {
            atomic(out, ".png") { it.write(bytes) }; ExportOutcome("png", 0, 0, false, false)
        }
        override suspend fun individualCards(accountId: String, formId: String, request: ExportRequest) = io {
            val p = prepare(accountId, formId, request.copy(individual = true))
            Triple(p.name, p.analysis.filter.label, Individual.build(p.analysis, p.rows, p.tz, Numbering::formatUserLabel, request.includeText, request.maskPersonal))
        }
    }

    // ================= copias de seguridad =================
    private fun item(b: BackupInfo) = BackupItem(b.filename, Iso.format(b.createdAt.toEpochMilli()), b.reason, b.schemaVersion, b.sizeBytes)

    override val backups = object : BackupService {
        override suspend fun list() = io { backupMgr.list().map(::item) }
        override suspend fun create() = io { item(backupMgr.create("manual")).also { backupMgr.applyRetention() } }
        override suspend fun restore(filename: String) { io { backupMgr.restore(filename, migrations.size) { runMigrations(false); reconcileCredentials() }; changed() } }
        override suspend fun delete(filename: String) { io { backupMgr.delete(filename) } }
    }

    // ================= ajustes =================
    override val settings = object : SettingsService {
        override suspend fun get(key: String) = io { settingsRepo.get(key) }
        override suspend fun set(key: String, value: String) { io { settingsRepo.set(key, value); changed() } }
        override fun observe(key: String): Flow<String> = changes.map { io { settingsRepo.get(key) } }.distinctUntilChanged()
    }

    // ================= diagnóstico =================
    override val diagnostics = object : DiagnosticsService {
        override suspend fun snapshot(): Diagnostics = io {
            val ids = accountsRepo.list().map { it.accountId }.toSet()
            Diagnostics(db.userVersion, db.quickCheck().isEmpty(), ids.size, store.ids().size, store.ids() == ids, analytics.count("data_form"), analytics.count("data_submission"),
                backupMgr.list().groupingBy { it.reason }.eachCount(), listOf("log_level", "auto_backup", "sync_mode", "theme", "notify_mode", "notify_interval_min").associateWith { settingsRepo.get(it) }, analytics.lastErrors())
        }
        override suspend fun report(): String {
            val s = try { snapshot() } catch (e: Exception) { null }
            return buildString {
                appendLine("Tally Monitor $appVersion (Android)")
                if (s == null) appendLine("No se pudo leer el estado de la base de datos.") else {
                    appendLine("Esquema v${s.schemaVersion} · base ${if (s.dbHealthy) "sana" else "CON PROBLEMAS"}")
                    appendLine("Cuentas: ${s.accounts} · credenciales: ${s.credentialsStored} (${if (s.credentialsMatchAccounts) "coinciden" else "NO coinciden"})")
                    appendLine("Encuestas: ${s.surveys} · respuestas: ${s.submissions}")
                    appendLine("Copias: ${s.backupsByReason}")
                    appendLine("Ajustes: ${s.settings}")
                    appendLine("Errores de sincronización: ${s.lastErrors.ifEmpty { listOf("ninguno") }}")
                }
            }
        }
    }
}

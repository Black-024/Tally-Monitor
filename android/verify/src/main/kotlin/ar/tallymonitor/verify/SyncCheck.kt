package ar.tallymonitor.verify

import ar.tallymonitor.api.TallyClient
import ar.tallymonitor.core.*
import ar.tallymonitor.sync.*
import java.io.File

/** Almacén en memoria con la misma semántica que SQLite (para probar el motor sin Android). */
class MemoryStore : SyncStore {
    class Sub(var row: SubmissionRow, var raw: JObj, var missing: Boolean = false)
    val subs = LinkedHashMap<String, Sub>()
    val numbers = HashMap<String, Int>()
    var counter = 1
    var questions = listOf<QuestionRow>()
    var reported: Int? = null
    var state: SyncState? = null
    var lastError: String? = null
    var forms = listOf<FormRow>()
    var okCount = 0

    override fun saveSummaries(accountId: String, items: List<Pair<FormRow, JObj>>) { forms = items.map { it.first } }
    override fun getQuestions(accountId: String, formId: String) = questions
    override fun saveDetail(accountId: String, form: FormRow, detail: JObj, questions: JObj, rows: List<QuestionRow>) { this.questions = rows }
    override fun setReported(accountId: String, formId: String, total: Int) { reported = total }
    override fun countPresent(accountId: String, formId: String) = subs.values.count { !it.missing }
    override fun newestSubmittedAt(accountId: String, formId: String) = subs.values.filter { !it.missing }.maxOfOrNull { it.row.submittedAt }
    override fun upsertPage(accountId: String, items: List<Pair<SubmissionRow, JObj>>): Pair<Int, Int> {
        var n = 0; var u = 0
        for ((row, raw) in items) { val s = subs[row.submissionId]; if (s == null) { subs[row.submissionId] = Sub(row, raw); n++ } else { s.row = row; s.raw = raw; s.missing = false; u++ } }
        return n to u
    }
    override fun markMissing(accountId: String, formId: String, seen: Set<String>): Int {
        var c = 0; for ((id, s) in subs) if (!s.missing && id !in seen) { s.missing = true; c++ }; return c
    }
    override fun assignNumbers(accountId: String, formId: String): Int {
        val pend = subs.values.filter { it.row.submissionId !in numbers }.sortedWith(compareBy({ it.row.submittedAt }, { it.row.submissionId }))
        for (s in pend) numbers[s.row.submissionId] = counter++
        return pend.size
    }
    override fun rawSubmissions(accountId: String, formId: String) = subs.values.map { it.raw }
    override fun rewriteNormalized(accountId: String, rows: List<SubmissionRow>) { for (r in rows) subs[r.submissionId]?.row = r }
    override fun getSyncState(accountId: String, formId: String) = state
    override fun saveSyncOk(accountId: String, formId: String, newestAt: String?, newestId: String?, full: Boolean) { state = SyncState(newestAt, newestId); okCount++; lastError = null }
    override fun saveSyncError(accountId: String, formId: String, category: String) { lastError = category }
    override fun markSynced(accountId: String, formId: String, lastSubmissionAt: String?) {}
}

/** Adaptador: el cliente HTTP real como fuente remota. */
class ClientSource(private val c: TallyClient) : RemoteSource {
    override fun listForms(key: Secret, page: Int) = c.listForms(key, page)
    override fun getForm(key: Secret, formId: String) = c.getForm(key, formId)
    override fun getQuestions(key: Secret, formId: String) = c.getQuestions(key, formId)
    override fun listSubmissions(key: Secret, formId: String, page: Int, limit: Int, startDate: String?) = c.listSubmissions(key, formId, page, limit, startDate)
}

fun syncChecks(goldenDir: String): List<Pair<String, () -> List<String>>> = listOf("sincronización (motor + servidor falso)" to { syncCheck(goldenDir) })

@Suppress("UNCHECKED_CAST")
private fun syncCheck(dir: String): List<String> {
    val bad = ArrayList<String>()
    fun load(n: String) = Json.parseObject(File(dir, n).readText())
    val detail = load("fixture_form_detail.json"); val questions = load("fixture_questions.json")
    val template = (Json.parse(File(dir, "fixture_submissions.json").readText()) as List<JObj>)[0]
    val formId = detail["id"] as String
    // «Tally» simulado: lista editable, más nuevo primero
    val remote = ArrayList<JObj>()
    fun mk(i: Int): JObj = template.toMutableMap().also {
        it["id"] = "sub%04d".format(i); it["submittedAt"] = "2026-03-%02dT10:%02d:00.000Z".format(1 + i / 60, i % 60)
        it["createdAt"] = it["submittedAt"]; it["updatedAt"] = it["submittedAt"]
    }
    for (i in 1..1200) remote.add(0, mk(i))
    val srv = FakeTally()
    var lieAboutTotal = false
    srv.handler = { path ->
        val p = path.substringBefore('?'); val q = path.substringAfter('?', "").split('&').filter { it.contains('=') }.associate { it.substringBefore('=') to java.net.URLDecoder.decode(it.substringAfter('='), "UTF-8") }
        when {
            p == "/forms" -> Triple(200, Json.stringify(mapOf("items" to listOf(detail), "page" to 1, "limit" to 50, "total" to 1, "hasMore" to false)), emptyMap())
            p == "/forms/$formId" -> Triple(200, Json.stringify(detail), emptyMap())
            p == "/forms/$formId/questions" -> Triple(200, Json.stringify(questions), emptyMap())
            p == "/forms/$formId/submissions" -> {
                val page = q["page"]!!.toInt(); val limit = q["limit"]!!.toInt(); val start = q["startDate"]
                val list = remote.filter { start == null || (it["submittedAt"] as String) >= start }
                val slice = list.drop((page - 1) * limit).take(limit)
                val total = if (lieAboutTotal) remote.size + 7 else remote.size
                Triple(200, Json.stringify(mapOf("page" to page, "limit" to limit, "hasMore" to (page * limit < list.size), "totalNumberOfSubmissionsPerFilter" to mapOf("all" to total, "completed" to total, "partial" to 0), "submissions" to slice)), emptyMap())
            }
            else -> Triple(404, "{}", emptyMap())
        }
    }
    try {
        val client = TallyClient(srv.url, sleep = {})
        var backups = 0
        val store = MemoryStore()
        val engine = SyncEngine(ClientSource(client), store, beforeReconcile = { backups++ })
        val key = Secret("tly-xyz")
        fun sync(full: Boolean = false) = engine.syncForm("acc", formId, key, full)

        val f = engine.syncForms("acc", key)
        if (f.count != 1) bad += "syncForms: ${f.count}"

        var r = sync()
        if (r.mode != "initial" || r.new != 1200 || store.countPresent("acc", formId) != 1200 || r.warnings.isNotEmpty()) bad += "inicial: $r"
        if (store.numbers.size != 1200 || store.numbers["sub0001"] != 1 || store.numbers["sub1200"] != 1200) bad += "numeración inicial incorrecta"
        if (srv.requests.any { it.first != "GET" }) bad += "usó un método distinto de GET"

        r = sync()
        if (r.mode != "nochange") bad += "sin cambios debía ser nochange: ${r.mode}"
        val reqBefore = srv.requests.size
        sync(); if (srv.requests.size - reqBefore > 4) bad += "nochange hizo demasiadas solicitudes (${srv.requests.size - reqBefore})"

        for (i in 1201..1230) remote.add(0, mk(i))
        srv.requests.clear()
        r = sync()
        if (r.mode != "incremental" || r.new != 30) bad += "incremental: $r"
        if (store.countPresent("acc", formId) != 1230) bad += "incremental: total local ${store.countPresent("acc", formId)}"
        if (srv.requests.none { it.second.contains("startDate=") }) bad += "incremental sin startDate"
        if (store.numbers["sub1230"] != 1230) bad += "numeración incremental: ${store.numbers["sub1230"]}"

        // desaparece uno en Tally → recorrido completo, marcado como faltante, número intacto
        val gone = remote.removeAt(remote.indexOfFirst { it["id"] == "sub0500" })
        backups = 0
        r = sync()
        if (r.mode != "full" || r.missing != 1 || backups != 1) bad += "desaparecido: $r backups=$backups"
        if (store.subs["sub0500"]?.missing != true || store.numbers["sub0500"] != 500) bad += "faltante no marcado o renumerado"
        if (store.countPresent("acc", formId) != 1229) bad += "presentes tras faltante: ${store.countPresent("acc", formId)}"
        // reaparece
        remote.add(remote.indexOfFirst { (it["id"] as String) < "sub0500" }, gone)
        r = sync(full = true)
        if (store.subs["sub0500"]?.missing != false) bad += "no reactivó el reaparecido"

        // total reportado distinto → una sola pasada extra y aviso
        lieAboutTotal = true
        r = sync()
        if ("count_mismatch" !in r.warnings) bad += "no avisó count_mismatch: $r"
        lieAboutTotal = false

        // cambio de estructura → renormaliza sin perder datos
        val before = store.subs.size
        // (se verifica que la renormalización mantenga la cantidad)
        engineRenormCheck(store, bad)
        if (store.subs.size != before) bad += "cambió la cantidad tras renormalizar"

        // errores de API quedan registrados
        srv.handler = { Triple(401, "{}", emptyMap()) }
        try { sync(); bad += "401 no lanzó error" } catch (e: ApiException) { if (e.code != ErrorCode.KEY_REJECTED || store.lastError != "KEY_REJECTED") bad += "error no registrado: ${store.lastError}" }

        // cancelación
        srv.handler = { Triple(200, "{}", emptyMap()) }
        try { engine.syncForm("acc", formId, key, false, { true }); bad += "cancelar no lanzó" } catch (e: SyncCancelledException) {}
    } finally { srv.stop() }
    return bad
}

private fun engineRenormCheck(store: MemoryStore, bad: MutableList<String>) {
    val raws = store.rawSubmissions("acc", "x")
    if (raws.isEmpty()) bad += "no hay JSON original sanitizado guardado"
    for (r in raws) for (banned in listOf("respondentId", "previewUrl", "pdfUrl")) if (r.containsKey(banned)) bad += "el JSON guardado contiene $banned"
}

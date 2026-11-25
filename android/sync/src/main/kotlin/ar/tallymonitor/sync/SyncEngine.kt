package ar.tallymonitor.sync

import ar.tallymonitor.core.ApiException
import ar.tallymonitor.core.ErrorCode
import ar.tallymonitor.core.FormRow
import ar.tallymonitor.core.JObj
import ar.tallymonitor.core.QuestionRow
import ar.tallymonitor.core.Secret
import ar.tallymonitor.core.SubmissionRow
import ar.tallymonitor.core.SyncCancelledException

const val PAGE_SIZE = 500

/** Lo que el motor necesita de Tally (lo implementa el cliente de red; en pruebas, un servidor falso). */
interface RemoteSource {
    fun listForms(key: Secret, page: Int): JObj
    fun getForm(key: Secret, formId: String): JObj
    fun getQuestions(key: Secret, formId: String): JObj
    fun listSubmissions(key: Secret, formId: String, page: Int, limit: Int, startDate: String?): JObj
}

data class SyncState(val newestSubmittedAt: String?, val newestSubmissionId: String?)

/** Persistencia que necesita el motor. La implementa SQLite en la app y una versión en memoria en las pruebas. */
interface SyncStore {
    fun saveSummaries(accountId: String, items: List<Pair<FormRow, JObj>>)
    fun getQuestions(accountId: String, formId: String): List<QuestionRow>
    fun saveDetail(accountId: String, form: FormRow, detail: JObj, questions: JObj, rows: List<QuestionRow>)
    fun setReported(accountId: String, formId: String, total: Int)
    fun countPresent(accountId: String, formId: String): Int
    fun newestSubmittedAt(accountId: String, formId: String): String?
    fun upsertPage(accountId: String, items: List<Pair<SubmissionRow, JObj>>): Pair<Int, Int>     // (nuevos, actualizados)
    fun markMissing(accountId: String, formId: String, seen: Set<String>): Int
    fun assignNumbers(accountId: String, formId: String): Int
    fun rawSubmissions(accountId: String, formId: String): List<JObj>
    fun rewriteNormalized(accountId: String, rows: List<SubmissionRow>)
    fun getSyncState(accountId: String, formId: String): SyncState?
    fun saveSyncOk(accountId: String, formId: String, newestAt: String?, newestId: String?, full: Boolean)
    fun saveSyncError(accountId: String, formId: String, category: String)
    fun markSynced(accountId: String, formId: String, lastSubmissionAt: String?)
}

data class SyncResult(
    val formId: String, val mode: String,                // initial | incremental | full | nochange
    val new: Int = 0, val updated: Int = 0, val missing: Int = 0, val remoteTotal: Int? = null, val localTotal: Int = 0,
    val warnings: List<String> = emptyList(), val unknownFields: List<String> = emptyList(),
)

data class FormsSyncResult(val count: Int, val unknownFields: List<String> = emptyList())

typealias Progress = (stage: String, done: Int, total: Int?) -> Unit

/**
 * Sincronización de SOLO LECTURA desde Tally hacia la copia local. Bloqueante: se corre en un hilo de fondo y se
 * cancela con `isCancelled`. Misma lógica que la versión de Windows (sondeo barato, incremental con startDate,
 * deduplicación por ID, verificación contra el total de Tally y un único recorrido completo si no coincide).
 */
class SyncEngine(
    private val source: RemoteSource, private val store: SyncStore,
    /** Se llama antes de reconciliar (recorrido completo con datos locales): ahí la app hace su copia de seguridad. */
    private val beforeReconcile: () -> Unit = {},
) {
    private fun check(c: () -> Boolean) { if (c()) throw SyncCancelledException() }

    fun syncForms(accountId: String, key: Secret, isCancelled: () -> Boolean = { false }, progress: Progress? = null): FormsSyncResult {
        val items = ArrayList<Pair<FormRow, JObj>>(); val unknown = ArrayList<String>()
        var page = 1
        while (true) {
            check(isCancelled)
            val data = source.listForms(key, page)
            val raw = data["items"] as? List<*> ?: throw ApiException(ErrorCode.BAD_RESPONSE)
            for (f in raw) {
                @Suppress("UNCHECKED_CAST") val m = f as? JObj ?: continue
                if (!Normalizer.truthy(m["id"])) continue
                val s = Sanitizer.sanitizeForm(m)
                unknown += s.unknownFields
                items += Normalizer.formRow(s.data) to s.data
            }
            progress?.invoke("encuestas", items.size, (data["total"] as? Number)?.toInt())
            if (data["hasMore"] != true || raw.isEmpty() || page >= 200) break
            page++
        }
        store.saveSummaries(accountId, items)
        return FormsSyncResult(items.size, unknown.distinct())
    }

    fun syncForm(accountId: String, formId: String, key: Secret, full: Boolean = false, isCancelled: () -> Boolean = { false },
                 progress: Progress? = null): SyncResult {
        try {
            return run(accountId, formId, key, full, isCancelled, progress)
        } catch (e: SyncCancelledException) {
            throw e
        } catch (e: ApiException) {
            store.saveSyncError(accountId, formId, e.code.name)
            throw e
        }
    }

    @Suppress("UNCHECKED_CAST")
    private fun run(acc: String, formId: String, key: Secret, full: Boolean, cancel: () -> Boolean, progress: Progress?): SyncResult {
        val warnings = ArrayList<String>(); val unknown = ArrayList<String>()

        // 1) estructura
        val detail = Sanitizer.sanitizeForm(source.getForm(key, formId))
        check(cancel)
        val qs = Sanitizer.sanitizeQuestions(source.getQuestions(key, formId))
        unknown += detail.unknownFields + qs.unknownFields
        val previous = store.getQuestions(acc, formId)
        val qrows = Normalizer.questionRows(detail.data, qs.data)
        store.saveDetail(acc, Normalizer.formRow(detail.data), detail.data, qs.data, qrows)
        fun sig(l: List<QuestionRow>) = l.map { listOf(it.questionId, it.type, it.options, it.hasOtherOption) }
        val structureChanged = sig(previous) != sig(qrows)
        val qmap = qrows.associateBy { it.questionId }
        check(cancel)

        // 2) sondeo barato
        val probe = source.listSubmissions(key, formId, 1, 1, null)
        val totals = probe["totalNumberOfSubmissionsPerFilter"] as? JObj
        val remoteTotal = (totals?.get("all") as? Number)?.toInt()
        if (remoteTotal != null) store.setReported(acc, formId, remoteTotal)
        val local = store.countPresent(acc, formId)
        val st = store.getSyncState(acc, formId)
        val marker = st?.newestSubmittedAt
        var mode = when {
            full -> "full"
            marker == null -> "initial"
            remoteTotal != null && remoteTotal < local -> "full"
            else -> "incremental"
        }

        if (mode == "incremental" && remoteTotal != null && remoteTotal == local && !structureChanged) {
            val newest = probeNewest(probe)
            if (newest == null || newest <= marker!!) {
                store.assignNumbers(acc, formId)
                store.saveSyncOk(acc, formId, marker, st?.newestSubmissionId, false)
                store.markSynced(acc, formId, store.newestSubmittedAt(acc, formId))
                return SyncResult(formId, "nochange", remoteTotal = remoteTotal, localTotal = local, unknownFields = unknown.distinct())
            }
        }

        var missing = 0
        if (mode == "full" && local > 0) beforeReconcile()
        var dl = download(acc, formId, key, qmap, if (mode == "full" || mode == "initial") null else marker, cancel, progress, unknown, remoteTotal)
        var new = dl.new; var upd = dl.updated
        if (mode == "full") missing = store.markMissing(acc, formId, dl.seen)
        else if (structureChanged) renormalize(acc, formId, qmap)

        // 3) verificación contra el total de Tally
        var localAfter = store.countPresent(acc, formId)
        if (mode == "incremental" && remoteTotal != null && localAfter != remoteTotal) {
            beforeReconcile()
            dl = download(acc, formId, key, qmap, null, cancel, progress, unknown, remoteTotal)
            new += dl.new; upd += dl.updated
            missing = store.markMissing(acc, formId, dl.seen)
            mode = "full"
            localAfter = store.countPresent(acc, formId)
        }
        if (remoteTotal != null && localAfter != remoteTotal) warnings += "count_mismatch"

        store.assignNumbers(acc, formId)
        val newest = store.newestSubmittedAt(acc, formId)
        store.saveSyncOk(acc, formId, newest, null, mode == "full")
        store.markSynced(acc, formId, newest)
        return SyncResult(formId, mode, new, upd, missing, remoteTotal, localAfter, warnings, unknown.distinct())
    }

    private fun probeNewest(probe: JObj): String? {
        val subs = probe["submissions"] as? List<*>
        val first = subs?.firstOrNull() as? Map<*, *> ?: return null
        val v = first["submittedAt"].takeIf { Normalizer.truthy(it) } ?: first["createdAt"]
        return v as? String
    }

    private class Downloaded(val new: Int, val updated: Int, val seen: Set<String>)

    @Suppress("UNCHECKED_CAST")
    private fun download(acc: String, formId: String, key: Secret, qmap: Map<String, QuestionRow>, startDate: String?, cancel: () -> Boolean,
                         progress: Progress?, unknown: MutableList<String>, total: Int?): Downloaded {
        var new = 0; var upd = 0; val seen = HashSet<String>(); var page = 1
        while (true) {
            check(cancel)
            val data = source.listSubmissions(key, formId, page, PAGE_SIZE, startDate)
            val raw = data["submissions"] as? List<*> ?: throw ApiException(ErrorCode.BAD_RESPONSE)
            val batch = ArrayList<Pair<SubmissionRow, JObj>>()
            for (sub in raw) {
                val m = sub as? JObj ?: continue
                if (!Normalizer.truthy(m["id"])) continue
                val s = Sanitizer.sanitizeSubmission(m)
                unknown += s.unknownFields
                val row = Normalizer.submissionRow(s.data, qmap)
                batch += row to s.data
                seen += row.submissionId
            }
            val (n, u) = store.upsertPage(acc, batch)
            new += n; upd += u
            progress?.invoke("respuestas", seen.size, total)
            if (data["hasMore"] != true || raw.isEmpty() || page >= 1000) break
            page++
        }
        return Downloaded(new, upd, seen)
    }

    private fun renormalize(acc: String, formId: String, qmap: Map<String, QuestionRow>) {
        store.rewriteNormalized(acc, store.rawSubmissions(acc, formId).map { Normalizer.submissionRow(it, qmap) })
    }
}

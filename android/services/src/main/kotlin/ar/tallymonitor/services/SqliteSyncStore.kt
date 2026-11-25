package ar.tallymonitor.services

import ar.tallymonitor.core.FormRow
import ar.tallymonitor.core.JObj
import ar.tallymonitor.core.QuestionRow
import ar.tallymonitor.core.SubmissionRow
import ar.tallymonitor.storage.StateRepository
import ar.tallymonitor.storage.SubmissionsRepository
import ar.tallymonitor.storage.SurveysRepository
import ar.tallymonitor.sync.SyncState
import ar.tallymonitor.sync.SyncStore

/** Une el motor de sincronización con SQLite (los repositorios ya hacen una transacción por página). */
class SqliteSyncStore(private val surveys: SurveysRepository, private val subs: SubmissionsRepository, private val state: StateRepository) : SyncStore {
    override fun saveSummaries(accountId: String, items: List<Pair<FormRow, JObj>>) = surveys.saveSummaries(accountId, items)
    override fun getQuestions(accountId: String, formId: String): List<QuestionRow> =
        surveys.getQuestions(accountId, formId).map { QuestionRow(it.questionId, it.position, it.type, it.title, null, null, it.hasOtherOption, it.isDeleted, it.options) }
    override fun saveDetail(accountId: String, form: FormRow, detail: JObj, questions: JObj, rows: List<QuestionRow>) = surveys.saveDetail(accountId, form, detail, questions, rows)
    override fun setReported(accountId: String, formId: String, total: Int) = surveys.setReported(accountId, formId, total)
    override fun countPresent(accountId: String, formId: String) = subs.countPresent(accountId, formId)
    override fun newestSubmittedAt(accountId: String, formId: String) = subs.newestSubmittedAt(accountId, formId)
    override fun upsertPage(accountId: String, items: List<Pair<SubmissionRow, JObj>>) = subs.upsertPage(accountId, items)
    override fun markMissing(accountId: String, formId: String, seen: Set<String>) = subs.markMissing(accountId, formId, seen)
    override fun assignNumbers(accountId: String, formId: String) = subs.assignNumbers(accountId, formId)
    override fun rawSubmissions(accountId: String, formId: String) = subs.rawSubmissions(accountId, formId)
    override fun rewriteNormalized(accountId: String, rows: List<SubmissionRow>) = subs.rewriteNormalized(accountId, rows)
    override fun getSyncState(accountId: String, formId: String) = state.getSync(accountId, formId)?.let { SyncState(it.newestSubmittedAt, it.newestSubmissionId) }
    override fun saveSyncOk(accountId: String, formId: String, newestAt: String?, newestId: String?, full: Boolean) = state.saveSyncOk(accountId, formId, newestAt, newestId, full)
    override fun saveSyncError(accountId: String, formId: String, category: String) = state.saveSyncError(accountId, formId, category)
    override fun markSynced(accountId: String, formId: String, lastSubmissionAt: String?) = surveys.markSynced(accountId, formId, lastSubmissionAt)
}

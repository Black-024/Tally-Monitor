package ar.tallymonitor.storage

import android.database.Cursor
import ar.tallymonitor.core.*
import java.util.UUID

// ======================= Cuentas =======================
data class AccountRecord(val accountId: String, val name: String, val status: String, val lastCheckResult: String?,
                         val lastCheckedAt: String?, val lastValidatedAt: String?, val createdAt: String, val updatedAt: String)

class AccountsRepository(private val db: Db, private val clock: Clock = Clock.SYSTEM) {
    companion object { val STATUSES = setOf("unverified", "active", "key_rejected", "check_failed", "no_credential") }
    private fun row(c: Cursor) = AccountRecord(c.getString(0), c.getString(1), c.getString(2), c.str(3), c.str(4), c.str(5), c.getString(6), c.getString(7))
    private val COLS = "account_id,name,status,last_check_result,last_checked_at,last_validated_at,created_at,updated_at"

    fun add(name: String, status: String = "unverified", lastCheckResult: String? = null, validated: Boolean = false, accountId: String? = null): AccountRecord {
        val now = clock.nowIso(); val id = accountId ?: UUID.randomUUID().toString()
        try {
            db.tx { it.exec("INSERT INTO data_account($COLS) VALUES (?,?,?,?,?,?,?,?)",
                listOf(id, name, status, lastCheckResult, if (lastCheckResult != null) now else null, if (validated) now else null, now, now)) }
        } catch (e: android.database.sqlite.SQLiteConstraintException) { throw TallyMonitorException(ErrorCode.ALREADY_EXISTS) }
        return get(id)
    }
    fun get(id: String): AccountRecord = db.queryOne("SELECT $COLS FROM data_account WHERE account_id=?", listOf(id), ::row) ?: throw TallyMonitorException(ErrorCode.NOT_FOUND_LOCAL)
    fun list(): List<AccountRecord> = db.query("SELECT $COLS FROM data_account ORDER BY created_at, rowid", emptyList(), ::row)
    fun nameExists(name: String, excludeId: String? = null): Boolean =
        db.queryOne("SELECT account_id FROM data_account WHERE name=? COLLATE NOCASE", listOf(name)) { it.getString(0) }.let { it != null && it != excludeId }

    fun rename(id: String, name: String): AccountRecord {
        val n = try { db.tx { it.exec("UPDATE data_account SET name=?, updated_at=? WHERE account_id=?", listOf(name, clock.nowIso(), id)) } }
        catch (e: android.database.sqlite.SQLiteConstraintException) { throw TallyMonitorException(ErrorCode.ALREADY_EXISTS) }
        if (n == 0) throw TallyMonitorException(ErrorCode.NOT_FOUND_LOCAL)
        return get(id)
    }

    /** `last_validated_at` solo avanza si result == 'ok'. */
    fun setCheck(id: String, status: String, result: String): AccountRecord {
        require(status in STATUSES)
        val now = clock.nowIso()
        val n = db.tx { it.exec("UPDATE data_account SET status=?, last_check_result=?, last_checked_at=?, last_validated_at=CASE WHEN ?='ok' THEN ? ELSE last_validated_at END, updated_at=? WHERE account_id=?",
            listOf(status, result, now, result, now, now, id)) }
        if (n == 0) throw TallyMonitorException(ErrorCode.NOT_FOUND_LOCAL)
        return get(id)
    }

    fun setStatus(id: String, status: String): AccountRecord {
        require(status in STATUSES)
        if (db.tx { it.exec("UPDATE data_account SET status=?, updated_at=? WHERE account_id=?", listOf(status, clock.nowIso(), id)) } == 0) throw TallyMonitorException(ErrorCode.NOT_FOUND_LOCAL)
        return get(id)
    }

    /** Borra la cuenta y, en cascada, todo lo suyo. La credencial cifrada la borra quien llama. */
    fun delete(id: String) { if (db.tx { it.exec("DELETE FROM data_account WHERE account_id=?", listOf(id)) } == 0) throw TallyMonitorException(ErrorCode.NOT_FOUND_LOCAL) }
}

// ======================= Encuestas =======================
data class FormRecord(val formId: String, val name: String, val status: String, val isClosed: Boolean, val reportedSubmissions: Int?,
                      val createdAt: String?, val updatedAt: String?, val lastSubmissionAt: String?, val lastSyncedAt: String?, val localSubmissions: Int)

data class QuestionRecord(val questionId: String, val position: Int, val type: String, val title: String, val hasOtherOption: Boolean,
                          val isDeleted: Boolean, val options: List<String>)

class SurveysRepository(private val db: Db, private val sanitizerVersion: Int, private val clock: Clock = Clock.SYSTEM) {
    private val LIST_SQL = "SELECT f.form_id,f.name,f.status,f.is_closed,f.reported_submissions,f.created_at,f.updated_at,f.last_submission_at,f.last_synced_at," +
        "(SELECT COUNT(*) FROM data_submission s JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id " +
        "WHERE s.account_id=f.account_id AND s.form_id=f.form_id AND s.missing_at_source_at IS NULL) AS local_n FROM data_form f WHERE f.account_id=?"
    private fun rec(c: Cursor) = FormRecord(c.getString(0), c.getString(1), c.getString(2), c.bool(3), c.int(4), c.str(5), c.str(6), c.str(7), c.str(8), c.getInt(9))

    private fun upsertForm(tx: Db.Tx, acc: String, f: FormRow) = tx.exec(
        "INSERT INTO data_form(account_id,form_id,name,status,is_closed,workspace_id,reported_submissions,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?) " +
        "ON CONFLICT(account_id,form_id) DO UPDATE SET name=excluded.name,status=excluded.status,is_closed=excluded.is_closed,workspace_id=excluded.workspace_id," +
        "reported_submissions=COALESCE(excluded.reported_submissions,reported_submissions),created_at=excluded.created_at,updated_at=excluded.updated_at",
        listOf(acc, f.formId, f.name, f.status, f.isClosed, f.workspaceId, f.reportedSubmissions, f.createdAt, f.updatedAt))

    @Suppress("UNCHECKED_CAST")
    private fun mergeRaw(tx: Db.Tx, acc: String, formId: String, key: String, value: JObj) {
        val cur = tx.query("SELECT sanitized_json FROM raw_form WHERE account_id=? AND form_id=?", listOf(acc, formId)) { it.getString(0) }.firstOrNull()
            ?.let { (Json.parse(it) as? JObj)?.toMutableMap() } ?: mutableMapOf<String, Any?>("summary" to null, "detail" to null)
        cur[key] = value
        tx.exec("INSERT INTO raw_form(account_id,form_id,sanitized_json,sanitizer_version,fetched_at) VALUES (?,?,?,?,?) ON CONFLICT(account_id,form_id) DO UPDATE SET " +
            "sanitized_json=excluded.sanitized_json,sanitizer_version=excluded.sanitizer_version,fetched_at=excluded.fetched_at",
            listOf(acc, formId, Json.stringify(cur), sanitizerVersion, clock.nowIso()))
    }

    fun saveSummaries(acc: String, items: List<Pair<FormRow, JObj>>) = db.tx { tx -> for ((row, san) in items) { upsertForm(tx, acc, row); mergeRaw(tx, acc, row.formId, "summary", san) } }

    fun saveDetail(acc: String, form: FormRow, detail: JObj, questionsRaw: JObj, questions: List<QuestionRow>) = db.tx { tx ->
        upsertForm(tx, acc, form); mergeRaw(tx, acc, form.formId, "detail", detail)
        tx.exec("INSERT INTO raw_questions(account_id,form_id,sanitized_json,sanitizer_version,fetched_at) VALUES (?,?,?,?,?) ON CONFLICT(account_id,form_id) DO UPDATE SET " +
            "sanitized_json=excluded.sanitized_json,sanitizer_version=excluded.sanitizer_version,fetched_at=excluded.fetched_at",
            listOf(acc, form.formId, Json.stringify(questionsRaw), sanitizerVersion, clock.nowIso()))
        replaceQuestions(tx, acc, form.formId, questions)
    }

    private fun replaceQuestions(tx: Db.Tx, acc: String, formId: String, qs: List<QuestionRow>) {
        tx.exec("DELETE FROM data_option WHERE account_id=? AND form_id=?", listOf(acc, formId))
        tx.exec("DELETE FROM data_question WHERE account_id=? AND form_id=?", listOf(acc, formId))
        for (q in qs) {
            tx.exec("INSERT INTO data_question(account_id,form_id,question_id,position,type,title,reported_responses,group_uuid,has_other_option,is_deleted) VALUES (?,?,?,?,?,?,?,?,?,?)",
                listOf(acc, formId, q.questionId, q.position, q.type, q.title, q.reportedResponses, q.groupUuid, q.hasOtherOption, q.isDeleted))
            q.options.distinct().forEachIndexed { i, t -> tx.exec("INSERT INTO data_option(account_id,form_id,question_id,option_text,position) VALUES (?,?,?,?,?)", listOf(acc, formId, q.questionId, t, i)) }
        }
    }

    fun markSynced(acc: String, formId: String, lastSubmissionAt: String?) { db.exec("UPDATE data_form SET last_synced_at=?, last_submission_at=? WHERE account_id=? AND form_id=?", listOf(clock.nowIso(), lastSubmissionAt, acc, formId)) }
    fun setReported(acc: String, formId: String, n: Int) { db.exec("UPDATE data_form SET reported_submissions=? WHERE account_id=? AND form_id=?", listOf(n, acc, formId)) }
    fun listForms(acc: String): List<FormRecord> = db.query("$LIST_SQL ORDER BY f.updated_at DESC, f.name COLLATE NOCASE", listOf(acc), ::rec)
    fun getForm(acc: String, formId: String): FormRecord? = db.queryOne("$LIST_SQL AND f.form_id=?", listOf(acc, formId), ::rec)

    fun getQuestions(acc: String, formId: String): List<QuestionRecord> {
        val opts = db.query("SELECT question_id,option_text FROM data_option WHERE account_id=? AND form_id=? ORDER BY position", listOf(acc, formId)) { it.getString(0) to it.getString(1) }
            .groupBy({ it.first }, { it.second })
        return db.query("SELECT question_id,position,type,title,has_other_option,is_deleted FROM data_question WHERE account_id=? AND form_id=? ORDER BY position", listOf(acc, formId)) { c ->
            QuestionRecord(c.getString(0), c.getInt(1), c.getString(2), c.getString(3), c.bool(4), c.bool(5), opts[c.getString(0)] ?: emptyList()) }
    }

    /** (detalle sanitizado, preguntas sanitizadas) tal como se guardaron. */
    @Suppress("UNCHECKED_CAST")
    fun rawStructure(acc: String, formId: String): Pair<JObj?, JObj?> {
        val f = db.queryOne("SELECT sanitized_json FROM raw_form WHERE account_id=? AND form_id=?", listOf(acc, formId)) { it.getString(0) }
        val q = db.queryOne("SELECT sanitized_json FROM raw_questions WHERE account_id=? AND form_id=?", listOf(acc, formId)) { it.getString(0) }
        return ((f?.let { Json.parse(it) } as? JObj)?.get("detail") as? JObj) to (q?.let { Json.parse(it) } as? JObj)
    }
}

// ======================= Envíos =======================
data class AnswerRecord(val questionId: String, val kind: String, val textValue: String?, val isBlank: Boolean, val choices: List<Pair<String, String>>)
data class SubmissionRecord(val number: Int?, val submittedAt: String, val isCompleted: Boolean, val answers: List<AnswerRecord>)

class SubmissionsRepository(private val db: Db, private val sanitizerVersion: Int, private val clock: Clock = Clock.SYSTEM) {
    private fun writeNormalized(tx: Db.Tx, acc: String, s: SubmissionRow) {
        tx.exec("INSERT INTO data_submission(account_id,submission_id,form_id,submitted_at,is_completed,created_at,updated_at,missing_at_source_at) VALUES (?,?,?,?,?,?,?,NULL) " +
            "ON CONFLICT(account_id,submission_id) DO UPDATE SET form_id=excluded.form_id,submitted_at=excluded.submitted_at,is_completed=excluded.is_completed,created_at=excluded.created_at,updated_at=excluded.updated_at,missing_at_source_at=NULL",
            listOf(acc, s.submissionId, s.formId, s.submittedAt, s.isCompleted, s.createdAt, s.updatedAt))
        tx.exec("DELETE FROM data_choice WHERE account_id=? AND submission_id=?", listOf(acc, s.submissionId))
        tx.exec("DELETE FROM data_answer WHERE account_id=? AND submission_id=?", listOf(acc, s.submissionId))
        for (a in s.answers) {
            tx.exec("INSERT OR REPLACE INTO data_answer(account_id,submission_id,question_id,kind,text_value,is_blank,raw_json) VALUES (?,?,?,?,?,?,?)",
                listOf(acc, s.submissionId, a.questionId, a.kind, a.textValue, a.isBlank, a.rawJson))
            for (ch in a.choices) tx.exec("INSERT OR IGNORE INTO data_choice(account_id,submission_id,question_id,option_text,origin) VALUES (?,?,?,?,?)", listOf(acc, s.submissionId, a.questionId, ch.optionText, ch.origin))
        }
    }

    /** Una página en una sola transacción. Devuelve (nuevos, actualizados). */
    fun upsertPage(acc: String, items: List<Pair<SubmissionRow, JObj>>): Pair<Int, Int> {
        val now = clock.nowIso(); var n = 0; var u = 0
        db.tx { tx ->
            for ((row, san) in items) {
                val exists = tx.query("SELECT 1 FROM raw_submission WHERE account_id=? AND submission_id=?", listOf(acc, row.submissionId)) { 1 }.isNotEmpty()
                tx.exec("INSERT INTO raw_submission(account_id,submission_id,form_id,sanitized_json,sanitizer_version,first_seen_at,last_seen_at,missing_at_source_at) VALUES (?,?,?,?,?,?,?,NULL) " +
                    "ON CONFLICT(account_id,submission_id) DO UPDATE SET sanitized_json=excluded.sanitized_json,sanitizer_version=excluded.sanitizer_version,last_seen_at=excluded.last_seen_at,missing_at_source_at=NULL",
                    listOf(acc, row.submissionId, row.formId, Json.stringify(san), sanitizerVersion, now, now))
                writeNormalized(tx, acc, row)
                if (exists) u++ else n++
            }
        }
        return n to u
    }

    fun countPresent(acc: String, formId: String): Int = db.queryOne("SELECT COUNT(*) FROM data_submission WHERE account_id=? AND form_id=? AND missing_at_source_at IS NULL", listOf(acc, formId)) { it.getInt(0) } ?: 0
    fun newestSubmittedAt(acc: String, formId: String): String? = db.queryOne("SELECT MAX(submitted_at) FROM data_submission WHERE account_id=? AND form_id=? AND missing_at_source_at IS NULL", listOf(acc, formId)) { it.str(0) }

    /** Tras un recorrido completo: marca como «desaparecidos del origen» (sin borrar) los que no vinieron. */
    fun markMissing(acc: String, formId: String, seen: Set<String>): Int {
        val now = clock.nowIso()
        return db.tx { tx ->
            val gone = tx.query("SELECT submission_id FROM data_submission WHERE account_id=? AND form_id=? AND missing_at_source_at IS NULL", listOf(acc, formId)) { it.getString(0) }.filter { it !in seen }
            for (id in gone) for (t in listOf("data_submission", "raw_submission")) tx.exec("UPDATE $t SET missing_at_source_at=? WHERE account_id=? AND submission_id=?", listOf(now, acc, id))
            gone.size
        }
    }

    /** Numera los envíos sin número por fecha ascendente (empate: ID). Nunca renumera ni reutiliza. */
    fun assignNumbers(acc: String, formId: String): Int = db.tx { tx ->
        val rows = tx.query("SELECT s.submission_id FROM data_submission s LEFT JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id " +
            "WHERE s.account_id=? AND s.form_id=? AND n.number IS NULL ORDER BY s.submitted_at ASC, s.submission_id ASC", listOf(acc, formId)) { it.getString(0) }
        if (rows.isEmpty()) return@tx 0
        var next = tx.query("SELECT next_number FROM state_form_counter WHERE account_id=? AND form_id=?", listOf(acc, formId)) { it.getInt(0) }.firstOrNull() ?: 1
        for (id in rows) { tx.exec("INSERT INTO state_user_number(account_id,form_id,submission_id,number) VALUES (?,?,?,?)", listOf(acc, formId, id, next)); next++ }
        tx.exec("INSERT INTO state_form_counter(account_id,form_id,next_number) VALUES (?,?,?) ON CONFLICT(account_id,form_id) DO UPDATE SET next_number=excluded.next_number", listOf(acc, formId, next))
        rows.size
    }

    @Suppress("UNCHECKED_CAST")
    fun rawSubmissions(acc: String, formId: String): List<JObj> =
        db.query("SELECT sanitized_json FROM raw_submission WHERE account_id=? AND form_id=?", listOf(acc, formId)) { Json.parse(it.getString(0)) as JObj }

    fun rewriteNormalized(acc: String, rows: List<SubmissionRow>) = db.tx { tx ->
        for (s in rows) {
            val prev = tx.query("SELECT missing_at_source_at FROM data_submission WHERE account_id=? AND submission_id=?", listOf(acc, s.submissionId)) { it.str(0) }.firstOrNull()
            writeNormalized(tx, acc, s)
            if (prev != null) tx.exec("UPDATE data_submission SET missing_at_source_at=? WHERE account_id=? AND submission_id=?", listOf(prev, acc, s.submissionId))
        }
    }

    // ---- lectura (paginada por offset/limit) ----
    private val BASE = "SELECT s.submission_id,s.form_id,s.submitted_at,s.is_completed,n.number FROM data_submission s LEFT JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id " +
        "WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL AND n.number IS NOT NULL"

    private class Head(val sid: String, val formId: String, val at: String, val done: Boolean, val number: Int)

    private fun load(acc: String, heads: List<Head>): List<SubmissionRecord> = heads.map { h ->
        val answers = db.query("SELECT a.question_id,a.kind,a.text_value,a.is_blank FROM data_answer a LEFT JOIN data_question q ON q.account_id=a.account_id AND q.question_id=a.question_id AND q.form_id=? " +
            "WHERE a.account_id=? AND a.submission_id=? ORDER BY COALESCE(q.position,1000000), a.question_id", listOf(h.formId, acc, h.sid)) { c ->
            val qid = c.getString(0)
            val ch = db.query("SELECT option_text,origin FROM data_choice WHERE account_id=? AND submission_id=? AND question_id=? ORDER BY option_text", listOf(acc, h.sid, qid)) { it.getString(0) to it.getString(1) }
            AnswerRecord(qid, c.getString(1), c.str(2), c.bool(3), ch)
        }
        SubmissionRecord(h.number, h.at, h.done, answers)
    }

    private fun head(c: Cursor) = Head(c.getString(0), c.getString(1), c.getString(2), c.bool(3), c.getInt(4))

    fun listPage(acc: String, formId: String, offset: Int = 0, limit: Int = 50, descending: Boolean = false): List<SubmissionRecord> =
        load(acc, db.query("$BASE ORDER BY n.number ${if (descending) "DESC" else "ASC"} LIMIT ${limit.coerceAtLeast(1)} OFFSET ${offset.coerceAtLeast(0)}", listOf(acc, formId), ::head))

    fun getByNumber(acc: String, formId: String, number: Int): SubmissionRecord? =
        load(acc, db.query("$BASE AND n.number=?", listOf(acc, formId, number), ::head)).firstOrNull()
}

// ======================= Estado (favoritos, recientes, sincronización) =======================
data class SyncStateRecord(val newestSubmittedAt: String?, val newestSubmissionId: String?, val lastSyncAt: String?, val lastFullReconcileAt: String?, val lastError: String?)

class StateRepository(private val db: Db, private val clock: Clock = Clock.SYSTEM) {
    companion object { const val MAX_RECENTS = 10 }
    fun setFavorite(acc: String, formId: String, value: Boolean) {
        if (value) db.exec("INSERT OR IGNORE INTO state_favorite(account_id,form_id) VALUES (?,?)", listOf(acc, formId))
        else db.exec("DELETE FROM state_favorite WHERE account_id=? AND form_id=?", listOf(acc, formId))
    }
    fun favorites(acc: String): Set<String> = db.query("SELECT form_id FROM state_favorite WHERE account_id=?", listOf(acc)) { it.getString(0) }.toSet()

    fun touchRecent(acc: String, formId: String) = db.tx { tx ->
        tx.exec("INSERT INTO state_recent(account_id,form_id,opened_at) VALUES (?,?,?) ON CONFLICT(account_id,form_id) DO UPDATE SET opened_at=excluded.opened_at", listOf(acc, formId, clock.nowIso()))
        tx.exec("DELETE FROM state_recent WHERE account_id=? AND form_id NOT IN (SELECT form_id FROM state_recent WHERE account_id=? ORDER BY opened_at DESC, rowid DESC LIMIT $MAX_RECENTS)", listOf(acc, acc))
    }
    fun recents(acc: String): List<String> = db.query("SELECT form_id FROM state_recent WHERE account_id=? ORDER BY opened_at DESC, rowid DESC", listOf(acc)) { it.getString(0) }

    fun getSync(acc: String, formId: String): SyncStateRecord? =
        db.queryOne("SELECT newest_submitted_at,newest_submission_id,last_sync_at,last_full_reconcile_at,last_error FROM state_sync WHERE account_id=? AND form_id=?", listOf(acc, formId)) {
            SyncStateRecord(it.str(0), it.str(1), it.str(2), it.str(3), it.str(4)) }

    fun saveSyncOk(acc: String, formId: String, newestAt: String?, newestId: String?, full: Boolean) {
        val now = clock.nowIso()
        db.exec("INSERT INTO state_sync(account_id,form_id,newest_submitted_at,newest_submission_id,last_sync_at,last_full_reconcile_at,last_error) VALUES (?,?,?,?,?,?,NULL) " +
            "ON CONFLICT(account_id,form_id) DO UPDATE SET newest_submitted_at=excluded.newest_submitted_at,newest_submission_id=excluded.newest_submission_id,last_sync_at=excluded.last_sync_at," +
            "last_full_reconcile_at=COALESCE(excluded.last_full_reconcile_at,last_full_reconcile_at),last_error=NULL", listOf(acc, formId, newestAt, newestId, now, if (full) now else null))
    }
    fun saveSyncError(acc: String, formId: String, category: String) {
        db.exec("INSERT INTO state_sync(account_id,form_id,last_error) VALUES (?,?,?) ON CONFLICT(account_id,form_id) DO UPDATE SET last_error=excluded.last_error", listOf(acc, formId, category))
    }
}

// ======================= Datos propios de cada encuesta (meta, nota, etiquetas, archivada) =======================
data class SurveyMetaRecord(val goal: Int?, val note: String, val archived: Boolean, val tags: List<String>)

/** Solo guarda: las reglas (rangos, largos, duplicados) las valida la capa de servicios antes de llamar. */
class SurveyMetaRepository(private val db: Db) {
    private val EMPTY = SurveyMetaRecord(null, "", false, emptyList())

    /** Todas las encuestas de la cuenta que tienen algo guardado. */
    fun all(acc: String): Map<String, SurveyMetaRecord> {
        val tags = db.query("SELECT form_id, tag FROM survey_tags WHERE account_id=? ORDER BY tag COLLATE NOCASE, tag", listOf(acc)) { it.getString(0) to it.getString(1) }
            .groupBy({ it.first }, { it.second })
        val out = HashMap<String, SurveyMetaRecord>()
        db.query("SELECT form_id, goal, note, archived FROM survey_meta WHERE account_id=?", listOf(acc)) { c ->
            out[c.getString(0)] = SurveyMetaRecord(c.int(1), c.getString(2), c.bool(3), tags[c.getString(0)] ?: emptyList())
        }
        for ((form, list) in tags) if (form !in out) out[form] = EMPTY.copy(tags = list)
        return out
    }

    fun get(acc: String, formId: String): SurveyMetaRecord = all(acc)[formId] ?: EMPTY

    /** Atómico: meta, nota y etiquetas en una sola transacción. No toca «archivada». Sin UPSERT (SQLite viejo de Android 8). */
    fun save(acc: String, formId: String, goal: Int?, note: String, tags: List<String>) = db.tx { tx ->
        tx.exec("INSERT OR IGNORE INTO survey_meta(account_id,form_id,goal,note,archived) VALUES (?,?,NULL,'',0)", listOf(acc, formId))
        tx.exec("UPDATE survey_meta SET goal=?, note=? WHERE account_id=? AND form_id=?", listOf(goal, note, acc, formId))
        tx.exec("DELETE FROM survey_tags WHERE account_id=? AND form_id=?", listOf(acc, formId))
        for (t in tags) tx.exec("INSERT INTO survey_tags(account_id,form_id,tag) VALUES (?,?,?)", listOf(acc, formId, t))
    }

    fun setArchived(acc: String, formId: String, archived: Boolean) = db.tx { tx ->
        tx.exec("INSERT OR IGNORE INTO survey_meta(account_id,form_id,goal,note,archived) VALUES (?,?,NULL,'',0)", listOf(acc, formId))
        tx.exec("UPDATE survey_meta SET archived=? WHERE account_id=? AND form_id=?", listOf(archived, acc, formId))
    }
}

// ======================= Preferencias =======================
class SettingsRepository(private val db: Db, private val clock: Clock = Clock.SYSTEM) {
    companion object {
        val ALLOWED = mapOf("log_level" to setOf("DEBUG", "INFO", "WARNING", "ERROR"), "auto_backup" to setOf("1", "0"), "sync_mode" to setOf("manual", "auto"),
            "update_check" to setOf("1", "0"), "theme" to setOf("dark", "light"),
            "notify_mode" to setOf("off", "on"), "notify_interval_min" to setOf("15", "30", "60", "360"))
        /** Ajustes numéricos (no una lista cerrada): entero de hasta 9 cifras. */
        private val NUMERIC = setOf("notified_new_total")
        private val DIGITS = Regex("^[0-9]{1,9}$")
        val DEFAULTS = mapOf("log_level" to "INFO", "auto_backup" to "1", "sync_mode" to "manual", "update_check" to "0", "theme" to "dark",
            "notify_mode" to "off", "notify_interval_min" to "60", "notified_new_total" to "0")
    }
    fun get(key: String): String {
        require(key in ALLOWED || key in NUMERIC)
        return db.queryOne("SELECT value FROM state_setting WHERE key=?", listOf(key)) { it.getString(0) } ?: DEFAULTS.getValue(key)
    }
    fun set(key: String, value: String) {
        require(ALLOWED[key]?.contains(value) == true || (key in NUMERIC && DIGITS.matches(value))) { "Preferencia inválida" }
        db.exec("INSERT INTO state_setting(key,value,updated_at) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at", listOf(key, value, clock.nowIso()))
    }
}

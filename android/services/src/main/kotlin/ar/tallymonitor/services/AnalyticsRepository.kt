package ar.tallymonitor.services

import ar.tallymonitor.analysis.AnswerPoint
import ar.tallymonitor.analysis.Cell
import ar.tallymonitor.analysis.QuestionInfo
import ar.tallymonitor.analysis.ResponseRow
import ar.tallymonitor.analysis.SubmissionPoint
import ar.tallymonitor.core.JObj
import ar.tallymonitor.core.Json
import ar.tallymonitor.storage.Db
import ar.tallymonitor.storage.bool
import ar.tallymonitor.storage.int
import ar.tallymonitor.storage.str

/** Lectura para el análisis y la exportación (el filtro de fechas se aplica en SQL). Solo lee. */
class AnalyticsRepository(private val db: Db) {
    private val FROM = "FROM data_submission s JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL"

    private fun where(start: String?, end: String?, incomplete: Boolean): Pair<String, List<Any?>> {
        val sb = StringBuilder(); val args = ArrayList<Any?>()
        if (start != null) { sb.append(" AND s.submitted_at >= ?"); args += start }
        if (end != null) { sb.append(" AND s.submitted_at < ?"); args += end }
        if (!incomplete) sb.append(" AND s.is_completed = 1")
        return sb.toString() to args
    }

    private fun choices(acc: String, form: String, extra: String, args: List<Any?>): Map<Pair<Int, String>, List<Pair<String, String>>> {
        val m = HashMap<Pair<Int, String>, MutableList<Pair<String, String>>>()
        db.query("SELECT n.number, ch.question_id, ch.option_text, ch.origin FROM data_choice ch JOIN data_submission s ON s.account_id=ch.account_id AND s.submission_id=ch.submission_id " +
            "JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL$extra", listOf(acc, form) + args) {
            Triple(it.getInt(0) to it.getString(1), it.getString(2), it.getString(3)) }
            .forEach { (k, t, o) -> m.getOrPut(k) { ArrayList() } += t to o }
        return m
    }

    fun load(acc: String, form: String, startIso: String?, endIso: String?, includeIncomplete: Boolean): Triple<List<SubmissionPoint>, List<AnswerPoint>, List<QuestionInfo>> {
        val (extra, args) = where(startIso, endIso, includeIncomplete); val base = listOf<Any?>(acc, form) + args
        val subs = db.query("SELECT n.number, s.submitted_at, s.is_completed $FROM$extra ORDER BY n.number", base) { SubmissionPoint(it.getInt(0), it.getString(1), it.bool(2)) }
        val ch = choices(acc, form, extra, args)
        val answers = db.query("SELECT n.number, a.question_id, a.kind, a.is_blank, CASE WHEN a.kind='text' THEN length(a.text_value) END FROM data_answer a " +
            "JOIN data_submission s ON s.account_id=a.account_id AND s.submission_id=a.submission_id JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id " +
            "WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL$extra", base) {
            AnswerPoint(it.getInt(0), it.getString(1), it.getString(2), it.bool(3), it.int(4), (ch[it.getInt(0) to it.getString(1)] ?: emptyList()).sortedBy { c -> c.first }) }
        val opts = db.query("SELECT question_id, option_text FROM data_option WHERE account_id=? AND form_id=? ORDER BY position", listOf(acc, form)) { it.getString(0) to it.getString(1) }.groupBy({ it.first }, { it.second })
        val questions = db.query("SELECT question_id, position, type, title, has_other_option, is_deleted FROM data_question WHERE account_id=? AND form_id=? ORDER BY position", listOf(acc, form)) {
            QuestionInfo(it.getString(0), it.getInt(1), it.getString(2), it.getString(3), opts[it.getString(0)] ?: emptyList(), it.bool(4), it.bool(5)) }
        return Triple(subs, answers, questions)
    }

    /** Todos los envíos guardados y numerados (sin filtro de fechas): base del ritmo de los últimos 7 días. */
    fun points(acc: String, form: String): List<SubmissionPoint> =
        db.query("SELECT n.number, s.submitted_at, s.is_completed $FROM ORDER BY n.number", listOf(acc, form)) { SubmissionPoint(it.getInt(0), it.getString(1), it.bool(2)) }

    /** (número, opción elegida) de UNA pregunta en todos los envíos guardados: sirve para el cruce de preguntas. */
    fun choicesFor(acc: String, form: String, questionId: String): List<Pair<Int, String>> =
        db.query("SELECT n.number, ch.option_text FROM data_choice ch JOIN data_submission s ON s.account_id=ch.account_id AND s.submission_id=ch.submission_id " +
            "JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id " +
            "WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL AND ch.question_id=?", listOf(acc, form, questionId)) { it.getInt(0) to it.getString(1) }

    /** formId → cantidad de envíos guardados con fecha en [startIso, endIso] (ambos inclusivos). */
    fun countsBetween(acc: String, startIso: String, endIso: String): Map<String, Int> {
        val out = HashMap<String, Int>()
        db.query("SELECT s.form_id, COUNT(*) FROM data_submission s JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id " +
            "WHERE s.account_id=? AND s.missing_at_source_at IS NULL AND s.submitted_at >= ? AND s.submitted_at <= ? GROUP BY s.form_id", listOf(acc, startIso, endIso)) { out[it.getString(0)] = it.getInt(1) }
        return out
    }

    fun exportRows(acc: String, form: String, startIso: String?, endIso: String?, includeIncomplete: Boolean, includeText: Boolean, onlyNumber: Int? = null): List<ResponseRow> {
        val (extra0, args) = where(startIso, endIso, includeIncomplete)
        val extra = extra0 + (if (onlyNumber != null) " AND n.number = $onlyNumber" else "")
        val base = listOf<Any?>(acc, form) + args
        class Head(val at: String, val done: Boolean, val cells: MutableMap<String, Cell> = HashMap())
        val rows = LinkedHashMap<Int, Head>()
        db.query("SELECT n.number, s.submitted_at, s.is_completed $FROM$extra ORDER BY n.number", base) { Triple(it.getInt(0), it.getString(1), it.bool(2)) }.forEach { (n, at, d) -> rows[n] = Head(at, d) }
        val ch = choices(acc, form, extra, args)
        db.query("SELECT n.number, a.question_id, a.kind, a.is_blank, a.text_value FROM data_answer a JOIN data_submission s ON s.account_id=a.account_id AND s.submission_id=a.submission_id " +
            "JOIN state_user_number n ON n.account_id=s.account_id AND n.submission_id=s.submission_id WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL$extra", base) {
            arrayOf(it.getInt(0), it.getString(1), it.getString(2), it.bool(3), it.str(4)) }.forEach { r ->
            val h = rows[r[0] as Int] ?: return@forEach
            val kind = r[2] as String
            h.cells[r[1] as String] = Cell(kind, r[3] as Boolean, if (kind == "text" && includeText) r[4] as String? else null, (ch[(r[0] as Int) to (r[1] as String)] ?: emptyList()).sortedBy { c -> c.first })
        }
        return rows.entries.map { (k, v) -> ResponseRow(k, v.at, v.done, v.cells) }
    }

    /** JSON original sanitizado de los mismos envíos que usa el análisis (presentes y numerados). */
    @Suppress("UNCHECKED_CAST")
    fun rawPresent(acc: String, form: String, includeIncomplete: Boolean): List<JObj> =
        db.query("SELECT r.sanitized_json FROM raw_submission r JOIN data_submission s ON s.account_id=r.account_id AND s.submission_id=r.submission_id JOIN state_user_number n ON n.account_id=s.account_id " +
            "AND n.submission_id=s.submission_id WHERE s.account_id=? AND s.form_id=? AND s.missing_at_source_at IS NULL" + (if (includeIncomplete) "" else " AND s.is_completed = 1"), listOf(acc, form)) { Json.parse(it.getString(0)) as JObj }

    // ---- diagnóstico (solo conteos) ----
    fun count(table: String): Int {
        require(table in setOf("data_account", "data_form", "data_submission"))
        return db.queryOne("SELECT COUNT(*) FROM $table") { it.getInt(0) } ?: 0
    }
    fun lastErrors(): List<String> = db.query("SELECT last_error, COUNT(*) FROM state_sync WHERE last_error IS NOT NULL GROUP BY last_error") { "${it.getString(0)}: ${it.getInt(1)}" }
}

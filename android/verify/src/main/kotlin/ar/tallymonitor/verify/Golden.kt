package ar.tallymonitor.verify

import ar.tallymonitor.core.JObj
import ar.tallymonitor.core.Json
import ar.tallymonitor.core.QuestionRow
import ar.tallymonitor.sync.Normalizer
import ar.tallymonitor.sync.Numbering
import ar.tallymonitor.sync.Sanitizer
import java.io.File

/**
 * Comprobaciones contra los vectores «golden» generados ejecutando el código Python de referencia (carpeta `golden/`).
 * Cada función devuelve la lista de diferencias; vacía = idéntico.
 */
class Golden(val dir: File) {
    fun read(name: String): Any? = Json.parse(File(dir, name).readText(Charsets.UTF_8))

    @Suppress("UNCHECKED_CAST")
    fun obj(name: String): JObj = read(name) as JObj

    /** Compara dos valores JSON; los objetos no dependen del orden de las claves. Los números se comparan por valor. */
    fun diff(path: String, a: Any?, b: Any?, out: MutableList<String>, tolerance: Double = 0.0) {
        when {
            a is Map<*, *> && b is Map<*, *> -> {
                for (k in (a.keys + b.keys).map { it.toString() }.distinct()) {
                    if (!a.containsKey(k)) out += "$path.$k: falta en el resultado (esperado ${b[k]})"
                    else if (!b.containsKey(k)) out += "$path.$k: sobra en el resultado (${a[k]})"
                    else diff("$path.$k", a[k], b[k], out, tolerance)
                }
            }
            a is List<*> && b is List<*> -> {
                if (a.size != b.size) out += "$path: largo ${a.size} ≠ ${b.size}"
                else a.indices.forEach { diff("$path[$it]", a[it], b[it], out, tolerance) }
            }
            a is Number && b is Number -> if (Math.abs(a.toDouble() - b.toDouble()) > tolerance) out += "$path: $a ≠ $b"
            a != b -> out += "$path: «$a» ≠ «$b»"
        }
    }

    fun numbering(): List<String> {
        val out = ArrayList<String>()
        val g = obj("numbering.json")
        for (e in g["format"] as List<*>) {
            val m = e as Map<*, *>
            val n = (m["n"] as Number).toInt()
            val got = Numbering.formatUserLabel(n)
            if (got != m["label"]) out += "format($n): «$got» ≠ «${m["label"]}»"
        }
        for (e in g["parse"] as List<*>) {
            val m = e as Map<*, *>
            val got = Numbering.parseUserLabel(m["text"] as String)
            val exp = (m["n"] as Number?)?.toInt()
            if (got != exp) out += "parse(«${m["text"]}»): $got ≠ $exp"
        }
        return out
    }

    private fun toObjList(v: Any?): List<JObj> = (v as List<*>).map { it as JObj }

    fun sanitizer(): List<String> {
        val out = ArrayList<String>()
        val exp = obj("expected_sanitized.json")
        val form = Sanitizer.sanitizeForm(obj("fixture_form_detail.json"))
        diff("form", form.data, exp["form"], out)
        diff("form_unknown", form.unknownFields, exp["form_unknown"], out)
        val qs = Sanitizer.sanitizeQuestions(obj("fixture_questions.json"))
        diff("questions", qs.data, exp["questions"], out)
        diff("questions_unknown", qs.unknownFields, exp["questions_unknown"], out)
        val subs = toObjList(read("fixture_submissions.json")).map { Sanitizer.sanitizeSubmission(it) }
        diff("submissions", subs.map { it.data }, exp["submissions"], out)
        diff("submissions_unknown", subs.map { it.unknownFields }, exp["submissions_unknown"], out)
        return out
    }

    /** Normaliza el golden sanitizado y compara con `expected_normalized.json` (claves en snake_case de Python). */
    fun normalizer(): List<String> {
        val out = ArrayList<String>()
        val san = obj("expected_sanitized.json")
        @Suppress("UNCHECKED_CAST")
        val form = san["form"] as JObj
        @Suppress("UNCHECKED_CAST")
        val questions = san["questions"] as JObj
        val exp = obj("expected_normalized.json")
        diff("form_row", formMap(Normalizer.formRow(form)), exp["form_row"], out)
        val qrows = Normalizer.questionRows(form, questions)
        diff("question_rows", qrows.map { questionMap(it) }, exp["question_rows"], out)
        val byId: Map<String, QuestionRow> = qrows.associateBy { it.questionId }
        @Suppress("UNCHECKED_CAST")
        val subs = (san["submissions"] as List<JObj>).map { Normalizer.submissionRow(it, byId) }
        diff("submission_rows", subs.map { submissionMap(it) }, exp["submission_rows"], out)
        return out
    }

    private fun formMap(f: ar.tallymonitor.core.FormRow) = mapOf("form_id" to f.formId, "name" to f.name, "status" to f.status,
        "is_closed" to f.isClosed, "workspace_id" to f.workspaceId, "reported_submissions" to f.reportedSubmissions,
        "created_at" to f.createdAt, "updated_at" to f.updatedAt)

    private fun questionMap(q: QuestionRow) = mapOf("question_id" to q.questionId, "position" to q.position, "type" to q.type,
        "title" to q.title, "reported_responses" to q.reportedResponses, "group_uuid" to q.groupUuid,
        "has_other_option" to q.hasOtherOption, "is_deleted" to q.isDeleted, "options" to q.options)

    private fun submissionMap(s: ar.tallymonitor.core.SubmissionRow) = mapOf(
        "submission_id" to s.submissionId, "form_id" to s.formId, "submitted_at" to s.submittedAt, "is_completed" to s.isCompleted,
        "created_at" to s.createdAt, "updated_at" to s.updatedAt,
        "answers" to s.answers.map { a ->
            mapOf("question_id" to a.questionId, "kind" to a.kind, "text_value" to a.textValue, "is_blank" to a.isBlank,
                "raw_json" to a.rawJson, "choices" to a.choices.map { mapOf("option_text" to it.optionText, "origin" to it.origin) })
        })
}

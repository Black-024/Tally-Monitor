package ar.tallymonitor.sync

import ar.tallymonitor.core.AnswerRow
import ar.tallymonitor.core.ChoiceRow
import ar.tallymonitor.core.FormRow
import ar.tallymonitor.core.JObj
import ar.tallymonitor.core.Json
import ar.tallymonitor.core.QuestionRow
import ar.tallymonitor.core.SubmissionRow

/** Del JSON sanitizado a filas normalizadas. Reconstruible: solo depende del JSON sanitizado. */
object Normalizer {
    // Tipos de pregunta VERIFICADOS con datos reales. El resto se guarda como 'raw' sin interpretarlo.
    private val SINGLE = setOf("MULTIPLE_CHOICE")
    private val MULTI = setOf("CHECKBOXES")
    private val TEXT = setOf("TEXTAREA")
    private val OPTION_BLOCK_TYPES = setOf("CHECKBOX")

    /** Equivale al `bool()` de Python para los valores que llegan de JSON. */
    fun truthy(v: Any?): Boolean = when (v) {
        null -> false
        is Boolean -> v
        is Number -> v.toDouble() != 0.0
        is String -> v.isNotEmpty()
        is Collection<*> -> v.isNotEmpty()
        is Map<*, *> -> v.isNotEmpty()
        else -> true
    }

    @Suppress("UNCHECKED_CAST")
    private fun obj(v: Any?): JObj? = v as? Map<String, Any?>

    private fun int(v: Any?): Int? = (v as? Long)?.toInt() ?: (v as? Int)

    fun formRow(data: JObj): FormRow = FormRow(
        formId = data["id"].toString(), name = (data["name"] as? String) ?: "", status = (data["status"] as? String) ?: "",
        isClosed = truthy(data["isClosed"]), workspaceId = data["workspaceId"] as? String,
        reportedSubmissions = int(data["numberOfSubmissions"]),
        createdAt = data["createdAt"] as? String, updatedAt = data["updatedAt"] as? String,
    )

    private fun isOptionBlock(b: JObj): Boolean {
        val t = (b["type"] as? String) ?: ""
        return t.endsWith("_OPTION") || t in OPTION_BLOCK_TYPES
    }

    /** Une las preguntas con sus opciones: pregunta.fields[].blockGroupUuid == bloque.groupUuid. */
    fun questionRows(detail: JObj?, questions: JObj): List<QuestionRow> {
        val blocks = ((detail?.get("blocks") as? List<*>) ?: emptyList<Any?>()).mapNotNull { obj(it) }
        val order = HashMap<String, Int>()
        blocks.forEachIndexed { i, b -> order.putIfAbsent(b["groupUuid"].toString(), i) }
        val rows = ArrayList<QuestionRow>()
        ((questions["questions"] as? List<*>) ?: emptyList<Any?>()).forEachIndexed { idx, qAny ->
            val q = obj(qAny) ?: return@forEachIndexed
            val fields = (q["fields"] as? List<*>) ?: emptyList<Any?>()
            val group = obj(fields.firstOrNull())?.get("blockGroupUuid") as? String
            val opts = ArrayList<Pair<Int, String>>()
            var other = false
            for (b in blocks) {
                if (group != null && b["groupUuid"] == group) {
                    val p = obj(b["payload"]) ?: emptyMap()
                    val text = p["text"] as? String
                    if (isOptionBlock(b) && text != null) opts.add((int(p["index"]) ?: opts.size) to text)
                    if (truthy(p["hasOtherOption"]) || truthy(p["isOtherOption"])) other = true
                }
            }
            opts.sortBy { it.first }
            rows.add(QuestionRow(
                questionId = q["id"].toString(), position = order[group.toString()] ?: (10_000 + idx),
                type = (q["type"] as? String) ?: "", title = (q["title"] as? String) ?: "",
                reportedResponses = int(q["numberOfResponses"]), groupUuid = group, hasOtherOption = other,
                isDeleted = truthy(q["isDeleted"]), options = opts.map { it.second },
            ))
        }
        // Python ordena por (posición, id); con group=None busca la clave «None» como en la referencia.
        rows.sortWith(compareBy<QuestionRow>({ it.position }, { it.questionId }))
        return rows.mapIndexed { i, r -> r.copy(position = i) }
    }

    private fun blank(a: Any?): Boolean = when (a) {
        null -> true
        is String -> a.trim().isEmpty()
        is List<*> -> a.all { blank(it) }
        else -> false
    }

    private fun human(a: Any?): String = when (a) {
        null -> ""
        is String -> a
        is List<*> -> a.filter { !blank(it) }.joinToString(", ") { human(it) }
        else -> Json.stringify(a)
    }

    fun answerRow(response: JObj, question: QuestionRow?): AnswerRow {
        val answer = response["answer"]
        val qid = response["questionId"].toString()
        val raw = Json.stringify(answer)
        val blank = blank(answer)
        val qtype = question?.type
        if (qtype != null && qtype in TEXT && (answer == null || answer is String)) {
            return AnswerRow(qid, "text", answer as? String, blank, raw)
        }
        if (question != null && qtype != null && qtype in (SINGLE + MULTI) && (answer == null || (answer is List<*> && answer.all { it is String }))) {
            val labels = ((answer as? List<*>) ?: emptyList<Any?>()).map { it as String }.filter { it.trim().isNotEmpty() }
            val choices = labels.map { lab ->
                val origin = if (lab in question.options) "declared" else if (question.hasOtherOption) "other" else "unmatched"
                ChoiceRow(lab, origin)
            }
            val kind = if (qtype in SINGLE) "single" else "multi"
            return AnswerRow(qid, kind, human(labels).ifEmpty { null }, blank, raw, choices)
        }
        return AnswerRow(qid, "raw", human(answer).ifEmpty { null }, blank, raw)
    }

    fun submissionRow(sub: JObj, questions: Map<String, QuestionRow>): SubmissionRow {
        val answers = ((sub["responses"] as? List<*>) ?: emptyList<Any?>()).mapNotNull { obj(it) }
            .map { answerRow(it, questions[it["questionId"].toString()]) }
        val submitted = (sub["submittedAt"] as? String)?.takeIf { it.isNotEmpty() } ?: (sub["createdAt"] as? String) ?: ""
        return SubmissionRow(
            submissionId = sub["id"].toString(), formId = (sub["formId"] as? String) ?: "", submittedAt = submitted,
            isCompleted = truthy(sub["isCompleted"]), createdAt = sub["createdAt"] as? String,
            updatedAt = sub["updatedAt"] as? String, answers = answers,
        )
    }
}

package ar.tallymonitor.sync

import ar.tallymonitor.core.JObj

/**
 * Lista blanca de campos («JSON original sanitizado»). Lo que no figura en la lista NO se guarda.
 * De lo descartado y de lo desconocido solo se informa el NOMBRE del campo, nunca su valor.
 */
const val SANITIZER_VERSION = 2

data class Sanitized(val data: JObj, val unknownFields: List<String> = emptyList())

object Sanitizer {
    private val FORM_KEEP = setOf("id", "name", "status", "isClosed", "numberOfSubmissions", "createdAt", "updatedAt", "workspaceId")
    private val FORM_DROP = setOf("createdByUserId", "organizationId", "folderId", "index", "isNameModifiedByUser", "hasDraftBlocks", "settings", "blocks")
    private val BLOCK_KEEP = setOf("type", "groupType", "uuid", "groupUuid")
    private val PAYLOAD_KEEP = setOf("text", "index", "isHidden", "isRequired", "hasOtherOption", "isFirst", "isLast",
        "logicalOperator", "conditionals", "actions", "updateUuid", "isOtherOption")
    private val PAYLOAD_DROP = setOf("safeHTMLSchema", "placeholder", "button", "logo", "title", "isFolded")
    private val Q_KEEP = setOf("id", "type", "title", "numberOfResponses", "isDeleted", "fields")
    private val Q_DROP = setOf("formId", "createdAt", "updatedAt", "isTitleModifiedByUser")
    private val FIELD_KEEP = setOf("blockGroupUuid", "questionType", "type", "uuid")
    private val FIELD_DROP = setOf("title")
    private val SUB_KEEP = setOf("id", "formId", "isCompleted", "submittedAt", "createdAt", "updatedAt", "responses")
    private val SUB_DROP = setOf("respondentId", "previewUrl", "pdfUrl", "locale")
    private val RESP_KEEP = setOf("questionId", "answer")
    private val RESP_DROP = setOf("id", "formId", "respondentId", "submissionId", "sessionUuid", "createdAt", "updatedAt")

    private fun unknown(raw: JObj, keep: Set<String>, drop: Set<String>, where: String): List<String> =
        raw.keys.filter { it !in keep && it !in drop }.map { "$where.$it" }

    private fun pick(raw: JObj, keep: Set<String>): MutableMap<String, Any?> {
        val out = LinkedHashMap<String, Any?>()
        for ((k, v) in raw) if (k in keep) out[k] = v
        return out
    }

    @Suppress("UNCHECKED_CAST")
    private fun obj(v: Any?): JObj? = v as? Map<String, Any?>

    fun sanitizeForm(raw: JObj): Sanitized {
        val unknown = unknown(raw, FORM_KEEP, FORM_DROP, "form").toMutableList()
        val out = pick(raw, FORM_KEEP)
        val blocksRaw = raw["blocks"]
        if (blocksRaw is List<*>) {
            val blocks = ArrayList<Any?>()
            for (b in blocksRaw) {
                val bo = obj(b) ?: continue
                val (sb, u) = sanitizeBlock(bo)
                blocks.add(sb); unknown += u
            }
            out["blocks"] = blocks
        }
        return Sanitized(out, unknown.distinct())
    }

    private fun sanitizeBlock(b: JObj): Pair<JObj, List<String>> {
        val unknown = unknown(b, BLOCK_KEEP + "payload", emptySet(), "block").toMutableList()
        val out = pick(b, BLOCK_KEEP)
        val payload = obj(b["payload"])
        if (payload != null) {
            unknown += unknown(payload, PAYLOAD_KEEP, PAYLOAD_DROP, "block.payload")
            val p = pick(payload, PAYLOAD_KEEP)
            if ("conditionals" in p) p["conditionals"] = sanitizeConditionals(p["conditionals"])
            if ("actions" in p) p["actions"] = sanitizeActions(p["actions"])
            out["payload"] = p
        }
        return out to unknown
    }

    private fun sanitizeConditionals(items: Any?): List<Any?> {
        val out = ArrayList<Any?>()
        for (c in (items as? List<*>) ?: emptyList<Any?>()) {
            val co = obj(c) ?: continue
            val p = obj(co["payload"]) ?: emptyMap()
            val field = obj(p["field"]) ?: emptyMap()
            val value = p["value"]
            out.add(linkedMapOf(
                "type" to co["type"], "uuid" to co["uuid"],
                "payload" to linkedMapOf(
                    "comparison" to p["comparison"],
                    "value" to (if (value is String && value.length <= 200) value else null),
                    "field" to pick(field, setOf("blockGroupUuid", "questionType", "type", "uuid")),
                ),
            ))
        }
        return out
    }

    private fun sanitizeActions(items: Any?): List<Any?> {
        val out = ArrayList<Any?>()
        for (a in (items as? List<*>) ?: emptyList<Any?>()) {
            val ao = obj(a) ?: continue
            val p = obj(ao["payload"]) ?: emptyMap()
            val blocks = p["showBlocks"]
            out.add(linkedMapOf(
                "type" to ao["type"],
                "payload" to linkedMapOf("showBlocks" to (if (blocks is List<*>) blocks.filterIsInstance<String>() else emptyList<String>())),
            ))
        }
        return out
    }

    fun sanitizeQuestions(raw: JObj): Sanitized {
        val unknown = unknown(raw, setOf("questions", "hasResponses"), emptySet(), "questions").toMutableList()
        val questions = ArrayList<Any?>()
        for (q in (raw["questions"] as? List<*>) ?: emptyList<Any?>()) {
            val qo = obj(q) ?: continue
            unknown += unknown(qo, Q_KEEP, Q_DROP, "question")
            val sq = pick(qo, Q_KEEP)
            val fields = ArrayList<Any?>()
            for (f in (qo["fields"] as? List<*>) ?: emptyList<Any?>()) {
                val fo = obj(f) ?: continue
                unknown += unknown(fo, FIELD_KEEP, FIELD_DROP, "question.field")
                fields.add(pick(fo, FIELD_KEEP))
            }
            sq["fields"] = fields
            questions.add(sq)
        }
        val out = linkedMapOf<String, Any?>("questions" to questions)
        if ("hasResponses" in raw) out["hasResponses"] = Normalizer.truthy(raw["hasResponses"])
        return Sanitized(out, unknown.distinct())
    }

    fun sanitizeSubmission(raw: JObj): Sanitized {
        val unknown = unknown(raw, SUB_KEEP, SUB_DROP, "submission").toMutableList()
        val out = pick(raw, SUB_KEEP - "responses")
        val responses = ArrayList<Any?>()
        for (r in (raw["responses"] as? List<*>) ?: emptyList<Any?>()) {
            val ro = obj(r) ?: continue
            unknown += unknown(ro, RESP_KEEP, RESP_DROP, "response")
            responses.add(pick(ro, RESP_KEEP))
        }
        out["responses"] = responses
        return Sanitized(out, unknown.distinct())
    }
}

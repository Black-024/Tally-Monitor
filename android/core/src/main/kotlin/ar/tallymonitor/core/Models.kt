package ar.tallymonitor.core

data class FormRow(
    val formId: String, val name: String, val status: String, val isClosed: Boolean, val workspaceId: String?,
    val reportedSubmissions: Int?, val createdAt: String?, val updatedAt: String?,
)

data class QuestionRow(
    val questionId: String, val position: Int, val type: String, val title: String, val reportedResponses: Int?,
    val groupUuid: String?, val hasOtherOption: Boolean, val isDeleted: Boolean, val options: List<String> = emptyList(),
)

/** origin: declared (está en las opciones) | other (texto de «Otro») | unmatched (no coincide con nada). */
data class ChoiceRow(val optionText: String, val origin: String)

/** kind: text | single | multi | raw. */
data class AnswerRow(
    val questionId: String, val kind: String, val textValue: String?, val isBlank: Boolean, val rawJson: String,
    val choices: List<ChoiceRow> = emptyList(),
)

data class SubmissionRow(
    val submissionId: String, val formId: String, val submittedAt: String, val isCompleted: Boolean,
    val createdAt: String?, val updatedAt: String?, val answers: List<AnswerRow> = emptyList(),
)

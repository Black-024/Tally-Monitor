package ar.tallymonitor.analysis

/** Una encuesta tal como la ve el chequeo de avisos: lo que informa Tally, lo guardado y si está archivada. */
data class PendingInput(val reported: Int?, val local: Int, val archived: Boolean)

data class PendingTotals(val total: Int, val surveys: Int)

/** Qué hacer tras un chequeo: avisar o no, y qué total guardar como «último avisado». */
data class NotifyDecision(val notify: Boolean, val storeTotal: Int)

/** Lógica pura de los avisos de respuestas nuevas (spec 1.1 §4), sin Android: se puede probar con JUnit. */
object NewResponses {
    /** Suma max(0, reportadas − locales) de las encuestas NO archivadas; cuenta las que aportan algo. */
    fun totals(items: Collection<PendingInput>): PendingTotals {
        var total = 0L; var surveys = 0
        for (i in items) {
            if (i.archived) continue
            val extra = maxOf(0, (i.reported ?: 0) - i.local)
            if (extra > 0) { total += extra; surveys++ }
        }
        return PendingTotals(minOf(total, 999_999_999L).toInt(), surveys)
    }

    /** Avisa solo si el total subió respecto del último avisado y es > 0. Siempre se guarda el total actual (si bajó a 0, 0). */
    fun decide(current: PendingTotals, notifiedTotal: Int): NotifyDecision =
        NotifyDecision(current.total > 0 && current.total > notifiedTotal, current.total)

    /** («3 respuestas nuevas en 2 encuestas»). */
    fun title(t: PendingTotals): String =
        "${t.total} ${if (t.total == 1) "respuesta nueva" else "respuestas nuevas"} en ${t.surveys} ${if (t.surveys == 1) "encuesta" else "encuestas"}"

    const val BODY = "Tocá para abrir Tally Monitor"
}

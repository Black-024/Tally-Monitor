package ar.tallymonitor.export

import ar.tallymonitor.analysis.Cell
import ar.tallymonitor.analysis.ResponseRow
import ar.tallymonitor.analysis.SurveyAnalysis
import java.io.OutputStream
import java.time.LocalDateTime
import java.time.ZoneId

const val PRIVACY_NOTE = "Las respuestas de texto libre pueden contener datos personales escritos voluntariamente por las " +
    "personas. El enmascarado automático ayuda, pero no garantiza ocultar todo: revisá el archivo antes de compartirlo."

/** Libro de Excel de una encuesta: resumen, estadísticas, línea de tiempo y respuestas (o fichas individuales). */
object XlsxExport {
    private fun s(t: String) = XCell.s(t)

    /** Texto de una respuesta para una celda (null = vacía). */
    fun cellText(cell: Cell?, includeText: Boolean, mask: Boolean): String? {
        if (cell == null || cell.isBlank) return null
        return when (cell.kind) {
            "single", "multi" -> cell.choices.joinToString(" | ") { it.first }.ifEmpty { null }
            "text" -> if (!includeText || cell.text == null) null else if (mask) Masking.maskText(cell.text!!) else cell.text
            else -> null
        }
    }

    fun write(out: OutputStream, surveyName: String, analysis: SurveyAnalysis, rows: List<ResponseRow>, labelFor: (Int) -> String,
              tz: ZoneId, options: ExportOptions, generatedAtLocal: LocalDateTime, cancel: CancelCheck = CancelCheck { false }) {
        val book = XlsxBook(out)
        val o = analysis.overview
        val individual = options.scope == "individual"

        // ---- Resumen ----
        val ws = book.sheet("Resumen", listOf(26, 60))
        ws.row(listOf(XCell.b("Tally Monitor — exportación")))
        ws.row(emptyList())
        val items: List<Pair<String, XCell?>> = listOf(
            "Encuesta" to s(surveyName), "Período" to s(analysis.filter.label),
            "Envíos incompletos" to s(if (options.includeIncomplete) "incluidos" else "excluidos"),
            "Generado" to XCell.Date(generatedAtLocal),
            "Respuestas" to XCell.n(o.total), "Completas" to XCell.n(o.completed), "Incompletas" to XCell.n(o.partial),
            "Promedio por día" to o.perDay?.let { XCell.n(Math.round(it * 100) / 100.0) },
            "Primera respuesta" to o.firstAt?.let { XCell.Date(Individual.localTime(it, tz)) },
            "Última respuesta" to o.lastAt?.let { XCell.Date(Individual.localTime(it, tz)) },
            "Respuestas de texto" to s(if (options.includeText) "incluidas" + (if (options.maskPersonal) ", con datos personales enmascarados" else ", SIN enmascarar") else "no incluidas"),
        )
        for ((k, v) in items) ws.row(listOf(XCell.b(k), v))
        ws.row(listOf(s(PRIVACY_NOTE)), height = 62)
        ws.mergeAcross(items.size + 4, 1, 2)

        if (individual) { individualSheets(book, analysis, rows, labelFor, tz, options, cancel); book.finish(); return }

        // ---- Estadísticas ----
        val st = book.sheet("Estadísticas", listOf(6, 50, 42, 12, 24), freezeRow = true)
        st.row(listOf("N.º", "Pregunta", "Opción", "Cantidad", "% de quienes respondieron").map { XCell.h(it) })
        analysis.questions.forEachIndexed { idx, q ->
            val title = q.title.ifEmpty { "(sin título)" } + (if (q.isDeleted) " (eliminada)" else "")
            st.row(listOf(XCell.n(idx + 1), XCell.b(title),
                s("Respondieron ${q.answered} · sin respuesta ${q.blank}" + (if (q.notAsked > 0) " · no la vieron ${q.notAsked}" else ""))))
            when (q.kind) {
                "single", "multi" -> {
                    for (opt in q.options) st.row(listOf(null, null, s(opt.text), XCell.n(opt.count), XCell.Pct((opt.pct ?: 0.0) / 100.0)))
                    for ((label, n) in listOf("Otro (texto escrito)" to q.otherCount, "Opciones que ya no existen" to q.orphanCount)) {
                        if (n > 0) st.row(listOf(null, null, s(label), XCell.n(n), XCell.Pct(if (q.answered > 0) n.toDouble() / q.answered else 0.0)))
                    }
                }
                "text" -> st.row(listOf(null, null, s("Largo promedio (caracteres)"), q.avgLen?.let { XCell.n(Math.round(it * 10) / 10.0) }))
                else -> st.row(listOf(null, null, s("Tipo de pregunta sin análisis propio")))
            }
        }

        // ---- Línea de tiempo ----
        val tl = book.sheet("En el tiempo", listOf(24, 14), freezeRow = true)
        tl.row(listOf(XCell.h("Intervalo (hora local)"), XCell.h("Respuestas")))
        val kind = when (analysis.timeline.bucket) { "hour" -> "datetime"; "month" -> "month"; else -> "date" }
        for (p in analysis.timeline.points) tl.row(listOf(XCell.Date(p.start, kind), XCell.n(p.count)))

        // ---- Respuestas ----
        wideTable(book, analysis, rows, labelFor, tz, options, cancel)
        book.finish()
    }

    private fun wideTable(book: XlsxBook, analysis: SurveyAnalysis, rows: List<ResponseRow>, labelFor: (Int) -> String, tz: ZoneId,
                          options: ExportOptions, cancel: CancelCheck) {
        val shown = analysis.questions.withIndex().filter { !(it.value.kind == "text" && !options.includeText) }
        val rs = book.sheet("Respuestas", listOf(14, 20, 12) + shown.map { 32 }, freezeRow = true, freezeCol = true)
        rs.row((listOf("Usuario", "Fecha y hora (local)", "Estado") +
            shown.map { (i, q) -> "${i + 1}. ${q.title.ifEmpty { "(sin título)" }}" + (if (q.isDeleted) " (eliminada)" else "") }).map { XCell.h(it) })
        rows.forEachIndexed { n, row ->
            if (n % 500 == 0 && cancel.isCancelled()) throw ar.tallymonitor.core.TallyMonitorException(ar.tallymonitor.core.ErrorCode.EXPORT_CANCELLED)
            val cells = ArrayList<XCell?>()
            cells += s(labelFor(row.key)); cells += XCell.Date(Individual.localTime(row.submittedAt, tz))
            cells += s(if (row.isCompleted) "Completa" else "Incompleta")
            for ((_, q) in shown) cells += cellText(row.cells[q.questionId], options.includeText, options.maskPersonal)?.let { s(it) }
            rs.row(cells)
        }
        rs.autoFilter()
    }

    /** Respuestas individuales: tabla ancha (una fila por persona) y «Detalle» (una fila por respuesta). */
    private fun individualSheets(book: XlsxBook, analysis: SurveyAnalysis, rows: List<ResponseRow>, labelFor: (Int) -> String, tz: ZoneId,
                                 options: ExportOptions, cancel: CancelCheck) {
        wideTable(book, analysis, rows, labelFor, tz, options, cancel)
        val ds = book.sheet("Detalle", listOf(14, 20, 6, 48, 60), freezeRow = true)
        ds.row(listOf("Usuario", "Fecha y hora (local)", "N.º", "Pregunta", "Respuesta").map { XCell.h(it) })
        rows.forEachIndexed { n, row ->
            if (n % 500 == 0 && cancel.isCancelled()) throw ar.tallymonitor.core.TallyMonitorException(ar.tallymonitor.core.ErrorCode.EXPORT_CANCELLED)
            val card = Individual.card(analysis, row, tz, labelFor, options.includeText, options.maskPersonal)
            for (it in card.items) ds.row(listOf(s(card.label), XCell.Date(card.whenLocal), XCell.n(it.number), s(it.title), s(it.text)))
        }
        ds.autoFilter()
    }
}

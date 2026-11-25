package ar.tallymonitor.export

import ar.tallymonitor.analysis.Cell
import ar.tallymonitor.analysis.QuestionStats
import ar.tallymonitor.analysis.ResponseRow
import ar.tallymonitor.analysis.SurveyAnalysis
import ar.tallymonitor.analysis.Timeline
import ar.tallymonitor.core.ErrorCode
import ar.tallymonitor.core.TallyMonitorException
import java.io.OutputStream
import java.time.LocalDateTime
import java.time.ZoneId

/** Colores del PDF (mismos que la paleta de la aplicación). */
class PdfPalette(style: String) {
    val dark = style != "light"
    private fun h(d: String, l: String) = Rgb.hex(if (dark) d else l)
    val bg = h("#0b0b0f", "#ffffff"); val card = h("#17171f", "#f7fbfa"); val card2 = h("#1f1f2b", "#e6f2f0"); val line = h("#2e2b45", "#c8dfdb")
    val tx = h("#f4f2ff", "#1b2b29"); val mu = h("#aaa5c4", "#4d6965"); val dim = h("#827d9c", "#7a948f")
    val accent = h("#8b7bff", "#12a198"); val action = h("#e6b84a", "#8a5a3b")
}

/** Informes PDF: resumen estadístico o fichas individuales. Mismo diseño que la versión de escritorio. */
object PdfExport {
    private const val MM = 72.0 / 25.4
    private const val LEFT = 20 * MM
    private const val CW = PdfDoc.W - 2 * LEFT
    private const val TOP = 18 * MM
    private const val BOTTOM = 20 * MM
    private const val BRAND = "Tally Monitor"

    private class Ctx(val doc: PdfDoc, val pal: PdfPalette, val cancel: CancelCheck) {
        var y = 0.0                         // cursor: distancia desde el borde superior
        fun remaining() = PdfDoc.H - BOTTOM - y
        fun check() { if (cancel.isCancelled()) throw TallyMonitorException(ErrorCode.EXPORT_CANCELLED) }
        fun newPage() { check(); doc.newPage(pal.bg) { d, n -> decorate(d, n, pal) }; y = TOP }
        fun ensure(h: Double) { if (h > remaining()) newPage() }
        fun py(fromTop: Double) = PdfDoc.H - fromTop
    }

    private fun decorate(d: PdfDoc, page: Int, pal: PdfPalette) {
        d.fillRect(0.0, PdfDoc.H - 2.4 * MM, PdfDoc.W, 2.4 * MM, pal.action)
        d.text("Página $page", LEFT, 10 * MM, PFont.REGULAR, 7.5, pal.dim)
        d.text(BRAND, PdfDoc.W - LEFT, 10 * MM, PFont.BOLD, 9.0, pal.mu, align = 2)
        val tw = PdfDoc.width(BRAND, PFont.BOLD, 9.0)
        val x = PdfDoc.W - LEFT - tw - 6.5 * MM
        if (!d.drawLogo(x, 8.8 * MM, 5 * MM, 5 * MM)) d.roundRect(x, 9.2 * MM, 4 * MM, 4 * MM, 1.2 * MM, pal.action)
    }

    /** Párrafo: dibuja y avanza el cursor. Parte entre páginas si hace falta. Devuelve la altura usada. */
    private fun para(c: Ctx, s: String, f: PFont, size: Double, leading: Double, col: Rgb, before: Double = 0.0, after: Double = 0.0, x: Double = LEFT, w: Double = CW) {
        val lines = c.doc.wrap(s, f, size, w)
        c.y += before
        for (l in lines) {
            c.ensure(leading); if (c.y == TOP && before > 0) { /* página nueva: sin espacio previo */ }
            c.doc.text(l, x, c.py(c.y + size), f, size, col); c.y += leading
        }
        c.y += after
    }

    private fun paraHeight(c: Ctx, s: String, f: PFont, size: Double, leading: Double, w: Double) = c.doc.wrap(s, f, size, w).size * leading

    private fun tiles(c: Ctx, values: List<Pair<String, String>>) {
        val h = 26.0 + 11.0 + 20.0
        c.ensure(h)
        val d = c.doc; val p = c.pal
        val top = c.py(c.y)
        d.roundRect(LEFT, top - h, CW, h, 10.0, p.card)
        val cw = CW / values.size
        values.forEachIndexed { i, (v, l) ->
            val cx = LEFT + cw * i + cw / 2
            d.text(v, cx, top - 10 - 20, PFont.BOLD, 20.0, p.tx, 1)
            d.text(l, cx, top - 10 - 26 - 8, PFont.REGULAR, 8.0, p.mu, 1)
            if (i > 0) d.line(LEFT + cw * i, top - 6, LEFT + cw * i, top - h + 6, p.line, 0.6)
        }
        c.y += h
    }

    private fun timelineChart(c: Ctx, t: Timeline) {
        val h = 130.0; val left = 26.0; val bottom = 18.0
        c.ensure(h)
        val d = c.doc; val p = c.pal
        val top = c.py(c.y)                 // esquina superior del dibujo
        val base = top - h
        val plotW = CW - left - 4; val plotH = h - bottom - 8
        d.line(LEFT + left, base + bottom, LEFT + left + plotW, base + bottom, p.line)
        val series = t.points.map { pt ->
            val label = when (t.bucket) { "hour" -> "%02d/%02d %02d:00".format(pt.start.dayOfMonth, pt.start.monthValue, pt.start.hour)
                "month" -> "%02d/%d".format(pt.start.monthValue, pt.start.year) else -> "%02d/%02d".format(pt.start.dayOfMonth, pt.start.monthValue) }
            label to pt.count
        }
        if (series.isNotEmpty()) {
            val peak = maxOf(1, series.maxOf { it.second })
            d.text(peak.toString(), LEFT + left - 4, base + h - 12, PFont.REGULAR, 7.0, p.dim, 2)
            d.text("0", LEFT + left - 4, base + bottom - 2, PFont.REGULAR, 7.0, p.dim, 2)
            val n = series.size; val slot = plotW / n; val bw = maxOf(1.5, minOf(20.0, slot * 0.7))
            series.forEachIndexed { i, (_, cnt) ->
                if (cnt > 0) {
                    val bh = maxOf(2.0, plotH * cnt / peak)
                    d.roundRect(LEFT + left + i * slot + (slot - bw) / 2, base + bottom, bw, bh, minOf(3.0, bw / 2), p.accent)
                }
            }
            for (i in sortedSetOf(0, n / 2, n - 1)) d.text(series[i].first, LEFT + left + i * slot + slot / 2, base + 5, PFont.REGULAR, 7.0, p.dim, 1)
        }
        c.y += h
    }

    private fun barRows(q: QuestionStats): List<Triple<String, Int, Double>> {
        val base = q.answered
        val f = { n: Int -> if (base > 0) n.toDouble() / base else 0.0 }
        val rows = ArrayList<Triple<String, Int, Double>>()
        for (o in q.options) rows += Triple(o.text, o.count, f(o.count))
        if (q.otherCount > 0) rows += Triple("Otro (texto escrito)", q.otherCount, f(q.otherCount))
        if (q.orphanCount > 0) rows += Triple("Opciones que ya no existen", q.orphanCount, f(q.orphanCount))
        return rows
    }

    private fun bars(c: Ctx, rows: List<Triple<String, Int, Double>>) {
        val rowH = 18.0
        val d = c.doc; val p = c.pal
        val labelW = CW * 0.36; val valueW = 78.0
        val barX = LEFT + labelW + 8; val barW = CW - labelW - valueW - 16
        for ((text, count, frac) in rows) {
            c.ensure(rowH)
            val top = c.py(c.y); val y = top - rowH
            var shown = text.replace('\n', ' ')
            val full = shown
            while (shown.length > 3 && PdfDoc.width(shown, PFont.REGULAR, 8.5) > labelW) shown = shown.dropLast(1)
            d.text(if (shown == full) shown else shown.trimEnd() + "…", LEFT, y + 5, PFont.REGULAR, 8.5, p.tx)
            d.roundRect(barX, y + 3, barW, 10.0, 5.0, p.card2)
            if (count > 0 && frac > 0) d.roundRect(barX, y + 3, maxOf(3.0, barW * minOf(1.0, frac)), 10.0, 5.0, p.accent)
            d.text("$count · ${Format.pct(frac * 100)}", LEFT + CW, y + 5, PFont.REGULAR, 8.5, p.mu, 2)
            c.y += rowH
        }
    }

    fun write(out: OutputStream, surveyName: String, analysis: SurveyAnalysis, rows: List<ResponseRow>, labelFor: (Int) -> String, tz: ZoneId,
              options: ExportOptions, generatedAtLocal: LocalDateTime, logo: PdfImage?, cancel: CancelCheck = CancelCheck { false }) {
        val pal = PdfPalette(options.style)
        val individual = options.scope == "individual"
        val doc = PdfDoc(out, (if (individual) "Respuestas — " else "Informe — ") + surveyName, BRAND, logo)
        val c = Ctx(doc, pal, cancel)
        c.newPage()
        if (individual) individualBody(c, surveyName, analysis, rows, labelFor, tz, options, generatedAtLocal)
        else summaryBody(c, surveyName, analysis, rows, tz, options, generatedAtLocal)
        doc.finish()
    }

    private fun summaryBody(c: Ctx, name: String, a: SurveyAnalysis, rows: List<ResponseRow>, tz: ZoneId, o: ExportOptions, gen: LocalDateTime) {
        val p = c.pal; val ov = a.overview
        para(c, name, PFont.BOLD, 24.0, 28.0, p.tx, after = 2.0)
        para(c, "${a.filter.label} · envíos incompletos ${if (o.includeIncomplete) "incluidos" else "excluidos"} · generado el ${Format.dt(gen)}", PFont.REGULAR, 8.0, 11.0, p.mu, after = 10.0)
        tiles(c, listOf(ov.total.toString() to "Respuestas", ov.completed.toString() to "Completas", ov.partial.toString() to "Incompletas", Format.dec(ov.perDay, 2) to "Promedio por día"))
        if (ov.firstAt != null && ov.lastAt != null) {
            para(c, "Primera respuesta: ${Format.dt(Individual.localTime(ov.firstAt!!, tz))} · Última: ${Format.dt(Individual.localTime(ov.lastAt!!, tz))}", PFont.REGULAR, 8.0, 11.0, p.mu, before = 4.0)
        }
        if (ov.total == 0) { para(c, "No hay respuestas en este período.", PFont.REGULAR, 9.5, 13.0, p.tx, before = 8.0); return }
        val bucket = when (a.timeline.bucket) { "hour" -> "por hora"; "day" -> "por día"; "month" -> "por mes"; else -> "" }
        c.ensure(160.0); para(c, "Respuestas en el tiempo · $bucket", PFont.BOLD, 13.0, 16.0, p.tx, before = 14.0, after = 6.0)
        timelineChart(c, a.timeline)
        c.ensure(40.0); para(c, "Preguntas", PFont.BOLD, 13.0, 16.0, p.tx, before = 14.0, after = 6.0)
        val byQ = HashMap<String, MutableList<Cell>>()
        for (r in rows) for ((qid, cell) in r.cells) byQ.getOrPut(qid) { ArrayList() }.add(cell)
        a.questions.forEachIndexed { idx, q ->
            c.check()
            val head = "${idx + 1}. ${q.title.ifEmpty { "(sin título)" }}" + (if (q.isDeleted) " (eliminada)" else "")
            val counts = "${q.answered} respondieron · ${q.blank} sin respuesta" + (if (q.notAsked > 0) " · ${q.notAsked} no la vieron" else "")
            when (q.kind) {
                "single", "multi" -> {
                    val br = barRows(q)
                    c.ensure(minOf(10 + 13 + 2 + 11 + 4 + br.size * 18.0, 700.0))      // mantiene el bloque junto si entra en una página
                    para(c, head, PFont.BOLD, 10.5, 13.0, p.tx, before = 10.0, after = 2.0); para(c, counts, PFont.REGULAR, 8.0, 11.0, p.mu, after = 4.0)
                    bars(c, br)
                }
                "text" -> {
                    c.ensure(55.0)
                    para(c, head, PFont.BOLD, 10.5, 13.0, p.tx, before = 10.0, after = 2.0); para(c, counts, PFont.REGULAR, 8.0, 11.0, p.mu, after = 4.0)
                    para(c, "Largo promedio: ${q.avgLen?.let { Format.dec(it, 0) } ?: "—"} caracteres · máximo: ${q.maxLen ?: 0}", PFont.REGULAR, 9.5, 13.0, p.tx)
                    if (o.includeText) {
                        val texts = (byQ[q.questionId] ?: emptyList<Cell>()).mapNotNull { XlsxExport.cellText(it, true, o.maskPersonal) }
                        for (t in texts.take(200)) para(c, "• " + t.take(600), PFont.REGULAR, 9.5, 13.0, p.tx)
                        if (texts.size > 200) para(c, "… y ${texts.size - 200} más (están en el Excel).", PFont.REGULAR, 8.0, 11.0, p.mu)
                    }
                }
                else -> {
                    c.ensure(60.0)
                    para(c, head, PFont.BOLD, 10.5, 13.0, p.tx, before = 10.0, after = 2.0); para(c, counts, PFont.REGULAR, 8.0, 11.0, p.mu, after = 4.0)
                    para(c, "Tipo de pregunta sin análisis propio (${q.type}).", PFont.REGULAR, 8.0, 11.0, p.mu)
                }
            }
        }
        if (o.includeText) para(c, PRIVACY_NOTE, PFont.REGULAR, 8.0, 11.0, p.mu, before = 10.0)
    }

    // ---------- fichas individuales ----------
    private const val PAD = 12.0
    private class ItemBox(val q: List<String>, val a: List<String>, val note: Boolean) {
        val qh = q.size * 10.5 + 6 + 1
        val ah = a.size * 13.5 + 12
        val h get() = qh + ah
    }

    private fun individualBody(c: Ctx, name: String, a: SurveyAnalysis, rows: List<ResponseRow>, labelFor: (Int) -> String, tz: ZoneId, o: ExportOptions, gen: LocalDateTime) {
        val p = c.pal
        val cards = rows.map { Individual.card(a, it, tz, labelFor, o.includeText, o.maskPersonal) }
        val span = if (cards.isNotEmpty()) " · del ${Format.dt(cards.minOf { it.whenLocal })} al ${Format.dt(cards.maxOf { it.whenLocal })}" else ""
        para(c, name, PFont.BOLD, 24.0, 28.0, p.tx, after = 2.0)
        para(c, "${cards.size} respuestas individuales$span · ${a.filter.label} · generado el ${Format.dt(gen)}", PFont.REGULAR, 8.0, 11.0, p.mu, after = 4.0)
        if (o.includeText) para(c, PRIVACY_NOTE, PFont.REGULAR, 9.0, 12.0, p.dim, after = 0.0)
        c.y += 10.0
        if (cards.isEmpty()) { para(c, "No hay respuestas en este período.", PFont.REGULAR, 9.5, 13.0, p.tx); return }
        for (card in cards) { c.check(); drawCard(c, card); c.y += 10.0 }
    }

    private fun drawCard(c: Ctx, card: ResponseCard) {
        val d = c.doc; val p = c.pal
        val whoW = CW * 0.62 - PAD; val whenW = CW * 0.38 - PAD
        val whenText = Format.dt(card.whenLocal) + (if (card.isCompleted) "" else " · incompleta")
        val headH = 10.0 + 15.0 + 4.0
        val boxes = card.items.map {
            ItemBox(d.wrap("${it.number}. ${it.title}", PFont.REGULAR, 8.0, CW - 2 * PAD), d.wrap(it.text, if (it.isNote) PFont.OBLIQUE else PFont.REGULAR, 10.0, CW - 2 * PAD - 8), it.isNote)
        }
        val total = headH + (if (boxes.isEmpty()) 13.0 + 10 else boxes.sumOf { it.h }) + 10.0
        if (total > c.remaining() && (card.items.size <= 10 && total < PdfDoc.H - TOP - BOTTOM)) c.newPage()
        var i = 0; var first = true
        do {
            // arma un tramo de la ficha que entre en lo que queda de página
            var h = (if (first) headH else 10.0)
            val start = i
            while (i < boxes.size) {
                if (i > start && h + boxes[i].h + 10 > c.remaining()) break
                if (i == start && h + boxes[i].h + 10 > c.remaining() && c.remaining() < PdfDoc.H - TOP - BOTTOM - 1) { if (!first || start > 0) { c.newPage(); h = if (first) headH else 10.0 } else if (h + boxes[i].h + 10 > c.remaining()) { c.newPage() } }
                h += boxes[i].h; i++
                if (h > PdfDoc.H - TOP - BOTTOM) break
            }
            if (boxes.isEmpty()) h += 13.0
            h += 10.0
            if (h > c.remaining()) c.newPage()
            val top = c.py(c.y)
            d.roundRect(LEFT, top - h, CW, h, 12.0, p.card)
            var yy = top
            if (first) {
                d.text(card.label, LEFT + PAD, yy - 10 - 12.5, PFont.BOLD, 12.5, p.action)
                d.text(whenText.let { t -> if (PdfDoc.width(t, PFont.REGULAR, 8.0) > whenW) t.take(30) else t }, LEFT + CW - PAD, yy - 10 - 8, PFont.REGULAR, 8.0, p.dim, 2)
                if (PdfDoc.width(card.label, PFont.BOLD, 12.5) > whoW) { /* etiquetas cortas: no ocurre */ }
                yy -= headH
            } else yy -= 10.0
            for (k in start until i) {
                val b = boxes[k]
                yy -= 6.0
                for (l in b.q) { yy -= 10.5; d.text(l, LEFT + PAD, yy + 2.5, PFont.REGULAR, 8.0, p.mu) }
                yy -= 1.0
                val ah = b.ah
                d.fillRect(LEFT, yy - ah, CW, ah, p.card2)
                d.fillRect(LEFT, yy - ah, 3.0, ah, p.accent)
                var ty = yy - 6.0
                for (l in b.a) { ty -= 13.5; d.text(l, LEFT + PAD, ty + 3.5, if (b.note) PFont.OBLIQUE else PFont.REGULAR, 10.0, if (b.note) p.dim else p.tx) }
                yy -= ah
            }
            if (boxes.isEmpty()) d.text("Sin respuestas registradas.", LEFT + PAD, yy - 13.0 + 3.0, PFont.OBLIQUE, 9.0, p.dim)
            c.y += h
            first = false
            if (i < boxes.size) c.newPage()
        } while (i < boxes.size)
    }
}

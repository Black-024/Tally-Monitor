package ar.tallymonitor.app.ui

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import androidx.compose.foundation.Canvas as ComposeCanvas
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ar.tallymonitor.analysis.QuestionStats
import ar.tallymonitor.analysis.SurveyAnalysis
import ar.tallymonitor.analysis.Timeline
import java.io.ByteArrayOutputStream

/** Barras de una pregunta de opción: texto, cantidad y porcentaje. */
@Composable
fun OptionBars(q: QuestionStats) {
    val rows = buildList {
        q.options.forEach { add(Triple(it.text, it.count, it.pct)) }
        if (q.otherCount > 0) add(Triple(tr("Otro (texto escrito)", "Other (written text)"), q.otherCount, if (q.answered > 0) q.otherCount * 100.0 / q.answered else null))
        if (q.orphanCount > 0) add(Triple(tr("Opciones que ya no existen", "Options that no longer exist"), q.orphanCount, if (q.answered > 0) q.orphanCount * 100.0 / q.answered else null))
    }
    rows.forEach { (text, count, pct) ->
        Column(Modifier.padding(vertical = 4.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                androidx.compose.material3.Text(text, color = t().text, fontSize = 13.sp, modifier = Modifier.weight(1f))
                androidx.compose.material3.Text("$count · ${pctText(pct)}", color = t().muted, fontSize = 12.sp)
            }
            val frac = ((pct ?: 0.0) / 100.0).coerceIn(0.0, 1.0).toFloat()
            val bar = t().accent; val back = t().card2
            ComposeCanvas(Modifier.fillMaxWidth().height(10.dp).padding(top = 3.dp)) {
                drawRoundRect(back, size = size, cornerRadius = CornerRadius(size.height / 2))
                if (count > 0) drawRoundRect(bar, size = Size(maxOf(size.height, size.width * frac), size.height), cornerRadius = CornerRadius(size.height / 2))
            }
        }
    }
}


/** Respuestas en el tiempo: una barra por intervalo. */
@Composable
fun TimelineChart(tl: Timeline) {
    if (tl.points.isEmpty()) return
    val peak = maxOf(1, tl.points.maxOf { it.count })
    val bar = t().accent; val axis = t().line
    ComposeCanvas(Modifier.fillMaxWidth().height(120.dp)) {
        drawLine(axis, Offset(0f, size.height), Offset(size.width, size.height), 2f)
        val slot = size.width / tl.points.size; val bw = (slot * 0.7f).coerceIn(2f, 40f)
        tl.points.forEachIndexed { i, p ->
            if (p.count > 0) {
                val h = maxOf(3f, (size.height - 4f) * p.count / peak)
                drawRoundRect(bar, Offset(i * slot + (slot - bw) / 2, size.height - h), Size(bw, h), CornerRadius(minOf(6f, bw / 2)))
            }
        }
    }
}

/** Imagen PNG del resumen (gráficos de todas las preguntas de opción), con el estilo elegido para el archivo. */
object ChartPng {
    fun render(title: String, a: SurveyAnalysis, dark: Boolean): ByteArray {
        val bg = if (dark) 0xFF0B0B0F.toInt() else 0xFFFFFFFF.toInt(); val tx = if (dark) 0xFFF4F2FF.toInt() else 0xFF1B2B29.toInt()
        val mu = if (dark) 0xFFAAA5C4.toInt() else 0xFF4D6965.toInt(); val ac = if (dark) 0xFF8B7BFF.toInt() else 0xFF12A198.toInt(); val trk = if (dark) 0xFF1F1F2B.toInt() else 0xFFE6F2F0.toInt()
        val qs = a.questions.filter { (it.kind == "single" || it.kind == "multi") && it.interpreted }
        val rowsTotal = qs.sumOf { it.options.size + (if (it.otherCount > 0) 1 else 0) + 2 }
        val w = 1200; val h = 220 + rowsTotal * 56
        val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888); val c = Canvas(bmp); c.drawColor(bg)
        val p = Paint(Paint.ANTI_ALIAS_FLAG)
        p.color = tx; p.textSize = 44f; p.isFakeBoldText = true; c.drawText(title.take(60), 48f, 80f, p)
        p.isFakeBoldText = false; p.color = mu; p.textSize = 28f; c.drawText("${a.overview.total} ${tr("respuestas", "responses")} · ${a.filter.label} · Tally Monitor", 48f, 124f, p)
        var y = 190f
        for (q in qs) {
            p.color = tx; p.textSize = 32f; p.isFakeBoldText = true; c.drawText(q.title.take(70), 48f, y, p); y += 52f; p.isFakeBoldText = false
            val rows = q.options.map { Triple(it.text, it.count, it.pct ?: 0.0) } + (if (q.otherCount > 0) listOf(Triple(tr("Otro", "Other"), q.otherCount, q.otherCount * 100.0 / maxOf(1, q.answered))) else emptyList())
            for ((text, count, pct) in rows) {
                p.color = tx; p.textSize = 26f; c.drawText(text.take(34), 48f, y, p)
                p.color = trk; c.drawRoundRect(RectF(500f, y - 24f, 1000f, y - 4f), 10f, 10f, p)
                p.color = ac; if (count > 0) c.drawRoundRect(RectF(500f, y - 24f, 500f + maxOf(20f, (500f * pct / 100.0).toFloat()), y - 4f), 10f, 10f, p)
                p.color = mu; c.drawText("$count · ${pctText(pct)}", 1020f, y, p); y += 56f
            }
            y += 24f
        }
        val out = ByteArrayOutputStream(); bmp.compress(Bitmap.CompressFormat.PNG, 100, out); bmp.recycle(); return out.toByteArray()
    }
}

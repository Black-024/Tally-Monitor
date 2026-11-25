package ar.tallymonitor.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ar.tallymonitor.analysis.AnswerFilter
import ar.tallymonitor.analysis.AnswerFilterResult
import ar.tallymonitor.analysis.AnswerFilters
import ar.tallymonitor.analysis.QuestionInfo
import ar.tallymonitor.analysis.Trends
import ar.tallymonitor.services.QuestionView

private fun weekdays() = if (I18n.current == Lang.EN) listOf("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    else listOf("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

fun weekText(trends: Trends): String {
    val n = trends.last7
    val base = tr("Esta semana: $n ${if (n == 1) "respuesta" else "respuestas"}", "This week: $n ${if (n == 1) "response" else "responses"}")
    val d = trends.deltaPct                              // copia local (propiedad de otro módulo)
    return when {
        d == null -> base
        d > 0 -> tr("$base (+$d % vs la anterior)", "$base (+$d % vs last week)")
        d < 0 -> tr("$base ($d % vs la anterior)", "$base ($d % vs last week)")
        else -> tr("$base (igual que la anterior)", "$base (same as last week)")
    }
}

/** Barras simples dibujadas con Canvas; la más alta (la de [peak]) va resaltada con el color de acción. */
@Composable
private fun MiniBars(values: List<Int>, labels: List<String>, peak: Int?) {
    if (values.isEmpty()) return
    val top = maxOf(1, values.maxOrNull() ?: 1)
    val normal = t().accent; val hot = t().action; val axis = t().line
    Canvas(Modifier.fillMaxWidth().height(72.dp)) {
        drawLine(axis, Offset(0f, size.height), Offset(size.width, size.height), 2f)
        val slot = size.width / values.size; val bw = (slot * 0.62f).coerceAtLeast(2f)
        values.forEachIndexed { i, v ->
            if (v > 0) {
                val h = maxOf(3f, (size.height - 4f) * v / top)
                drawRoundRect(if (i == peak) hot else normal, Offset(i * slot + (slot - bw) / 2, size.height - h), Size(bw, h), CornerRadius(minOf(5f, bw / 2)))
            }
        }
    }
    Row(Modifier.fillMaxWidth()) {
        labels.forEach { Text(it, color = t().muted, fontSize = 9.sp, textAlign = TextAlign.Center, maxLines = 1, softWrap = false, modifier = Modifier.weight(1f)) }
    }
}

/** «Ritmo»: semana contra semana, día y hora más activos, finalización, y dos gráficos de barras. */
@Composable
fun RhythmCard(trends: Trends) {
    val pw = trends.peakWeekday; val ph = trends.peakHour; val cp = trends.completionPct
    AppCard {
        Text(weekText(trends), color = t().text, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(4.dp))
        if (pw != null && ph != null) Muted(tr("Día más activo: ${weekdays()[pw]} · Hora pico: $ph h", "Busiest day: ${weekdays()[pw]} · Peak hour: $ph h")) else Muted(tr("Todavía no hay respuestas para ver el día y la hora más activos.", "There are no responses yet to show the busiest day and hour."))
        if (cp != null) Muted(tr("Completaron la encuesta: $cp %", "Completed the survey: $cp %"))
        Spacer(Modifier.height(10.dp))
        Muted(tr("Por día de la semana", "By day of the week"))
        MiniBars(trends.byWeekday, if (I18n.current == Lang.EN) listOf("M", "T", "W", "T", "F", "S", "S") else listOf("L", "M", "X", "J", "V", "S", "D"), pw)
        Spacer(Modifier.height(10.dp))
        Muted(tr("Por hora del día", "By hour of the day"))
        MiniBars(trends.byHour, (0..23).map { if (it % 6 == 0) it.toString() else "" }, ph)
    }
}

/** Cinta del cruce activo (§2.3) con «Quitar filtro». */
@Composable
fun CrossRibbon(res: AnswerFilterResult, questionTitle: String, onClear: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Note(tr("Mostrando ${res.matched} de ${res.totalInPeriod} personas que respondieron «${res.filter.optionText}» en «$questionTitle»", "Showing ${res.matched} of ${res.totalInPeriod} people who answered «${res.filter.optionText}» in «$questionTitle»"))
        PillButton(tr("Quitar filtro", "Clear filter"), onClear, primary = false)
        Muted(tr("Las exportaciones siguen usando todas las respuestas del período.", "Exports still use all the responses in the period."))
    }
}

/** «Cruzar preguntas»: elegir una pregunta de opción y una opción, y aplicar. Solo preguntas de opción (única o múltiple). */
@Composable
fun CrossCard(questions: List<QuestionView>, onApply: (AnswerFilter) -> Unit) {
    val eligible = questions.filter { !it.isDeleted && it.options.isNotEmpty() && AnswerFilters.isOptionQuestion(QuestionInfo(it.questionId, it.position, it.type, it.title)) }
    AppCard {
        Text(tr("Cruzar preguntas", "Cross questions"), color = t().text, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(4.dp))
        Muted(tr("Mirá todas las estadísticas solo con las personas que eligieron una opción en otra pregunta.", "See all the statistics only for people who chose an option in another question."))
        if (eligible.isEmpty()) { Spacer(Modifier.height(6.dp)); Muted(tr("Esta encuesta no tiene preguntas de opción para cruzar.", "This survey has no choice questions to cross.")); return@AppCard }
        var qSel by remember(eligible.map { it.questionId }) { mutableStateOf<QuestionView?>(null) }
        var oSel by remember { mutableStateOf<String?>(null) }
        var qMenu by remember { mutableStateOf(false) }
        var oMenu by remember { mutableStateOf(false) }
        val q = qSel
        Spacer(Modifier.height(10.dp))
        Box {
            PillButton((q?.title?.ifEmpty { tr("(sin título)", "(untitled)") } ?: tr("Elegí una pregunta", "Choose a question")) + "  ▾", { qMenu = true }, Modifier.fillMaxWidth(), primary = false)
            DropdownMenu(qMenu, { qMenu = false }) {
                eligible.forEach { e -> DropdownMenuItem(text = { Text(e.title.ifEmpty { tr("(sin título)", "(untitled)") }) }, onClick = { qSel = e; oSel = null; qMenu = false }) }
            }
        }
        Spacer(Modifier.height(8.dp))
        Box {
            PillButton((oSel ?: tr("Elegí una opción", "Choose an option")) + "  ▾", { oMenu = true }, Modifier.fillMaxWidth(), enabled = q != null, primary = false)
            DropdownMenu(oMenu, { oMenu = false }) {
                (q?.options ?: emptyList()).forEach { o -> DropdownMenuItem(text = { Text(o) }, onClick = { oSel = o; oMenu = false }) }
            }
        }
        Spacer(Modifier.height(10.dp))
        val o = oSel
        PillButton(tr("Aplicar", "Apply"), { if (q != null && o != null) onApply(AnswerFilter(q.questionId, o)) }, Modifier.fillMaxWidth(), enabled = q != null && o != null)
    }
}

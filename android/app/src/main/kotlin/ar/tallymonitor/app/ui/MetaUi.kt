package ar.tallymonitor.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.Canvas
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ar.tallymonitor.analysis.GoalProjection
import ar.tallymonitor.core.TallyMonitorException
import ar.tallymonitor.services.SurveyMetaRules
import java.time.format.DateTimeFormatter

private fun dateText(d: java.time.LocalDate): String = DateTimeFormatter.ofPattern(if (I18n.current == Lang.EN) "MM/dd/yyyy" else "dd/MM/yyyy").format(d)

private fun num(n: Int) = String.format(I18n.locale, "%,d", n)

/** «124 de 200 (62 %)» */
fun goalHeadline(local: Int, goal: Int, p: GoalProjection) = tr("${num(local)} de ${num(goal)} (${p.pct} %)", "${num(local)} of ${num(goal)} (${p.pct} %)")

/** Línea de estimación según §2.1; el texto de «meta alcanzada» va sin emoji (la tipografía de la app no los usa). */
fun goalDetail(p: GoalProjection): String {
    val date = p.etaDate                         // copia local: la propiedad es de otro módulo y no admite smart cast
    return when {
        p.done -> tr("¡Meta alcanzada!", "Goal reached!")
        p.perDay <= 0.0 -> tr("Sin respuestas en los últimos 7 días: no se puede estimar", "No responses in the last 7 days: can't estimate")
        date == null -> tr("Sin ritmo suficiente para estimar una fecha", "Not enough pace to estimate a date")
        else -> tr("Al ritmo de los últimos 7 días (≈ ${String.format(I18n.locale, "%.1f", p.perDay)} por día) se llega el ${dateText(date)}", "At the pace of the last 7 days (≈ ${String.format(I18n.locale, "%.1f", p.perDay)} per day) you reach it on ${dateText(date)}")
    }
}

/** Barra simple de progreso (0..100). */
@Composable
fun GoalBar(pct: Int, modifier: Modifier = Modifier) {
    val frac = (pct / 100f).coerceIn(0f, 1f)
    val bar = t().accent; val back = t().card2
    Canvas(modifier.fillMaxWidth().height(10.dp)) {
        drawRoundRect(back, size = size, cornerRadius = CornerRadius(size.height / 2))
        if (frac > 0f) drawRoundRect(bar, size = Size(maxOf(size.height, size.width * frac), size.height), cornerRadius = CornerRadius(size.height / 2))
    }
}

/** Etiqueta en forma de píldora. Si tiene [onClick] se puede tocar; si tiene [onRemove] muestra una ✕. */
@Composable
fun TagChip(text: String, selected: Boolean = false, onClick: (() -> Unit)? = null, onRemove: (() -> Unit)? = null) {
    val bg = if (selected) t().action else t().card2
    val fg = if (selected) (if (t().dark) Color(0xFF1A1405) else Color.White) else t().text
    val base = Modifier.background(bg, Pill).border(1.dp, t().line, Pill).let { if (onClick != null) it.clickable(onClick = onClick) else it }
    Row(base.padding(horizontal = 12.dp, vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(text, color = fg, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
        if (onRemove != null) { Spacer(Modifier.width(8.dp)); Text("✕", color = fg, fontSize = 12.sp, modifier = Modifier.clickable(onClick = onRemove)) }
    }
}

/** Fila de chips para filtrar por etiqueta: «Todas» + una por etiqueta (una a la vez). */
@Composable
fun TagFilterRow(tags: List<String>, selected: String?, onSelect: (String?) -> Unit) {
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        TagChip(tr("Todas", "All"), selected = selected == null, onClick = { onSelect(null) })
        tags.forEach { tag -> TagChip(tag, selected = selected != null && selected.equals(tag, ignoreCase = true), onClick = { onSelect(tag) }) }
    }
}

/** Interruptor con texto (para «Mostrar archivadas», etc.). */
@Composable
fun LabeledSwitch(label: String, value: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(label, color = t().text, modifier = Modifier.weight(1f)); Switch(value, onChange)
    }
}

/**
 * Hoja de edición: meta (número, vacío = sin meta), nota (multilínea) y etiquetas (alta y baja). Valida con las mismas reglas
 * que el backend ([SurveyMetaRules]) y no deja guardar mientras haya un problema.
 */
@Composable
fun EditSurveyDialog(name: String, goal: Int?, note: String, tags: List<String>, onDismiss: () -> Unit, onSave: (Int?, String, List<String>) -> Unit) {
    var goalText by remember { mutableStateOf(goal?.toString() ?: "") }
    var noteText by remember { mutableStateOf(note) }
    var tagList by remember { mutableStateOf(tags) }
    var tagInput by remember { mutableStateOf("") }
    var tagError by remember { mutableStateOf<String?>(null) }

    val parsedGoal: Int? = goalText.trim().toIntOrNull()
    val goalBad = goalText.isNotBlank() && parsedGoal == null
    // Lo que se guardaría: si quedó una etiqueta escrita sin agregar, se suma sola.
    val candidateTags = if (tagInput.isNotBlank()) tagList + tagInput else tagList
    val problem: String? = if (goalBad) tr("La meta tiene que ser un número entre 1 y 1.000.000.", "The goal must be a number between 1 and 1,000,000.") else try {
        SurveyMetaRules.clean(parsedGoal, noteText, candidateTags); null
    } catch (e: TallyMonitorException) { errorText(e) }

    fun addTag() {
        if (tagInput.isBlank()) return
        try { tagList = SurveyMetaRules.tags(tagList + tagInput); tagInput = ""; tagError = null } catch (e: TallyMonitorException) { tagError = errorText(e) }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(tr("Editar encuesta", "Edit survey")) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Muted(name)
                OutlinedTextField(goalText, { v -> goalText = v.filter { it.isDigit() }.take(7) }, Modifier.fillMaxWidth(), singleLine = true,
                    label = { Text(tr("Meta de respuestas", "Response goal")) }, supportingText = { Text(tr("Dejalo vacío si no querés meta.", "Leave it empty if you don't want a goal.")) }, isError = goalBad,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                OutlinedTextField(noteText, { noteText = it }, Modifier.fillMaxWidth(), minLines = 3, maxLines = 6, label = { Text(tr("Nota", "Note")) },
                    supportingText = { Text("${noteText.trim().let { it.codePointCount(0, it.length) }}/${SurveyMetaRules.MAX_NOTE}") },
                    isError = noteText.trim().let { it.codePointCount(0, it.length) } > SurveyMetaRules.MAX_NOTE)
                Text(tr("Etiquetas", "Tags"), color = t().text, fontWeight = FontWeight.SemiBold)
                if (tagList.isEmpty()) Muted(tr("Todavía no hay etiquetas (hasta ${SurveyMetaRules.MAX_TAGS}, de hasta ${SurveyMetaRules.MAX_TAG} caracteres).", "No tags yet (up to ${SurveyMetaRules.MAX_TAGS}, up to ${SurveyMetaRules.MAX_TAG} characters each)."))
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    tagList.chunked(2).forEach { pair -> Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) { pair.forEach { tg -> TagChip(tg, onRemove = { tagList = tagList - tg }) } } }
                }
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(tagInput, { tagInput = it; tagError = null }, Modifier.weight(1f), singleLine = true, label = { Text(tr("Nueva etiqueta", "New tag")) }, isError = tagError != null)
                    TextButton(onClick = { addTag() }, enabled = tagInput.isNotBlank()) { Text(tr("Agregar", "Add"), color = t().action) }
                }
                tagError?.let { Text(it, color = t().danger, fontSize = 12.sp) }
                problem?.let { Text(it, color = t().danger, fontSize = 12.sp) }
            }
        },
        confirmButton = {
            TextButton(enabled = problem == null, onClick = {
                val c = SurveyMetaRules.clean(parsedGoal, noteText, candidateTags)
                onSave(c.goal, c.note, c.tags)
            }) { Text(tr("Guardar", "Save"), color = t().action) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(tr("Cancelar", "Cancel")) } })
}

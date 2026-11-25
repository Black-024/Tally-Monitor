package ar.tallymonitor.app.ui

import android.content.ContentResolver
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ar.tallymonitor.analysis.AnswerFilter
import ar.tallymonitor.analysis.Goals
import ar.tallymonitor.analysis.SurveyAnalysis
import androidx.compose.foundation.horizontalScroll
import androidx.compose.ui.unit.sp
import ar.tallymonitor.services.*
import kotlinx.coroutines.launch

@Composable
fun SurveyScreen(vm: MainViewModel, formId: String, resolver: ContentResolver) {
    val account by vm.selectedAccount.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var detail by remember { mutableStateOf<SurveyDetail?>(null) }
    var tab by remember { mutableIntStateOf(0) }
    var filter by remember { mutableStateOf(TimeFilterSpec()) }
    var reloadKey by remember { mutableIntStateOf(0) }
    var editing by remember { mutableStateOf(false) }
    // El cruce de preguntas se reinicia al cambiar de encuesta (la clave es formId).
    var answerFilter by remember(formId) { mutableStateOf<AnswerFilter?>(null) }
    val acc = account ?: return

    // Releer cuando termina una sincronización (busy vuelve a null) o cambia el filtro.
    LaunchedEffect(acc, formId, busy == null) { try { detail = vm.backend.surveys.survey(acc, formId); reloadKey++ } catch (e: Throwable) { if (e is kotlinx.coroutines.CancellationException) throw e; vm.message.value = errorText(e) } }

    Column(Modifier.fillMaxSize()) {
        TextButton({ vm.go(Route.Surveys) }, Modifier.padding(horizontal = 8.dp)) { Text(tr("‹ Todas las encuestas", "‹ All surveys"), color = t().accent) }
        Column(Modifier.padding(horizontal = 16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.weight(1f)) { Title(detail?.summary?.name ?: "…") }
                if (detail != null) TextButton({ editing = true }) { Text(tr("Editar", "Edit"), color = t().action) }
            }
            val note = detail?.summary?.note.orEmpty()
            if (note.isNotBlank()) Text(note, color = t().muted, fontSize = 13.sp, modifier = Modifier.padding(bottom = 4.dp))
            val chips = detail?.summary?.tags.orEmpty()
            if (chips.isNotEmpty()) Row(Modifier.fillMaxWidth().padding(bottom = 4.dp).horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) { chips.forEach { TagChip(it) } }
            Muted(tr("${detail?.summary?.localSubmissions ?: 0} respuestas guardadas · última sincronización: ${localTime(detail?.summary?.lastSyncedAt)}", "${detail?.summary?.localSubmissions ?: 0} responses saved · last sync: ${localTime(detail?.summary?.lastSyncedAt)}"))
            Row(Modifier.padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                PillButton(tr("Sincronizar", "Sync"), { vm.syncSurvey(formId, false) }, enabled = busy == null)
                PillButton(tr("Recorrido completo", "Full pass"), { vm.syncSurvey(formId, true) }, enabled = busy == null, primary = false)
            }
        }
        UnderlineTabs(listOf(tr("Resumen", "Summary"), tr("Respuestas", "Responses"), tr("Exportar", "Export")), tab) { tab = it }
        when (tab) {
            0 -> SummaryTab(vm, acc, formId, filter, { filter = it }, reloadKey, detail, answerFilter, { answerFilter = it })
            1 -> ResponsesTab(vm, acc, formId, reloadKey)
            else -> ExportTab(vm, acc, formId, detail, filter, resolver)
        }
    }
    if (editing) detail?.summary?.let { sm ->
        EditSurveyDialog(sm.name, sm.goal, sm.note, sm.tags, { editing = false }) { g, n, tg -> editing = false; vm.saveMeta(formId, g, n, tg) { } }
    }
}

@Composable
private fun SummaryTab(vm: MainViewModel, acc: String, formId: String, filter: TimeFilterSpec, setFilter: (TimeFilterSpec) -> Unit, reloadKey: Int,
                       detail: SurveyDetail?, answerFilter: AnswerFilter?, setAnswerFilter: (AnswerFilter?) -> Unit) {
    var a by remember { mutableStateOf<SurveyAnalysis?>(null) }
    var diffs by remember { mutableStateOf<List<String>?>(null) }
    var recent by remember { mutableStateOf<Int?>(null) }
    LaunchedEffect(acc, formId, filter, answerFilter, reloadKey) {
        try { a = vm.backend.analysis.analyze(acc, formId, filter, answerFilter) }
        catch (e: Throwable) { if (e is kotlinx.coroutines.CancellationException) throw e; vm.message.value = errorText(e); if (answerFilter != null) setAnswerFilter(null) }
    }
    // Respuestas de los últimos 7 días para la meta: siempre sobre todas las guardadas (no cambian con el filtro ni con el cruce).
    LaunchedEffect(acc, formId, reloadKey) {
        try { recent = vm.backend.analysis.recentCounts(acc)[formId] ?: 0 }
        catch (e: Throwable) { if (e is kotlinx.coroutines.CancellationException) throw e; recent = null }
    }
    val r = a
    val questions = detail?.questions ?: emptyList()
    val sm = detail?.summary
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        FilterRow(filter, setFilter)
        if (r == null) { Muted(tr("Calculando…", "Calculating…")); return@Column }
        val cross = r.answerFilter                                   // copia local: la propiedad es de otro módulo
        if (cross != null) CrossRibbon(cross, questions.firstOrNull { it.questionId == cross.filter.questionId }?.title?.ifEmpty { tr("(sin título)", "(untitled)") } ?: tr("la pregunta", "the question")) { setAnswerFilter(null) }
        if (r.overview.total == 0) {
            if (cross != null) { AppCard { Text(tr("Nadie contestó esa opción en este período.", "Nobody chose that option in this period."), color = t().text) }; CrossCard(questions) { setAnswerFilter(it) } }
            else AppCard { Text(tr("No hay respuestas en este período.", "There are no responses in this period."), color = t().text); Muted(tr("Si todavía no las descargaste, tocá «Actualizar».", "If you haven't downloaded them yet, tap «Sync».")) }
            return@Column
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Tile(r.overview.total.toString(), tr("Respuestas", "Responses"), Modifier.weight(1f)); Tile(r.overview.completed.toString(), tr("Completas", "Complete"), Modifier.weight(1f))
            Tile(r.overview.partial.toString(), tr("Incompletas", "Incomplete"), Modifier.weight(1f))
        }
        r.overview.perDay?.let { Muted(tr("Promedio: " + String.format(I18n.locale, "%.2f", it) + " respuestas por día · primera: ${localTime(r.overview.firstAt)} · última: ${localTime(r.overview.lastAt)}", "Average: " + String.format(I18n.locale, "%.2f", it) + " responses per day · first: ${localTime(r.overview.firstAt)} · last: ${localTime(r.overview.lastAt)}")) }
        if ("preguntas_agregadas_despues" in r.warnings) Muted(tr("Algunas preguntas se agregaron después: las personas anteriores no las vieron y no cuentan como «sin respuesta».", "Some questions were added later: earlier respondents didn't see them and aren't counted as «no answer»."))
        if ("tipos_no_interpretados" in r.warnings) Muted(tr("Hay tipos de pregunta que la app todavía no analiza; solo se cuentan.", "Some question types aren't analyzed by the app yet; they are only counted."))
        val goal = sm?.goal
        if (sm != null && goal != null) {
            val proj = Goals.projection(sm.localSubmissions, goal, recent ?: 0, java.time.Instant.now(), java.time.ZoneId.systemDefault())
            Section(tr("Meta", "Goal"))
            AppCard {
                Text(goalHeadline(sm.localSubmissions, goal, proj), color = t().text, fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
                Spacer(Modifier.height(6.dp)); GoalBar(proj.pct); Spacer(Modifier.height(6.dp))
                if (recent != null) Muted(goalDetail(proj))
            }
        }
        val rhythm = r.trends
        if (rhythm != null) { Section(tr("Ritmo", "Pace")); RhythmCard(rhythm) }
        if (cross == null) { Section(tr("Cruzar preguntas", "Cross questions")); CrossCard(questions) { setAnswerFilter(it) } }
        Section(tr("Respuestas en el tiempo", "Responses over time"))
        AppCard { TimelineChart(r.timeline) }
        Section(tr("Preguntas", "Questions"))
        r.questions.forEachIndexed { i, q ->
            AppCard {
                Text("${i + 1}. ${q.title.ifEmpty { tr("(sin título)", "(untitled)") }}" + (if (q.isDeleted) tr(" (eliminada)", " (deleted)") else ""), color = t().text, style = MaterialTheme.typography.titleSmall)
                Muted(tr("${q.answered} respondieron · ${q.blank} sin respuesta", "${q.answered} answered · ${q.blank} no answer") + (if (q.notAsked > 0) tr(" · ${q.notAsked} no la vieron", " · ${q.notAsked} didn't see it") else ""))
                Spacer(Modifier.height(6.dp))
                when {
                    (q.kind == "single" || q.kind == "multi") && q.interpreted -> OptionBars(q)
                    q.kind == "text" -> Muted(tr("Largo promedio: ${q.avgLen?.let { String.format(I18n.locale, "%.0f", it) } ?: "—"} caracteres · máximo: ${q.maxLen ?: 0}", "Average length: ${q.avgLen?.let { String.format(I18n.locale, "%.0f", it) } ?: "—"} characters · maximum: ${q.maxLen ?: 0}"))
                    else -> Muted(tr("Tipo de pregunta sin análisis propio.", "Question type without its own analysis."))
                }
            }
        }
        if (cross != null) { Section(tr("Cruzar preguntas", "Cross questions")); CrossCard(questions) { setAnswerFilter(it) } }
        Section(tr("Control de coherencia", "Consistency check"))
        PillButton(tr("Recalcular desde los datos originales", "Recalculate from the original data"), { vm.run2 { diffs = vm.backend.analysis.crosscheck(acc, formId) } }, primary = false)
        diffs?.let { d -> if (d.isEmpty()) Muted(tr("Todo coincide con los datos originales.", "Everything matches the original data.")) else d.forEach { Muted("• $it") } }
    }
}

@Composable
private fun FilterRow(f: TimeFilterSpec, set: (TimeFilterSpec) -> Unit) {
    Segmented(listOf("all" to tr("Todo", "All"), "24h" to "24 h", "7d" to tr("7 días", "7 days"), "30d" to tr("30 días", "30 days")), f.kind, { set(f.copy(kind = it)) })
    Row(verticalAlignment = Alignment.CenterVertically) { Switch(f.includeIncomplete, { set(f.copy(includeIncomplete = it)) }); Spacer(Modifier.width(8.dp)); Text(tr("Incluir respuestas incompletas", "Include incomplete responses"), color = t().text) }
}

@Composable
private fun ResponsesTab(vm: MainViewModel, acc: String, formId: String, reloadKey: Int) {
    var items by remember { mutableStateOf<List<ResponseView>>(emptyList()) }
    var more by remember { mutableStateOf(true) }
    var search by remember { mutableStateOf("") }
    var found by remember { mutableStateOf<ResponseView?>(null) }
    var open by remember { mutableStateOf<ResponseView?>(null) }
    val scope = rememberCoroutineScope()
    val page = 40
    suspend fun load(reset: Boolean) {
        val off = if (reset) 0 else items.size
        try { val next = vm.backend.analysis.responses(acc, formId, off, page); items = if (reset) next else items + next; more = next.size == page } catch (e: Throwable) { if (e is kotlinx.coroutines.CancellationException) throw e; vm.message.value = errorText(e) }
    }
    LaunchedEffect(acc, formId, reloadKey) { load(true) }

    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(search, { search = it }, Modifier.weight(1f), singleLine = true, placeholder = { Text(tr("Buscar «Usuario 012»", "Search «User 012»")) }, shape = Pill)
            PillButton(tr("Buscar", "Search"), { scope.launch { found = vm.backend.analysis.findByLabel(acc, formId, search); if (found == null) vm.message.value = tr("No se encontró esa persona.", "That person wasn't found.") } }, enabled = search.isNotBlank())
        }
        found?.let { open = it; found = null }
        if (items.isEmpty()) Muted(tr("No hay respuestas guardadas todavía.", "There are no saved responses yet."))
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(items, key = { it.number }) { r ->
                AppCard(onClick = { open = r }) {
                    Text(r.label, color = t().action, style = MaterialTheme.typography.titleSmall)
                    Muted(localTime(r.submittedAt) + if (r.isCompleted) "" else tr(" · incompleta", " · incomplete"))
                    r.answers.firstOrNull { !it.isBlank }?.let { a -> Text((a.choices.joinToString(" | ") { it.text }.ifEmpty { a.text ?: "" }).take(100), color = t().text, style = MaterialTheme.typography.bodySmall) }
                }
            }
            if (more && items.isNotEmpty()) item { PillButton(tr("Cargar más", "Load more"), { scope.launch { load(false) } }, primary = false) }
        }
    }
    open?.let { r ->
        AlertDialog(onDismissRequest = { open = null }, confirmButton = { TextButton({ open = null }) { Text(tr("Cerrar", "Close")) } },
            title = { Column { Text(r.label); Muted(localTime(r.submittedAt) + if (r.isCompleted) "" else tr(" · incompleta", " · incomplete")) } },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    r.answers.forEach { a ->
                        Column { Muted(a.questionTitle); Text(if (a.isBlank) tr("(sin respuesta)", "(no answer)") else a.choices.joinToString(" | ") { it.text }.ifEmpty { a.text ?: tr("(sin respuesta)", "(no answer)") }, color = t().text) }
                    }
                }
            })
    }
}

@Composable
private fun ExportTab(vm: MainViewModel, acc: String, formId: String, detail: SurveyDetail?, filter: TimeFilterSpec, resolver: ContentResolver) {
    var includeText by remember { mutableStateOf(false) }
    var mask by remember { mutableStateOf(true) }
    var individual by remember { mutableStateOf(false) }
    var oneOnly by remember { mutableStateOf(false) }
    var who by remember { mutableStateOf("") }
    var darkStyle by remember { mutableStateOf(true) }
    var pending by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    fun request() = ExportRequest(filter, includeText, mask, individual, if (darkStyle) "dark" else "light", if (individual && oneOnly) who.filter { it.isDigit() }.toIntOrNull() else null)
    val out = { uri: Uri -> { resolver.openOutputStream(uri, "w") ?: throw java.io.IOException() } }

    val xlsx = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")) { uri -> uri?.let { vm.export(formId, "xlsx", request(), out(it)) } }
    val pdf = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/pdf")) { uri -> uri?.let { vm.export(formId, "pdf", request(), out(it)) } }
    val png = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("image/png")) { uri ->
        uri?.let { u -> scope.launch { try { val an = vm.backend.analysis.analyze(acc, formId, filter); vm.savePng(ChartPng.render(detail?.summary?.name ?: tr("Encuesta", "Survey"), an, darkStyle), out(u)) } catch (e: Throwable) { if (e is kotlinx.coroutines.CancellationException) throw e; vm.message.value = errorText(e) } } } }

    fun ask(fmt: String, launcher: androidx.activity.result.ActivityResultLauncher<String>) { if (individual && oneOnly && request().onlyNumber == null) { vm.message.value = tr("Escribí el número de la persona (por ejemplo 7).", "Enter the person's number (for example 7)."); return }
        scope.launch { launcher.launch(vm.backend.export.suggestedName(acc, formId, fmt, individual && fmt != "png")) } }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Muted(tr("Se exporta el período elegido en la pestaña Resumen. Vos elegís dónde se guarda el archivo.", "The period chosen in the Summary tab is exported. You choose where the file is saved."))
        AppCard {
            Section(tr("Qué exportar", "What to export"))
            Segmented(listOf("summary" to tr("Resumen de la encuesta", "Survey summary"), "ind" to tr("Respuestas individuales", "Individual responses")), if (individual) "ind" else "summary", { individual = it == "ind" })
            Muted(if (individual) tr("Una ficha por persona con lo que respondió. Las preguntas que no respondió no aparecen.", "One card per person with what they answered. Unanswered questions don't appear.") else tr("Estadísticas por pregunta, gráfico en el tiempo y el resumen general.", "Statistics per question, a chart over time and the general summary."))
            if (individual) {
                Spacer(Modifier.height(8.dp))
                Segmented(listOf("all" to tr("Todas las personas", "Everyone"), "one" to tr("Una sola persona", "One person")), if (oneOnly) "one" else "all", { oneOnly = it == "one" })
                if (oneOnly) OutlinedTextField(who, { who = it }, Modifier.fillMaxWidth().padding(top = 8.dp), singleLine = true, placeholder = { Text(tr("Por ejemplo: 7 o Usuario 007", "For example: 7 or User 007")) }, shape = Pill,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
            }
            Spacer(Modifier.height(8.dp))
            ToggleRow(tr("Incluir respuestas de texto libre", "Include free-text responses"), includeText) { includeText = it }
            if (includeText) ToggleRow(tr("Ocultar posibles datos personales (correos, teléfonos, números largos)", "Hide possible personal data (emails, phone numbers, long numbers)"), mask) { mask = it }
            if (includeText && !mask) Text(tr("Atención: los textos pueden contener datos personales y saldrán SIN ocultar.", "Warning: texts may contain personal data and will be exported UNMASKED."), color = t().danger, style = MaterialTheme.typography.bodySmall)
        }
        AppCard {
            Section(tr("Estilo del PDF y la imagen", "PDF and image style"))
            Segmented(listOf("light" to tr("Claro", "Light"), "dark" to tr("Oscuro", "Dark")), if (darkStyle) "dark" else "light", { darkStyle = it == "dark" })
        }
        PillButton(tr("Exportar a Excel", "Export to Excel"), { ask("xlsx", xlsx) }, Modifier.fillMaxWidth())
        PillButton(tr("Exportar a PDF", "Export to PDF"), { ask("pdf", pdf) }, Modifier.fillMaxWidth())
        PillButton(tr("Guardar gráficos como imagen (PNG)", "Save charts as image (PNG)"), { ask("png", png) }, Modifier.fillMaxWidth(), primary = false)
        Muted(tr("El enmascarado ayuda pero no garantiza ocultar todo: revisá el archivo antes de compartirlo.", "Masking helps but doesn't guarantee everything is hidden: review the file before sharing it."))
    }
}

@Composable
private fun ToggleRow(label: String, value: Boolean, set: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) { Text(label, color = t().text, modifier = Modifier.weight(1f)); Switch(value, set) }
}

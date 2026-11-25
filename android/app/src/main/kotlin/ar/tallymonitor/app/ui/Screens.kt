package ar.tallymonitor.app.ui

import android.content.ContentResolver
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ar.tallymonitor.core.Secret
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import ar.tallymonitor.services.Account
import ar.tallymonitor.services.BackupItem
import ar.tallymonitor.services.SurveySummary
import androidx.compose.ui.platform.LocalContext
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import ar.tallymonitor.analysis.Goals
import ar.tallymonitor.app.notify.NotificationScheduler
import ar.tallymonitor.app.notify.Notifier
import ar.tallymonitor.app.widget.WidgetSnapshot

@Composable
fun AppRoot(vm: MainViewModel, resolver: ContentResolver) {
    val theme by vm.theme.collectAsStateWithLifecycle()
    TallyTheme(dark = theme != "light") { AppScaffold(vm, resolver) }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppScaffold(vm: MainViewModel, resolver: ContentResolver) {
    val route by vm.route.collectAsStateWithLifecycle()
    val message by vm.message.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    val snack = remember { SnackbarHostState() }
    LaunchedEffect(message) { message?.let { snack.showSnackbar(it); vm.dismissMessage() } }
    BackHandler(enabled = route !is Route.Home) { vm.back() }
    val all by vm.allSurveys.collectAsStateWithLifecycle()
    val syncMode by vm.syncMode.collectAsStateWithLifecycle()
    val acct by vm.selectedAccount.collectAsStateWithLifecycle()
    val hasPending = all.any { (_, l) -> l.any { it.hasNewHint } }
    val ctx = LocalContext.current
    // Widget: instantánea de solo conteos cada vez que cambia el listado (la primera lista vacía, de arranque, no se guarda).
    var snapshotSeen by remember { mutableStateOf(false) }
    LaunchedEffect(all) { if (snapshotSeen || all.isNotEmpty()) WidgetSnapshot.save(ctx, WidgetSnapshot.countsOfAccounts(all.map { (a, l) -> a.id to l })); snapshotSeen = true }
    // Avisos: deja programado (o cancelado) el chequeo periódico según el ajuste.
    LaunchedEffect(Unit) { NotificationScheduler.reconcile(ctx, vm.backend) }
    // En modo automático: al abrir Inicio o Encuestas se actualiza la lista (como en Windows).
    LaunchedEffect(syncMode, acct, route is Route.Home || route is Route.Surveys, all.size) { if (route is Route.Home || route is Route.Surveys) vm.autoSyncLists() }

    Scaffold(
        containerColor = t().bg,
        snackbarHost = { SnackbarHost(snack) },
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize()) {
            BrandBar()
            NavPills(listOf("h" to tr("Inicio", "Home"), "s" to tr("Encuestas", "Surveys"), "a" to tr("Cuentas", "Accounts"), "c" to tr("Ajustes", "Settings")), when (route) { Route.Home -> "h"; Route.Accounts -> "a"; Route.Settings -> "c"; else -> "s" },
                badges = if (hasPending) setOf("s") else emptySet()) {
                vm.go(when (it) { "h" -> Route.Home; "a" -> Route.Accounts; "c" -> Route.Settings; else -> Route.Surveys })
            }
            busy?.let { b ->
                Column(Modifier.fillMaxWidth().background(t().card2).padding(horizontal = 16.dp, vertical = 8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(b.label + (b.total?.let { " ${b.done}/$it" } ?: if (b.done > 0) " ${b.done}" else ""), color = t().text, modifier = Modifier.weight(1f))
                        TextButton(onClick = vm::cancelSync) { Text(tr("Cancelar", "Cancel"), color = t().action) }
                    }
                    val tot = b.total
                    if (tot != null && tot > 0) LinearProgressIndicator(progress = { (b.done.toFloat() / tot).coerceIn(0f, 1f) }, Modifier.fillMaxWidth(), color = t().accent)
                    else LinearProgressIndicator(Modifier.fillMaxWidth(), color = t().accent)
                }
            }
            when (val r = route) {
                Route.Home -> HomeScreen(vm)
                Route.Surveys -> SurveysScreen(vm)
                Route.Accounts -> AccountsScreen(vm)
                Route.Settings -> SettingsScreen(vm)
                is Route.Survey -> SurveyScreen(vm, r.formId, resolver)
            }
        }
    }
}

// ============================ Encuestas ============================
@Composable
private fun SurveysScreen(vm: MainViewModel) {
    val accounts by vm.accounts.collectAsStateWithLifecycle()
    val selected by vm.selectedAccount.collectAsStateWithLifecycle()
    val list by vm.surveys.collectAsStateWithLifecycle()
    val query by vm.query.collectAsStateWithLifecycle()
    val favs by vm.onlyFavorites.collectAsStateWithLifecycle()
    val tagFilter by vm.tagFilter.collectAsStateWithLifecycle()
    val showArchived by vm.showArchived.collectAsStateWithLifecycle()
    val tags by vm.tags.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(tr("Tus encuestas", "Your surveys"), fontSize = 26.sp, fontWeight = FontWeight.Bold, color = t().text, modifier = Modifier.weight(1f))
            if (accounts.isNotEmpty()) PillButton(tr("Actualizar lista", "Refresh list"), vm::syncSurveys)
        }
        if (accounts.isEmpty()) {
            AppCard { Text(tr("Primero agregá una cuenta", "Add an account first"), color = t().text, fontWeight = FontWeight.Bold); Spacer(Modifier.height(8.dp)); Muted(tr("Las encuestas se leen con la API Key de una cuenta de Tally.", "Surveys are read with the API Key of a Tally account.")); Spacer(Modifier.height(12.dp)); PillButton(tr("Ir a Cuentas", "Go to Accounts"), { vm.go(Route.Accounts) }) }
            return@Column
        }
        Muted(tr("Tocá una para ver sus respuestas, el análisis y exportarla. Todo en un solo lugar.", "Tap one to see its responses, the analysis and to export it. All in one place."))
        var menu by remember { mutableStateOf(false) }
        Box {
            PillButton((accounts.firstOrNull { it.id == selected }?.name ?: tr("Elegí una cuenta", "Choose an account")) + "  ▾", { menu = true }, primary = false)
            DropdownMenu(menu, { menu = false }) { accounts.forEach { a -> DropdownMenuItem(text = { Text(a.name) }, onClick = { vm.selectedAccount.value = a.id; menu = false }) } }
        }
        OutlinedTextField(query, { vm.query.value = it }, Modifier.fillMaxWidth(), singleLine = true, placeholder = { Text(tr("Buscar por nombre, etiqueta o nota…", "Search by name, tag or note…")) }, shape = Pill)
        Segmented(listOf("all" to tr("Todas", "All"), "fav" to tr("Favoritas", "Favorites")), if (favs) "fav" else "all", { vm.onlyFavorites.value = it == "fav" })
        if (tags.isNotEmpty()) TagFilterRow(tags, tagFilter) { vm.tagFilter.value = it }
        LabeledSwitch(tr("Mostrar archivadas", "Show archived"), showArchived) { vm.showArchived.value = it }
        if (list.isEmpty()) Muted(if (query.isNotBlank() || favs || tagFilter != null) tr("No hay encuestas que coincidan con el filtro.", "No surveys match the filter.") else tr("Todavía no hay encuestas guardadas. Tocá «Actualizar lista» para traer las encuestas de esta cuenta.", "There are no saved surveys yet. Tap «Refresh list» to fetch this account's surveys."))
        LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(bottom = 16.dp)) { items(list, key = { it.formId }) { SurveyCard(it, { vm.open(it.formId) }, { vm.toggleFavorite(it) }, { vm.setArchived(it.formId, !it.archived) }) } }
    }
}

@Composable
private fun SurveyCard(s: SurveySummary, onOpen: () -> Unit, onFav: () -> Unit, onArchive: () -> Unit) {
    AppCard(onClick = onOpen) {
        Row(verticalAlignment = Alignment.Top) {
            Text(if (s.neverSynced) "—" else s.localSubmissions.toString(), fontSize = 36.sp, fontWeight = FontWeight.ExtraBold, color = t().accent, modifier = Modifier.weight(1f))
            Text(if (s.isFavorite) "★" else "☆", color = t().action, fontSize = 26.sp, modifier = Modifier.clickable(onClick = onFav).padding(4.dp))
        }
        Row(verticalAlignment = Alignment.Top) {
            Text(s.name, color = t().text, fontSize = 17.sp, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
            if (s.hasNewHint) Row(Modifier.padding(start = 8.dp).background(t().card2, Pill).padding(horizontal = 10.dp, vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                RedDot(8.dp); Spacer(Modifier.width(6.dp)); Text(tr("sin actualizar", "not updated"), color = t().action, fontSize = 11.sp, fontWeight = FontWeight.Bold)
            }
        }
        Muted((if (s.neverSynced) tr("sin descargar", "not downloaded") else if (s.localSubmissions == 1) tr("respuesta guardada", "response saved") else tr("respuestas guardadas", "responses saved")) + (if (s.isClosed) tr(" · cerrada", " · closed") else tr(" · abierta", " · open")))
        Text((s.reportedSubmissions?.let { tr("Tally informa $it · ", "Tally reports $it · ") } ?: "") + (if (s.neverSynced) tr("todavía no se descargaron las respuestas", "responses haven't been downloaded yet") else tr("última respuesta: ${localTime(s.lastSubmissionAt)}", "last response: ${localTime(s.lastSubmissionAt)}")), color = t().dim, fontSize = 11.sp)
        if (s.note.isNotBlank()) Text(s.note.lineSequence().first().take(120), color = t().muted, fontSize = 12.sp, maxLines = 1, modifier = Modifier.padding(top = 4.dp))
        if (s.tags.isNotEmpty()) Row(Modifier.fillMaxWidth().padding(top = 6.dp).horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) { s.tags.forEach { TagChip(it) } }
        val goal = s.goal
        if (goal != null && !s.neverSynced) {
            val pct = Goals.projection(s.localSubmissions, goal, 0, java.time.Instant.now(), java.time.ZoneId.systemDefault()).pct
            Spacer(Modifier.height(8.dp)); GoalBar(pct)
            Muted(tr("Meta: ${s.localSubmissions} de $goal ($pct %)", "Goal: ${s.localSubmissions} of $goal ($pct %)"), Modifier.padding(top = 2.dp))
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (s.archived) Muted(tr("archivada", "archived"), Modifier.weight(1f)) else Spacer(Modifier.weight(1f))
            TextButton(onClick = onArchive) { Text(if (s.archived) tr("Desarchivar", "Unarchive") else tr("Archivar", "Archive"), color = t().action, fontSize = 12.sp) }
        }
    }
}

// ============================ Cuentas ============================
@Composable
private fun AccountsScreen(vm: MainViewModel) {
    val accounts by vm.accounts.collectAsStateWithLifecycle()
    var adding by remember { mutableStateOf(false) }
    var replacing by remember { mutableStateOf<Account?>(null) }
    var renaming by remember { mutableStateOf<Account?>(null) }
    var deleting by remember { mutableStateOf<Account?>(null) }

    Column(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) { Text(tr("Cuentas", "Accounts"), fontSize = 26.sp, fontWeight = FontWeight.Bold, color = t().text, modifier = Modifier.weight(1f)); PillButton(tr("+ Agregar cuenta", "+ Add account"), { adding = true }) }
        Muted(tr("La API Key se guarda cifrada con el almacén seguro de Android y nunca se muestra ni se incluye en copias de seguridad.", "The API Key is stored encrypted in Android's secure storage and is never shown or included in backups."))
        if (accounts.isEmpty()) AppCard { Text(tr("Todavía no hay cuentas", "No accounts yet"), color = t().text, fontWeight = FontWeight.Bold); Spacer(Modifier.height(6.dp)); Muted(tr("Agregá una API Key de Tally para empezar. Se guarda cifrada en este teléfono y no se vuelve a mostrar.", "Add a Tally API Key to get started. It is stored encrypted on this phone and is never shown again.")) }
        LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(accounts, key = { it.id }) { a ->
                AppCard {
                    Text(a.name, color = t().text, style = MaterialTheme.typography.titleMedium)
                    Muted(tr("${statusText(a.status)} · última validación: ${localTime(a.lastValidatedAt)}", "${statusText(a.status)} · last validation: ${localTime(a.lastValidatedAt)}"))
                    Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        TextButton({ vm.verify(a.id) }) { Text(tr("Validar", "Validate"), color = t().action) }
                        TextButton({ replacing = a }) { Text(tr("Cambiar clave", "Change key")) }
                        TextButton({ renaming = a }) { Text(tr("Renombrar", "Rename")) }
                        TextButton({ deleting = a }) { Text(tr("Eliminar", "Delete"), color = t().danger) }
                    }
                }
            }
        }
    }
    if (adding) KeyDialog(tr("Agregar cuenta", "Add account"), withName = true, initialName = "", onDismiss = { adding = false }) { name, key -> vm.addAccount(name, key) { adding = false } }
    replacing?.let { a -> KeyDialog(tr("Cambiar la clave de ${a.name}", "Change the key for ${a.name}"), withName = false, initialName = a.name, onDismiss = { replacing = null }) { _, key -> vm.replaceKey(a.id, key) { replacing = null } } }
    renaming?.let { a ->
        var n by remember { mutableStateOf(a.name) }
        AlertDialog(onDismissRequest = { renaming = null }, title = { Text(tr("Renombrar cuenta", "Rename account")) }, text = { OutlinedTextField(n, { n = it }, singleLine = true) },
            confirmButton = { TextButton({ vm.rename(a.id, n); renaming = null }) { Text(tr("Guardar", "Save")) } }, dismissButton = { TextButton({ renaming = null }) { Text(tr("Cancelar", "Cancel")) } })
    }
    deleting?.let { a -> Confirm(tr("Eliminar cuenta", "Delete account"), tr("Se borran la clave cifrada y todas las encuestas y respuestas guardadas de «${a.name}». No se toca nada en Tally.", "The encrypted key and all saved surveys and responses of «${a.name}» are deleted. Nothing is changed in Tally."), tr("Eliminar", "Delete"), { vm.removeAccount(a.id) }, { deleting = null }) }
}

/** La clave se escribe o pega aquí, se oculta con puntos y se entrega como Secret; el texto se borra al cerrar. */
@Composable
private fun KeyDialog(title: String, withName: Boolean, initialName: String, onDismiss: () -> Unit, onOk: (String, Secret) -> Unit) {
    var name by remember { mutableStateOf(initialName) }
    var key by remember { mutableStateOf("") }
    AlertDialog(onDismissRequest = { key = ""; onDismiss() }, title = { Text(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (withName) OutlinedTextField(name, { name = it }, singleLine = true, label = { Text(tr("Nombre de la cuenta", "Account name")) })
                OutlinedTextField(key, { key = it.trim() }, singleLine = true, label = { Text(tr("API Key de Tally", "Tally API Key")) }, visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, autoCorrectEnabled = false))
                Muted(tr("Se valida con Tally antes de guardarse. Solo se usa para leer.", "It is validated with Tally before being saved. It is only used to read."))
            }
        },
        confirmButton = { TextButton(enabled = key.isNotEmpty() && (!withName || name.isNotBlank()), onClick = { val s = Secret(key); key = ""; onOk(name, s) }) { Text(tr("Validar y guardar", "Validate and save")) } },
        dismissButton = { TextButton({ key = ""; onDismiss() }) { Text(tr("Cancelar", "Cancel")) } })
}

// ============================ Ajustes ============================
@Composable
private fun SettingsScreen(vm: MainViewModel) {
    val b = vm.backend
    var theme by remember { mutableStateOf("dark") }
    var autoBackup by remember { mutableStateOf(true) }
    var syncMode by remember { mutableStateOf("manual") }
    var notifyOn by remember { mutableStateOf(false) }
    var notifyEvery by remember { mutableStateOf("60") }
    val ctx = LocalContext.current
    var permissionOk by remember { mutableStateOf(Notifier.hasPermission(ctx)) }
    var backups by remember { mutableStateOf<List<BackupItem>>(emptyList()) }
    var restoring by remember { mutableStateOf<BackupItem?>(null) }
    var deleting by remember { mutableStateOf<BackupItem?>(null) }
    var legal by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    fun reload() { scope.launch2 { backups = b.backups.list() } }
    LaunchedEffect(Unit) { theme = b.settings.get("theme"); autoBackup = b.settings.get("auto_backup") == "1"; syncMode = b.settings.get("sync_mode")
        notifyOn = b.settings.get("notify_mode") == "on"; notifyEvery = b.settings.get("notify_interval_min"); permissionOk = Notifier.hasPermission(ctx); reload() }
    fun enableNotifications() {
        notifyOn = true; permissionOk = true
        vm.setSetting("notify_mode", "on"); Notifier.ensureChannel(ctx)
        NotificationScheduler.schedule(ctx, notifyEvery.toIntOrNull() ?: 60, replace = true)
    }
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) enableNotifications() else {
            notifyOn = false; permissionOk = false
            vm.message.value = tr("Sin el permiso de notificaciones no se pueden mostrar avisos. Podés dárselo a la app desde los ajustes del sistema.", "Without the notifications permission, alerts can't be shown. You can grant it to the app from the system settings.")
        }
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Title(tr("Configuración", "Settings"))
        AppCard {
            Section("Idioma / Language")
            Segmented(Lang.values().map { it.code to it.label }, I18n.current.code, { code -> Lang.values().firstOrNull { it.code == code }?.let { I18n.set(ctx, it) } })
        }
        AppCard {
            Section(tr("Apariencia", "Appearance"))
            Text(tr("Modo", "Mode"), color = t().text, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
            Segmented(listOf("light" to tr("Claro", "Light"), "dark" to tr("Oscuro", "Dark")), if (theme == "light") "light" else "dark", { theme = it; vm.setSetting("theme", it) })
            Spacer(Modifier.height(8.dp))
            Muted(tr("Elegí el aspecto de la aplicación. Los PDF y las imágenes tienen su propia opción de estilo al exportar.", "Choose the look of the app. PDFs and images have their own style option when exporting."))
        }
        AppCard {
            Section(tr("Sincronización", "Sync"))
            Text(tr("Modo de sincronización", "Sync mode"), color = t().text, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
            Segmented(listOf("manual" to tr("Manual", "Manual"), "auto" to tr("Automática", "Automatic")), if (syncMode == "auto") "auto" else "manual", { syncMode = it; vm.setSetting("sync_mode", it) })
            Spacer(Modifier.height(8.dp))
            Muted(tr("Manual (recomendado): solo se sincroniza cuando tocás el botón. Automática: al abrir Inicio o Encuestas se actualiza la lista y al abrir una encuesta se traen sus respuestas nuevas. En ambos modos se muestra primero lo ya guardado.", "Manual (recommended): syncs only when you tap the button. Automatic: opening Home or Surveys refreshes the list, and opening a survey fetches its new responses. In both modes, what is already saved is shown first."))
        }
        AppCard {
            Section(tr("Avisos", "Alerts"))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(tr("Avisarme cuando haya respuestas nuevas", "Alert me when there are new responses"), color = t().text, modifier = Modifier.weight(1f))
                Switch(notifyOn, { want ->
                    if (!want) { notifyOn = false; vm.setSetting("notify_mode", "off"); NotificationScheduler.cancel(ctx) }
                    else if (Notifier.needsRuntimePermission() && !Notifier.hasPermission(ctx)) permissionLauncher.launch(android.Manifest.permission.POST_NOTIFICATIONS)
                    else enableNotifications()
                })
            }
            if (notifyOn) {
                Spacer(Modifier.height(8.dp))
                Text(tr("Cada cuánto revisar", "How often to check"), color = t().text, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(8.dp))
                Segmented(listOf("15" to "15 min", "30" to "30 min", "60" to "1 h", "360" to "6 h"), notifyEvery, {
                    notifyEvery = it; vm.setSetting("notify_interval_min", it); NotificationScheduler.schedule(ctx, it.toInt(), replace = true)
                })
                if (!permissionOk || !Notifier.canNotify(ctx)) { Spacer(Modifier.height(8.dp)); Note(tr("Los avisos están activados, pero Android no deja mostrarlos: falta el permiso de notificaciones de la app.", "Alerts are on, but Android won't let them show: the app is missing the notifications permission.")) }
            }
            Spacer(Modifier.height(8.dp))
            Muted(tr("Se revisa en segundo plano con tu conexión a Internet, sin servidores propios: solo se consulta la lista de encuestas y se avisa con un número («3 respuestas nuevas en 2 encuestas»). Android decide el momento exacto y no revisa más seguido que cada 15 minutos. Las encuestas archivadas no cuentan.", "It checks in the background over your Internet connection, with no servers of our own: it only queries the survey list and alerts you with a number («3 new responses in 2 surveys»). Android decides the exact moment and never checks more often than every 15 minutes. Archived surveys don't count."))
        }
        AppCard {
            Section("Widgets")
            var showNames by remember { mutableStateOf(ar.tallymonitor.app.widget.WidgetSnapshot.showNames(ctx)) }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(tr("Mostrar nombres de encuestas en los widgets", "Show survey names in widgets"), color = t().text, modifier = Modifier.weight(1f))
                Switch(showNames, { showNames = it; ar.tallymonitor.app.widget.WidgetSnapshot.setShowNames(ctx, it) })
            }
            Spacer(Modifier.height(8.dp))
            Muted(tr("Hay 7 widgets: Resumen, Semáforo (1×1), Meta (elegís la encuesta al agregarlo; si ninguna tiene meta, se la ponés ahí mismo), Ranking (top 3), Novedades, Acceso directo y Lista de encuestas. El ranking, el acceso directo y la lista necesitan los nombres; si los ocultás se ven como «Encuesta N» (útil si te preocupa que se vean con el teléfono bloqueado).", "There are 7 widgets: Summary, Traffic light (1×1), Goal (you pick the survey when adding it; if none has a goal, you set one right there), Ranking (top 3), News, Shortcut and Survey list. The ranking, shortcut and list need the names; if you hide them they show as «Survey N» (useful if you worry about them being visible on a locked phone)."))
        }
        AppCard {
            Section(tr("Datos y copias de seguridad", "Data and backups"))
            Row(verticalAlignment = Alignment.CenterVertically) { Text(tr("Copia automática diaria al iniciar", "Daily automatic backup on launch"), color = t().text, modifier = Modifier.weight(1f)); Switch(autoBackup, { autoBackup = it; vm.setSetting("auto_backup", if (it) "1" else "0") }) }
            Muted(tr("Las copias se guardan solo en este teléfono y no incluyen las API Keys: tras restaurar en otro equipo hay que reingresarlas.", "Backups are stored only on this phone and don't include API Keys: after restoring on another device you have to enter them again."))
            Spacer(Modifier.height(8.dp))
            PillButton(tr("Crear copia ahora", "Create backup now"), { vm.createBackup { reload() } })
            backups.take(8).forEach { bk ->
                Spacer(Modifier.height(8.dp))
                Column(Modifier.fillMaxWidth().background(t().card2, RoundedCornerShape(14.dp)).padding(12.dp)) {
                    Text("${localTime(bk.createdAtIso)} · ${backupReasonText(bk.reason)}", color = t().text); Muted(tr("${bk.sizeBytes / 1024} KB · esquema v${bk.schemaVersion}", "${bk.sizeBytes / 1024} KB · schema v${bk.schemaVersion}"))
                    Row { TextButton({ restoring = bk }) { Text(tr("Restaurar…", "Restore…"), color = t().action) }; TextButton({ deleting = bk }) { Text(tr("Eliminar copia", "Delete backup"), color = t().danger) } }
                }
            }
        }
        AppCard {
            Section(tr("Acerca de", "About"))
            Muted(tr("Versión 1.0.0. Solo lectura: no modifica nada en Tally. No usa servidores propios.", "Version 1.0.0. Read-only: it changes nothing in Tally. It uses no servers of its own."))
            Muted(tr("Novedades: pestaña Inicio con metas, etiquetas, notas y archivado de encuestas, ritmo de respuestas, cruce de preguntas, avisos de respuestas nuevas y widget.", "What's new: Home tab with goals, tags, notes and survey archiving, response pace, question cross-filtering, new-response alerts and widgets."))
            Row { TextButton({ legal = licenseText() }) { Text(tr("Licencia y terceros", "License and third parties"), color = t().action) }; TextButton({ legal = privacyText() }) { Text(tr("Privacidad", "Privacy"), color = t().action) } }
        }
        Spacer(Modifier.height(12.dp))
        Text(tr("Tally Monitor: Android 1.0.0. Por: Valentín Mangano", "Tally Monitor: Android 1.0.0. By: Valentín Mangano"), color = t().dim, fontSize = 11.sp, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp))
    }
    restoring?.let { Confirm(tr("Restaurar copia", "Restore backup"), tr("Se reemplazan los datos actuales por los de esta copia (antes se guarda una copia de lo actual).", "The current data is replaced with this backup's (a copy of the current data is saved first)."), tr("Restaurar", "Restore"), { vm.restoreBackup(it.filename) { reload() } }, { restoring = null }) }
    deleting?.let { Confirm(tr("Eliminar copia", "Delete backup"), tr("Esta copia se borra del teléfono.", "This backup is deleted from the phone."), tr("Eliminar", "Delete"), { vm.deleteBackup(it.filename) { reload() } }, { deleting = null }) }
    legal?.let { AlertDialog(onDismissRequest = { legal = null }, confirmButton = { TextButton({ legal = null }) { Text(tr("Cerrar", "Close")) } }, text = { Text(it, Modifier.verticalScroll(rememberScrollState())) }) }
}

private fun CoroutineScope.launch2(block: suspend () -> Unit) { launch { try { block() } catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (_: Throwable) {} } }

fun licenseText(): String = tr("Tally Monitor se distribuye bajo licencia MIT. Es software libre y se entrega «tal cual», sin garantía. No está afiliado a Tally.",
    "Tally Monitor is distributed under the MIT license. It is free software provided «as is», without warranty. It is not affiliated with Tally.")
fun privacyText(): String = tr("Tally Monitor solo LEE tus encuestas con tu propia API Key. Todo se guarda en este teléfono. La clave se cifra con el almacén seguro de Android y no se incluye en copias de seguridad ni en exportaciones. La app no tiene servidores propios, no envía estadísticas y solo pide el permiso de Internet (y el de notificaciones, únicamente si activás los avisos). Las metas, notas y etiquetas que escribís se guardan solo en este teléfono, y los avisos y el widget muestran solamente cantidades. Las respuestas de texto libre pueden contener datos personales: al exportarlas conviene enmascararlas y revisar el archivo antes de compartirlo.",
    "Tally Monitor only READS your surveys with your own API Key. Everything is stored on this phone. The key is encrypted with Android's secure storage and is not included in backups or exports. The app has no servers of its own, sends no analytics and only asks for the Internet permission (and the notifications permission, only if you turn on alerts). The goals, notes and tags you write are stored only on this phone, and alerts and widgets show only counts. Free-text responses may contain personal data: when exporting them, it's best to mask them and review the file before sharing it.")

// ============================ Inicio ============================
@Composable
private fun HomeScreen(vm: MainViewModel) {
    val accounts by vm.accounts.collectAsStateWithLifecycle()
    val all by vm.allSurveys.collectAsStateWithLifecycle()
    val greet = remember(I18n.current) { greetingFor(java.time.LocalDateTime.now()) }
    val surveys = all.flatMap { it.second }
    val pending = all.flatMap { (a, l) -> l.filter { it.hasNewHint }.map { a to it } }
    val newCount = pending.sumOf { (_, s) -> ((s.reportedSubmissions ?: 0) - s.localSubmissions).coerceAtLeast(0) }
    val total = surveys.sumOf { it.localSubmissions }
    val open = surveys.count { !it.isClosed }
    val lastAny = surveys.mapNotNull { it.lastSubmissionAt }.maxOrNull()
    // Metas: solo encuestas con meta (las archivadas ya no llegan acá). Los 7 días se piden al backend por cuenta.
    val withGoal = all.flatMap { (a, l) -> l.filter { it.goal != null }.map { a to it } }
    var recent by remember { mutableStateOf<Map<String, Map<String, Int>>>(emptyMap()) }
    LaunchedEffect(all) {
        val m = HashMap<String, Map<String, Int>>()
        for ((a, l) in all) if (l.any { it.goal != null }) {
            m[a.id] = try { vm.backend.analysis.recentCounts(a.id) } catch (e: Throwable) { if (e is kotlinx.coroutines.CancellationException) throw e; emptyMap() }
        }
        recent = m
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(greet.title, fontSize = 28.sp, fontWeight = FontWeight.ExtraBold, color = t().text)
        Text(greet.subtitle, fontSize = 15.sp, color = t().muted)
        if (accounts.isEmpty()) {
            AppCard { Text(tr("Empecemos", "Let's get started"), color = t().text, fontWeight = FontWeight.Bold); Spacer(Modifier.height(8.dp)); Muted(tr("Agregá la API Key de tu cuenta de Tally para ver acá cómo van tus encuestas.", "Add your Tally account's API Key to see how your surveys are doing here.")); Spacer(Modifier.height(12.dp)); PillButton(tr("Ir a Cuentas", "Go to Accounts"), { vm.go(Route.Accounts) }) }
            return@Column
        }
        if (pending.isNotEmpty()) {
            AppCard {
                Row(verticalAlignment = Alignment.CenterVertically) { RedDot(10.dp); Spacer(Modifier.width(8.dp)); Text(tr("Hay respuestas sin actualizar", "There are responses not updated"), color = t().text, fontWeight = FontWeight.Bold, fontSize = 16.sp) }
                Spacer(Modifier.height(6.dp))
                Muted((if (newCount > 0) tr("Tally informa $newCount respuesta${if (newCount == 1) "" else "s"} más que las guardadas en este teléfono, en ${pending.size} encuesta${if (pending.size == 1) "" else "s"}.", "Tally reports $newCount more response${if (newCount == 1) "" else "s"} than the ones saved on this phone, in ${pending.size} survey${if (pending.size == 1) "" else "s"}.") else tr("Hay encuestas con respuestas que todavía no se descargaron.", "Some surveys have responses that haven't been downloaded yet.")))
                Spacer(Modifier.height(12.dp))
                PillButton(tr("Ir a Encuestas", "Go to Surveys"), { vm.goToPending(pending.first().first.id) })
            }
        }
        if (surveys.isEmpty()) {
            AppCard { Text(tr("Todavía no hay encuestas guardadas", "There are no saved surveys yet"), color = t().text, fontWeight = FontWeight.Bold); Spacer(Modifier.height(6.dp)); Muted(tr("Andá a Encuestas y tocá «Actualizar lista» para traerlas.", "Go to Surveys and tap «Refresh list» to fetch them.")); Spacer(Modifier.height(12.dp)); PillButton(tr("Ir a Encuestas", "Go to Surveys"), { vm.go(Route.Surveys) }) }
        } else {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Tile(surveys.size.toString(), tr("encuestas", "surveys"), Modifier.weight(1f))
                Tile(total.toString(), tr("respuestas", "responses"), Modifier.weight(1f))
                Tile(open.toString(), tr("abiertas", "open"), Modifier.weight(1f))
            }
            Muted(tr("Última respuesta recibida: ${localTime(lastAny)}", "Last response received: ${localTime(lastAny)}"))
            if (withGoal.isNotEmpty()) {
                Section(tr("Metas", "Goals"))
                withGoal.forEach { (a, s) ->
                    val goal = s.goal ?: return@forEach
                    val last7 = recent[a.id]?.get(s.formId)
                    val proj = Goals.projection(s.localSubmissions, goal, last7 ?: 0, java.time.Instant.now(), java.time.ZoneId.systemDefault())
                    AppCard(onClick = { vm.selectedAccount.value = a.id; vm.open(s.formId) }) {
                        Text(s.name, color = t().text, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                        Spacer(Modifier.height(4.dp))
                        Text(goalHeadline(s.localSubmissions, goal, proj), color = t().accent, fontWeight = FontWeight.SemiBold)
                        Spacer(Modifier.height(6.dp)); GoalBar(proj.pct); Spacer(Modifier.height(6.dp))
                        if (recent[a.id] != null) Muted(goalDetail(proj))
                    }
                }
            }
            Section(tr("Cómo les va", "How they're doing"))
            surveys.sortedByDescending { it.lastSubmissionAt ?: "" }.take(4).forEach { s ->
                AppCard(onClick = { vm.selectedAccount.value = all.first { (_, l) -> l.any { it.formId == s.formId } }.first.id; vm.open(s.formId) }) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(s.name, color = t().text, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                            Muted((if (s.isClosed) tr("cerrada", "closed") else tr("abierta", "open")) + tr(" · última: ${localTime(s.lastSubmissionAt)}", " · last: ${localTime(s.lastSubmissionAt)}"))
                        }
                        if (s.hasNewHint) { RedDot(); Spacer(Modifier.width(8.dp)) }
                        Text(if (s.neverSynced) "—" else s.localSubmissions.toString(), fontSize = 24.sp, fontWeight = FontWeight.ExtraBold, color = t().accent)
                    }
                }
            }
        }
    }
}

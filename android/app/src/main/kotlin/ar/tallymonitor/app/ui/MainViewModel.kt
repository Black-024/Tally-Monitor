package ar.tallymonitor.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import ar.tallymonitor.analysis.SurveyAnalysis
import ar.tallymonitor.core.Secret
import ar.tallymonitor.services.*
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import java.io.OutputStream

sealed interface Route {
    data object Home : Route
    data object Surveys : Route
    data object Accounts : Route
    data object Settings : Route
    data class Survey(val formId: String) : Route
}

data class Busy(val label: String, val done: Int = 0, val total: Int? = null)

/** Estado de toda la app. La interfaz solo llama a estas funciones; la clave entra como Secret y se descarta al terminar. */
class MainViewModel(val backend: TallyMonitorBackend) : ViewModel() {
    companion object {
        fun factory(b: TallyMonitorBackend) = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST") override fun <T : ViewModel> create(modelClass: Class<T>): T = MainViewModel(b) as T
        }
    }

    val route = MutableStateFlow<Route>(Route.Home)
    val message = MutableStateFlow<String?>(null)                    // aviso breve (error o confirmación)
    val busy = MutableStateFlow<Busy?>(null)
    val selectedAccount = MutableStateFlow<String?>(null)
    val accounts: StateFlow<List<Account>> = backend.accounts.observeAccounts().catch { message.value = errorText(it) }.stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())
    val theme: StateFlow<String> = backend.settings.observe("theme").stateIn(viewModelScope, SharingStarted.Eagerly, "dark")

    val syncMode: StateFlow<String> = backend.settings.observe("sync_mode").stateIn(viewModelScope, SharingStarted.Eagerly, "manual")

    /** Encuestas de todas las cuentas (sin filtros): alimenta la pestaña Inicio y los puntos rojos. */
    @OptIn(ExperimentalCoroutinesApi::class)
    val allSurveys: StateFlow<List<Pair<Account, List<SurveySummary>>>> = accounts
        .flatMapLatest { list ->
            if (list.isEmpty()) flowOf(emptyList())
            else combine(list.map { a -> backend.surveys.observeSurveys(a.id, null, false).map { a to it } }) { it.toList() }
        }
        .catch { message.value = errorText(it) }.stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    val query = MutableStateFlow("")
    val onlyFavorites = MutableStateFlow(false)
    /** Etiqueta elegida para filtrar (null = «Todas») y «Mostrar archivadas» (apagado por defecto). */
    val tagFilter = MutableStateFlow<String?>(null)
    val showArchived = MutableStateFlow(false)

    @OptIn(ExperimentalCoroutinesApi::class)
    val surveys: StateFlow<List<SurveySummary>> = combine(selectedAccount, query, onlyFavorites, tagFilter, showArchived) { a, q, f, tag, arch -> SurveyQuery(a, q, f, tag, arch) }
        .flatMapLatest { s -> val acc = s.account; if (acc == null) flowOf(emptyList()) else backend.surveys.observeSurveys(acc, s.query, s.onlyFavorites, s.tag, s.includeArchived) }
        .catch { message.value = errorText(it) }.stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    private class SurveyQuery(val account: String?, val query: String, val onlyFavorites: Boolean, val tag: String?, val includeArchived: Boolean)

    /** Etiquetas de la cuenta elegida (sin repetir, sin distinguir mayúsculas) para la fila de chips; respeta «Mostrar archivadas». */
    @OptIn(ExperimentalCoroutinesApi::class)
    val tags: StateFlow<List<String>> = combine(selectedAccount, showArchived) { a, arch -> a to arch }
        .flatMapLatest { (a, arch) ->
            if (a == null) flowOf(emptyList())
            else backend.surveys.observeSurveys(a, null, false, null, arch).map { list ->
                list.flatMap { it.tags }.distinctBy { it.lowercase() }.sortedBy { it.lowercase() }
            }
        }
        .catch { message.value = errorText(it) }.stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    init {
        // Si la etiqueta elegida ya no existe (se quitó o cambió la cuenta), vuelve a «Todas».
        viewModelScope.launch { tags.collect { list -> val cur = tagFilter.value; if (cur != null && list.none { it.equals(cur, ignoreCase = true) }) tagFilter.value = null } }
        viewModelScope.launch { accounts.collect { list -> if (selectedAccount.value == null || list.none { it.id == selectedAccount.value }) selectedAccount.value = list.firstOrNull()?.id } }
    }

    /** Para acciones sueltas de la interfaz: muestra el error traducido si falla. */
    fun run2(block: suspend () -> Unit) { viewModelScope.launch { try { block() } catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (e: Throwable) { if (e is kotlinx.coroutines.CancellationException) throw e; message.value = errorText(e) } } }

    fun go(r: Route) { route.value = r }
    fun back(): Boolean = if (route.value is Route.Home) false else { route.value = if (route.value is Route.Survey) Route.Surveys else Route.Home; true }
    fun dismissMessage() { message.value = null }

    private fun run(label: String, block: suspend () -> Unit): Job = viewModelScope.launch {
        busy.value = Busy(label)
        try { block() } catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (e: Throwable) { if (e is kotlinx.coroutines.CancellationException) throw e; message.value = errorText(e) } finally { busy.value = null }
    }

    private var syncJob: Job? = null
    fun cancelSync() { syncJob?.cancel(); busy.value = null; message.value = tr("Sincronización cancelada.", "Sync cancelled.") }

    private fun collectSync(label: String, flow: Flow<SyncEvent>, onDone: (SyncEvent) -> String) {
        syncJob?.cancel()
        syncJob = viewModelScope.launch {
            busy.value = Busy(label)
            try { flow.collect { ev -> if (ev is SyncEvent.Progress) busy.value = Busy(label, ev.done, ev.total) else onDone(ev).let { if (it.isNotEmpty()) message.value = it } } }
            catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (e: Throwable) { if (e is kotlinx.coroutines.CancellationException) throw e; message.value = errorText(e) } finally { busy.value = null }
        }
    }

    fun syncSurveys() { val a = selectedAccount.value ?: return; collectSync(tr("Buscando encuestas…", "Looking for surveys…"), backend.sync.syncForms(a)) { if (it is SyncEvent.FormsDone) tr("${it.count} encuestas actualizadas.", "${it.count} surveys updated.") else "" } }

    // ---- sincronización automática (ajuste «Sincronización: Automática») ----
    private var lastAutoAt = 0L
    /** En modo automático trae la lista de encuestas de todas las cuentas (como mucho una vez cada 2 minutos). Silenciosa si sale bien. */
    fun autoSyncLists() {
        if (syncMode.value != "auto" || busy.value != null) return
        val now = System.currentTimeMillis()
        if (now - lastAutoAt < 120_000) return
        val ids = accounts.value.filter { it.status != "no_credential" }.map { it.id }
        if (ids.isEmpty()) return
        lastAutoAt = now
        syncJob?.cancel()
        syncJob = viewModelScope.launch {
            busy.value = Busy(tr("Buscando encuestas…", "Looking for surveys…"))
            try { for (id in ids) backend.sync.syncForms(id).collect { ev -> if (ev is SyncEvent.Progress) busy.value = Busy(tr("Buscando encuestas…", "Looking for surveys…"), ev.done, ev.total) } }
            catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (e: Throwable) { if (e is kotlinx.coroutines.CancellationException) throw e; message.value = errorText(e) } finally { busy.value = null }
        }
    }

    fun syncSurvey(formId: String, full: Boolean, silent: Boolean = false) {
        val a = selectedAccount.value ?: return
        collectSync(if (full) tr("Recorrido completo…", "Full pass…") else tr("Actualizando respuestas…", "Updating responses…"), backend.sync.syncForm(a, formId, full)) {
            if (silent && it is SyncEvent.FormDone && it.warnings.isEmpty()) "" else
            if (it is SyncEvent.FormDone) when {
                it.mode == "nochange" -> tr("Sin cambios: ya tenés todo.", "No changes: you already have everything.")
                else -> tr("Listo: ${it.new} nuevas, ${it.updated} actualizadas", "Done: ${it.new} new, ${it.updated} updated") + (if (it.missing > 0) tr(", ${it.missing} ya no están en Tally", ", ${it.missing} no longer in Tally") else "") + (if ("count_mismatch" in it.warnings) tr(". Ojo: el total no coincide con el de Tally.", ". Heads up: the total doesn't match Tally's.") else ".")
            } else ""
        }
    }

    // ---- cuentas ----
    fun addAccount(name: String, key: Secret, done: () -> Unit) { run(tr("Verificando la clave…", "Verifying the key…")) { backend.accounts.add(name, key); message.value = tr("Cuenta agregada.", "Account added."); done() } }
    fun replaceKey(id: String, key: Secret, done: () -> Unit) { run(tr("Verificando la clave…", "Verifying the key…")) { val ok = backend.accounts.replaceKey(id, key); message.value = if (ok) tr("Clave reemplazada.", "Key replaced.") else tr("Clave reemplazada (no se pudo comprobar que sea del mismo usuario).", "Key replaced (couldn't check that it belongs to the same user)."); done() } }
    fun rename(id: String, name: String) { run(tr("Guardando…", "Saving…")) { backend.accounts.rename(id, name) } }
    fun removeAccount(id: String) { run(tr("Eliminando…", "Deleting…")) { backend.accounts.remove(id); message.value = tr("Cuenta eliminada junto con sus datos.", "Account deleted along with its data.") } }
    fun verify(id: String) { run(tr("Verificando…", "Verifying…")) { val r = backend.accounts.verify(id); message.value = when (r.result) { "ok" -> tr("La clave es válida.", "The key is valid."); "auth" -> tr("Tally rechazó la clave.", "Tally rejected the key."); "forbidden" -> tr("La clave no tiene permiso.", "The key doesn't have permission."); "no_credential" -> tr("Falta la clave de esta cuenta.", "This account's key is missing."); "network", "timeout" -> tr("No se pudo conectar con Tally.", "Couldn't connect to Tally."); "rate_limit" -> tr("Tally pidió esperar.", "Tally asked to wait."); else -> tr("No se pudo verificar.", "Couldn't verify.") } } }

    /** Meta, nota y etiquetas de una encuesta de la cuenta elegida. Las reglas las valida el backend (mismas que la pantalla). */
    fun saveMeta(formId: String, goal: Int?, note: String, tags: List<String>, done: () -> Unit) {
        val a = selectedAccount.value ?: return
        run(tr("Guardando…", "Saving…")) { backend.surveys.setSurveyMeta(a, formId, goal, note, tags); message.value = tr("Guardado.", "Saved."); done() }
    }
    fun setArchived(formId: String, archived: Boolean) {
        val a = selectedAccount.value ?: return
        run(tr("Guardando…", "Saving…")) { backend.surveys.setArchived(a, formId, archived); message.value = if (archived) tr("Encuesta archivada.", "Survey archived.") else tr("Encuesta desarchivada.", "Survey unarchived.") }
    }

    fun toggleFavorite(s: SurveySummary) { val a = selectedAccount.value ?: return; viewModelScope.launch { backend.surveys.setFavorite(a, s.formId, !s.isFavorite) } }
    fun open(formId: String) { val a = selectedAccount.value ?: return; viewModelScope.launch { backend.surveys.markOpened(a, formId) }; route.value = Route.Survey(formId); if (syncMode.value == "auto" && busy.value == null) syncSurvey(formId, false, silent = true) }

    /** Desde un widget: espera a que carguen las cuentas (hasta 5 s) y abre esa encuesta. */
    fun openFromWidget(accountId: String, formId: String) {
        viewModelScope.launch {
            val ok = kotlinx.coroutines.withTimeoutOrNull(5000) { accounts.first { list -> list.any { it.id == accountId } } }
            if (ok == null) return@launch
            selectedAccount.value = accountId
            open(formId)
        }
    }

    /** Desde el aviso de Inicio: va a Encuestas con la primera cuenta que tenga respuestas sin actualizar. */
    fun goToPending(accountId: String?) { if (accountId != null) selectedAccount.value = accountId; route.value = Route.Surveys }

    // ---- ajustes y copias ----
    fun setSetting(k: String, v: String) { viewModelScope.launch { try { backend.settings.set(k, v) } catch (e: Throwable) { if (e is kotlinx.coroutines.CancellationException) throw e; message.value = errorText(e) } } }
    fun createBackup(after: () -> Unit) { run(tr("Creando copia…", "Creating backup…")) { backend.backups.create(); message.value = tr("Copia creada.", "Backup created."); after() } }
    fun restoreBackup(name: String, after: () -> Unit) { run(tr("Restaurando…", "Restoring…")) { backend.backups.restore(name); message.value = tr("Copia restaurada.", "Backup restored."); after() } }
    fun deleteBackup(name: String, after: () -> Unit) { run(tr("Eliminando copia…", "Deleting backup…")) { backend.backups.delete(name); after() } }

    // ---- exportar ----
    fun export(formId: String, format: String, req: ExportRequest, out: () -> OutputStream) {
        val a = selectedAccount.value ?: return
        run(tr("Generando archivo…", "Generating file…")) {
            val r = if (format == "pdf") backend.export.exportPdf(a, formId, req, out) else backend.export.exportXlsx(a, formId, req, out)
            message.value = tr("Archivo guardado (${r.responses} respuestas", "File saved (${r.responses} responses") + (if (r.textIncluded) if (r.masked) tr(", textos con datos personales enmascarados", ", texts with personal data masked") else tr(", textos SIN enmascarar", ", texts NOT masked") else "") + ")."
        }
    }
    fun savePng(bytes: ByteArray, out: () -> OutputStream) { run(tr("Guardando imagen…", "Saving image…")) { backend.export.savePng(bytes, out); message.value = tr("Imagen guardada.", "Image saved.") } }
}

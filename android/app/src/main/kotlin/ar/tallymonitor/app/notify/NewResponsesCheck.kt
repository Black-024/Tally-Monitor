package ar.tallymonitor.app.notify

import android.content.Context
import ar.tallymonitor.analysis.NewResponses
import ar.tallymonitor.analysis.PendingInput
import ar.tallymonitor.app.widget.WidgetSnapshot
import ar.tallymonitor.core.ApiException
import ar.tallymonitor.core.ErrorCode
import ar.tallymonitor.services.SurveySummary
import ar.tallymonitor.services.TallyMonitorBackend
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.first

/**
 * Un chequeo de avisos (spec 1.1 §4), con el MISMO backend que usa la app (sin secretos propios):
 * 1) por cada cuenta con clave válida trae solo el listado de encuestas; 2) suma lo que Tally informa de más en las no archivadas;
 * 3) avisa solo si el total subió desde el último aviso. Los errores de red/401/429 son silenciosos: se reintenta en el próximo ciclo.
 */
object NewResponsesCheck {
    suspend fun run(context: Context, backend: TallyMonitorBackend) {
        if (backend.settings.get("notify_mode") != "on") return
        val accounts = backend.accounts.observeAccounts().first()
        var tried = 0; var ok = 0
        for (acc in accounts) {
            if (acc.status == "no_credential" || acc.status == "key_rejected") continue          // sin clave válida no se consulta
            tried++
            try {
                backend.sync.syncForms(acc.id).collect { }
                ok++
            } catch (e: CancellationException) { throw e
            } catch (e: ApiException) {
                // 401/403: se marca la cuenta como hace la app al validar; el resto (red, 429, 5xx) se ignora hasta el próximo ciclo
                if (e.code == ErrorCode.KEY_REJECTED || e.code == ErrorCode.FORBIDDEN) {
                    try { backend.accounts.verify(acc.id) } catch (e2: CancellationException) { throw e2 } catch (e2: Exception) { /* silencioso */ }
                }
            } catch (e: Exception) { /* silencioso */ }
        }
        if (tried == 0 || ok == 0) return                                   // nada se pudo consultar: no se decide nada

        val all = ArrayList<SurveySummary>()
        val per = ArrayList<Pair<String, List<SurveySummary>>>()
        for (acc in accounts) {
            val l = backend.surveys.observeSurveys(acc.id, includeArchived = true).first()
            all += l; per += (acc.id to l)
        }
        WidgetSnapshot.save(context, WidgetSnapshot.countsOfAccounts(per))

        val totals = NewResponses.totals(all.map { PendingInput(it.reportedSubmissions, it.localSubmissions, it.archived) })
        val last = backend.settings.get("notified_new_total").toIntOrNull() ?: 0
        val decision = NewResponses.decide(totals, last)
        if (decision.notify && !Notifier.show(context, totals)) return          // si no se pudo mostrar, no se «gasta» el aviso
        backend.settings.set("notified_new_total", decision.storeTotal.toString())
    }
}

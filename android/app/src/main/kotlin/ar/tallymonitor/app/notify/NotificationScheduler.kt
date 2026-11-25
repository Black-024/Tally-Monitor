package ar.tallymonitor.app.notify

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import ar.tallymonitor.services.TallyMonitorBackend
import kotlinx.coroutines.CancellationException
import java.util.concurrent.TimeUnit

/** Programa o cancela el chequeo periódico. El intervalo mínimo real lo fija el sistema (15 min). */
object NotificationScheduler {
    private const val UNIQUE = "new_responses_check"
    val INTERVALS = listOf(15, 30, 60, 360)

    /** `replace`: aplica un intervalo nuevo; si no, deja programado lo que ya había. */
    fun schedule(context: Context, minutes: Int, replace: Boolean) {
        val every = (if (minutes in INTERVALS) minutes else 60).toLong()
        val req = PeriodicWorkRequestBuilder<NewResponsesWorker>(every, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(context.applicationContext)
            .enqueueUniquePeriodicWork(UNIQUE, if (replace) ExistingPeriodicWorkPolicy.UPDATE else ExistingPeriodicWorkPolicy.KEEP, req)
    }

    fun cancel(context: Context) { WorkManager.getInstance(context.applicationContext).cancelUniqueWork(UNIQUE) }

    /** Al abrir la app: deja la programación acorde con el ajuste (también tras restaurar una copia). */
    suspend fun reconcile(context: Context, backend: TallyMonitorBackend) {
        try {
            if (backend.settings.get("notify_mode") == "on" && Notifier.hasPermission(context)) {
                Notifier.ensureChannel(context)
                schedule(context, backend.settings.get("notify_interval_min").toIntOrNull() ?: 60, replace = false)
            } else cancel(context)
        } catch (e: CancellationException) { throw e
        } catch (e: Exception) { /* sin avisos hasta la próxima vez */ }
    }
}

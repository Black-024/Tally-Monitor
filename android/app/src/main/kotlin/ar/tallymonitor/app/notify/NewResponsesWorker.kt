package ar.tallymonitor.app.notify

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import ar.tallymonitor.app.TallyApp
import kotlinx.coroutines.CancellationException

/** Tarea periódica de WorkManager. Reutiliza el backend de la app (TallyApp.backend); no guarda ni lee claves por su cuenta. */
class NewResponsesWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        try {
            val app = applicationContext as TallyApp
            NewResponsesCheck.run(applicationContext, app.backend)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            // silencioso: el próximo ciclo reintenta
        }
        return Result.success()
    }
}

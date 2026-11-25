package ar.tallymonitor.app.notify

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import ar.tallymonitor.analysis.NewResponses
import ar.tallymonitor.analysis.PendingTotals
import ar.tallymonitor.app.MainActivity
import ar.tallymonitor.app.R
import ar.tallymonitor.app.ui.tr

/** Canal y notificación de «Respuestas nuevas». Solo lleva conteos: nunca nombres de encuestas ni textos de respuestas. */
object Notifier {
    const val CHANNEL_ID = "new_responses"
    const val EXTRA_OPEN_HOME = "ar.tallymonitor.OPEN_HOME"
    private const val NOTIFICATION_ID = 1001

    fun ensureChannel(context: Context) {
        val mgr = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val ch = NotificationChannel(CHANNEL_ID, tr("Respuestas nuevas", "New responses"), NotificationManager.IMPORTANCE_DEFAULT)
        ch.description = tr("Avisa cuando Tally informa respuestas que todavía no descargaste.", "Notifies you when Tally reports responses you haven't downloaded yet.")
        mgr.createNotificationChannel(ch)
    }

    /** («3 respuestas nuevas en 2 encuestas» / «3 new responses in 2 surveys»). El español sale idéntico a [NewResponses.title]. */
    private fun title(t: PendingTotals): String = tr(
        "${t.total} ${if (t.total == 1) "respuesta nueva" else "respuestas nuevas"} en ${t.surveys} ${if (t.surveys == 1) "encuesta" else "encuestas"}",
        "${t.total} ${if (t.total == 1) "new response" else "new responses"} in ${t.surveys} ${if (t.surveys == 1) "survey" else "surveys"}")

    /** Android 13+ pide el permiso en tiempo de ejecución; antes no hace falta. */
    fun needsRuntimePermission(): Boolean = Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU

    fun hasPermission(context: Context): Boolean =
        !needsRuntimePermission() || ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    /** Permiso concedido y notificaciones de la app (y del canal) no bloqueadas. */
    fun canNotify(context: Context): Boolean = hasPermission(context) && NotificationManagerCompat.from(context).areNotificationsEnabled()

    /** Devuelve true si se publicó. Tocarla abre la app en Inicio. */
    fun show(context: Context, totals: PendingTotals): Boolean {
        if (!canNotify(context)) return false
        ensureChannel(context)
        val open = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra(EXTRA_OPEN_HOME, true)
        }
        val pi = PendingIntent.getActivity(context, 1, open, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val n = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_notify)
            .setContentTitle(title(totals))
            .setContentText(tr(NewResponses.BODY, "Tap to open Tally Monitor"))
            .setContentIntent(pi)
            .setAutoCancel(true)
            .setOnlyAlertOnce(true)
            .build()
        return try { NotificationManagerCompat.from(context).notify(NOTIFICATION_ID, n); true } catch (e: SecurityException) { false }
    }
}

package ar.tallymonitor.app.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.view.View
import android.widget.RemoteViews
import android.widget.RemoteViewsService
import ar.tallymonitor.app.MainActivity
import ar.tallymonitor.app.R
import ar.tallymonitor.app.ui.tr

object WidgetIntents {
    const val EXTRA_ACCOUNT = "ar.tallymonitor.app.WIDGET_ACCOUNT"
    const val EXTRA_FORM = "ar.tallymonitor.app.WIDGET_FORM"

    fun openApp(context: Context, requestCode: Int = 0): PendingIntent {
        val open = Intent(context, MainActivity::class.java).apply { flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP }
        return PendingIntent.getActivity(context, requestCode, open, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    }

    /** Abre la app directamente en una encuesta. */
    fun openSurvey(context: Context, requestCode: Int, accountId: String, formId: String): PendingIntent {
        val open = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra(EXTRA_ACCOUNT, accountId); putExtra(EXTRA_FORM, formId)
            data = Uri.parse("tallymonitor://survey/$requestCode")        // distingue un PendingIntent de otro
        }
        return PendingIntent.getActivity(context, requestCode, open, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    }
}

/** Base de los widgets: cada uno arma sus RemoteViews con la instantánea guardada. Tocar un widget abre la app (salvo que el widget haga otra cosa). */
abstract class BaseTallyWidget : AppWidgetProvider() {
    abstract fun build(context: Context, counts: WidgetCounts?, showNames: Boolean, appWidgetId: Int): RemoteViews

    /** Los que tienen su propio manejo del toque (acceso directo, lista) devuelven false. */
    protected open val rootOpensApp: Boolean get() = true

    override fun onUpdate(context: Context, appWidgetManager: AppWidgetManager, appWidgetIds: IntArray) {
        for (id in appWidgetIds) appWidgetManager.updateAppWidget(id, safeBuild(context, id))
    }

    fun safeBuild(context: Context, appWidgetId: Int): RemoteViews {
        val views = build(context, WidgetSnapshot.load(context), WidgetSnapshot.showNames(context), appWidgetId)
        if (rootOpensApp) views.setOnClickPendingIntent(R.id.widget_root, WidgetIntents.openApp(context))
        return views
    }
}

internal fun plural(n: Int, one: String, many: String) = if (n == 1) one else many
internal fun group(n: Int): String = String.format(ar.tallymonitor.app.ui.I18n.locale, "%,d", n)

/** «hace 5 min», «hace 3 h», «hace 4 días». */
internal fun ago(thenMillis: Long, nowMillis: Long): String {
    val min = ((nowMillis - thenMillis) / 60_000L).coerceAtLeast(0L)
    return when {
        min < 1 -> tr("hace un momento", "just now")
        min < 60 -> tr("hace $min min", "$min min ago")
        min < 48 * 60 -> tr("hace ${min / 60} h", "${min / 60} h ago")
        else -> tr("hace ${min / (24 * 60)} días", "${min / (24 * 60)} days ago")
    }
}

internal fun surveyName(s: WidgetSurvey, index: Int, showNames: Boolean): String =
    if (showNames && s.name.isNotBlank()) s.name else tr("Encuesta ${index + 1}", "Survey ${index + 1}")

/** 1) Resumen 2×1. */
class TallyWidgetProvider : BaseTallyWidget() {
    override fun build(context: Context, counts: WidgetCounts?, showNames: Boolean, appWidgetId: Int): RemoteViews {
        val views = RemoteViews(context.packageName, R.layout.widget_tally)
        if (counts == null) {
            views.setTextViewText(R.id.widget_title, tr("Tally Monitor: abrí la app para ver tus encuestas", "Tally Monitor: open the app to see your surveys"))
            views.setViewVisibility(R.id.widget_stale, View.GONE)
        } else {
            views.setTextViewText(R.id.widget_title, tr("${group(counts.surveys)} ${plural(counts.surveys, "encuesta", "encuestas")} · ${group(counts.responses)} ${plural(counts.responses, "respuesta", "respuestas")}", "${group(counts.surveys)} ${plural(counts.surveys, "survey", "surveys")} · ${group(counts.responses)} ${plural(counts.responses, "response", "responses")}"))
            if (counts.stale > 0) {
                views.setTextViewText(R.id.widget_stale, tr("● ${counts.stale} sin actualizar", "● ${counts.stale} not updated"))
                views.setViewVisibility(R.id.widget_stale, View.VISIBLE)
            } else views.setViewVisibility(R.id.widget_stale, View.GONE)
        }
        return views
    }
}

/** 2) Semáforo 1×1: círculo redondo (nunca estirado) rojo con el número / verde con ✓ / gris sin datos. */
class TallyDotWidgetProvider : BaseTallyWidget() {
    override fun build(context: Context, counts: WidgetCounts?, showNames: Boolean, appWidgetId: Int): RemoteViews {
        val views = RemoteViews(context.packageName, R.layout.widget_dot)
        val (img, text) = when {
            counts == null || counts.surveys == 0 -> R.drawable.widget_dot_gray to "–"
            counts.stale > 0 -> R.drawable.widget_dot_red to (if (counts.stale > 99) "99+" else counts.stale.toString())
            else -> R.drawable.widget_dot_green to "✓"
        }
        views.setImageViewResource(R.id.widget_dot_img, img)
        views.setTextViewText(R.id.widget_dot_text, text)
        return views
    }
}

/** 4) Meta 2×2: sigue la meta de UNA encuesta (se elige al agregar el widget; si no hay ninguna con meta, se la podés crear ahí mismo). */
class TallyGoalWidgetProvider : BaseTallyWidget() {
    override val rootOpensApp: Boolean get() = false

    override fun build(context: Context, counts: WidgetCounts?, showNames: Boolean, appWidgetId: Int): RemoteViews {
        val views = RemoteViews(context.packageName, R.layout.widget_goal)
        views.setOnClickPendingIntent(R.id.widget_root, WidgetIntents.openApp(context, appWidgetId))
        val chosen = WidgetSnapshot.goalChoice(context, appWidgetId)
        if (chosen != null) {
            val s = counts?.list?.firstOrNull { it.accountId == chosen.first && it.formId == chosen.second }
            if (s == null) { empty(views, tr("Encuesta no disponible. Tocá para abrir la app.", "Survey not available. Tap to open the app.")); return views }
            views.setOnClickPendingIntent(R.id.widget_root, WidgetIntents.openSurvey(context, 1000 + appWidgetId, s.accountId, s.formId))
            val name = if (showNames && s.name.isNotBlank()) s.name else tr("Encuesta elegida", "Chosen survey")
            if (s.goal <= 0) { empty(views, tr("Esta encuesta ya no tiene meta. Tocá para abrirla y ponerle una.", "This survey no longer has a goal. Tap to open it and set one."), name); return views }
            fill(views, name, s.count, s.goal)
            return views
        }
        // widgets agregados antes de poder elegir: siguen con la meta más avanzada
        if (counts == null || counts.goalPct < 0) {
            empty(views, if (counts == null) tr("Abrí la app para empezar.", "Open the app to get started.") else tr("Ponele una meta a una encuesta para seguirla acá.", "Set a goal on a survey to follow it here."))
        } else {
            fill(views, if (showNames && counts.goalName.isNotBlank()) counts.goalName else tr("Meta principal", "Main goal"), counts.goalLocal, counts.goalTotal)
        }
        return views
    }

    private fun empty(views: RemoteViews, detail: String, label: String = tr("Meta", "Goal")) {
        views.setTextViewText(R.id.widget_goal_label, label)
        views.setTextViewText(R.id.widget_goal_pct, "—")
        views.setProgressBar(R.id.widget_goal_bar, 100, 0, false)
        views.setTextViewText(R.id.widget_goal_detail, detail)
    }

    private fun fill(views: RemoteViews, label: String, local: Int, goal: Int) {
        val pct = minOf(100, local * 100 / maxOf(1, goal))
        views.setTextViewText(R.id.widget_goal_label, label)
        views.setTextViewText(R.id.widget_goal_pct, "$pct %")
        views.setProgressBar(R.id.widget_goal_bar, 100, pct, false)
        views.setTextViewText(R.id.widget_goal_detail,
            if (local >= goal) tr("¡Meta alcanzada! ${group(local)} respuestas", "Goal reached! ${group(local)} responses")
            else tr("${group(local)} de ${group(goal)} respuestas", "${group(local)} of ${group(goal)} responses"))
    }

    override fun onDeleted(context: Context, appWidgetIds: IntArray) {
        for (id in appWidgetIds) WidgetSnapshot.clearGoalChoice(context, id)
    }
}

/** 5) Ranking 3×2: las 3 encuestas con más respuestas, con barras proporcionales. */
class TallyRankingWidgetProvider : BaseTallyWidget() {
    private val rows = intArrayOf(R.id.race_row1, R.id.race_row2, R.id.race_row3)
    private val names = intArrayOf(R.id.race_name1, R.id.race_name2, R.id.race_name3)
    private val counts = intArrayOf(R.id.race_count1, R.id.race_count2, R.id.race_count3)
    private val bars = intArrayOf(R.id.race_bar1, R.id.race_bar2, R.id.race_bar3)

    override fun build(context: Context, counts: WidgetCounts?, showNames: Boolean, appWidgetId: Int): RemoteViews {
        val views = RemoteViews(context.packageName, R.layout.widget_race)
        val top = counts?.list?.take(3) ?: emptyList()
        views.setViewVisibility(R.id.race_empty, if (top.isEmpty()) View.VISIBLE else View.GONE)
        views.setTextViewText(R.id.race_empty, if (counts == null) tr("Abrí la app para ver tus encuestas.", "Open the app to see your surveys.") else tr("Todavía no hay encuestas guardadas.", "There are no saved surveys yet."))
        val max = maxOf(1, top.firstOrNull()?.count ?: 1)
        for (i in 0 until 3) {
            val s = top.getOrNull(i)
            if (s == null) { views.setViewVisibility(rows[i], View.GONE); continue }
            views.setViewVisibility(rows[i], View.VISIBLE)
            views.setTextViewText(names[i], (if (s.pending) "● " else "") + surveyName(s, i, showNames))
            views.setTextViewText(this.counts[i], group(s.count))
            views.setProgressBar(bars[i], max, s.count, false)
        }
        return views
    }
}

/** 6) Novedades 2×2: «3 respuestas nuevas» / «Sin nuevas respuestas». */
class TallyNewsWidgetProvider : BaseTallyWidget() {
    override fun build(context: Context, counts: WidgetCounts?, showNames: Boolean, appWidgetId: Int): RemoteViews {
        val views = RemoteViews(context.packageName, R.layout.widget_news)
        when {
            counts == null || counts.surveys == 0 -> {
                views.setInt(R.id.widget_root, "setBackgroundResource", R.drawable.widget_bg)
                views.setTextViewText(R.id.news_big, "—")
                views.setTextViewText(R.id.news_title, tr("Sin datos todavía", "No data yet"))
                views.setTextViewText(R.id.news_sub, tr("Abrí la app y actualizá la lista de encuestas.", "Open the app and refresh the survey list."))
            }
            counts.newResponses > 0 -> {
                views.setInt(R.id.widget_root, "setBackgroundResource", R.drawable.widget_bg_alert)
                views.setTextViewText(R.id.news_big, if (counts.newResponses > 999) "999+" else counts.newResponses.toString())
                views.setTextViewText(R.id.news_title, plural(counts.newResponses, tr("respuesta nueva", "new response"), tr("respuestas nuevas", "new responses")))
                views.setTextViewText(R.id.news_sub, tr("en ${counts.stale} ${plural(counts.stale, "encuesta", "encuestas")} · tocá para actualizar", "in ${counts.stale} ${plural(counts.stale, "survey", "surveys")} · tap to refresh"))
            }
            else -> {
                views.setInt(R.id.widget_root, "setBackgroundResource", R.drawable.widget_bg)
                views.setTextViewText(R.id.news_big, "✓")
                views.setTextViewText(R.id.news_title, tr("Sin nuevas respuestas", "No new responses"))
                views.setTextViewText(R.id.news_sub,
                    if (counts.lastAtMillis > 0L) tr("Todo al día · última ${ago(counts.lastAtMillis, System.currentTimeMillis())}", "All up to date · last ${ago(counts.lastAtMillis, System.currentTimeMillis())}") else tr("Todo al día", "All up to date"))
            }
        }
        return views
    }
}

/** 7) Acceso directo 2×1 a UNA encuesta (se elige al agregar el widget). */
class TallyShortcutWidgetProvider : BaseTallyWidget() {
    override val rootOpensApp: Boolean get() = false

    override fun build(context: Context, counts: WidgetCounts?, showNames: Boolean, appWidgetId: Int): RemoteViews {
        val views = RemoteViews(context.packageName, R.layout.widget_shortcut)
        val chosen = WidgetSnapshot.shortcut(context, appWidgetId)
        val survey = if (chosen == null) null else counts?.list?.firstOrNull { it.accountId == chosen.first && it.formId == chosen.second }
        if (chosen == null || survey == null) {
            views.setTextViewText(R.id.shortcut_name, if (chosen == null) tr("Elegí una encuesta", "Choose a survey") else tr("Encuesta no disponible", "Survey not available"))
            views.setTextViewText(R.id.shortcut_count, if (chosen == null) tr("Volvé a agregar el widget", "Add the widget again") else tr("Tocá para abrir la app", "Tap to open the app"))
            views.setViewVisibility(R.id.shortcut_dot, View.GONE)
            views.setOnClickPendingIntent(R.id.widget_root, WidgetIntents.openApp(context, appWidgetId))
        } else {
            views.setTextViewText(R.id.shortcut_name, if (showNames && survey.name.isNotBlank()) survey.name else tr("Encuesta elegida", "Chosen survey"))
            views.setTextViewText(R.id.shortcut_count, tr("${group(survey.count)} ${plural(survey.count, "respuesta", "respuestas")}", "${group(survey.count)} ${plural(survey.count, "response", "responses")}") + if (survey.pending) tr(" · hay nuevas", " · new ones") else "")
            views.setViewVisibility(R.id.shortcut_dot, if (survey.pending) View.VISIBLE else View.GONE)
            views.setOnClickPendingIntent(R.id.widget_root, WidgetIntents.openSurvey(context, appWidgetId, survey.accountId, survey.formId))
        }
        return views
    }

    override fun onDeleted(context: Context, appWidgetIds: IntArray) {
        for (id in appWidgetIds) WidgetSnapshot.clearShortcut(context, id)
    }
}

/** 8) Lista 5×2 (se achica hasta 3×2): todas las encuestas, se desliza y cada una abre la encuesta. */
class TallyListWidgetProvider : BaseTallyWidget() {
    override val rootOpensApp: Boolean get() = false

    override fun build(context: Context, counts: WidgetCounts?, showNames: Boolean, appWidgetId: Int): RemoteViews {
        val views = RemoteViews(context.packageName, R.layout.widget_list)
        val service = Intent(context, WidgetListService::class.java).apply {
            putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, appWidgetId)
            data = Uri.parse(toUri(Intent.URI_INTENT_SCHEME))
        }
        views.setRemoteAdapter(R.id.widget_list, service)
        views.setEmptyView(R.id.widget_list, R.id.widget_empty)
        views.setTextViewText(R.id.widget_empty, if (counts == null) tr("Abrí la app para ver tus encuestas.", "Open the app to see your surveys.") else tr("Todavía no hay encuestas guardadas.", "There are no saved surveys yet."))
        views.setTextViewText(R.id.widget_title, tr("Tus encuestas", "Your surveys") + if (counts != null && counts.stale > 0) tr("  ● ${counts.stale} sin actualizar", "  ● ${counts.stale} not updated") else "")
        // Plantilla del toque en cada fila: las filas completan la cuenta y la encuesta. Tiene que ser MUTABLE para que Android pueda completarla.
        val template = Intent(context, MainActivity::class.java).apply { flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP }
        val pi = PendingIntent.getActivity(context, appWidgetId, template, PendingIntent.FLAG_MUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        views.setPendingIntentTemplate(R.id.widget_list, pi)
        views.setOnClickPendingIntent(R.id.widget_title, WidgetIntents.openApp(context, appWidgetId))
        return views
    }
}

class WidgetListService : RemoteViewsService() {
    override fun onGetViewFactory(intent: Intent): RemoteViewsFactory = Factory(applicationContext)

    private class Factory(private val context: Context) : RemoteViewsFactory {
        private var items: List<WidgetSurvey> = emptyList()
        private var showNames = true

        override fun onCreate() {}
        override fun onDataSetChanged() {
            items = WidgetSnapshot.load(context)?.list ?: emptyList()
            showNames = WidgetSnapshot.showNames(context)
        }
        override fun onDestroy() { items = emptyList() }
        override fun getCount(): Int = items.size
        override fun getViewAt(position: Int): RemoteViews {
            val rv = RemoteViews(context.packageName, R.layout.widget_list_item)
            val s = items.getOrNull(position) ?: return rv
            rv.setTextViewText(R.id.item_name, surveyName(s, position, showNames))
            rv.setTextViewText(R.id.item_count, group(s.count))
            rv.setViewVisibility(R.id.item_dot, if (s.pending) View.VISIBLE else View.GONE)
            rv.setOnClickFillInIntent(R.id.item_root, Intent().apply {
                putExtra(WidgetIntents.EXTRA_ACCOUNT, s.accountId); putExtra(WidgetIntents.EXTRA_FORM, s.formId)
            })
            return rv
        }
        override fun getLoadingView(): RemoteViews? = null
        override fun getViewTypeCount(): Int = 1
        override fun getItemId(position: Int): Long = position.toLong()
        override fun hasStableIds(): Boolean = false
    }
}

object WidgetProviders {
    private val ALL = listOf<Class<out BaseTallyWidget>>(
        TallyWidgetProvider::class.java, TallyDotWidgetProvider::class.java,
        TallyGoalWidgetProvider::class.java, TallyRankingWidgetProvider::class.java, TallyNewsWidgetProvider::class.java,
        TallyShortcutWidgetProvider::class.java, TallyListWidgetProvider::class.java,
    )

    /** Redibuja todos los widgets que la persona haya puesto en la pantalla de inicio. */
    fun refreshAll(context: Context) {
        val app = context.applicationContext
        val mgr = AppWidgetManager.getInstance(app)
        for (cls in ALL) {
            val ids = mgr.getAppWidgetIds(ComponentName(app, cls))
            if (ids.isEmpty()) continue
            val provider = cls.getDeclaredConstructor().newInstance()
            for (id in ids) mgr.updateAppWidget(id, provider.safeBuild(app, id))
            if (cls == TallyListWidgetProvider::class.java) mgr.notifyAppWidgetViewDataChanged(ids, R.id.widget_list)
        }
    }
}

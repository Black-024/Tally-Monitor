package ar.tallymonitor.app.widget

import android.content.Context
import ar.tallymonitor.services.SurveySummary
import java.time.Instant
import java.time.OffsetDateTime
import org.json.JSONArray
import org.json.JSONObject

/** Una encuesta tal como la ven los widgets (sin claves ni identificadores de personas). */
data class WidgetSurvey(val accountId: String, val formId: String, val name: String, val count: Int, val pending: Boolean, val goal: Int = 0)

/**
 * Instantánea para los widgets, en un SharedPreferences privado de la app: conteos, la meta más avanzada y la lista de
 * encuestas (con nombre, para el ranking, el acceso directo y la lista). Con «Mostrar nombres» apagado en Ajustes los widgets
 * no muestran los nombres (usan «Encuesta 1», «Encuesta 2»…). La guarda la app cada vez que carga el listado y en el chequeo de avisos.
 */
data class WidgetCounts(
    val surveys: Int, val responses: Int, val stale: Int,
    val lastAtMillis: Long = 0L,           // 0 = sin datos
    val goalPct: Int = -1,                 // -1 = ninguna encuesta con meta
    val goalLocal: Int = 0, val goalTotal: Int = 0, val goalName: String = "",
    val lastName: String = "",
    val newResponses: Int = 0,             // lo que Tally informa de más que lo guardado, sumando las encuestas no archivadas
    val list: List<WidgetSurvey> = emptyList(),   // de la que más respuestas tiene a la que menos
)

object WidgetSnapshot {
    private const val FILE = "widget_snapshot"
    private const val K_SURVEYS = "surveys"
    private const val K_RESPONSES = "responses"
    private const val K_STALE = "stale"
    private const val K_LAST_AT = "last_at"
    private const val K_GOAL_PCT = "goal_pct"
    private const val K_GOAL_LOCAL = "goal_local"
    private const val K_GOAL_TOTAL = "goal_total"
    private const val K_GOAL_NAME = "goal_name"
    private const val K_LAST_NAME = "last_name"
    private const val K_NEW = "new_responses"
    private const val K_LIST = "list"
    private const val K_SHOW_NAMES = "show_names"
    private const val MAX_LIST = 40

    private fun parseMillis(s: String?): Long {
        if (s.isNullOrBlank()) return 0L
        return try { Instant.parse(s).toEpochMilli() } catch (e: RuntimeException) {
            try { OffsetDateTime.parse(s).toInstant().toEpochMilli() } catch (e2: RuntimeException) { 0L }
        }
    }

    fun countsOf(all: Collection<SurveySummary>): WidgetCounts = countsOfAccounts(listOf("" to all))

    /** Solo cuenta las encuestas NO archivadas. La meta elegida es la más avanzada que todavía no se alcanzó (si todas se alcanzaron, una alcanzada). */
    fun countsOfAccounts(perAccount: List<Pair<String, Collection<SurveySummary>>>): WidgetCounts {
        val live = ArrayList<Pair<String, SurveySummary>>()
        for ((acc, items) in perAccount) for (s in items) if (!s.archived) live.add(acc to s)
        var lastAt = 0L
        var lastName = ""
        for ((_, s) in live) {
            val t = parseMillis(s.lastSubmissionAt)
            if (t > lastAt) { lastAt = t; lastName = s.name }
        }
        val withGoal = live.map { it.second }.filter { (it.goal ?: 0) > 0 }
        val open = withGoal.filter { it.localSubmissions < (it.goal ?: 0) }
        val pick = open.maxByOrNull { it.localSubmissions.toDouble() / (it.goal ?: 1) } ?: withGoal.firstOrNull()
        val goal = pick?.goal ?: 0
        val pct = if (pick == null || goal <= 0) -1 else minOf(100, pick.localSubmissions * 100 / goal)
        val news = live.sumOf { (_, s) -> maxOf(0, (s.reportedSubmissions ?: 0) - s.localSubmissions) }
        val list = live.sortedByDescending { it.second.localSubmissions }.take(MAX_LIST)
            .map { (acc, s) -> WidgetSurvey(acc, s.formId, s.name, s.localSubmissions, s.hasNewHint, s.goal ?: 0) }
        return WidgetCounts(live.size, live.sumOf { it.second.localSubmissions }, live.count { it.second.hasNewHint }, lastAt, pct,
            pick?.localSubmissions ?: 0, goal, pick?.name ?: "", lastName, news, list)
    }

    private fun prefs(context: Context) = context.applicationContext.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    fun save(context: Context, counts: WidgetCounts) {
        try {
            val arr = JSONArray()
            for (s in counts.list) arr.put(JSONObject().put("a", s.accountId).put("f", s.formId).put("n", s.name).put("c", s.count).put("p", s.pending).put("g", s.goal))
            prefs(context).edit()
                .putInt(K_SURVEYS, counts.surveys).putInt(K_RESPONSES, counts.responses).putInt(K_STALE, counts.stale)
                .putLong(K_LAST_AT, counts.lastAtMillis).putInt(K_GOAL_PCT, counts.goalPct)
                .putInt(K_GOAL_LOCAL, counts.goalLocal).putInt(K_GOAL_TOTAL, counts.goalTotal)
                .putString(K_GOAL_NAME, counts.goalName).putString(K_LAST_NAME, counts.lastName)
                .putInt(K_NEW, counts.newResponses).putString(K_LIST, arr.toString()).apply()
            WidgetProviders.refreshAll(context)
        } catch (e: RuntimeException) { /* los widgets son accesorios: nunca deben romper la app */ }
    }

    /** null si todavía no se guardó nada. */
    fun load(context: Context): WidgetCounts? {
        val p = prefs(context)
        if (!p.contains(K_SURVEYS)) return null
        val list = ArrayList<WidgetSurvey>()
        try {
            val arr = JSONArray(p.getString(K_LIST, "[]") ?: "[]")
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                list.add(WidgetSurvey(o.optString("a"), o.optString("f"), o.optString("n"), o.optInt("c"), o.optBoolean("p"), o.optInt("g")))
            }
        } catch (e: org.json.JSONException) { list.clear() }
        return WidgetCounts(p.getInt(K_SURVEYS, 0), p.getInt(K_RESPONSES, 0), p.getInt(K_STALE, 0),
            p.getLong(K_LAST_AT, 0L), p.getInt(K_GOAL_PCT, -1), p.getInt(K_GOAL_LOCAL, 0), p.getInt(K_GOAL_TOTAL, 0),
            p.getString(K_GOAL_NAME, "") ?: "", p.getString(K_LAST_NAME, "") ?: "", p.getInt(K_NEW, 0), list)
    }

    /** Por defecto los nombres SE MUESTRAN (el ranking, el acceso directo y la lista no tendrían sentido sin ellos). */
    fun showNames(context: Context): Boolean = prefs(context).getBoolean(K_SHOW_NAMES, true)

    fun setShowNames(context: Context, on: Boolean) {
        try { prefs(context).edit().putBoolean(K_SHOW_NAMES, on).apply(); WidgetProviders.refreshAll(context) } catch (e: RuntimeException) { /* ídem */ }
    }

    // ---- acceso directo: cada widget guarda qué encuesta eligió ----
    fun shortcut(context: Context, widgetId: Int): Pair<String, String>? {
        val v = prefs(context).getString("shortcut_$widgetId", null) ?: return null
        val i = v.indexOf('\u0001')
        return if (i < 0) null else v.substring(0, i) to v.substring(i + 1)
    }

    fun setShortcut(context: Context, widgetId: Int, accountId: String, formId: String) {
        prefs(context).edit().putString("shortcut_$widgetId", accountId + "\u0001" + formId).apply()
    }

    fun clearShortcut(context: Context, widgetId: Int) { prefs(context).edit().remove("shortcut_$widgetId").apply() }

    // ---- widget Meta: cada widget guarda de qué encuesta sigue la meta ----
    fun goalChoice(context: Context, widgetId: Int): Pair<String, String>? {
        val v = prefs(context).getString("goal_$widgetId", null) ?: return null
        val i = v.indexOf('\u0001')
        return if (i < 0) null else v.substring(0, i) to v.substring(i + 1)
    }

    fun setGoalChoice(context: Context, widgetId: Int, accountId: String, formId: String) {
        prefs(context).edit().putString("goal_$widgetId", accountId + "\u0001" + formId).apply()
    }

    fun clearGoalChoice(context: Context, widgetId: Int) { prefs(context).edit().remove("goal_$widgetId").apply() }

    /** Refleja en la instantánea una meta recién guardada (la app la rehace completa en la próxima carga). */
    fun withGoal(context: Context, accountId: String, formId: String, goal: Int) {
        try {
            val arr = JSONArray(prefs(context).getString(K_LIST, "[]") ?: "[]")
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                if (o.optString("a") == accountId && o.optString("f") == formId) o.put("g", goal)
            }
            prefs(context).edit().putString(K_LIST, arr.toString()).apply()
        } catch (e: org.json.JSONException) { /* ídem */ }
    }
}

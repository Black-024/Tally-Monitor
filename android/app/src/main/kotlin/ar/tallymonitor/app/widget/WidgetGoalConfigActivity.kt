package ar.tallymonitor.app.widget

import android.app.Activity
import android.app.AlertDialog
import android.appwidget.AppWidgetManager
import android.content.Intent
import android.os.Bundle
import android.text.InputType
import android.widget.ArrayAdapter
import android.widget.EditText
import android.widget.ListView
import android.widget.TextView
import android.widget.Toast
import ar.tallymonitor.app.TallyApp
import ar.tallymonitor.app.ui.errorText
import ar.tallymonitor.app.ui.tr
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * Se abre al agregar el widget «Meta»: elegís de qué encuesta seguir la meta. Las que todavía no tienen meta también aparecen:
 * al tocarlas te pide el número y se lo guarda ahí mismo (igual que «Editar» dentro de la app). No llama a Tally ni toca claves.
 */
class WidgetGoalConfigActivity : Activity() {
    private val scope = CoroutineScope(Dispatchers.Main + Job())
    private var widgetId = AppWidgetManager.INVALID_APPWIDGET_ID
    private var items: List<WidgetSurvey> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        widgetId = intent?.extras?.getInt(AppWidgetManager.EXTRA_APPWIDGET_ID, AppWidgetManager.INVALID_APPWIDGET_ID) ?: AppWidgetManager.INVALID_APPWIDGET_ID
        setResult(RESULT_CANCELED, Intent().putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, widgetId))
        if (widgetId == AppWidgetManager.INVALID_APPWIDGET_ID) { finish(); return }
        items = WidgetSnapshot.load(this)?.list ?: emptyList()
        if (items.isEmpty()) {
            Toast.makeText(this, tr("Abrí Tally Monitor y actualizá la lista de encuestas; después volvé a agregar el widget.",
                "Open Tally Monitor and refresh the survey list; then add the widget again."), Toast.LENGTH_LONG).show()
            finish(); return
        }
        title = tr("Elegí la encuesta", "Choose a survey")
        render()
    }

    private fun label(s: WidgetSurvey) = (s.name.ifBlank { tr("Encuesta", "Survey") }) + "  ·  " +
        if (s.goal > 0) tr("${group(s.count)} de ${group(s.goal)}", "${group(s.count)} of ${group(s.goal)}") else tr("sin meta", "no goal")

    private fun render() {
        val sorted = items.sortedByDescending { it.goal > 0 }      // primero las que ya tienen meta
        val list = ListView(this)
        list.adapter = ArrayAdapter(this, android.R.layout.simple_list_item_1, sorted.map { label(it) })
        list.setOnItemClickListener { _, _, position, _ ->
            val s = sorted.getOrNull(position - list.headerViewsCount) ?: return@setOnItemClickListener
            if (s.goal > 0) choose(s) else askGoal(s)
        }
        val anyGoal = items.any { it.goal > 0 }
        val header = TextView(this).apply {
            text = if (anyGoal) tr("Elegí la encuesta para seguir su meta. Si tocás una «sin meta», podés ponerle una ahora.",
                "Choose the survey whose goal you want to follow. Tap one with «no goal» to set one now.")
            else tr("Ninguna encuesta tiene meta todavía. Tocá una y escribí cuántas respuestas querés alcanzar.",
                "No survey has a goal yet. Tap one and enter how many responses you want to reach.")
            textSize = 16f; setPadding(48, 36, 48, 24)
        }
        list.addHeaderView(header, null, false)
        setContentView(list)
    }

    private fun choose(s: WidgetSurvey) {
        WidgetSnapshot.setGoalChoice(this, widgetId, s.accountId, s.formId)
        WidgetProviders.refreshAll(this)
        setResult(RESULT_OK, Intent().putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, widgetId))
        finish()
    }

    private fun askGoal(s: WidgetSurvey) {
        val input = EditText(this).apply { inputType = InputType.TYPE_CLASS_NUMBER; hint = tr("Meta de respuestas (1 a 1.000.000)", "Response goal (1 to 1,000,000)") }
        AlertDialog.Builder(this)
            .setTitle(s.name.ifBlank { tr("Encuesta", "Survey") })
            .setView(input)
            .setPositiveButton(tr("Guardar y usar", "Save and use")) { _, _ ->
                val goal = input.text.toString().trim().toIntOrNull()
                if (goal == null || goal < 1 || goal > 1_000_000) {
                    Toast.makeText(this, tr("La meta tiene que ser un número entre 1 y 1.000.000.", "The goal must be a number between 1 and 1,000,000."), Toast.LENGTH_LONG).show()
                } else saveGoal(s, goal)
            }
            .setNegativeButton(tr("Cancelar", "Cancel"), null)
            .show()
    }

    /** Guarda la meta con el mismo servicio que usa la app, conservando la nota y las etiquetas que ya tenía la encuesta. */
    private fun saveGoal(s: WidgetSurvey, goal: Int) {
        scope.launch {
            try {
                val backend = (application as TallyApp).backend
                val current = backend.surveys.observeSurveys(s.accountId, includeArchived = true).first().firstOrNull { it.formId == s.formId }
                if (current == null) { Toast.makeText(this@WidgetGoalConfigActivity, tr("No se encontró la encuesta.", "Survey not found."), Toast.LENGTH_LONG).show(); return@launch }
                backend.surveys.setSurveyMeta(s.accountId, s.formId, goal, current.note, current.tags)
                WidgetSnapshot.withGoal(this@WidgetGoalConfigActivity, s.accountId, s.formId, goal)
                choose(s.copy(goal = goal))
            } catch (e: CancellationException) { throw e
            } catch (e: Exception) {
                Toast.makeText(this@WidgetGoalConfigActivity, errorText(e), Toast.LENGTH_LONG).show()
            }
        }
    }

    override fun onDestroy() { scope.cancel(); super.onDestroy() }
}

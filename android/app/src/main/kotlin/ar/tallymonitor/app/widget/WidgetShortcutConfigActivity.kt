package ar.tallymonitor.app.widget

import android.app.Activity
import android.appwidget.AppWidgetManager
import android.content.Intent
import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.ListView
import android.widget.TextView
import android.widget.Toast
import ar.tallymonitor.app.ui.tr

/** Se abre al agregar el widget «Acceso directo»: elegís la encuesta. Usa la instantánea guardada (no llama a Tally ni toca claves). */
class WidgetShortcutConfigActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val widgetId = intent?.extras?.getInt(AppWidgetManager.EXTRA_APPWIDGET_ID, AppWidgetManager.INVALID_APPWIDGET_ID) ?: AppWidgetManager.INVALID_APPWIDGET_ID
        setResult(RESULT_CANCELED, Intent().putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, widgetId))
        if (widgetId == AppWidgetManager.INVALID_APPWIDGET_ID) { finish(); return }
        val items = WidgetSnapshot.load(this)?.list ?: emptyList()
        if (items.isEmpty()) {
            Toast.makeText(this, tr("Abrí Tally Monitor y actualizá la lista de encuestas; después volvé a agregar el widget.", "Open Tally Monitor and refresh the survey list; then add the widget again."), Toast.LENGTH_LONG).show()
            finish(); return
        }
        title = tr("Elegí la encuesta", "Choose the survey")
        val labels = items.map { "${it.name.ifBlank { tr("Encuesta", "Survey") }}  ·  ${group(it.count)}" }
        val list = ListView(this)
        list.adapter = ArrayAdapter(this, android.R.layout.simple_list_item_1, labels)
        list.setOnItemClickListener { _, _, position, _ ->
            val s = items.getOrNull(position - list.headerViewsCount) ?: return@setOnItemClickListener
            WidgetSnapshot.setShortcut(this, widgetId, s.accountId, s.formId)
            WidgetProviders.refreshAll(this)
            setResult(RESULT_OK, Intent().putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, widgetId))
            finish()
        }
        val header = TextView(this).apply { text = tr("Elegí la encuesta para el acceso directo", "Choose the survey for the shortcut"); textSize = 16f; setPadding(48, 36, 48, 24) }
        list.addHeaderView(header, null, false)
        setContentView(list)
    }
}

package ar.tallymonitor.app.ui

import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import java.util.Locale

/** Idiomas de la app. Si la persona nunca eligió, se sigue el del teléfono (español → español; cualquier otro → inglés). */
enum class Lang(val code: String, val label: String) { ES("es", "Español"), EN("en", "English") }

object I18n {
    private const val FILE = "tally_prefs"
    private const val KEY = "app_lang"

    /** Estado observable: los composables que llaman a [tr] se redibujan solos al cambiar el idioma. */
    private var state by mutableStateOf(Lang.ES)
    val current: Lang get() = state
    val locale: Locale get() = if (state == Lang.EN) Locale.US else Locale("es", "AR")

    /** Se llama una vez al arrancar el proceso (TallyApp.onCreate), así también los widgets, el worker y las notificaciones lo ven. */
    fun init(context: Context) {
        val saved = try { context.applicationContext.getSharedPreferences(FILE, Context.MODE_PRIVATE).getString(KEY, null) } catch (e: RuntimeException) { null }
        state = Lang.values().firstOrNull { it.code == saved } ?: if (Locale.getDefault().language == "es") Lang.ES else Lang.EN
    }

    fun set(context: Context, lang: Lang) {
        state = lang
        try { context.applicationContext.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit().putString(KEY, lang.code).apply() } catch (e: RuntimeException) { /* sigue en memoria */ }
        try { ar.tallymonitor.app.widget.WidgetProviders.refreshAll(context) } catch (e: RuntimeException) { /* los widgets son accesorios */ }
    }
}

/** Texto según el idioma elegido: `tr("Hola", "Hello")`. */
fun tr(es: String, en: String): String = if (I18n.current == Lang.EN) en else es

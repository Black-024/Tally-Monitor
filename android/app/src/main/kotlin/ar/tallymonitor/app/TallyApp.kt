package ar.tallymonitor.app

import android.app.Application
import ar.tallymonitor.app.ui.I18n
import ar.tallymonitor.services.TallyMonitorBackend

class TallyApp : Application() {
    /** El backend se crea una sola vez, al primer uso (abre la base, migra y concilia credenciales). */
    val backend: TallyMonitorBackend by lazy { TallyMonitorBackend.create(this) }

    override fun onCreate() {
        super.onCreate()
        I18n.init(this)          // el idioma queda disponible también para widgets, avisos y tareas en segundo plano
    }
}

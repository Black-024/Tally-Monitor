package ar.tallymonitor.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import ar.tallymonitor.app.notify.Notifier
import ar.tallymonitor.app.widget.WidgetIntents
import ar.tallymonitor.app.ui.AppRoot
import ar.tallymonitor.app.ui.MainViewModel
import ar.tallymonitor.app.ui.Route

class MainActivity : ComponentActivity() {
    private val vm: MainViewModel by viewModels { MainViewModel.factory((application as TallyApp).backend) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { AppRoot(vm, contentResolver) }
        if (savedInstanceState == null) openFromWidget(intent)
    }

    /** Un widget (acceso directo o lista) abre la app directamente en una encuesta. */
    private fun openFromWidget(i: Intent?) {
        val acc = i?.getStringExtra(WidgetIntents.EXTRA_ACCOUNT)
        val form = i?.getStringExtra(WidgetIntents.EXTRA_FORM)
        if (acc != null && form != null) vm.openFromWidget(acc, form)
    }

    /** Al tocar la notificación con la app ya abierta (launchMode singleTop) se vuelve a Inicio. */
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (intent.getBooleanExtra(Notifier.EXTRA_OPEN_HOME, false)) vm.go(Route.Home)
        openFromWidget(intent)
    }
}

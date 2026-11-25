package ar.tallymonitor.app.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import ar.tallymonitor.app.R
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable fun t() = LocalTokens.current

@Composable
fun AppCard(modifier: Modifier = Modifier, onClick: (() -> Unit)? = null, content: @Composable ColumnScope.() -> Unit) {
    val m = modifier.fillMaxWidth().clip(CardShape).background(t().card, CardShape).border(1.dp, t().line, CardShape).let { if (onClick != null) it.clickable(onClick = onClick) else it }
    Column(m.padding(16.dp), content = content)
}

/** Botón principal: píldora, color de acción. */
@Composable
fun PillButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, primary: Boolean = true) {
    Button(onClick, modifier, enabled = enabled, shape = Pill,
        colors = if (primary) ButtonDefaults.buttonColors(containerColor = t().action, contentColor = if (t().dark) androidx.compose.ui.graphics.Color.Black else androidx.compose.ui.graphics.Color.White)
        else ButtonDefaults.buttonColors(containerColor = t().card2, contentColor = t().text)) { Text(text, fontWeight = FontWeight.SemiBold) }
}

@Composable fun Title(text: String) = Text(text, fontSize = 22.sp, fontWeight = FontWeight.Bold, color = t().text)
@Composable fun Muted(text: String, modifier: Modifier = Modifier) = Text(text, fontSize = 12.sp, color = t().muted, modifier = modifier)
@Composable fun Section(text: String) = Text(text, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = t().text, modifier = Modifier.padding(top = 16.dp, bottom = 6.dp))

@Composable
fun Tile(value: String, label: String, modifier: Modifier = Modifier) {
    Column(modifier.background(t().card, RoundedCornerShape(16.dp)).padding(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, fontSize = 22.sp, fontWeight = FontWeight.Bold, color = t().text)
        Text(label, fontSize = 11.sp, color = t().muted)
    }
}

@Composable
fun Confirm(title: String, text: String, confirm: String, onConfirm: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(onDismissRequest = onDismiss, title = { Text(title) }, text = { Text(text) },
        confirmButton = { TextButton(onClick = { onConfirm(); onDismiss() }) { Text(confirm, color = t().action) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(tr("Cancelar", "Cancel")) } })
}

/** Selector de dos o más opciones en una sola píldora (como «Claro | Oscuro»): la elegida se rellena con el color de acción. */
@Composable
fun Segmented(options: List<Pair<String, String>>, selected: String, onSelect: (String) -> Unit, modifier: Modifier = Modifier, badges: Set<String> = emptySet()) {
    Row(modifier.fillMaxWidth().clip(Pill).background(t().bg2, Pill).border(1.dp, t().line, Pill).padding(4.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        options.forEach { (key, label) ->
            val on = key == selected
            Box(Modifier.weight(1f).clip(Pill).background(if (on) t().action else androidx.compose.ui.graphics.Color.Transparent, Pill)
                .clickable { if (!on) onSelect(key) }.padding(vertical = 10.dp), contentAlignment = Alignment.Center) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(label, fontWeight = FontWeight.Bold, fontSize = if (options.size > 3) 13.sp else 14.sp, maxLines = 1, softWrap = false, color = if (on) (if (t().dark) androidx.compose.ui.graphics.Color(0xFF1A1405) else androidx.compose.ui.graphics.Color.White) else t().muted)
                    if (key in badges) { Spacer(Modifier.width(4.dp)); RedDot() }
                }
            }
        }
    }
}

/** Barra de marca: logo + nombre, igual que la de Windows. */
@Composable
fun BrandBar() {
    Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Image(painterResource(if (t().dark) R.drawable.logo_dark else R.drawable.logo_light), contentDescription = null, modifier = Modifier.size(34.dp))
        Spacer(Modifier.width(10.dp))
        Text("Tally Monitor", fontSize = 20.sp, fontWeight = FontWeight.ExtraBold, color = t().text)
    }
}

/** Navegación principal en píldoras (Encuestas · Cuentas · Ajustes). */
@Composable
fun NavPills(items: List<Pair<String, String>>, selected: String, badges: Set<String> = emptySet(), onSelect: (String) -> Unit) {
    Box(Modifier.padding(horizontal = 16.dp).padding(bottom = 6.dp)) { Segmented(items, selected, onSelect, badges = badges) }
}

/** Pestañas con subrayado (Resumen · Respuestas · Exportar), como en Windows. */
@Composable
fun UnderlineTabs(labels: List<String>, selected: Int, onSelect: (Int) -> Unit) {
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(24.dp)) {
            labels.forEachIndexed { i, s ->
                val on = i == selected
                Column(Modifier.width(IntrinsicSize.Max).clickable { onSelect(i) }.padding(top = 8.dp)) {
                    Text(s, fontWeight = FontWeight.Bold, fontSize = 16.sp, color = if (on) t().text else t().muted, modifier = Modifier.padding(bottom = 6.dp))
                    Box(Modifier.height(3.dp).fillMaxWidth().background(if (on) t().action else androidx.compose.ui.graphics.Color.Transparent, Pill))
                }
            }
        }
        Box(Modifier.fillMaxWidth().height(1.dp).background(t().line))
    }
}

/** Aviso corto (nota) con fondo suave. */
@Composable
fun Note(text: String, modifier: Modifier = Modifier) {
    Text(text, color = t().text, fontSize = 13.sp, modifier = modifier.fillMaxWidth().background(t().card2, RoundedCornerShape(12.dp)).border(1.dp, t().line, RoundedCornerShape(12.dp)).padding(horizontal = 14.dp, vertical = 8.dp))
}

/** Círculo rojo: marca algo pendiente (respuestas sin actualizar). */
@Composable
fun RedDot(size: androidx.compose.ui.unit.Dp = 9.dp) {
    Box(Modifier.size(size).background(androidx.compose.ui.graphics.Color(0xFFE53935), androidx.compose.foundation.shape.CircleShape))
}

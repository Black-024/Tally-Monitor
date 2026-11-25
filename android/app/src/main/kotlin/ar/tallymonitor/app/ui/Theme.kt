package ar.tallymonitor.app.ui

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

/** Paleta de la app. Oscuro: violeta + dorado. Claro: aqua + café. Sin degradados ni emojis. */
class Tokens(val dark: Boolean, val bg: Color, val card: Color, val card2: Color, val line: Color, val text: Color, val muted: Color, val accent: Color, val action: Color, val danger: Color, val bg2: Color, val dim: Color)

val DarkTokens = Tokens(true, Color(0xFF0B0B0F), Color(0xFF17171F), Color(0xFF1F1F2B), Color(0xFF2E2B45), Color(0xFFF4F2FF), Color(0xFFAAA5C4), Color(0xFF8B7BFF), Color(0xFFE6B84A), Color(0xFFFF7B7B), Color(0xFF121218), Color(0xFF827D9C))
val LightTokens = Tokens(false, Color(0xFFFFFFFF), Color(0xFFF7FBFA), Color(0xFFE6F2F0), Color(0xFFC8DFDB), Color(0xFF1B2B29), Color(0xFF4D6965), Color(0xFF12A198), Color(0xFF8A5A3B), Color(0xFFB3261E), Color(0xFFF2F8F7), Color(0xFF7A948F))

val LocalTokens = staticCompositionLocalOf { DarkTokens }
val Pill = RoundedCornerShape(50)
val CardShape = RoundedCornerShape(20.dp)

@Composable
fun TallyTheme(dark: Boolean, content: @Composable () -> Unit) {
    val t = if (dark) DarkTokens else LightTokens
    val scheme = (if (dark) darkColorScheme() else lightColorScheme()).copy(
        primary = t.accent, onPrimary = if (dark) Color.Black else Color.White, secondary = t.action, background = t.bg, onBackground = t.text,
        surface = t.card, onSurface = t.text, surfaceVariant = t.card2, onSurfaceVariant = t.muted, outline = t.line, error = t.danger)
    CompositionLocalProvider(LocalTokens provides t) { MaterialTheme(colorScheme = scheme, content = content) }
}

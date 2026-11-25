package ar.tallymonitor.export

import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Formato es-AR para textos de exportación. */
object Format {
    fun pct(value: Double?): String = if (value == null) "—" else String.format(Locale.ROOT, "%.1f %%", value).replace('.', ',')
    fun dec(value: Double?, digits: Int = 1): String = if (value == null) "—" else String.format(Locale.ROOT, "%.${digits}f", value).replace('.', ',')
    private val DT = DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm")
    fun dt(value: LocalDateTime?): String = if (value == null) "—" else DT.format(value)
}

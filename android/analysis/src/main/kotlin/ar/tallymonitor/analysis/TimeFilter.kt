package ar.tallymonitor.analysis

import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/** Filtros de tiempo (24 h, 7 d, 30 d, todo, rango propio). Inicio inclusivo, fin exclusivo. */
object TimeFilter {
    val KINDS = listOf("all", "24h", "7d", "30d", "custom")
    private val WINDOWS = mapOf("24h" to Duration.ofHours(24), "7d" to Duration.ofDays(7), "30d" to Duration.ofDays(30))
    private val LABELS = mapOf("all" to "Todo el período", "24h" to "Últimas 24 horas", "7d" to "Últimos 7 días", "30d" to "Últimos 30 días")
    private val ISO = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.'000Z'").withZone(ZoneOffset.UTC)
    private val DMY = DateTimeFormatter.ofPattern("dd/MM/yyyy")

    fun toIso(i: Instant): String = ISO.format(i)

    /** Rango propio: días COMPLETOS en la hora local, con ambos extremos incluidos. */
    fun resolve(kind: String, now: Instant, tz: ZoneId, startDate: LocalDate? = null, endDate: LocalDate? = null): ResolvedFilter {
        if (kind == "all") return ResolvedFilter("all", null, null, LABELS.getValue("all"))
        WINDOWS[kind]?.let { return ResolvedFilter(kind, toIso(now.minus(it)), toIso(now.plusSeconds(1)), LABELS.getValue(kind)) }
        if (kind == "custom") {
            require(startDate != null && endDate != null) { "El rango personalizado necesita fecha de inicio y de fin" }
            require(startDate <= endDate) { "La fecha de inicio es posterior a la de fin" }
            val start = startDate.atStartOfDay(tz).toInstant()
            val end = endDate.plusDays(1).atStartOfDay(tz).toInstant()
            return ResolvedFilter("custom", toIso(start), toIso(end), "Del ${DMY.format(startDate)} al ${DMY.format(endDate)}")
        }
        throw IllegalArgumentException("Filtro desconocido: $kind")
    }
}

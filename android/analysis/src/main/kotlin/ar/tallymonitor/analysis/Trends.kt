package ar.tallymonitor.analysis

import java.time.Duration
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeParseException

/**
 * Ritmo de respuestas (spec 1.1 §2.2). byWeekday: lunes = 0. byHour: 0..23 en hora local.
 * peakWeekday/peakHour: null sin datos; con empate gana el índice menor.
 */
data class Trends(
    val last7: Int, val prev7: Int, val deltaPct: Int?, val completionPct: Int?,
    val byWeekday: List<Int>, val byHour: List<Int>, val peakWeekday: Int?, val peakHour: Int?,
) {
    /** Reemplaza last7/prev7/delta por los de [all] (ellos ignoran el filtro de período y usan todos los envíos guardados). */
    fun withRecentFrom(all: Trends): Trends = copy(last7 = all.last7, prev7 = all.prev7, deltaPct = all.deltaPct)
}

private val WEEK = Duration.ofDays(7)

private fun parseOrNull(iso: String): Instant? = try { Instant.parse(iso) } catch (e: DateTimeParseException) { null }

/** Porcentaje entero redondeado «mitad hacia afuera del cero», en aritmética entera (sin errores de coma flotante). */
internal fun roundedPct(numerator: Long, denominator: Long): Int {
    require(denominator > 0)
    val n = numerator * 100L
    val r = (Math.abs(n) * 2L + denominator) / (2L * denominator)
    return (if (n < 0) -r else r).toInt()
}

/**
 * last7 = envíos en [now−7×24 h, now]; prev7 = [now−14×24 h, now−7×24 h). Los futuros (reloj adelantado) no cuentan.
 * byWeekday, byHour y completionPct usan TODOS los envíos recibidos aquí. Fechas ilegibles se ignoran.
 */
fun trends(submissions: Collection<SubmissionPoint>, now: Instant, tz: ZoneId): Trends {
    val startLast = now.minus(WEEK)
    val startPrev = now.minus(WEEK).minus(WEEK)
    var last7 = 0; var prev7 = 0; var completed = 0; var total = 0
    val wd = IntArray(7); val hr = IntArray(24)
    for (s in submissions) {
        val at = parseOrNull(s.submittedAt) ?: continue
        total++
        if (s.isCompleted) completed++
        if (!at.isBefore(startLast) && !at.isAfter(now)) last7++
        else if (!at.isBefore(startPrev) && at.isBefore(startLast)) prev7++
        val local = at.atZone(tz)
        wd[local.dayOfWeek.value - 1]++
        hr[local.hour]++
    }
    val delta = if (prev7 == 0) null else roundedPct((last7 - prev7).toLong(), prev7.toLong())
    val completion = if (total == 0) null else roundedPct(completed.toLong(), total.toLong())
    return Trends(last7, prev7, delta, completion, wd.toList(), hr.toList(), peak(wd), peak(hr))
}

private fun peak(a: IntArray): Int? {
    var best = -1; var idx: Int? = null
    for (i in a.indices) if (a[i] > best && a[i] > 0) { best = a[i]; idx = i }
    return idx
}

/** Cuenta envíos en [now−7×24 h, now] (misma ventana que `trends`); útil para metas. */
fun countLast7(submittedAt: Collection<String>, now: Instant): Int {
    val start = now.minus(WEEK)
    return submittedAt.count { iso -> parseOrNull(iso)?.let { !it.isBefore(start) && !it.isAfter(now) } == true }
}

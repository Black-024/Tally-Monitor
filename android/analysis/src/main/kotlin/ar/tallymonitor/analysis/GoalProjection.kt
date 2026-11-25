package ar.tallymonitor.analysis

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

/**
 * Proyección de una meta de respuestas (spec 1.1 §2.1). Función pura, sin Android ni base de datos.
 * [etaDays] es null si ya se llegó, si no hay ritmo (0 respuestas en 7 días) o si superaría [MAX_ETA_DAYS];
 * la interfaz distingue «sin ritmo» de «demasiado lento» con `perDay`.
 */
data class GoalProjection(
    val done: Boolean, val pct: Int, val remaining: Int, val perDay: Double, val etaDays: Int?, val etaDate: LocalDate?,
)

object Goals {
    const val MAX_ETA_DAYS = 3650
    const val MAX_GOAL = 1_000_000

    /**
     * [localCount] respuestas guardadas, [goal] meta (>= 1), [last7Count] guardadas con fecha en los 7×24 h previos a [now].
     * pct = parte entera de local*100/goal (nunca muestra 100 % si falta una respuesta), con tope 100.
     * eta_days = ceil(remaining / (last7/7)) calculado en enteros: ceil(remaining*7 / last7).
     * La fecha estimada es el día local de [now] más eta_days.
     */
    fun projection(localCount: Int, goal: Int, last7Count: Int, now: Instant, tz: ZoneId = ZoneId.systemDefault()): GoalProjection {
        require(goal >= 1) { "La meta debe ser al menos 1" }
        val local = maxOf(0, localCount)
        val last7 = maxOf(0, last7Count)
        val done = local >= goal
        val remaining = maxOf(0, goal - local)
        val pct = minOf(100L, local.toLong() * 100L / goal.toLong()).toInt()
        val perDay = last7 / 7.0
        var eta: Int? = null
        if (!done && last7 > 0) {
            val days = (remaining.toLong() * 7L + last7 - 1L) / last7.toLong()
            if (days <= MAX_ETA_DAYS) eta = days.toInt()
        }
        val date = eta?.let { now.atZone(tz).toLocalDate().plusDays(it.toLong()) }
        return GoalProjection(done, pct, remaining, perDay, eta, date)
    }
}

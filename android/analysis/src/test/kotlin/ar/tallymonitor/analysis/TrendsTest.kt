package ar.tallymonitor.analysis

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.Instant
import java.time.ZoneOffset

class TrendsTest {
    // 2026-11-20 es viernes
    private val now = Instant.parse("2026-11-20T15:00:00Z")
    private val utc = ZoneOffset.UTC
    private fun p(iso: String, done: Boolean = true, k: Int = 0) = SubmissionPoint(k, iso, done)

    @Test fun vacio() {
        val t = trends(emptyList(), now, utc)
        assertEquals(0, t.last7); assertEquals(0, t.prev7); assertNull(t.deltaPct); assertNull(t.completionPct)
        assertEquals(List(7) { 0 }, t.byWeekday); assertEquals(List(24) { 0 }, t.byHour); assertNull(t.peakWeekday); assertNull(t.peakHour)
    }
    @Test fun ventanasYDelta() {
        val subs = (1..18).map { p("2026-11-19T10:00:00.000Z", k = it) } + (1..15).map { p("2026-11-12T10:00:00.000Z", k = 100 + it) }
        val t = trends(subs, now, utc)
        assertEquals(18, t.last7); assertEquals(15, t.prev7); assertEquals(20, t.deltaPct) // +20 %
    }
    @Test fun deltaMenosCincuenta() {
        val t = trends(listOf(p("2026-11-19T10:00:00Z")) + List(2) { p("2026-11-12T10:00:00Z") }, now, utc)
        assertEquals(-50, t.deltaPct)
    }
    @Test fun deltaMitadSeRedondeaHaciaAfueraDelCero() {
        // 9 vs 8 → +12,5 → 13 ; 7 vs 8 → -12,5 → -13
        val up = trends(List(9) { p("2026-11-19T10:00:00Z") } + List(8) { p("2026-11-12T10:00:00Z") }, now, utc)
        assertEquals(13, up.deltaPct)
        val down = trends(List(7) { p("2026-11-19T10:00:00Z") } + List(8) { p("2026-11-12T10:00:00Z") }, now, utc)
        assertEquals(-13, down.deltaPct)
    }
    @Test fun semanaAnteriorSinDatosDaNull() {
        assertNull(trends(listOf(p("2026-11-19T10:00:00Z")), now, utc).deltaPct)
    }
    @Test fun semanaActualVaciaDaMenos100() {
        assertEquals(-100, trends(listOf(p("2026-11-12T10:00:00Z")), now, utc).deltaPct)
    }
    @Test fun bordesDeLasVentanas() {
        val exactoInicioLast = p("2026-11-13T15:00:00.000Z")      // now-7d: entra en last7
        val justoAntes = p("2026-11-13T14:59:59.999Z")            // prev7
        val exactoInicioPrev = p("2026-11-06T15:00:00.000Z")      // now-14d: entra en prev7
        val fuera = p("2026-11-06T14:59:59.999Z")                 // no cuenta en ninguna
        val exactoAhora = p("2026-11-20T15:00:00.000Z")           // now: entra en last7
        val futuro = p("2026-11-20T15:00:00.001Z")                // no cuenta
        val t = trends(listOf(exactoInicioLast, justoAntes, exactoInicioPrev, fuera, exactoAhora, futuro), now, utc)
        assertEquals(2, t.last7); assertEquals(2, t.prev7)
    }
    @Test fun finalizacion() {
        val subs = List(87) { p("2026-11-19T10:00:00Z") } + List(13) { p("2026-11-19T10:00:00Z", done = false) }
        assertEquals(87, trends(subs, now, utc).completionPct)
        assertEquals(0, trends(listOf(p("2026-11-19T10:00:00Z", false)), now, utc).completionPct)
        assertEquals(100, trends(listOf(p("2026-11-19T10:00:00Z")), now, utc).completionPct)
        // 1 de 8 = 12,5 → 13 ; 2 de 3 = 66,67 → 67
        assertEquals(13, trends(listOf(p("2026-11-19T10:00:00Z")) + List(7) { p("2026-11-19T10:00:00Z", false) }, now, utc).completionPct)
        assertEquals(67, trends(List(2) { p("2026-11-19T10:00:00Z") } + p("2026-11-19T10:00:00Z", false), now, utc).completionPct)
    }
    @Test fun diaDeSemanaLunesEsCero() {
        // 2026-11-16 lunes, 2026-11-22 domingo
        val t = trends(listOf(p("2026-11-16T10:00:00Z"), p("2026-11-22T10:00:00Z"), p("2026-11-22T11:00:00Z")), now, utc)
        assertEquals(1, t.byWeekday[0]); assertEquals(2, t.byWeekday[6]); assertEquals(3, t.byWeekday.sum())
        assertEquals(6, t.peakWeekday)
    }
    @Test fun horaLocalCambiaElDia() {
        // 01:30Z del sábado 21 es viernes 22:30 en UTC-3
        val tz = ZoneOffset.ofHours(-3)
        val t = trends(listOf(p("2026-11-21T01:30:00Z")), now, tz)
        assertEquals(1, t.byWeekday[4]); assertEquals(1, t.byHour[22]); assertEquals(4, t.peakWeekday); assertEquals(22, t.peakHour)
        val u = trends(listOf(p("2026-11-21T01:30:00Z")), now, utc)
        assertEquals(1, u.byWeekday[5]); assertEquals(1, u.byHour[1])
    }
    @Test fun empateGanaElMenorIndice() {
        val t = trends(listOf(p("2026-11-18T18:00:00Z"), p("2026-11-17T09:00:00Z")), now, utc) // miércoles 18 h y martes 9 h
        assertEquals(1, t.peakWeekday); assertEquals(9, t.peakHour)
    }
    @Test fun picoConMayoria() {
        val t = trends(List(3) { p("2026-11-19T18:10:00Z") } + p("2026-11-18T09:00:00Z"), now, utc)
        assertEquals(3, t.peakWeekday); assertEquals(18, t.peakHour) // jueves 19
    }
    @Test fun byWeekdayYByHourUsanTodoElConjuntoAunqueSeaViejo() {
        val t = trends(listOf(p("2020-01-06T23:59:59Z")), now, utc) // lunes
        assertEquals(0, t.last7); assertEquals(0, t.prev7); assertEquals(1, t.byWeekday[0]); assertEquals(1, t.byHour[23])
    }
    @Test fun fechaIlegibleSeIgnora() {
        val t = trends(listOf(p("no es fecha"), p("2026-11-19T10:00:00Z")), now, utc)
        assertEquals(1, t.last7); assertEquals(100, t.completionPct); assertEquals(1, t.byHour.sum())
    }
    @Test fun withRecentFromCambiaSoloLosRecientes() {
        val period = trends(listOf(p("2026-01-05T10:00:00Z")), now, utc)
        val all = trends(List(3) { p("2026-11-19T10:00:00Z") } + p("2026-11-12T10:00:00Z"), now, utc)
        val r = period.withRecentFrom(all)
        assertEquals(3, r.last7); assertEquals(1, r.prev7); assertEquals(200, r.deltaPct)
        assertEquals(period.byWeekday, r.byWeekday); assertEquals(period.completionPct, r.completionPct)
    }
    @Test fun roundedPctCasos() {
        assertEquals(0, roundedPct(0, 5)); assertEquals(100, roundedPct(5, 5)); assertEquals(33, roundedPct(1, 3)); assertEquals(-33, roundedPct(-1, 3))
    }
    @Test fun countLast7() {
        val n = countLast7(listOf("2026-11-19T10:00:00Z", "2026-11-13T15:00:00.000Z", "2026-11-13T14:59:59Z", "basura", "2026-11-21T00:00:00Z"), now)
        assertEquals(2, n)
    }
}

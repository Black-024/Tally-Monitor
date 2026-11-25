package ar.tallymonitor.analysis

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import org.junit.Test

class GoalProjectionTest {
    private val now = Instant.parse("2026-11-20T15:00:00Z")
    private val tz = ZoneOffset.ofHours(-3)

    @Test fun ejemploDeLaEspecificacion() {
        // 124 de 200 (62 %), 25 en 7 días (≈ 3,57/día): faltan 76 → ceil(76*7/25) = 22 días
        val p = Goals.projection(124, 200, 25, now, tz)
        assertFalse(p.done); assertEquals(62, p.pct); assertEquals(76, p.remaining)
        assertEquals(25 / 7.0, p.perDay, 1e-12)
        assertEquals(22, p.etaDays); assertEquals(LocalDate.of(2026, 12, 12), p.etaDate)
    }
    @Test fun ritmoDeTresYMedio() {
        val p = Goals.projection(124, 200, 7 * 3 + 3, now, tz) // 24/7 ≈ 3,43
        assertEquals(23, p.etaDays) // ceil(76*7/24 = 22,17)
    }
    @Test fun metaAlcanzadaExacta() {
        val p = Goals.projection(200, 200, 10, now, tz)
        assertTrue(p.done); assertEquals(100, p.pct); assertEquals(0, p.remaining); assertNull(p.etaDays); assertNull(p.etaDate)
    }
    @Test fun metaSuperadaTopaEn100() {
        val p = Goals.projection(350, 200, 0, now, tz)
        assertTrue(p.done); assertEquals(100, p.pct); assertEquals(0, p.remaining); assertNull(p.etaDays)
    }
    @Test fun sinRitmo() {
        val p = Goals.projection(10, 200, 0, now, tz)
        assertFalse(p.done); assertEquals(0.0, p.perDay, 0.0); assertNull(p.etaDays); assertNull(p.etaDate); assertEquals(190, p.remaining)
    }
    @Test fun ceroLocalesNoEsHecho() {
        val p = Goals.projection(0, 1, 7, now, tz)
        assertFalse(p.done); assertEquals(0, p.pct); assertEquals(1, p.remaining); assertEquals(1, p.etaDays)
    }
    @Test fun faltaUnaNoMuestra100() {
        assertEquals(99, Goals.projection(199, 200, 1, now, tz).pct)
        assertEquals(99, Goals.projection(999_999, 1_000_000, 1, now, tz).pct)
    }
    @Test fun pctEsParteEntera() {
        assertEquals(33, Goals.projection(1, 3, 0, now, tz).pct)
        assertEquals(66, Goals.projection(2, 3, 0, now, tz).pct)
    }
    @Test fun etaExactaSinRedondeoHaciaArriba() {
        // faltan 7, 7 por semana → 1 por día → 7 días exactos
        assertEquals(7, Goals.projection(93, 100, 7, now, tz).etaDays)
        // faltan 8 → 8 días
        assertEquals(8, Goals.projection(92, 100, 7, now, tz).etaDays)
    }
    @Test fun topeDe3650Dias() {
        // faltan 3650, 7/semana (1 por día) → 3650 exactos: se informa
        assertEquals(3650, Goals.projection(1, 3651, 7, now, tz).etaDays)
        // faltan 3651 → supera el tope: null
        assertNull(Goals.projection(1, 3652, 7, now, tz).etaDays)
        assertNull(Goals.projection(1, 3652, 7, now, tz).etaDate)
        // un solo envío en 7 días y meta enorme
        assertNull(Goals.projection(0, 1_000_000, 1, now, tz).etaDays)
    }
    @Test fun fechaUsaDiaLocal() {
        // 2026-11-20T01:00Z en UTC-3 es el 19 a la noche local
        val early = Instant.parse("2026-11-20T01:00:00Z")
        assertEquals(LocalDate.of(2026, 11, 20), Goals.projection(0, 1, 7, early, tz).etaDate) // 19 + 1
        assertEquals(LocalDate.of(2026, 11, 21), Goals.projection(0, 1, 7, early, ZoneOffset.UTC).etaDate)
    }
    @Test fun finDeAnioYBisiesto() {
        val n = Instant.parse("2027-12-30T12:00:00Z")
        assertEquals(LocalDate.of(2028, 1, 4), Goals.projection(0, 5, 7, n, ZoneOffset.UTC).etaDate)
        val f = Instant.parse("2028-02-27T12:00:00Z")
        assertEquals(LocalDate.of(2028, 3, 1), Goals.projection(0, 3, 7, f, ZoneOffset.UTC).etaDate)
    }
    @Test fun conteosNegativosSeTratanComoCero() {
        val p = Goals.projection(-5, 10, -3, now, tz)
        assertEquals(0, p.pct); assertEquals(10, p.remaining); assertNull(p.etaDays)
    }
    @Test fun metaInvalidaLanza() {
        try { Goals.projection(1, 0, 1, now, tz); fail() } catch (e: IllegalArgumentException) { /* esperado */ }
    }
    @Test fun metaMaximaNoDesborda() {
        val p = Goals.projection(Int.MAX_VALUE, 1_000_000, Int.MAX_VALUE, now, tz)
        assertTrue(p.done); assertEquals(100, p.pct)
        val q = Goals.projection(999_999, 1_000_000, Int.MAX_VALUE, now, tz)
        assertEquals(1, q.etaDays)
    }
}

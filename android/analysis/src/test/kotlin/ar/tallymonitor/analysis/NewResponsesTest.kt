package ar.tallymonitor.analysis

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NewResponsesTest {
    private fun i(rep: Int?, loc: Int, arch: Boolean = false) = PendingInput(rep, loc, arch)

    @Test fun sumaSoloLoPositivo() {
        val t = NewResponses.totals(listOf(i(10, 7), i(5, 5), i(3, 8), i(null, 4)))
        assertEquals(PendingTotals(3, 1), t)
    }
    @Test fun archivadasNoCuentan() {
        val t = NewResponses.totals(listOf(i(10, 0, arch = true), i(6, 4)))
        assertEquals(PendingTotals(2, 1), t)
    }
    @Test fun cuentaEncuestasQueAportan() {
        assertEquals(PendingTotals(3, 2), NewResponses.totals(listOf(i(3, 2), i(4, 2), i(9, 9))))
    }
    @Test fun vacioEsCero() { assertEquals(PendingTotals(0, 0), NewResponses.totals(emptyList())) }

    @Test fun avisaSiSubio() {
        val d = NewResponses.decide(PendingTotals(5, 2), 3)
        assertTrue(d.notify); assertEquals(5, d.storeTotal)
    }
    @Test fun noAvisaSiIgual() {
        val d = NewResponses.decide(PendingTotals(5, 2), 5)
        assertFalse(d.notify); assertEquals(5, d.storeTotal)
    }
    @Test fun noAvisaSiBajoPeroGuardaElActual() {
        val d = NewResponses.decide(PendingTotals(2, 1), 5)
        assertFalse(d.notify); assertEquals(2, d.storeTotal)
    }
    @Test fun siBajoACeroGuardaCeroYLaProximaSubidaAvisa() {
        val d0 = NewResponses.decide(PendingTotals(0, 0), 4)
        assertFalse(d0.notify); assertEquals(0, d0.storeTotal)
        assertTrue(NewResponses.decide(PendingTotals(1, 1), d0.storeTotal).notify)
    }
    @Test fun ceroNuncaAvisa() { assertFalse(NewResponses.decide(PendingTotals(0, 0), 0).notify) }
    @Test fun primerChequeoConPendientesAvisa() { assertTrue(NewResponses.decide(PendingTotals(1, 1), 0).notify) }

    @Test fun textos() {
        assertEquals("3 respuestas nuevas en 2 encuestas", NewResponses.title(PendingTotals(3, 2)))
        assertEquals("1 respuesta nueva en 1 encuesta", NewResponses.title(PendingTotals(1, 1)))
        assertEquals("Tocá para abrir Tally Monitor", NewResponses.BODY)
    }
}

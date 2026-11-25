package ar.tallymonitor.services

import ar.tallymonitor.core.ErrorCode
import ar.tallymonitor.core.TallyMonitorException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.fail
import org.junit.Test

class SurveyMetaRulesTest {
    private fun code(block: () -> Unit): ErrorCode {
        try { block() } catch (e: TallyMonitorException) { return e.code }
        fail("Debía fallar"); throw IllegalStateException()
    }

    @Test fun metaLimites() {
        assertNull(SurveyMetaRules.goal(null))
        assertEquals(1, SurveyMetaRules.goal(1)); assertEquals(1_000_000, SurveyMetaRules.goal(1_000_000))
        assertEquals(ErrorCode.INVALID_GOAL, code { SurveyMetaRules.goal(0) })
        assertEquals(ErrorCode.INVALID_GOAL, code { SurveyMetaRules.goal(-5) })
        assertEquals(ErrorCode.INVALID_GOAL, code { SurveyMetaRules.goal(1_000_001) })
    }
    @Test fun notaSeRecorta() {
        assertEquals("hola", SurveyMetaRules.note("  hola \n"))
        assertEquals("", SurveyMetaRules.note("   "))
        assertEquals("a  b", SurveyMetaRules.note(" a  b ")) // no se tocan los espacios internos de la nota
    }
    @Test fun notaLargo() {
        assertEquals(500, SurveyMetaRules.note("x".repeat(500)).length)
        assertEquals(500, SurveyMetaRules.note("  " + "x".repeat(500) + "  ").length) // el recorte va antes de contar
        assertEquals(ErrorCode.NOTE_TOO_LONG, code { SurveyMetaRules.note("x".repeat(501)) })
    }
    @Test fun notaCuentaCaracteresUnicode() {
        val emoji = "😀" // 1 carácter, 2 unidades UTF-16
        SurveyMetaRules.note(emoji.repeat(500))
        assertEquals(ErrorCode.NOTE_TOO_LONG, code { SurveyMetaRules.note(emoji.repeat(501)) })
    }
    @Test fun etiquetaNormaliza() {
        assertEquals(listOf("a b c"), SurveyMetaRules.tags(listOf("  a   b\tc ")))
    }
    @Test fun etiquetaVaciaFalla() {
        assertEquals(ErrorCode.INVALID_TAG, code { SurveyMetaRules.tags(listOf("   ")) })
        assertEquals(ErrorCode.INVALID_TAG, code { SurveyMetaRules.tags(listOf("")) })
        assertEquals(ErrorCode.INVALID_TAG, code { SurveyMetaRules.tags(listOf("ok", " ")) })
    }
    @Test fun etiquetaLargo24() {
        assertEquals(24, SurveyMetaRules.tags(listOf("x".repeat(24)))[0].length)
        assertEquals(ErrorCode.INVALID_TAG, code { SurveyMetaRules.tags(listOf("x".repeat(25))) })
        // el largo se cuenta después de colapsar espacios
        assertEquals(1, SurveyMetaRules.tags(listOf("a" + " ".repeat(40) + "b".repeat(21))).size)
    }
    @Test fun repetidasSinDistinguirMayusculasConservanLaPrimera() {
        assertEquals(listOf("Taller", "otra"), SurveyMetaRules.tags(listOf("Taller", "TALLER", "otra", "taller")))
        assertEquals(listOf("a b"), SurveyMetaRules.tags(listOf("a b", " A   B ")))
    }
    @Test fun maximoOchoEtiquetas() {
        val ocho = (1..8).map { "t$it" }
        assertEquals(ocho, SurveyMetaRules.tags(ocho))
        assertEquals(ErrorCode.TOO_MANY_TAGS, code { SurveyMetaRules.tags(ocho + "t9") })
        // los repetidos no cuentan para el tope
        assertEquals(8, SurveyMetaRules.tags(ocho + "T1" + "t2").size)
    }
    @Test fun listaVaciaEsValida() { assertEquals(emptyList<String>(), SurveyMetaRules.tags(emptyList())) }
    @Test fun cleanValidaTodoJunto() {
        val c = SurveyMetaRules.clean(200, " nota ", listOf(" A ", "a", "B"))
        assertEquals(200, c.goal); assertEquals("nota", c.note); assertEquals(listOf("A", "B"), c.tags)
        assertEquals(ErrorCode.INVALID_GOAL, code { SurveyMetaRules.clean(0, "x".repeat(900), listOf("")) }) // falla la primera regla
        assertEquals(ErrorCode.NOTE_TOO_LONG, code { SurveyMetaRules.clean(5, "x".repeat(501), listOf("ok")) })
        assertEquals(ErrorCode.INVALID_TAG, code { SurveyMetaRules.clean(5, "ok", listOf("x".repeat(30))) })
    }
}

package ar.tallymonitor.analysis

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AnswerFilterTest {
    @Test fun normalizaEspacios() {
        assertEquals("a b c", AnswerFilters.normalize("  a   b\t\nc  "))
        assertEquals("", AnswerFilters.normalize("   "))
        assertEquals("Sí", AnswerFilters.normalize("Sí"))
        assertEquals("a b", AnswerFilters.normalize("a b")) // espacio duro
    }
    @Test fun coincidenciaExactaTrasNormalizar() {
        val f = AnswerFilter("q1", "Redes  sociales")
        val keys = AnswerFilters.matchingKeys(f, listOf(1 to "Redes sociales", 2 to " Redes sociales ", 3 to "Redes", 4 to "redes sociales"))
        assertEquals(setOf(1, 2), keys) // distingue mayúsculas, no es «contiene»
    }
    @Test fun multipleBastaQueEsteEntreLasElegidas() {
        val f = AnswerFilter("q", "B")
        val keys = AnswerFilters.matchingKeys(f, listOf(1 to "A", 1 to "B", 2 to "A", 2 to "C", 3 to "B"))
        assertEquals(setOf(1, 3), keys)
    }
    @Test fun sinCoincidenciasDaVacio() {
        assertTrue(AnswerFilters.matchingKeys(AnswerFilter("q", "Z"), listOf(1 to "A")).isEmpty())
        assertTrue(AnswerFilters.matchingKeys(AnswerFilter("q", "Z"), emptyList()).isEmpty())
    }
    @Test fun repetidosNoDuplican() {
        assertEquals(setOf(1), AnswerFilters.matchingKeys(AnswerFilter("q", "A"), listOf(1 to "A", 1 to "A")))
    }
    @Test fun soloPreguntasDeOpcion() {
        fun q(type: String) = QuestionInfo("q", 0, type, "t")
        assertTrue(AnswerFilters.isOptionQuestion(q("MULTIPLE_CHOICE")))
        assertTrue(AnswerFilters.isOptionQuestion(q("CHECKBOXES")))
        assertFalse(AnswerFilters.isOptionQuestion(q("TEXTAREA")))
        assertFalse(AnswerFilters.isOptionQuestion(q("INPUT_TEXT")))
    }
    @Test fun elFiltroDejaCienPorCientoEnLaOpcionFiltrada() {
        // Con los envíos que quedan, la pregunta filtrada muestra 100 % en la opción (esperable).
        val q = QuestionInfo("q1", 0, "MULTIPLE_CHOICE", "¿Cómo?", listOf("A", "B"))
        val subs = (1..4).map { SubmissionPoint(it, "2026-11-19T10:00:00.000Z", true) }
        val answers = listOf(1 to "A", 2 to "A", 3 to "B", 4 to "A").map { (k, o) -> AnswerPoint(k, "q1", "single", false, null, listOf(o to "declared")) }
        val keys = AnswerFilters.matchingKeys(AnswerFilter("q1", "A"), answers.flatMap { a -> a.choices.map { a.key to it.first } })
        val st = Stats.allQuestionStats(listOf(q), answers.filter { it.key in keys }, subs.count { it.key in keys })
        assertEquals(3, st[0].answered); assertEquals(100.0, st[0].options[0].pct!!, 1e-9); assertEquals(0, st[0].options[1].count)
    }
}

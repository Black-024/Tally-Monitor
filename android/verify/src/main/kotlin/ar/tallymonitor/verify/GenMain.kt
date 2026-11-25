package ar.tallymonitor.verify

import ar.tallymonitor.analysis.*
import ar.tallymonitor.export.*
import java.io.File
import java.time.LocalDateTime
import java.time.ZoneId

/** Genera archivos de muestra (xlsx / pdf) con datos sintéticos, para validarlos con herramientas externas. */
fun sampleAnalysis(n: Int): Pair<SurveyAnalysis, List<ResponseRow>> {
    val qs = listOf(
        QuestionStats("q1", 1, "MULTIPLE_CHOICE", "¿Cómo te enteraste?", "single", true, n, n, 0, 0, "",
            options = listOf(OptionStat("Redes", n / 2, 50.0), OptionStat("=HYPERLINK(\"x\")", n - n / 2, 50.0))),
        QuestionStats("q2", 2, "TEXTAREA", "Comentarios", "text", true, n, n, 0, 0, "", avgLen = 21.5, maxLen = 40),
    )
    val rows = (1..n).map { i ->
        ResponseRow(i, "2026-03-%02dT12:%02d:00Z".format(1 + i % 20, i % 60), i % 5 != 0, mapOf(
            "q1" to Cell("single", false, null, listOf((if (i % 2 == 0) "Redes" else "=HYPERLINK(\"x\")") to "c1")),
            "q2" to Cell("text", false, "Escribime a juan@mail.com o 1155551234 \u0001 ñandú", emptyList())))
    }
    val tl = Timeline("day", (1..5).map { TimeBucket(LocalDateTime.of(2026, 3, it, 0, 0), it * 3) }, 45)
    val a = SurveyAnalysis("abc", ResolvedFilter("all", null, null, "Todo el tiempo"), true, "2026-03-30T00:00:00Z",
        Overview(n, n - n / 5, n / 5, rows.first().submittedAt, rows.last().submittedAt, 20, n / 20.0), qs, tl)
    return a to rows
}

fun main(args: Array<String>) {
    val dir = File(args[0]); dir.mkdirs()
    val (a, rows) = sampleAnalysis(if (args.size > 1) args[1].toInt() else 40)
    val tz = ZoneId.of("America/Argentina/Buenos_Aires")
    val now = LocalDateTime.of(2026, 3, 30, 10, 0)
    for (scope in listOf("summary", "individual")) {
        File(dir, "muestra_$scope.xlsx").outputStream().use {
            XlsxExport.write(it, "Encuesta =cmd|' /C calc'!A0", a, rows, { k -> "Usuario %03d".format(k) }, tz,
                ExportOptions(includeText = true, scope = scope), now)
        }
    }
    val logo = PdfImage(2, 2, ByteArray(12) { (it * 20).toByte() }, ByteArray(4) { 255.toByte() })
    for (style in listOf("dark", "light")) for (scope in listOf("summary", "individual")) {
        File(dir, "muestra_${scope}_$style.pdf").outputStream().use {
            PdfExport.write(it, "Encuesta (prueba) ñandú €", a, rows, { k -> "Usuario %03d".format(k) }, tz,
                ExportOptions(includeText = true, scope = scope, style = style), now, logo)
        }
    }
    println("ok")
}

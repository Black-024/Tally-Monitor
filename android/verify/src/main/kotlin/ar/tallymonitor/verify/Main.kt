package ar.tallymonitor.verify

import java.io.File
import kotlin.system.exitProcess

/** Ejecuta todas las comprobaciones contra los vectores golden. Uso: Main <carpeta golden>. */
fun main(args: Array<String>) {
    val g = Golden(File(args.getOrElse(0) { "golden" }))
    var failures = 0
    val checks = listOf<Pair<String, () -> List<String>>>(
        "numeración" to g::numbering, "sanitizer" to g::sanitizer, "normalizer" to g::normalizer,
    ) + extraChecks(g)
    for ((name, run) in checks) {
        val diffs = try { run() } catch (e: Throwable) { listOf("EXCEPCIÓN ${e::class.simpleName}: ${e.message}") }
        if (diffs.isEmpty()) println("[OK]    $name") else { failures++; println("[FALLO] $name"); diffs.take(15).forEach { println("          $it") } }
    }
    println(if (failures == 0) "TODO IDÉNTICO A LA REFERENCIA PYTHON" else "$failures comprobaciones con diferencias")
    exitProcess(if (failures == 0) 0 else 1)
}

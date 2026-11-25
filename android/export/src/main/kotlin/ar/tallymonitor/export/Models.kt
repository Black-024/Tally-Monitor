package ar.tallymonitor.export

import java.time.LocalDate

data class ExportOptions(
    val kind: String = "all",                 // all | 24h | 7d | 30d | custom
    val startDate: LocalDate? = null,
    val endDate: LocalDate? = null,           // inclusivo
    val includeIncomplete: Boolean = true,
    val includeText: Boolean = false,         // respuestas de texto libre (pueden tener datos personales)
    val maskPersonal: Boolean = true,         // ocultar correos, teléfonos, etc. en esos textos
    val scope: String = "summary",            // summary (estadísticas) | individual (una ficha por persona)
    val style: String = "dark",               // estilo visual de PDF e imagen: dark | light (Excel no cambia)
    val onlyNumber: Int? = null,              // solo en individual: una sola persona (n.º de «Usuario»)
)

data class ExportResult(val format: String, val responses: Int, val questions: Int, val textIncluded: Boolean, val masked: Boolean)

/** Imagen ya decodificada para incrustar en el PDF (la plataforma decodifica el PNG): RGB de 8 bits y alfa opcional. */
class PdfImage(val width: Int, val height: Int, val rgb: ByteArray, val alpha: ByteArray? = null)

/** Cancelación cooperativa: la exportación consulta esto cada tanto y se detiene sin dejar archivos a medias. */
fun interface CancelCheck { fun isCancelled(): Boolean }

package ar.tallymonitor.export

import java.io.OutputStream
import java.time.LocalDateTime
import java.time.temporal.ChronoUnit
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** Valor de una celda. Los textos siempre se guardan como TEXTO (nunca como fórmula). */
sealed class XCell {
    class Str(val text: String, val bold: Boolean = false, val header: Boolean = false) : XCell()
    class Num(val value: Double) : XCell()
    class Date(val value: LocalDateTime, val kind: String = "datetime") : XCell()      // datetime | date | month
    class Pct(val fraction: Double) : XCell()

    companion object {
        fun s(t: String) = Str(t)
        fun b(t: String) = Str(t, bold = true)
        fun h(t: String) = Str(t, header = true)
        fun n(v: Number) = Num(v.toDouble())
    }
}

/**
 * Escritor mínimo de libros .xlsx (sin dependencias). Cada hoja se escribe en streaming, así que 20 000+ filas no
 * ocupan memoria. Protección contra inyección de fórmulas: todo texto va como «cadena en línea» y, si empieza con
 * = + - @ tab o CR, además lleva el atributo quotePrefix (Excel lo trata como texto, nunca como fórmula).
 */
class XlsxBook(out: OutputStream) {
    private val zip = ZipOutputStream(out)
    private val names = ArrayList<String>()
    private var open: SheetWriter? = null

    // Estilos (índices de cellXfs; ver styles.xml más abajo).
    private object S { const val DEFAULT = 0; const val BOLD = 1; const val HEADER = 2; const val WRAP = 3; const val WRAP_Q = 4
        const val BOLD_WRAP = 5; const val DATETIME = 6; const val DATE = 7; const val MONTH = 8; const val PCT = 9; const val BOLD_Q = 10; const val HEADER_Q = 11 }

    init { zip.setLevel(6) }

    inner class SheetWriter(val name: String, widths: List<Int>, freezeRow: Boolean, freezeCol: Boolean) {
        private val w = zip.also { it.putNextEntry(ZipEntry("xl/worksheets/sheet${names.size + 1}.xml")) }
        private var rowNo = 0
        private var maxCols = 0
        private var merge: String? = null
        private var filter = false

        init {
            val pane = when {
                freezeRow && freezeCol -> """<pane xSplit="1" ySplit="1" topLeftCell="B2" activePane="bottomRight" state="frozen"/>"""
                freezeRow -> """<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>"""
                else -> ""
            }
            write("""<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">""")
            write("""<sheetViews><sheetView workbookViewId="0">$pane</sheetView></sheetViews><sheetFormatPr defaultRowHeight="15"/>""")
            if (widths.isNotEmpty()) {
                write("<cols>")
                widths.forEachIndexed { i, wd -> write("""<col min="${i + 1}" max="${i + 1}" width="$wd" customWidth="1"/>""") }
                write("</cols>")
            }
            write("<sheetData>")
        }

        private fun write(s: String) = zip.write(s.toByteArray(Charsets.UTF_8))

        /** Agrega una fila. `null` = celda vacía. `height` fija el alto de la fila (puntos). */
        fun row(cells: List<XCell?>, height: Int? = null) {
            rowNo++
            maxCols = maxOf(maxCols, cells.size)
            val sb = StringBuilder()
            sb.append("""<row r="$rowNo"""")
            if (height != null) sb.append(""" ht="$height" customHeight="1"""")
            sb.append('>')
            cells.forEachIndexed { i, c -> if (c != null) cell(sb, col(i) + rowNo, c) }
            sb.append("</row>")
            write(sb.toString())
        }

        private fun cell(sb: StringBuilder, ref: String, c: XCell) {
            when (c) {
                is XCell.Str -> {
                    val t = clean(c.text)
                    val q = t.isNotEmpty() && t[0] in "=+-@\t\r"
                    val style = when {
                        c.header -> if (q) S.HEADER_Q else S.HEADER
                        c.bold -> if (q) S.BOLD_Q else S.BOLD_WRAP
                        else -> if (q) S.WRAP_Q else S.WRAP
                    }
                    sb.append("""<c r="$ref" s="$style" t="inlineStr"><is><t xml:space="preserve">${esc(t)}</t></is></c>""")
                }
                is XCell.Num -> sb.append("""<c r="$ref" s="${S.DEFAULT}"><v>${num(c.value)}</v></c>""")
                is XCell.Pct -> sb.append("""<c r="$ref" s="${S.PCT}"><v>${num(c.fraction)}</v></c>""")
                is XCell.Date -> {
                    val style = when (c.kind) { "date" -> S.DATE; "month" -> S.MONTH; else -> S.DATETIME }
                    sb.append("""<c r="$ref" s="$style"><v>${num(serial(c.value))}</v></c>""")
                }
            }
        }

        fun mergeAcross(row: Int, fromCol: Int, toCol: Int) { merge = col(fromCol - 1) + row + ":" + col(toCol - 1) + row }
        fun autoFilter() { filter = true }

        fun close() {
            write("</sheetData>")
            if (filter && rowNo > 0 && maxCols > 0) write("""<autoFilter ref="A1:${col(maxCols - 1)}$rowNo"/>""")
            merge?.let { write("""<mergeCells count="1"><mergeCell ref="$it"/></mergeCells>""") }
            write("</worksheet>")
            zip.closeEntry()
        }
    }

    /** Abre una hoja nueva (cierra la anterior). */
    fun sheet(name: String, widths: List<Int> = emptyList(), freezeRow: Boolean = false, freezeCol: Boolean = false): SheetWriter {
        open?.close()
        val s = SheetWriter(name, widths, freezeRow, freezeCol)
        names += name
        open = s
        return s
    }

    fun finish() {
        open?.close(); open = null
        entry("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>""" +
            names.indices.joinToString("") { """<Override PartName="/xl/worksheets/sheet${it + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>""" } + "</Types>")
        entry("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>""")
        entry("xl/workbook.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>""" +
            names.mapIndexed { i, n -> """<sheet name="${esc(n)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>""" }.joinToString("") + "</sheets></workbook>")
        entry("xl/_rels/workbook.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">""" +
            names.indices.joinToString("") { """<Relationship Id="rId${it + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${it + 1}.xml"/>""" } +
            """<Relationship Id="rId${names.size + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>""")
        entry("xl/styles.xml", STYLES)
        zip.finish()
    }

    private fun entry(name: String, body: String) {
        zip.putNextEntry(ZipEntry(name)); zip.write(body.toByteArray(Charsets.UTF_8)); zip.closeEntry()
    }

    companion object {
        /** A, B … Z, AA … (índice desde 0). */
        fun col(index: Int): String {
            var i = index + 1
            val sb = StringBuilder()
            while (i > 0) { val r = (i - 1) % 26; sb.insert(0, ('A'.code + r).toChar()); i = (i - 1) / 26 }
            return sb.toString()
        }

        private val EPOCH = LocalDateTime.of(1899, 12, 30, 0, 0)
        fun serial(dt: LocalDateTime): Double = ChronoUnit.SECONDS.between(EPOCH, dt) / 86400.0
        private fun num(v: Double) = if (v == Math.floor(v) && Math.abs(v) < 1e15) v.toLong().toString() else v.toString()

        /** Quita caracteres no permitidos en XML 1.0 y recorta al máximo de Excel (32 767). */
        fun clean(t: String): String {
            val sb = StringBuilder(minOf(t.length, 32767))
            var i = 0
            while (i < t.length && sb.length < 32767) {
                val ch = t[i]
                val ok = ch == '\t' || ch == '\n' || ch == '\r' || (ch in ' '..'퟿') || (ch in ''..'�') || Character.isHighSurrogate(ch) || Character.isLowSurrogate(ch)
                if (ok) sb.append(ch)
                i++
            }
            return sb.toString()
        }

        fun esc(t: String): String = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")

        // cellXfs: 0 normal · 1 negrita · 2 encabezado · 3 texto ajustado · 4 texto ajustado + quotePrefix · 5 negrita ajustada ·
        // 6 fecha y hora · 7 fecha · 8 mes · 9 porcentaje · 10 negrita + quotePrefix · 11 encabezado + quotePrefix
        private const val STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="4"><numFmt numFmtId="164" formatCode="dd/mm/yyyy\ hh:mm"/><numFmt numFmtId="165" formatCode="dd/mm/yyyy"/><numFmt numFmtId="166" formatCode="mm/yyyy"/><numFmt numFmtId="167" formatCode="0.0%"/></numFmts><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFDDE1F5"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="12"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1" quotePrefix="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="167" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1" quotePrefix="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1" quotePrefix="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>"""
    }
}

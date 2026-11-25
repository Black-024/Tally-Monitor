package ar.tallymonitor.export

import java.io.ByteArrayOutputStream
import java.io.OutputStream
import java.nio.charset.Charset
import java.util.zip.Deflater
import java.util.zip.DeflaterOutputStream

/** Color RGB 0..1. */
class Rgb(val r: Double, val g: Double, val b: Double) {
    companion object { fun hex(h: String): Rgb { val v = h.removePrefix("#").toInt(16); return Rgb((v shr 16 and 255) / 255.0, (v shr 8 and 255) / 255.0, (v and 255) / 255.0) } }
}

enum class PFont(val res: String, val metrics: IntArray) { REGULAR("F1", FontMetrics.REGULAR), BOLD("F2", FontMetrics.BOLD), OBLIQUE("F3", FontMetrics.OBLIQUE) }

/**
 * Escritor de PDF de bajo nivel, sin dependencias: páginas A4, fuentes estándar Helvetica (WinAnsi), rectángulos,
 * texto, líneas e imagen opcional. Cada página se comprime y se escribe apenas termina, así que el uso de memoria
 * no crece con la cantidad de páginas. Origen de coordenadas abajo a la izquierda (como PDF), en puntos.
 */
class PdfDoc(private val out: OutputStream, title: String, author: String, private val logo: PdfImage? = null) {
    companion object {
        const val W = 595.276
        const val H = 841.89
        private val CP = Charset.forName("windows-1252")

        /** Texto → bytes WinAnsi; lo que Helvetica no cubre se reemplaza por «?». */
        fun encode(s: String): ByteArray {
            val t = s.replace('‑', '-').map { if (it < ' ' && it != '\t') ' ' else it }.joinToString("").replace('\t', ' ')
            val b = t.toByteArray(CP)               // el charset sustituye lo no mapeable por '?'
            return b
        }

        fun width(s: String, f: PFont, size: Double): Double {
            var w = 0
            for (c in encode(s)) { val i = (c.toInt() and 255) - 32; w += if (i in f.metrics.indices) f.metrics[i] else 556 }
            return w * size / 1000.0
        }

        private fun pdfString(s: String): String {
            val sb = StringBuilder("(")
            for (c in encode(s)) {
                val v = c.toInt() and 255
                when {
                    v == '('.code || v == ')'.code || v == '\\'.code -> sb.append('\\').append(v.toChar())
                    v in 32..126 -> sb.append(v.toChar())
                    else -> sb.append('\\').append(String.format("%03o", v))
                }
            }
            return sb.append(')').toString()
        }

        /** Cadena Unicode (UTF-16BE con BOM) para los metadatos. */
        private fun utf16(s: String): String = "<FEFF" + s.toByteArray(Charsets.UTF_16BE).joinToString("") { String.format("%02X", it.toInt() and 255) } + ">"

        private fun n(v: Double): String { val s = String.format(java.util.Locale.ROOT, "%.2f", v); return if (s.endsWith(".00")) s.dropLast(3) else s }
    }

    private var pos = 0L
    private val offsets = HashMap<Int, Long>()
    private val pageIds = ArrayList<Int>()
    private var nextId = 10
    private var page: StringBuilder? = null
    private var imgId = 0
    private var finished = false
    val pageCount get() = pageIds.size

    init {
        raw("%PDF-1.4\n%âãÏÓ\n")
        for ((id, name) in listOf(3 to "Helvetica", 4 to "Helvetica-Bold", 5 to "Helvetica-Oblique"))
            obj(id, "<< /Type /Font /Subtype /Type1 /BaseFont /$name /Encoding /WinAnsiEncoding >>")
        obj(6, "<< /Title ${utf16(title)} /Author ${utf16(author)} /Producer ${utf16(author)} >>")
        if (logo != null) writeImage(logo)
    }

    private fun raw(s: String) = raw(s.toByteArray(Charsets.ISO_8859_1))
    private fun raw(b: ByteArray) { out.write(b); pos += b.size }
    private fun obj(id: Int, body: String) { offsets[id] = pos; raw("$id 0 obj\n$body\nendobj\n") }

    private fun stream(id: Int, dict: String, data: ByteArray, compress: Boolean = true) {
        val bytes = if (compress) ByteArrayOutputStream().also { bo -> DeflaterOutputStream(bo, Deflater(6)).use { it.write(data) } }.toByteArray() else data
        offsets[id] = pos
        raw("$id 0 obj\n<< $dict ${if (compress) "/Filter /FlateDecode " else ""}/Length ${bytes.size} >>\nstream\n")
        raw(bytes); raw("\nendstream\nendobj\n")
    }

    private fun writeImage(img: PdfImage) {
        imgId = 7
        var extra = ""
        if (img.alpha != null) { stream(8, "/Type /XObject /Subtype /Image /Width ${img.width} /Height ${img.height} /ColorSpace /DeviceGray /BitsPerComponent 8", img.alpha); extra = "/SMask 8 0 R " }
        stream(7, "/Type /XObject /Subtype /Image /Width ${img.width} /Height ${img.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 $extra", img.rgb)
    }

    // ---------- páginas ----------
    fun newPage(background: Rgb, onPage: (PdfDoc, Int) -> Unit) {
        endPage()
        page = StringBuilder()
        fillRect(0.0, 0.0, W, H, background)
        onPage(this, pageIds.size + 1)
    }

    private var pendingPage = false
    private fun endPage() {
        val p = page ?: return
        val cid = nextId++; val pid = nextId++
        stream(cid, "", p.toString().toByteArray(Charsets.ISO_8859_1))
        val xo = if (imgId != 0) "/XObject << /Im1 7 0 R >> " else ""
        obj(pid, "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${n(W)} ${n(H)}] /Contents $cid 0 R /Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> $xo>> >>")
        pageIds += pid
        page = null
    }

    private fun cs(): StringBuilder = page ?: error("No hay página abierta")
    private fun fill(c: Rgb) = "${n3(c.r)} ${n3(c.g)} ${n3(c.b)} rg "
    private fun n3(v: Double) = String.format(java.util.Locale.ROOT, "%.3f", v)

    fun fillRect(x: Double, y: Double, w: Double, h: Double, c: Rgb) { cs().append(fill(c)).append("${n(x)} ${n(y)} ${n(w)} ${n(h)} re f\n") }

    fun roundRect(x: Double, y: Double, w: Double, h: Double, r0: Double, c: Rgb) {
        val r = minOf(r0, w / 2, h / 2); val k = 0.5523 * r
        val s = cs(); s.append(fill(c))
        s.append("${n(x + r)} ${n(y)} m ${n(x + w - r)} ${n(y)} l ${n(x + w - r + k)} ${n(y)} ${n(x + w)} ${n(y + r - k)} ${n(x + w)} ${n(y + r)} c ")
        s.append("${n(x + w)} ${n(y + h - r)} l ${n(x + w)} ${n(y + h - r + k)} ${n(x + w - r + k)} ${n(y + h)} ${n(x + w - r)} ${n(y + h)} c ")
        s.append("${n(x + r)} ${n(y + h)} l ${n(x + r - k)} ${n(y + h)} ${n(x)} ${n(y + h - r + k)} ${n(x)} ${n(y + h - r)} c ")
        s.append("${n(x)} ${n(y + r)} l ${n(x)} ${n(y + r - k)} ${n(x + r - k)} ${n(y)} ${n(x + r)} ${n(y)} c f\n")
    }

    fun line(x1: Double, y1: Double, x2: Double, y2: Double, c: Rgb, w: Double = 0.8) {
        cs().append("${n3(c.r)} ${n3(c.g)} ${n3(c.b)} RG ${n(w)} w ${n(x1)} ${n(y1)} m ${n(x2)} ${n(y2)} l S\n")
    }

    /** align: 0 izquierda, 1 centro, 2 derecha (x es el ancla). */
    fun text(s: String, x: Double, y: Double, f: PFont, size: Double, c: Rgb, align: Int = 0) {
        val w = width(s, f, size)
        val px = when (align) { 1 -> x - w / 2; 2 -> x - w; else -> x }
        cs().append("BT ").append(fill(c)).append("/${f.res} ${n(size)} Tf ${n(px)} ${n(y)} Td ${pdfString(s)} Tj ET\n")
    }

    fun drawLogo(x: Double, y: Double, w: Double, h: Double): Boolean {
        val img = logo ?: return false
        val s = minOf(w / img.width, h / img.height)
        val dw = img.width * s; val dh = img.height * s
        cs().append("q ${n(dw)} 0 0 ${n(dh)} ${n(x + (w - dw) / 2)} ${n(y + (h - dh) / 2)} cm /Im1 Do Q\n")
        return true
    }

    /** Parte un texto en líneas que caben en `maxW` (corta palabras largas por carácter). */
    fun wrap(s: String, f: PFont, size: Double, maxW: Double): List<String> {
        val lines = ArrayList<String>()
        for (para in s.replace("\r\n", "\n").replace('\r', '\n').split('\n')) {
            var cur = ""
            for (word in para.split(' ')) {
                var wd = word
                while (width(wd, f, size) > maxW && wd.length > 1) {          // palabra más ancha que la línea
                    var k = wd.length
                    while (k > 1 && width(wd.substring(0, k), f, size) > maxW) k--
                    if (cur.isNotEmpty()) { lines += cur; cur = "" }
                    lines += wd.substring(0, k); wd = wd.substring(k)
                }
                val trial = if (cur.isEmpty()) wd else "$cur $wd"
                if (width(trial, f, size) <= maxW) cur = trial else { lines += cur; cur = wd }
            }
            lines += cur
        }
        return lines
    }

    fun finish() {
        if (finished) return
        finished = true
        endPage()
        obj(2, "<< /Type /Pages /Kids [${pageIds.joinToString(" ") { "$it 0 R" }}] /Count ${pageIds.size} >>")
        obj(1, "<< /Type /Catalog /Pages 2 0 R >>")
        val xref = pos
        val max = nextId
        val sb = StringBuilder("xref\n0 $max\n0000000000 65535 f \n")
        for (i in 1 until max) { val o = offsets[i]; sb.append(if (o == null) "0000000000 65535 f \n" else String.format("%010d 00000 n \n", o)) }
        sb.append("trailer\n<< /Size $max /Root 1 0 R /Info 6 0 R >>\nstartxref\n$xref\n%%EOF\n")
        raw(sb.toString())
        out.flush()
    }
}

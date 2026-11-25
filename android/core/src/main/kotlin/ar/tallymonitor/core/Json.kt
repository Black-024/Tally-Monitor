package ar.tallymonitor.core

import java.lang.StringBuilder

/**
 * JSON mínimo sin dependencias. Valores: null, Boolean, Long, Double, String, List<Any?>, Map<String, Any?>.
 * La salida imita a `json.dumps(..., ensure_ascii=False)` de Python (separadores «, » y «: »), porque el texto
 * original de cada respuesta se guarda con ese formato y debe ser idéntico al de la versión de escritorio.
 */
typealias JObj = Map<String, Any?>

class JsonParseException(message: String) : RuntimeException(message)

object Json {
    fun parse(text: String): Any? {
        val p = Parser(text)
        p.skipWs()
        val v = p.value()
        p.skipWs()
        if (!p.atEnd()) throw JsonParseException("Texto sobrante después del JSON")
        return v
    }

    @Suppress("UNCHECKED_CAST")
    fun parseObject(text: String): JObj =
        parse(text) as? Map<String, Any?> ?: throw JsonParseException("Se esperaba un objeto JSON")

    fun stringify(v: Any?): String = StringBuilder().also { write(it, v) }.toString()

    private fun write(sb: StringBuilder, v: Any?) {
        when (v) {
            null -> sb.append("null")
            is Boolean -> sb.append(if (v) "true" else "false")
            is Int, is Long, is Short, is Byte -> sb.append(v.toString())
            is Double -> sb.append(if (v == Math.floor(v) && !v.isInfinite() && Math.abs(v) < 1e15) "${v.toLong()}.0" else v.toString())
            is Float -> write(sb, v.toDouble())
            is String -> quote(sb, v)
            is Map<*, *> -> {
                sb.append('{')
                var first = true
                for ((k, x) in v) {
                    if (!first) sb.append(", ")
                    first = false
                    quote(sb, k.toString()); sb.append(": "); write(sb, x)
                }
                sb.append('}')
            }
            is Iterable<*> -> {
                sb.append('[')
                var first = true
                for (x in v) {
                    if (!first) sb.append(", ")
                    first = false
                    write(sb, x)
                }
                sb.append(']')
            }
            is Array<*> -> write(sb, v.asList())
            else -> quote(sb, v.toString())
        }
    }

    private fun quote(sb: StringBuilder, s: String) {
        sb.append('"')
        for (c in s) {
            when (c) {
                '"' -> sb.append("\\\"")
                '\\' -> sb.append("\\\\")
                '\n' -> sb.append("\\n")
                '\r' -> sb.append("\\r")
                '\t' -> sb.append("\\t")
                '\b' -> sb.append("\\b")
                '\u000C' -> sb.append("\\f")
                else -> if (c < ' ') sb.append(String.format("\\u%04x", c.code)) else sb.append(c)
            }
        }
        sb.append('"')
    }

    private class Parser(private val s: String) {
        private var i = 0
        fun atEnd() = i >= s.length
        fun skipWs() { while (i < s.length && (s[i] == ' ' || s[i] == '\n' || s[i] == '\r' || s[i] == '\t')) i++ }

        fun value(): Any? {
            if (atEnd()) throw JsonParseException("JSON incompleto")
            return when (val c = s[i]) {
                '{' -> obj()
                '[' -> arr()
                '"' -> str()
                't' -> lit("true", true)
                'f' -> lit("false", false)
                'n' -> lit("null", null)
                else -> if (c == '-' || c.isDigit()) num() else throw JsonParseException("Carácter inesperado «$c» en $i")
            }
        }

        private fun lit(word: String, v: Any?): Any? {
            if (!s.startsWith(word, i)) throw JsonParseException("Valor inválido en $i")
            i += word.length
            return v
        }

        private fun obj(): Map<String, Any?> {
            val m = LinkedHashMap<String, Any?>()
            i++; skipWs()
            if (i < s.length && s[i] == '}') { i++; return m }
            while (true) {
                skipWs()
                if (i >= s.length || s[i] != '"') throw JsonParseException("Se esperaba una clave en $i")
                val k = str(); skipWs()
                if (i >= s.length || s[i] != ':') throw JsonParseException("Se esperaba ':' en $i")
                i++; skipWs()
                m[k] = value(); skipWs()
                if (i >= s.length) throw JsonParseException("Objeto sin cerrar")
                if (s[i] == ',') { i++; continue }
                if (s[i] == '}') { i++; return m }
                throw JsonParseException("Se esperaba ',' o '}' en $i")
            }
        }

        private fun arr(): List<Any?> {
            val l = ArrayList<Any?>()
            i++; skipWs()
            if (i < s.length && s[i] == ']') { i++; return l }
            while (true) {
                skipWs(); l.add(value()); skipWs()
                if (i >= s.length) throw JsonParseException("Lista sin cerrar")
                if (s[i] == ',') { i++; continue }
                if (s[i] == ']') { i++; return l }
                throw JsonParseException("Se esperaba ',' o ']' en $i")
            }
        }

        private fun str(): String {
            val sb = StringBuilder()
            i++
            while (true) {
                if (i >= s.length) throw JsonParseException("Texto sin cerrar")
                val c = s[i++]
                when (c) {
                    '"' -> return sb.toString()
                    '\\' -> {
                        if (i >= s.length) throw JsonParseException("Escape incompleto")
                        when (val e = s[i++]) {
                            '"' -> sb.append('"'); '\\' -> sb.append('\\'); '/' -> sb.append('/')
                            'b' -> sb.append('\b'); 'f' -> sb.append('\u000C'); 'n' -> sb.append('\n')
                            'r' -> sb.append('\r'); 't' -> sb.append('\t')
                            'u' -> {
                                if (i + 4 > s.length) throw JsonParseException("Escape \\u incompleto")
                                sb.append(s.substring(i, i + 4).toInt(16).toChar()); i += 4
                            }
                            else -> throw JsonParseException("Escape inválido «\\$e»")
                        }
                    }
                    else -> sb.append(c)
                }
            }
        }

        private fun num(): Any {
            val start = i
            if (s[i] == '-') i++
            while (i < s.length && s[i].isDigit()) i++
            var real = false
            if (i < s.length && s[i] == '.') { real = true; i++; while (i < s.length && s[i].isDigit()) i++ }
            if (i < s.length && (s[i] == 'e' || s[i] == 'E')) {
                real = true; i++
                if (i < s.length && (s[i] == '+' || s[i] == '-')) i++
                while (i < s.length && s[i].isDigit()) i++
            }
            val t = s.substring(start, i)
            if (!real) t.toLongOrNull()?.let { return it }
            return t.toDouble()
        }
    }
}

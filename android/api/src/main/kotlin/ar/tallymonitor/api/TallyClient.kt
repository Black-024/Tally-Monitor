package ar.tallymonitor.api

import ar.tallymonitor.core.ApiException
import ar.tallymonitor.core.ErrorCode
import ar.tallymonitor.core.Ids
import ar.tallymonitor.core.JObj
import ar.tallymonitor.core.Json
import ar.tallymonitor.core.Secret
import ar.tallymonitor.core.TallyMonitorException
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URI
import java.net.URL
import java.net.URLEncoder

const val BASE_URL = "https://api.tally.so"
const val USER_AGENT = "TallyMonitor/1.0 (lectura; android)"   // Tally rechaza los User-Agent genéricos
const val MAX_PAGE_SIZE = 500
private const val MAX_BODY = 25_000_000
private val LOCAL_HOSTS = setOf("127.0.0.1", "localhost", "[::1]", "::1")
private val DATE_RE = Regex("^[0-9T:.\\-]+Z$")

data class RateInfo(val limit: Int?, val remaining: Int?, val resetEpoch: Double?)

/** Lo único que se conserva de /users/me: el id opaco (puede faltar). */
data class TallyUser(val tallyUserId: String?)

/**
 * Cliente de Tally de SOLO LECTURA: único módulo que usa la red. Solo existe GET; no sigue redirecciones; la clave
 * viaja únicamente por HTTPS (HTTP solo hacia loopback, para pruebas). Los errores nunca incluyen la clave, la URL
 * completa ni el cuerpo de la respuesta.
 */
class TallyClient(
    baseUrl: String = BASE_URL,
    private val timeoutMs: Int = 20_000,
    private val maxRetries: Int = 2,
    private val maxWaitSeconds: Double = 30.0,
    private val minIntervalMs: Long = 0,
    private val sleep: (Long) -> Unit = { Thread.sleep(it) },
    private val wallClockMillis: () -> Long = { System.currentTimeMillis() },
    private val monotonicMillis: () -> Long = { System.nanoTime() / 1_000_000 },
    /** Solo observación (datos genéricos, nunca claves ni cuerpos). */
    private val onEvent: ((Map<String, Any?>) -> Unit)? = null,
) {
    private val base: String
    var rate = RateInfo(null, null, null); private set
    var requestCount = 0; private set
    private var lastRequestAt: Long? = null

    init {
        val u = URI(baseUrl)
        val ok = u.scheme == "https" || (u.scheme == "http" && u.host in LOCAL_HOSTS)
        require(ok) { "La API Key solo se envía por HTTPS (HTTP solo hacia localhost en pruebas)." }
        base = baseUrl.trimEnd('/')
    }

    // ---------- operaciones ----------
    fun getCurrentUser(key: Secret): TallyUser {
        val id = getJson("/users/me", key)["id"]
        return TallyUser(if (id is String && id.isNotEmpty()) id else null)
    }

    fun listForms(key: Secret, page: Int = 1): JObj = getJson("/forms?page=$page", key)
    fun getForm(key: Secret, formId: String): JObj = getJson("/forms/${Ids.check(formId)}", key)
    fun getQuestions(key: Secret, formId: String): JObj = getJson("/forms/${Ids.check(formId)}/questions", key)

    fun listSubmissions(key: Secret, formId: String, page: Int = 1, limit: Int = MAX_PAGE_SIZE, startDate: String? = null,
                        endDate: String? = null, filter: String = "all"): JObj {
        require(filter in setOf("all", "completed", "partial")) { "Filtro inválido" }
        val q = StringBuilder("page=$page&limit=${limit.coerceIn(1, MAX_PAGE_SIZE)}&filter=$filter")
        for ((k, v) in listOf("startDate" to startDate, "endDate" to endDate)) {
            if (v != null) {
                require(DATE_RE.matches(v)) { "Fecha inválida (se espera ISO UTC terminada en Z)" }
                q.append('&').append(k).append('=').append(URLEncoder.encode(v, "UTF-8"))
            }
        }
        return getJson("/forms/${Ids.check(formId)}/submissions?$q", key)
    }

    // ---------- núcleo ----------
    private fun getJson(path: String, key: Secret): JObj {
        val body = get(path, key)
        val obj = try { Json.parse(String(body, Charsets.UTF_8)) } catch (e: Exception) { throw ApiException(ErrorCode.BAD_RESPONSE, 200) }
        @Suppress("UNCHECKED_CAST")
        return obj as? JObj ?: throw ApiException(ErrorCode.BAD_RESPONSE, 200)
    }

    /** GET con reintentos para 429 y 5xx. No existe ningún otro método HTTP en este cliente. */
    private fun get(path: String, key: Secret): ByteArray {
        var attempt = 0
        while (true) {
            try {
                return singleGet(path, key)
            } catch (e: ApiException) {
                val retryable = e.code == ErrorCode.RATE_LIMITED || e.code == ErrorCode.SERVER_ERROR
                if (!retryable || attempt >= maxRetries) throw e
                val wait = minOf(e.retryAfterSeconds?.toDouble() ?: (2.0 * (attempt + 1)), maxWaitSeconds)
                sleep((wait * 1000).toLong())
                attempt++
            }
        }
    }

    private fun pace() {
        val r = rate
        if (r.remaining != null && r.remaining <= 2 && r.resetEpoch != null) {
            val wait = minOf(maxOf(0.0, r.resetEpoch - wallClockMillis() / 1000.0), maxWaitSeconds)
            if (wait > 0) { onEvent?.invoke(mapOf("espera_s" to Math.round(wait * 10) / 10.0, "ruta" to "(ventana agotada)")); sleep((wait * 1000).toLong()) }
            rate = RateInfo(r.limit, null, null)
        }
        val last = lastRequestAt
        if (minIntervalMs > 0 && last != null) {
            val gap = minIntervalMs - (monotonicMillis() - last)
            if (gap > 0) sleep(gap)
        }
    }

    private fun singleGet(path: String, key: Secret): ByteArray {
        pace()
        lastRequestAt = monotonicMillis()
        requestCount++
        val t0 = monotonicMillis()
        var status: Int? = null
        var error: String? = null
        try {
            return open(path, key) { status = it }
        } catch (e: ApiException) {
            status = e.status; error = e.code.name; throw e
        } finally {
            onEvent?.let { cb ->
                try {
                    val (route, params) = describe(path)
                    cb(buildMap { put("metodo", "GET"); put("ruta", route); put("consulta", params); put("ms", monotonicMillis() - t0)
                        put("restantes", rate.remaining); status?.let { put("estado", it) }; error?.let { put("error", it) } })
                } catch (_: Exception) { /* observar nunca debe romper una solicitud */ }
            }
        }
    }

    private fun open(path: String, key: Secret, onStatus: (Int) -> Unit): ByteArray {
        val conn = try { URL(base + path).openConnection() as HttpURLConnection } catch (e: IOException) { throw ApiException(ErrorCode.NETWORK) }
        try {
            conn.requestMethod = "GET"
            conn.instanceFollowRedirects = false
            conn.useCaches = false
            conn.connectTimeout = timeoutMs
            conn.readTimeout = timeoutMs
            conn.setRequestProperty("Authorization", "Bearer " + key.reveal())
            conn.setRequestProperty("Accept", "application/json")
            conn.setRequestProperty("User-Agent", USER_AGENT)
            val status = conn.responseCode
            onStatus(status)
            noteRate(conn)
            if (status in 200..299) return readBody(conn, status)
            val retryAfter = conn.getHeaderField("Retry-After")?.toDoubleOrNull()?.let { maxOf(0.0, it).toInt() }
            throw when {
                status == 401 || status == 403 -> ApiException(if (status == 401) ErrorCode.KEY_REJECTED else ErrorCode.FORBIDDEN, status)
                status == 429 -> ApiException(ErrorCode.RATE_LIMITED, status, retryAfter)
                status >= 500 -> ApiException(ErrorCode.SERVER_ERROR, status)
                status == 404 -> ApiException(ErrorCode.NOT_FOUND, status)
                else -> ApiException(ErrorCode.BAD_RESPONSE, status)          // incluye 3xx: no se siguen redirecciones
            }
        } catch (e: TallyMonitorException) {
            throw e
        } catch (e: SocketTimeoutException) {
            throw ApiException(ErrorCode.TIMEOUT)
        } catch (e: IOException) {
            throw ApiException(ErrorCode.NETWORK)                                  // nunca se propaga el mensaje (podría incluir la URL)
        } finally {
            conn.disconnect()
        }
    }

    private fun readBody(conn: HttpURLConnection, status: Int): ByteArray {
        conn.inputStream.use { ins ->
            val out = ByteArrayOutputStream()
            val buf = ByteArray(16 * 1024)
            while (true) {
                val n = ins.read(buf); if (n < 0) break
                out.write(buf, 0, n)
                if (out.size() > MAX_BODY) throw ApiException(ErrorCode.RESPONSE_TOO_LARGE, status)
            }
            return out.toByteArray()
        }
    }

    private fun noteRate(conn: HttpURLConnection) {
        val reset = conn.getHeaderField("x-ratelimit-reset")?.toDoubleOrNull()
        rate = RateInfo(conn.getHeaderField("x-ratelimit-limit")?.toIntOrNull(), conn.getHeaderField("x-ratelimit-remaining")?.toIntOrNull(), reset)
    }

    companion object {
        private val ROUTE_ID = Regex("^(/forms/)[^/]+")
        /** Ruta genérica (sin IDs) y parámetros no sensibles, para diagnóstico. */
        fun describe(path: String): Pair<String, Map<String, Any>> {
            val base = path.substringBefore('?'); val query = path.substringAfter('?', "")
            val params = LinkedHashMap<String, Any>()
            if (query.isNotEmpty()) for (part in query.split('&')) {
                val k = part.substringBefore('='); val v = part.substringAfter('=', "")
                when (k) { "page", "limit", "filter" -> params[k] = v.take(12); "startDate", "endDate" -> params[k] = true }
            }
            return ROUTE_ID.replace(base, "$1{id}") to params
        }
    }
}

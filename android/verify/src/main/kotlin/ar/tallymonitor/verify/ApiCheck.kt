package ar.tallymonitor.verify

import ar.tallymonitor.api.TallyClient
import ar.tallymonitor.api.USER_AGENT
import ar.tallymonitor.core.ApiException
import ar.tallymonitor.core.ErrorCode
import ar.tallymonitor.core.Secret
import com.sun.net.httpserver.HttpServer
import java.net.InetSocketAddress
import java.util.concurrent.CopyOnWriteArrayList

/** Servidor Tally falso (JDK) para probar el cliente real por HTTP, sin red externa. */
class FakeTally {
    val requests = CopyOnWriteArrayList<Triple<String, String, Map<String, String>>>()      // método, ruta+consulta, cabeceras
    @Volatile var handler: (String) -> Triple<Int, String, Map<String, String>> = { Triple(200, "{}", emptyMap()) }
    private val server: HttpServer = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
    val url get() = "http://127.0.0.1:${server.address.port}"
    init {
        server.createContext("/") { ex ->
            val path = ex.requestURI.rawPath + (ex.requestURI.rawQuery?.let { "?$it" } ?: "")
            requests += Triple(ex.requestMethod, path, ex.requestHeaders.entries.associate { it.key.lowercase() to it.value.first() })
            val (code, body, headers) = handler(path)
            headers.forEach { (k, v) -> ex.responseHeaders.add(k, v) }
            val b = body.toByteArray(); ex.sendResponseHeaders(code, if (code == 204) -1 else b.size.toLong())
            if (code != 204) ex.responseBody.use { it.write(b) } else ex.close()
        }
        server.start()
    }
    fun stop() = server.stop(0)
}

fun apiChecks(): List<Pair<String, () -> List<String>>> = listOf("cliente de la API (servidor falso)" to ::apiCheck)

private fun apiCheck(): List<String> {
    val bad = ArrayList<String>()
    val key = Secret("tly-SECRETO-123")
    val srv = FakeTally()
    val sleeps = ArrayList<Long>()
    try {
        fun client(retries: Int = 2) = TallyClient(srv.url, timeoutMs = 2000, maxRetries = retries, sleep = { sleeps += it })
        fun expect(name: String, code: ErrorCode, status: Int?, f: () -> Unit) {
            try { f(); bad += "$name: no lanzó error" } catch (e: ApiException) {
                if (e.code != code || (status != null && e.status != status)) bad += "$name: esperaba $code/$status y fue ${e.code}/${e.status}"
                if (e.message?.contains("SECRETO") == true || e.message?.contains("127.0.0.1") == true) bad += "$name: el mensaje filtra datos"
            } catch (e: Throwable) { bad += "$name: excepción inesperada ${e::class.simpleName}" }
        }

        // éxito + cabeceras + solo GET
        srv.handler = { Triple(200, """{"id":"u1","items":[]}""", mapOf("x-ratelimit-limit" to "100", "x-ratelimit-remaining" to "99", "x-ratelimit-reset" to "5")) }
        val c = client()
        if (c.getCurrentUser(key).tallyUserId != "u1") bad += "users/me: id incorrecto"
        val r = srv.requests.last()
        if (r.first != "GET") bad += "no usó GET"
        if (r.third["authorization"] != "Bearer tly-SECRETO-123") bad += "cabecera Authorization incorrecta"
        if (r.third["user-agent"] != USER_AGENT) bad += "User-Agent incorrecto: ${r.third["user-agent"]}"
        if (c.rate.remaining != 99 || c.rate.limit != 100) bad += "no leyó x-ratelimit-*"

        // consulta de envíos
        srv.handler = { Triple(200, """{"submissions":[]}""", emptyMap()) }
        c.listSubmissions(key, "abc_12", page = 2, limit = 9999, startDate = "2026-01-01T00:00:00.000Z", filter = "completed")
        val q = srv.requests.last().second
        if (!q.startsWith("/forms/abc_12/submissions?") || "limit=500" !in q || "page=2" !in q || "filter=completed" !in q || "startDate=2026-01-01T00%3A00%3A00.000Z" !in q) bad += "consulta mal armada: $q"
        for (badId in listOf("../x", "a/b", "", "a".repeat(65), "x?y=1")) try { c.getForm(key, badId); bad += "aceptó id inválido '$badId'" } catch (e: Exception) {}
        try { c.listSubmissions(key, "f", startDate = "2026-01-01; DROP"); bad += "aceptó fecha inválida" } catch (e: IllegalArgumentException) {}
        try { TallyClient("http://example.com"); bad += "aceptó HTTP no local" } catch (e: IllegalArgumentException) {}

        // errores
        for ((st, code) in listOf(401 to ErrorCode.KEY_REJECTED, 403 to ErrorCode.FORBIDDEN, 404 to ErrorCode.NOT_FOUND, 418 to ErrorCode.BAD_RESPONSE)) {
            srv.handler = { Triple(st, """{"message":"tly-SECRETO-123"}""", emptyMap()) }
            expect("HTTP $st", code, st) { client().getCurrentUser(key) }
        }
        // 3xx: no sigue la redirección
        val before = srv.requests.size
        srv.handler = { Triple(302, "", mapOf("Location" to "${srv.url}/otro")) }
        expect("redirección", ErrorCode.BAD_RESPONSE, 302) { client().getCurrentUser(key) }
        if (srv.requests.size - before != 1) bad += "siguió la redirección"
        // reintentos
        sleeps.clear(); var n = 0
        srv.handler = { if (n++ < 2) Triple(429, "{}", mapOf("Retry-After" to "3")) else Triple(200, """{"id":"u2"}""", emptyMap()) }
        if (client().getCurrentUser(key).tallyUserId != "u2") bad += "429: no se recuperó"
        if (sleeps != listOf(3000L, 3000L)) bad += "429: esperas $sleeps"
        n = 0; sleeps.clear()
        srv.handler = { Triple(503, "{}", emptyMap()) }
        expect("5xx agotado", ErrorCode.SERVER_ERROR, 503) { client().getCurrentUser(key) }
        if (sleeps != listOf(2000L, 4000L)) bad += "5xx: esperas $sleeps"
        srv.handler = { Triple(429, "{}", emptyMap()) }
        expect("429 sin reintentos", ErrorCode.RATE_LIMITED, 429) { client(0).getCurrentUser(key) }
        // cuerpo inválido
        srv.handler = { Triple(200, "no es json", emptyMap()) }
        expect("cuerpo no JSON", ErrorCode.BAD_RESPONSE, 200) { client().getCurrentUser(key) }
        srv.handler = { Triple(200, "[1,2]", emptyMap()) }
        expect("cuerpo no objeto", ErrorCode.BAD_RESPONSE, 200) { client().getCurrentUser(key) }
        // red caída
        val dead = FakeTally(); val deadUrl = dead.url; dead.stop()
        expect("red caída", ErrorCode.NETWORK, null) { TallyClient(deadUrl, timeoutMs = 500, sleep = {}).getCurrentUser(key) }
        // ventana agotada → espera hasta el reinicio
        sleeps.clear()
        var now = 1_000_000L
        val c2 = TallyClient(srv.url, sleep = { sleeps += it }, wallClockMillis = { now })
        srv.handler = { Triple(200, "{}", mapOf("x-ratelimit-remaining" to "1", "x-ratelimit-reset" to "1004")) }
        c2.getCurrentUser(key); c2.getCurrentUser(key)
        if (sleeps.size != 1 || sleeps[0] !in 3900L..4100L) bad += "no esperó el reinicio de ventana: $sleeps"
        // diagnóstico sin IDs
        val (route, params) = TallyClient.describe("/forms/abc123/submissions?page=1&limit=500&filter=all&startDate=2026-01-01T00%3A00%3A00.000Z")
        if (route != "/forms/{id}/submissions" || params["startDate"] != true) bad += "describe: $route $params"
    } finally { srv.stop() }
    return bad
}

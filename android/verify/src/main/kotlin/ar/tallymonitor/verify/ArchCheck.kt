package ar.tallymonitor.verify

import java.io.File

/** Reglas de arquitectura y seguridad, comprobadas leyendo el código fuente de producción (src/main) de cada módulo. */
fun archChecks(root: String): List<Pair<String, () -> List<String>>> = listOf("arquitectura y seguridad del código" to { archCheck(File(root)) })

private fun archCheck(root: File): List<String> {
    val bad = ArrayList<String>()
    val files = root.listFiles { f -> f.isDirectory }.orEmpty().filter { it.name != "verify" && File(it, "src/main").isDirectory }
        .flatMap { m -> File(m, "src/main").walkTopDown().filter { it.isFile && it.extension == "kt" }.map { m.name to it } }
    if (files.isEmpty()) return listOf("no se encontró código fuente en $root")
    fun strip(s: String) = s.lines().joinToString("\n") { l -> val t = l.trim(); if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) "" else l.substringBefore(" // ") }
    fun rule(name: String, allowed: Set<String>, re: Regex, exceptFiles: Set<String> = emptySet()) {
        for ((m, f) in files) if (m !in allowed && f.name !in exceptFiles && re.containsMatchIn(strip(f.readText()))) bad += "$name: $m/${f.name}"
    }
    // (a) red solo en :api
    rule("red fuera de :api", setOf("api"), Regex("HttpURLConnection|HttpsURLConnection|java\\.net\\.Socket|openConnection\\(|okhttp3"))
    // (b) criptografía solo en :security
    rule("cripto fuera de :security", setOf("security"), Regex("AndroidKeyStore|javax\\.crypto|java\\.security\\.(KeyStore|MessageDigest)"))
    // (c) reveal() solo donde hace falta
    rule("reveal() fuera de lugar", setOf("api", "credentials", "core"), Regex("\\.reveal\\(\\)"), exceptFiles = setOf("RealBackend.kt").let { emptySet() })
    // (d) sin salidas directas
    rule("salida directa (println/Log./printStackTrace)", setOf("none"), Regex("\\bprintln\\(|\\bandroid\\.util\\.Log\\b|\\bLog\\.[dievw]\\(|printStackTrace\\("))
    // (e) :api solo GET
    for ((m, f) in files) if (m == "api") {
        val t = strip(f.readText())
        if (Regex("requestMethod\\s*=\\s*\"(?!GET)").containsMatchIn(t) || Regex("doOutput|getOutputStream|RequestBody|\"(POST|PUT|DELETE|PATCH)\"").containsMatchIn(t)) bad += "método distinto de GET en api/${f.name}"
        if (!t.contains("instanceFollowRedirects = false")) bad += "api/${f.name}: no desactiva redirecciones"
    }
    // (f) sin reflexión ni ejecución dinámica
    rule("reflexión / código dinámico", setOf("none"), Regex("Runtime\\.getRuntime\\(\\)\\.exec|ProcessBuilder|Class\\.forName|DexClassLoader|\\.javaClass\\.getMethod|java\\.lang\\.reflect"))
    // (g) solo la capa de servicios une los módulos del mismo nivel; capas puras no importan android
    for ((m, f) in files) {
        val t = strip(f.readText())
        val imports = Regex("^import\\s+ar\\.tallymonitor\\.(\\w+)", RegexOption.MULTILINE).findAll(t).map { it.groupValues[1] }.toSet()
        val allowedDeps = mapOf("core" to setOf("core"), "credentials" to setOf("core", "credentials"), "security" to setOf("core", "credentials", "security"), "api" to setOf("core", "api"),
            "storage" to setOf("core", "storage"), "sync" to setOf("core", "sync"), "analysis" to setOf("core", "analysis"), "export" to setOf("core", "analysis", "export"),
            "services" to setOf("core", "credentials", "security", "storage", "sync", "analysis", "export", "api", "services"), "testing" to setOf("core", "analysis", "export", "services", "sync", "testing"), "app" to setOf("core", "analysis", "export", "services", "app"))
        val extra = imports - (allowedDeps[m] ?: setOf(m))
        if (extra.isNotEmpty()) bad += "dependencia no permitida: $m/${f.name} importa $extra"
        if (m in setOf("core", "credentials", "sync", "analysis", "export", "api") && Regex("^import\\s+android\\.", RegexOption.MULTILINE).containsMatchIn(t)) bad += "$m/${f.name} importa android.*"
    }
    // permisos y respaldo
    val manifest = File(root, "app/src/main/AndroidManifest.xml")
    if (manifest.exists()) {
        val x = manifest.readText()
        val perms = Regex("uses-permission[^>]*android:name=\"([^\"]+)\"").findAll(x).map { it.groupValues[1] }.toSet()
        if (!perms.all { it in setOf("android.permission.INTERNET", "android.permission.ACCESS_NETWORK_STATE", "android.permission.POST_NOTIFICATIONS") }) bad += "permisos de más: $perms"
        if (!x.contains("android:allowBackup=\"false\"")) bad += "allowBackup debe ser false"
        if (!x.contains("usesCleartextTraffic=\"false\"")) bad += "usesCleartextTraffic debe ser false"
    } else bad += "falta AndroidManifest.xml"
    return bad
}

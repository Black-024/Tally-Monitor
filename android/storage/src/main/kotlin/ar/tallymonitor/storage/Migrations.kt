package ar.tallymonitor.storage

import ar.tallymonitor.core.Clock
import ar.tallymonitor.core.ErrorCode
import ar.tallymonitor.core.TallyMonitorException

class Migration(val version: Int, val name: String, val sql: String)

data class MigrationResult(val from: Int, val to: Int, val applied: List<Int>)

object MigrationSql {
    private val FILE = Regex("^(\\d{4})_([a-z0-9_]+)\\.sql$")

    /** Lee las migraciones empaquetadas (recursos `migrations/<tipo>/NNNN_nombre.sql`). */
    fun load(kind: String, names: List<String>): List<Migration> = names.mapNotNull { n ->
        val m = FILE.matchEntire(n) ?: return@mapNotNull null
        val text = MigrationSql::class.java.getResourceAsStream("/migrations/$kind/$n")?.use { it.readBytes().toString(Charsets.UTF_8) }
            ?: throw TallyMonitorException(ErrorCode.MIGRATION_FAILED)
        Migration(m.groupValues[1].toInt(), m.groupValues[2], text)
    }.sortedBy { it.version }

    /** Quita comentarios `--` y separa sentencias por «;» (los esquemas no usan triggers ni «;» dentro de cadenas). */
    fun split(sql: String): List<String> =
        sql.lines().joinToString("\n") { l -> val i = l.indexOf("--"); if (i >= 0) l.substring(0, i) else l }
            .split(';').map { it.trim() }.filter { it.isNotEmpty() }
}

class MigrationRunner(private val db: Db, private val migrations: List<Migration>, private val appVersion: String,
                      private val clock: Clock = Clock.SYSTEM, private val beforeMigrate: ((Int, Int) -> Unit)? = null) {
    init { require(migrations.map { it.version } == (1..migrations.size).toList()) { "Las migraciones deben ser consecutivas desde 1." } }
    val latest get() = migrations.size

    fun migrate(): MigrationResult {
        val current = db.userVersion
        if (current > latest) throw TallyMonitorException(ErrorCode.DATABASE_TOO_NEW)
        val pending = migrations.filter { it.version > current }
        if (pending.isEmpty()) return MigrationResult(current, current, emptyList())
        if (beforeMigrate != null && current > 0) beforeMigrate.invoke(current, latest)      // si la copia previa falla, no se migra
        val applied = ArrayList<Int>()
        for (m in pending) {
            try { apply(m) } catch (e: Exception) { throw TallyMonitorException(ErrorCode.MIGRATION_FAILED, cause = e) }
            applied += m.version
        }
        return MigrationResult(current, latest, applied)
    }

    private fun apply(m: Migration) {
        val statements = MigrationSql.split(m.sql)
        db.tx { tx ->
            for (s in statements) tx.exec(s)
            val hasLog = tx.query("SELECT 1 FROM sqlite_master WHERE type='table' AND name='app_migration_log'") { 1 }.isNotEmpty()
            if (hasLog) tx.exec("INSERT INTO app_migration_log(version,name,applied_at,app_version) VALUES (?,?,?,?)", listOf(m.version, m.name, clock.nowIso(), appVersion))
        }
        db.userVersion = m.version          // PRAGMA user_version no puede ir dentro de la transacción en Android
    }
}

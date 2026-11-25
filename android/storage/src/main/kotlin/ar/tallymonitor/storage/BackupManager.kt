package ar.tallymonitor.storage

import android.database.sqlite.SQLiteDatabase
import ar.tallymonitor.core.Clock
import ar.tallymonitor.core.ErrorCode
import ar.tallymonitor.core.TallyMonitorException
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.UUID

data class BackupInfo(val filename: String, val file: File, val createdAt: Instant, val reason: String, val schemaVersion: Int, val sizeBytes: Long)

/**
 * Copias de seguridad de library.db. Las credenciales NO están en esa base (viven cifradas aparte), así que ninguna copia las
 * incluye. Android 8 trae SQLite 3.18 (sin VACUUM INTO): se hace checkpoint del WAL y se copia el archivo con el candado tomado.
 */
class BackupManager(private val db: Db, private val dir: File, private val clock: Clock = Clock.SYSTEM,
                    private val retention: Map<String, Int?> = DEFAULT_RETENTION) {
    companion object {
        val REASONS = listOf("auto", "manual", "pre_migracion", "pre_restauracion", "pre_reconciliacion")
        val DEFAULT_RETENTION: Map<String, Int?> = mapOf("auto" to 7, "manual" to null, "pre_migracion" to 5, "pre_restauracion" to 3, "pre_reconciliacion" to 5)
        private val NAME = Regex("^library_(\\d{8})_(\\d{6})_(auto|manual|pre_migracion|pre_restauracion|pre_reconciliacion)_v(\\d+)(?:_(\\d+))?\\.db$")
        private val STAMP = DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss").withZone(ZoneOffset.UTC)
        private val PARSE = DateTimeFormatter.ofPattern("yyyyMMddHHmmss").withZone(ZoneOffset.UTC)
    }

    private fun fail(code: ErrorCode, cause: Throwable? = null): Nothing = throw TallyMonitorException(code, cause = cause)

    fun create(reason: String): BackupInfo {
        require(reason in REASONS)
        dir.mkdirs()
        val tmp = File(dir, ".tmp_${UUID.randomUUID().toString().replace("-", "")}.partial")
        try {
            val version = db.locked {
                db.checkpoint()
                copy(db.file, tmp)
                db.userVersion
            }
            if (!integrityOk(tmp)) fail(ErrorCode.BACKUP_FAILED)
            val final = uniqueName(reason, version)
            if (!tmp.renameTo(final)) fail(ErrorCode.BACKUP_FAILED)
            return info(final)
        } catch (e: TallyMonitorException) { throw e
        } catch (e: Exception) { fail(ErrorCode.BACKUP_FAILED, e)
        } finally { tmp.delete() }
    }

    private fun uniqueName(reason: String, version: Int): File {
        val base = "library_${STAMP.format(Instant.ofEpochMilli(clock.nowMillis()))}_${reason}_v$version"
        var p = File(dir, "$base.db"); var n = 1
        while (p.exists()) { n++; p = File(dir, "${base}_$n.db") }
        return p
    }

    private fun copy(src: File, dst: File) {
        FileInputStream(src).use { i -> FileOutputStream(dst).use { o -> i.copyTo(o); o.flush(); o.fd.sync() } }
    }

    /** Abre en solo lectura y comprueba integridad. Devuelve el user_version o null si está dañada. */
    private fun integrityOk(f: File): Boolean = version(f) != null
    private fun version(f: File): Int? = try {
        SQLiteDatabase.openDatabase(f.path, null, SQLiteDatabase.OPEN_READONLY).use { d ->
            val ok = d.rawQuery("PRAGMA integrity_check", null).use { it.moveToFirst() && it.getString(0) == "ok" }
            if (ok) d.version else null
        }
    } catch (e: Exception) { null }

    private fun info(f: File): BackupInfo {
        val m = NAME.matchEntire(f.name) ?: fail(ErrorCode.BACKUP_FAILED)
        return BackupInfo(f.name, f, Instant.from(PARSE.parse(m.groupValues[1] + m.groupValues[2])), m.groupValues[3], m.groupValues[4].toInt(), f.length())
    }

    fun list(): List<BackupInfo> = (dir.listFiles() ?: emptyArray()).filter { it.isFile && NAME.matches(it.name) }.map { info(it) }
        .sortedWith(compareByDescending<BackupInfo> { it.createdAt }.thenByDescending { it.filename })

    /** Solo nombres del catálogo: nada de rutas. */
    fun find(filename: String): BackupInfo {
        if (filename != File(filename).name || !NAME.matches(filename)) fail(ErrorCode.BACKUP_FAILED)
        val f = File(dir, filename)
        if (!f.isFile) fail(ErrorCode.BACKUP_FAILED)
        return info(f)
    }

    fun applyRetention(): List<String> {
        val removed = ArrayList<String>()
        for ((reason, items) in list().groupBy { it.reason }) {
            val keep = retention[reason] ?: continue
            for (old in items.drop(keep)) { old.file.delete(); removed += old.filename }
        }
        return removed
    }

    fun delete(filename: String) { find(filename).file.delete() }

    private fun swapIn(source: File) {
        val target = db.file
        val staging = File(target.parentFile, target.name + ".restoring")
        copy(source, staging)
        db.close()
        File(target.path + "-wal").delete(); File(target.path + "-shm").delete()
        try { java.nio.file.Files.move(staging.toPath(), target.toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING) } catch (e: java.io.IOException) { fail(ErrorCode.RESTORE_FAILED, e) }
    }

    /** Restaura: copia `pre_restauracion` de lo actual, reemplaza el archivo y verifica; si algo falla, vuelve atrás. */
    fun restore(filename: String, latestVersion: Int, postRestore: (() -> Unit)? = null): BackupInfo {
        val info = find(filename)
        val v = version(info.file) ?: fail(ErrorCode.BACKUP_FAILED)
        if (v > latestVersion) fail(ErrorCode.DATABASE_TOO_NEW)
        db.locked {
            var safety: BackupInfo? = null; var aside: File? = null
            if (db.file.exists()) {
                try { safety = create("pre_restauracion") } catch (e: TallyMonitorException) {
                    aside = File(db.file.parentFile, "${db.file.name}.corrupt-${STAMP.format(Instant.ofEpochMilli(clock.nowMillis()))}")
                    copy(db.file, aside)                          // la base actual no se puede copiar: se conserva aparte tal cual
                }
            }
            try {
                swapIn(info.file)
                if (db.quickCheck().isNotEmpty()) fail(ErrorCode.RESTORE_FAILED)
                postRestore?.invoke()
            } catch (e: Exception) {
                try { (safety?.file ?: aside)?.let { swapIn(it) } } catch (_: Exception) { /* ya no hay más que intentar */ }
                throw TallyMonitorException(ErrorCode.RESTORE_FAILED, cause = e)
            }
            applyRetention()
        }
        return info
    }
}

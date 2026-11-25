package ar.tallymonitor.storage

import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteStatement
import java.io.File

/**
 * Una base SQLite: una sola conexión serializada con un candado (WAL, claves foráneas activas). Las escrituras de una
 * página de respuestas van en UNA transacción. Nunca guarda claves de API.
 */
class Db(val file: File) {
    private val lock = Any()
    private var conn: SQLiteDatabase? = null

    /** Reentrante: permite que backup/restauración tomen el candado y llamen a las demás operaciones. */
    fun <T> locked(block: () -> T): T = synchronized(lock, block)

    private fun db(): SQLiteDatabase = conn ?: run {
        file.parentFile?.mkdirs()
        SQLiteDatabase.openDatabase(file.path, null, SQLiteDatabase.CREATE_IF_NECESSARY).also {
            it.enableWriteAheadLogging()
            it.setForeignKeyConstraintsEnabled(true)
            it.execSQL("PRAGMA synchronous=FULL")
            conn = it
        }
    }

    fun close() = synchronized(lock) { conn?.close(); conn = null }

    /** Lectura: devuelve una lista mapeada fila por fila. */
    fun <T> query(sql: String, args: List<Any?> = emptyList(), map: (Cursor) -> T): List<T> = synchronized(lock) {
        db().rawQuery(sql, args.map { it?.toString() }.toTypedArray()).use { c ->
            val out = ArrayList<T>(); while (c.moveToNext()) out += map(c); out
        }
    }

    fun <T> queryOne(sql: String, args: List<Any?> = emptyList(), map: (Cursor) -> T): T? = query(sql, args, map).firstOrNull()

    fun exec(sql: String, args: List<Any?> = emptyList()): Int = synchronized(lock) { run(db(), sql, args) }

    /** Transacción inmediata: si el bloque lanza, se deshace todo. */
    fun <T> tx(block: (Tx) -> T): T = synchronized(lock) {
        val d = db()
        d.beginTransactionNonExclusive()
        try { val r = block(Tx(d)); d.setTransactionSuccessful(); r } finally { d.endTransaction() }
    }

    class Tx internal constructor(private val d: SQLiteDatabase) {
        fun exec(sql: String, args: List<Any?> = emptyList()): Int = run(d, sql, args)
        fun <T> query(sql: String, args: List<Any?> = emptyList(), map: (Cursor) -> T): List<T> =
            d.rawQuery(sql, args.map { it?.toString() }.toTypedArray()).use { c -> val o = ArrayList<T>(); while (c.moveToNext()) o += map(c); o }
    }

    var userVersion: Int
        get() = synchronized(lock) { db().version }
        set(v) = synchronized(lock) { db().version = v }

    /** [] si está sano; si no, descripciones del problema. */
    fun quickCheck(): List<String> = try {
        val rows = query("PRAGMA quick_check") { it.getString(0) }
        if (rows == listOf("ok")) emptyList() else rows.take(5)
    } catch (e: Exception) { listOf(e.javaClass.simpleName) }

    fun checkpoint() = synchronized(lock) { db().rawQuery("PRAGMA wal_checkpoint(TRUNCATE)", null).use { it.moveToFirst() } }

    fun removeFiles() = synchronized(lock) { close(); for (s in listOf("", "-wal", "-shm")) File(file.path + s).delete() }

    companion object {
        private fun run(d: SQLiteDatabase, sql: String, args: List<Any?>): Int {
            val st: SQLiteStatement = d.compileStatement(sql)
            try {
                args.forEachIndexed { i, a ->
                    val idx = i + 1
                    when (a) { null -> st.bindNull(idx); is Int -> st.bindLong(idx, a.toLong()); is Long -> st.bindLong(idx, a)
                        is Boolean -> st.bindLong(idx, if (a) 1 else 0); else -> st.bindString(idx, a.toString()) }
                }
                return st.executeUpdateDelete()
            } finally { st.close() }
        }
    }
}

fun Cursor.str(i: Int): String? = if (isNull(i)) null else getString(i)
fun Cursor.int(i: Int): Int? = if (isNull(i)) null else getInt(i)
fun Cursor.bool(i: Int): Boolean = !isNull(i) && getInt(i) != 0

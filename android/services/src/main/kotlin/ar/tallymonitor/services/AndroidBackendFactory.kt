package ar.tallymonitor.services

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import ar.tallymonitor.export.PdfImage
import ar.tallymonitor.security.KeystoreProtector
import java.io.File

/** Arma el backend real con las rutas de Android. Las credenciales van en noBackupFilesDir; la base y las copias, en filesDir. */
internal object AndroidBackendFactory {
    @Volatile private var instance: TallyMonitorBackend? = null

    fun create(context: Context): TallyMonitorBackend = instance ?: synchronized(this) {
        instance ?: run {
            val app = context.applicationContext
            val paths = BackendPaths(File(app.filesDir, "data"), File(app.noBackupFilesDir, "credentials.dat"), File(app.filesDir, "backups"), File(app.cacheDir, "export"))
            RealBackend(paths, KeystoreProtector(), AssetLogos(app), "1.0.0").also { instance = it }
        }
    }
}

/** Decodifica logo_dark.png / logo_light.png de los assets una sola vez y los entrega como RGB + alfa. */
private class AssetLogos(private val context: Context) : LogoProvider {
    private val cache = HashMap<String, PdfImage?>()
    override fun logo(style: String): PdfImage? = synchronized(cache) {
        cache.getOrPut(style) {
            try {
                val bmp = context.assets.open(if (style == "light") "logo_light.png" else "logo_dark.png").use { BitmapFactory.decodeStream(it) } ?: return@getOrPut null
                val w = bmp.width; val h = bmp.height
                val px = IntArray(w * h); bmp.getPixels(px, 0, w, 0, 0, w, h)
                val rgb = ByteArray(w * h * 3); val a = ByteArray(w * h)
                px.forEachIndexed { i, c -> rgb[i * 3] = (c shr 16).toByte(); rgb[i * 3 + 1] = (c shr 8).toByte(); rgb[i * 3 + 2] = c.toByte(); a[i] = (c ushr 24).toByte() }
                PdfImage(w, h, rgb, a)
            } catch (e: Exception) { null }       // sin logo, el PDF usa el cuadrito de marca
        }
    }
}

package ar.tallymonitor.verify

import ar.tallymonitor.core.ErrorCode
import ar.tallymonitor.core.Secret
import ar.tallymonitor.core.TallyMonitorException
import ar.tallymonitor.credentials.Credential
import ar.tallymonitor.credentials.CredentialProtector
import ar.tallymonitor.credentials.CredentialStore
import java.io.File
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/** Protector de PRUEBA con AES-GCM en software (en el teléfono se usa el Keystore). Mismo formato: IV + cifrado, AAD autenticado. */
private class SoftProtector : CredentialProtector {
    private val key = SecretKeySpec(ByteArray(32) { it.toByte() }, "AES")
    override fun protect(plain: ByteArray, aad: ByteArray): ByteArray {
        val iv = ByteArray(12).also { SecureRandom().nextBytes(it) }
        val c = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key, GCMParameterSpec(128, iv)); updateAAD(aad) }
        return iv + c.doFinal(plain)
    }
    override fun unprotect(blob: ByteArray, aad: ByteArray): ByteArray = try {
        val c = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, blob, 0, 12)); updateAAD(aad) }
        c.doFinal(blob, 12, blob.size - 12)
    } catch (e: Exception) { throw TallyMonitorException(ErrorCode.CREDENTIAL_UNREADABLE) }
}

fun credChecks(): List<Pair<String, () -> List<String>>> = listOf("almacén de credenciales" to ::credCheck)

private fun credCheck(): List<String> {
    val bad = ArrayList<String>()
    val dir = java.nio.file.Files.createTempDirectory("tm-cred").toFile()
    try {
        val f = File(dir, "credentials.dat")
        val st = CredentialStore(f, SoftProtector())
        val secret = "tly-SUPER-SECRETA-987"
        st.save("a1", Credential(Secret(secret), "user-1")); st.save("a2", Credential(Secret("otra-clave"), null))
        val raw = f.readText()
        if (raw.contains(secret) || raw.contains("otra-clave")) bad += "la clave quedó en claro en el archivo"
        if (raw.contains("user-1")) bad += "el id de usuario quedó en claro"
        val c = st.load("a1")
        if (c?.apiKey?.reveal() != secret || c.tallyUserId != "user-1") bad += "ida y vuelta incorrecta"
        if (c?.toString()?.contains(secret) == true || c?.apiKey.toString() != "***") bad += "toString filtra la clave"
        if (st.load("zzz") != null) bad += "devolvió credencial inexistente"
        // mover el cifrado de una cuenta a otra debe fallar (AAD)
        val lines = f.readLines(); val l1 = lines.first { it.startsWith("a1\t") }.substringAfter('\t')
        f.writeText("a1\t${lines.first { it.startsWith("a2\t") }.substringAfter('\t')}\na2\t$l1")
        for (id in listOf("a1", "a2")) try { st.load(id); bad += "aceptó cifrado de otra cuenta ($id)" } catch (e: TallyMonitorException) { if (e.code != ErrorCode.CREDENTIAL_UNREADABLE) bad += "código inesperado ${e.code}" }
        // alteración
        st.save("a3", Credential(Secret("x"), null))
        f.writeText(f.readLines().joinToString("\n") { if (it.startsWith("a3\t")) it.dropLast(6) + "AAAAA=" else it })
        try { st.load("a3"); bad += "aceptó contenido alterado" } catch (e: TallyMonitorException) {}
        // borrado
        st.delete("a3"); if (st.has("a3")) bad += "no borró la credencial"
        if (File(dir, "credentials.dat.tmp").exists()) bad += "quedó un temporal"
    } finally { dir.deleteRecursively() }
    return bad
}

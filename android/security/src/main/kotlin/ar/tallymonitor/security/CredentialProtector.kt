package ar.tallymonitor.security

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.security.keystore.StrongBoxUnavailableException
import ar.tallymonitor.core.ErrorCode
import ar.tallymonitor.core.TallyMonitorException
import ar.tallymonitor.credentials.CredentialProtector
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Android Keystore, AES-256-GCM. La clave es NO exportable (nunca sale del Keystore), no se incluye en copias de seguridad
 * y, si el dispositivo lo ofrece, vive en StrongBox (si no, en el TEE). Es el único lugar de la app que usa javax.crypto.
 */
class KeystoreProtector(private val alias: String = "tally_monitor_credentials_v1") : CredentialProtector {
    private companion object { const val PROVIDER = "AndroidKeyStore"; const val TRANSFORM = "AES/GCM/NoPadding"; const val IV_LEN = 12; const val TAG_BITS = 128 }

    private fun key(): SecretKey = try {
        val ks = KeyStore.getInstance(PROVIDER).apply { load(null) }
        (ks.getKey(alias, null) as? SecretKey) ?: generate()
    } catch (e: TallyMonitorException) { throw e
    } catch (e: Exception) { throw TallyMonitorException(ErrorCode.PROTECTION_UNAVAILABLE, cause = e) }

    private fun generate(): SecretKey {
        fun spec(strongBox: Boolean) = KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256).setRandomizedEncryptionRequired(true).apply { if (strongBox) setIsStrongBoxBacked(true) }.build()
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, PROVIDER)
        return try { gen.init(spec(true)); gen.generateKey() }
        catch (e: StrongBoxUnavailableException) { gen.init(spec(false)); gen.generateKey() }
        catch (e: Exception) { gen.init(spec(false)); gen.generateKey() }       // algunos equipos lanzan otra excepción sin StrongBox
    }

    override fun protect(plain: ByteArray, aad: ByteArray): ByteArray = try {
        val c = Cipher.getInstance(TRANSFORM).apply { init(Cipher.ENCRYPT_MODE, key()); updateAAD(aad) }
        c.iv + c.doFinal(plain)
    } catch (e: TallyMonitorException) { throw e
    } catch (e: Exception) { throw TallyMonitorException(ErrorCode.PROTECTION_UNAVAILABLE, cause = e) }

    override fun unprotect(blob: ByteArray, aad: ByteArray): ByteArray = try {
        if (blob.size <= IV_LEN) throw TallyMonitorException(ErrorCode.CREDENTIAL_UNREADABLE)
        val c = Cipher.getInstance(TRANSFORM).apply { init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(TAG_BITS, blob, 0, IV_LEN)); updateAAD(aad) }
        c.doFinal(blob, IV_LEN, blob.size - IV_LEN)
    } catch (e: TallyMonitorException) { throw e
    } catch (e: Exception) { throw TallyMonitorException(ErrorCode.CREDENTIAL_UNREADABLE, cause = e) }          // clave perdida (p. ej. restauración de equipo) o archivo alterado
}

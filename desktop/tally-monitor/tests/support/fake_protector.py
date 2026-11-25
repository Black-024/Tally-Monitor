"""Reemplazo de DPAPI SOLO PARA PRUEBAS (vive en tests/, no en el código de producción).
Sin dependencias: flujo de cifrado SHA-256 en modo contador + HMAC. No es criptografía para producción."""
import hashlib
import hmac
import secrets

from tally_monitor.core.errors import CredentialUnreadableError


class FakeProtector:
    def __init__(self, key: bytes | None = None) -> None:
        self._key = key or secrets.token_bytes(32)

    def _xor(self, nonce: bytes, data: bytes) -> bytes:
        out = bytearray()
        for i in range(0, len(data), 32):
            block = hashlib.sha256(self._key + nonce + i.to_bytes(8, "big")).digest()
            out += bytes(a ^ b for a, b in zip(data[i:i + 32], block))
        return bytes(out)

    def protect(self, data: bytes) -> bytes:
        nonce = secrets.token_bytes(16)
        ct = self._xor(nonce, data)
        return nonce + ct + hmac.new(self._key, nonce + ct, hashlib.sha256).digest()

    def unprotect(self, blob: bytes) -> bytes:
        if len(blob) < 48:
            raise CredentialUnreadableError()
        nonce, ct, tag = blob[:16], blob[16:-32], blob[-32:]
        if not hmac.compare_digest(tag, hmac.new(self._key, nonce + ct, hashlib.sha256).digest()):
            raise CredentialUnreadableError()
        return self._xor(nonce, ct)

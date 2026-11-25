"""Protector de credenciales para Linux y macOS: la API Key vive en el llavero del sistema.

El archivo credentials.dat solo guarda una referencia opaca («TMKR1:<id>»); el secreto está en el llavero
(Secret Service en Linux, Llavero de acceso en macOS). Nunca se usa un almacenamiento sin cifrar: si el llavero
disponible no es uno de los seguros conocidos, se rechaza.
"""
from __future__ import annotations

import base64
import binascii
import secrets
from typing import Any

from ..core.errors import CredentialUnreadableError, ProtectionUnavailableError
from ..core.language import pick as _t

SERVICE = "TallyMonitor"
_PREFIX = b"TMKR1:"
# Llaveros reales y cifrados. Cualquier otro (archivos de texto, «fail», «null», etc.) se descarta.
_SECURE_MODULES = ("keyring.backends.SecretService", "keyring.backends.libsecret", "keyring.backends.kwallet",
                   "keyring.backends.macOS", "keyring.backends.Windows")


def _find_secure_backend() -> Any:
    try:
        import keyring
        from keyring.backend import get_all_keyring
    except Exception as exc:  # noqa: BLE001 - sin la biblioteca no hay llavero
        raise ProtectionUnavailableError(
            _t("Falta el componente «keyring» para usar el llavero del sistema.", "The \"keyring\" component is missing, so the system keychain cannot be used.")) from exc
    candidates = []
    try:
        candidates = [b for b in get_all_keyring() if type(b).__module__.startswith(_SECURE_MODULES)]
        candidates.sort(key=lambda b: -getattr(b, "priority", 0))
    except Exception:  # noqa: BLE001
        pass
    for backend in candidates:
        try:
            if getattr(backend, "priority", 0) > 0:
                return backend
        except Exception:  # noqa: BLE001 - un backend que no se puede evaluar no sirve
            continue
    del keyring
    raise ProtectionUnavailableError(
        _t("No se encontró un llavero del sistema activo. En Linux instalá y abrí uno (por ejemplo gnome-keyring o "
        "KWallet) e iniciá sesión en él; en macOS desbloqueá el Llavero. No se guardan claves sin cifrar.", "No active system keychain was found. On Linux, install and open one (for example gnome-keyring or "
        "KWallet) and sign in to it; on macOS, unlock the Keychain. Keys are never stored unencrypted."))


class KeyringProtector:
    """Implementa CredentialProtector. `backend` solo se inyecta en pruebas (set/get/delete_password)."""

    def __init__(self, backend: Any | None = None) -> None:
        self._backend = backend if backend is not None else _find_secure_backend()

    def protect(self, data: bytes) -> bytes:
        ref = secrets.token_hex(16)
        try:
            self._backend.set_password(SERVICE, ref, base64.b64encode(data).decode("ascii"))
        except Exception as exc:  # noqa: BLE001 - el mensaje del llavero no se reenvía (podría traer datos)
            raise ProtectionUnavailableError(_t("El llavero del sistema no permitió guardar la clave.", "The system keychain did not allow saving the key.")) from exc
        return _PREFIX + ref.encode("ascii")

    def unprotect(self, blob: bytes) -> bytes:
        if not blob.startswith(_PREFIX):
            raise CredentialUnreadableError()
        ref = blob[len(_PREFIX):].decode("ascii", "replace")
        try:
            value = self._backend.get_password(SERVICE, ref)
        except Exception as exc:  # noqa: BLE001
            raise ProtectionUnavailableError(_t("No se pudo leer el llavero del sistema.", "Could not read the system keychain.")) from exc
        if value is None:
            raise CredentialUnreadableError()
        try:
            return base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise CredentialUnreadableError() from exc

    def discard(self, blob: bytes) -> None:
        """Borra del llavero la entrada a la que apunta [blob] (al eliminar o reemplazar una credencial)."""
        if not blob.startswith(_PREFIX):
            return
        try:
            self._backend.delete_password(SERVICE, blob[len(_PREFIX):].decode("ascii", "replace"))
        except Exception:  # noqa: BLE001 - si ya no estaba, no hay nada que borrar
            pass

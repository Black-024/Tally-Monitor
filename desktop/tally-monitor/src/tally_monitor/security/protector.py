"""Interfaz de cifrado de credenciales: DPAPI en Windows, llavero del sistema en Linux y macOS."""
from __future__ import annotations

import sys
from typing import Protocol



class CredentialProtector(Protocol):
    def protect(self, data: bytes) -> bytes: ...
    def unprotect(self, blob: bytes) -> bytes: ...
    # Opcional: `discard(blob)` libera lo que el protector guardó fuera del archivo (llavero).


def default_protector() -> CredentialProtector:
    """DPAPI en Windows; llavero del sistema en Linux y macOS. Si no hay protección segura se rechaza
    (nunca se guarda una clave sin cifrar)."""
    if sys.platform == "win32":
        from .dpapi import WindowsDpapiProtector
        return WindowsDpapiProtector()
    from .keyring_protector import KeyringProtector
    return KeyringProtector()

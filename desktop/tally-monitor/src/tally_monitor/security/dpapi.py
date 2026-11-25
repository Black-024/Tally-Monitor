"""Windows DPAPI mediante ctypes (sin dependencias). Alcance: usuario actual de Windows."""
from __future__ import annotations

import sys

from ..core.errors import CredentialUnreadableError, ProtectionUnavailableError
from ..core.language import pick as _t

# Entropía adicional fija de la aplicación: separa estos datos de otros que use el mismo usuario.
# No es un secreto (está en el código); la protección real es la del usuario de Windows.
_ENTROPY = b"TallyMonitor/credentials/v1"
_DESCRIPTION = "TallyMonitor"
_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class WindowsDpapiProtector:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise ProtectionUnavailableError()
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        self._ctypes = ctypes
        self._blob_t = DATA_BLOB
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        blob_p = ctypes.POINTER(DATA_BLOB)
        crypt32.CryptProtectData.argtypes = [blob_p, wintypes.LPCWSTR, blob_p, ctypes.c_void_p,
                                             ctypes.c_void_p, wintypes.DWORD, blob_p]
        crypt32.CryptProtectData.restype = wintypes.BOOL
        crypt32.CryptUnprotectData.argtypes = [blob_p, ctypes.c_void_p, blob_p, ctypes.c_void_p,
                                               ctypes.c_void_p, wintypes.DWORD, blob_p]
        crypt32.CryptUnprotectData.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        self._crypt32, self._kernel32 = crypt32, kernel32

    def _make_blob(self, data: bytes):
        ct = self._ctypes
        buf = ct.create_string_buffer(data, len(data))
        blob = self._blob_t(len(data), ct.cast(buf, ct.POINTER(ct.c_char)))
        return blob, buf  # buf debe seguir vivo mientras se usa blob

    def _read_and_free(self, out) -> bytes:
        ct = self._ctypes
        try:
            return ct.string_at(out.pbData, out.cbData)
        finally:
            self._kernel32.LocalFree(ct.cast(out.pbData, ct.c_void_p))

    def protect(self, data: bytes) -> bytes:
        if not data:
            raise ValueError("No hay nada que proteger")
        ct = self._ctypes
        blob_in, keep1 = self._make_blob(data)
        blob_ent, keep2 = self._make_blob(_ENTROPY)
        blob_out = self._blob_t()
        ok = self._crypt32.CryptProtectData(ct.byref(blob_in), _DESCRIPTION, ct.byref(blob_ent),
                                            None, None, _CRYPTPROTECT_UI_FORBIDDEN, ct.byref(blob_out))
        if not ok:
            raise ProtectionUnavailableError(_t("Windows no pudo cifrar la credencial (DPAPI).", "Windows could not encrypt the credential (DPAPI)."))
        return self._read_and_free(blob_out)

    def unprotect(self, blob: bytes) -> bytes:
        ct = self._ctypes
        blob_in, keep1 = self._make_blob(blob)
        blob_ent, keep2 = self._make_blob(_ENTROPY)
        blob_out = self._blob_t()
        ok = self._crypt32.CryptUnprotectData(ct.byref(blob_in), None, ct.byref(blob_ent),
                                              None, None, _CRYPTPROTECT_UI_FORBIDDEN, ct.byref(blob_out))
        if not ok:
            raise CredentialUnreadableError()
        return self._read_and_free(blob_out)

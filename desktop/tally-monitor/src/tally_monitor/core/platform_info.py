"""Datos del sistema operativo para textos y rutas (un solo lugar, para no repartir comprobaciones por el código)."""
from __future__ import annotations

import sys
from .language import pick as _t

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


def os_name() -> str:
    """Nombre del sistema tal como lo ve la persona."""
    return "Windows" if IS_WINDOWS else "macOS" if IS_MAC else "Linux"


def secure_store_name() -> str:
    """Cómo se llama, en los textos, el lugar donde se guarda la API Key."""
    if IS_WINDOWS:
        return _t("el cifrado de Windows (DPAPI)", "Windows encryption (DPAPI)")
    if IS_MAC:
        return _t("el llavero de macOS", "the macOS Keychain")
    return _t("el llavero del sistema (Secret Service: GNOME Keyring o KWallet)", "the system keychain (Secret Service: GNOME Keyring or KWallet)")

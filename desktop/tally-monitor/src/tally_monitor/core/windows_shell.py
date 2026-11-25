"""Identidad de la aplicación para el shell de Windows (para que la barra de tareas muestre el ícono propio)."""
from __future__ import annotations

import sys


def set_app_user_model_id(app_id: str = "TallyMonitor.App") -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:  # noqa: BLE001 - solo cosmético
        pass


def user_ui_language() -> str | None:
    """Idioma de la interfaz del usuario en Windows como código corto («es», «en», …); None si no se puede saber."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        name = {0x0A: "es", 0x09: "en"}.get(lcid & 0x3FF)           # idioma primario: 0x0A español, 0x09 inglés
        return name or "other"
    except Exception:  # noqa: BLE001 - solo para elegir el idioma inicial
        return None

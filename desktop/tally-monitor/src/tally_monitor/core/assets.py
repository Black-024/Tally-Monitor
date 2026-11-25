"""Búsqueda de los logos opcionales (carpeta `assets` del paquete). Si no están, todo funciona sin logo."""
from __future__ import annotations

import sys
from pathlib import Path

def _package_dir() -> Path:
    """Carpeta del paquete `tally_monitor`: también cuando va empaquetado con PyInstaller (carpeta de recursos)."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled) / "tally_monitor"
    return Path(__file__).resolve().parents[1]


ASSETS_DIR = _package_dir() / "assets"


def find_logo(style: str | None = None) -> Path | None:
    """Logo para un fondo «dark» o «light»; cae en logo.png. None si no hay ninguno."""
    names = ([f"logo_{style}.png"] if style in ("dark", "light") else []) + ["logo.png"]
    for name in names:
        path = ASSETS_DIR / name
        if path.is_file():
            return path
    return None


def find_icon() -> Path | None:
    order = ("logo.ico", "logo.png") if sys.platform == "win32" else ("logo.png", "logo.ico")   # fuera de Windows, PNG
    for name in order:
        path = ASSETS_DIR / name
        if path.is_file():
            return path
    return None


_PACKAGE_LEGAL = _package_dir() / "legal"                            # dentro de la versión empaquetada
_PROJECT_ROOT = Path(__file__).resolve().parents[3]                  # al ejecutar desde el código fuente


def read_legal(name: str) -> str | None:
    """Texto de LICENSE, PRIVACIDAD.md o THIRD_PARTY_LICENSES.md, esté el programa empaquetado o en el código fuente."""
    for base in (_PACKAGE_LEGAL, _PROJECT_ROOT):
        path = base / name
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return None

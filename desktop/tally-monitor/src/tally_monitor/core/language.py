"""Idioma de la aplicación (Español / English). Sin dependencias de Qt.

- Prioridad: variable de entorno TALLY_MONITOR_LANG > archivo `language.txt` en la carpeta de datos >
  idioma del sistema (empieza con «es» -> es; cualquier otro -> en).
- El idioma ACTIVO se fija la primera vez que se consulta y no cambia durante la sesión: `set_language()` solo
  guarda la preferencia y se aplica al reiniciar la app (los textos de la interfaz se evalúan al importar).
- `language.txt` contiene solo «es» o «en»: no hay secretos y no va en las bases ni junto a las credenciales.
"""
from __future__ import annotations

import locale
import os
from pathlib import Path

from .config import resolve_paths

SUPPORTED = ("es", "en")
ENV_LANG = "TALLY_MONITOR_LANG"

_active: str | None = None


def _normalize(code: str | None) -> str | None:
    """«es», «ES», «es_AR.UTF-8», «en-US» -> «es» / «en»; lo que no se reconoce -> None."""
    if not code:
        return None
    short = code.strip().lower().replace("-", "_").split("_")[0].split(".")[0]
    return short if short in SUPPORTED else None


def detect_system() -> str:
    """Idioma del sistema: empieza con «es» -> «es»; cualquier otro (o desconocido) -> «en»."""
    candidates: list[str | None] = []
    try:
        from .windows_shell import user_ui_language
        candidates.append(user_ui_language())                  # Windows: idioma de la interfaz del usuario
    except Exception:  # noqa: BLE001
        pass
    for var in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        candidates.append(os.environ.get(var))
    try:
        candidates.append(locale.getlocale()[0])
    except Exception:  # noqa: BLE001 - un locale roto no debe impedir arrancar
        pass
    for c in candidates:
        if c:
            first = c.strip().lower().split(":")[0]            # LANGUAGE puede ser «es:en»
            if first in ("c", "posix"):
                continue
            return "es" if first.startswith(("es", "spanish")) else "en"
    return "en"


def _file(home: str | os.PathLike | None = None) -> Path:
    return resolve_paths(home).language_file


def stored(home: str | os.PathLike | None = None) -> str | None:
    """Preferencia guardada («es»/«en») o None si no hay archivo o su contenido no es válido."""
    try:
        return _normalize(_file(home).read_text(encoding="utf-8").strip()[:16])
    except (OSError, ValueError):
        return None


def resolve(home: str | os.PathLike | None = None) -> str:
    """Aplica la prioridad (entorno > archivo > sistema) sin tocar el idioma activo."""
    return _normalize(os.environ.get(ENV_LANG)) or stored(home) or detect_system()


def current() -> str:
    """Idioma activo de esta sesión (se fija en la primera consulta)."""
    global _active
    if _active is None:
        _active = resolve()
    return _active


def set_language(code: str, home: str | os.PathLike | None = None) -> None:
    """Guarda la preferencia (se aplica al reiniciar). No cambia el idioma activo de la sesión."""
    norm = _normalize(code)
    if norm is None:
        raise ValueError(f"Idioma no soportado: {code!r}")
    path = _file(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(norm + "\n", encoding="utf-8")
    os.replace(tmp, path)


def pick(es: str, en: str) -> str:
    """Texto en el idioma activo (para mensajes fuera de la interfaz: errores, exportaciones)."""
    return es if current() == "es" else en


def _reset_for_tests() -> None:
    global _active
    _active = None

"""Autodiagnóstico: `TallyMonitor.exe --self-check` (o `py -m tally_monitor --self-check`).
Comprueba que el programa empaquetado tiene todo lo necesario. No usa la red ni toca tus datos reales."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from ._version import __version__


class _ThrowawayProtector:
    """Solo para el autodiagnóstico sobre una carpeta temporal: no protege nada real porque nunca se guardan claves."""

    def protect(self, data: bytes) -> bytes:
        return data[::-1]

    def unprotect(self, blob: bytes) -> bytes:
        return blob[::-1]


def run() -> int:
    lines: list[str] = []
    ok_all = True

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal ok_all
        ok_all &= bool(ok)
        lines.append(f"[{'OK' if ok else 'FALLO'}] {name}" + (f" ({detail})" if detail else ""))

    lines.append(f"Tally Monitor {__version__} | Python {sys.version.split()[0]} | "
                 f"empaquetado: {bool(getattr(sys, 'frozen', False))}")
    try:
        import PySide6
        from PySide6 import QtWidgets  # noqa: F401
        check("PySide6 disponible", True, PySide6.__version__)
    except Exception as exc:  # noqa: BLE001
        check("PySide6 disponible", False, type(exc).__name__)
    try:
        from .storage.migrations import load_migrations
        lib, cache = load_migrations("library"), load_migrations("cache")
        check("migraciones SQL incluidas", len(lib) >= 2 and len(cache) >= 1, f"library={len(lib)} cache={len(cache)}")
    except Exception as exc:  # noqa: BLE001
        check("migraciones SQL incluidas", False, type(exc).__name__)
    try:
        from .app import build_core
        from .core.config import AppPaths
        from .core.errors import ProtectionUnavailableError
        from .security.protector import default_protector
        try:
            prot = default_protector()
            blob = prot.protect(b"autodiagnostico")
            check("almacén seguro de claves (DPAPI / llavero)",
                  prot.unprotect(blob) == b"autodiagnostico" and b"autodiag" not in blob)
            getattr(prot, "discard", lambda _b: None)(blob)          # no deja restos en el llavero
        except ProtectionUnavailableError:
            # Depende del equipo (p. ej. un servidor sin escritorio no tiene llavero), no de si el paquete está completo:
            # se avisa pero no cuenta como fallo, y el resto de la revisión usa un protector descartable sin guardar claves.
            lines.append("[AVISO] almacén seguro de claves: no disponible en este equipo (la app no guardará claves aquí)")
            prot = _ThrowawayProtector()
        with tempfile.TemporaryDirectory(prefix="tally-monitor-selfcheck-") as tmp:
            core = build_core(paths=AppPaths(Path(tmp)), protector=prot, configure_logging=False)
            rep = core.startup.run()
            check("bases creadas y migradas en una carpeta temporal", rep.library_ok and not rep.needs_restore)
            snap = core.diagnostics.snapshot()
            check("esquema de la base al día", snap["library"].get("version_esquema", 0) >= 2,
                  f"v{snap['library'].get('version_esquema')}")
    except Exception as exc:  # noqa: BLE001
        check("núcleo de la aplicación", False, type(exc).__name__)
    lines.append("RESULTADO: " + ("TODO BIEN" if ok_all else "HAY FALLOS"))
    text = "\n".join(lines) + "\n"
    out = Path(os.environ.get("TEMP", tempfile.gettempdir())) / "tally-monitor-autodiagnostico.txt"
    try:
        out.write_text(text, encoding="utf-8")
    except OSError:
        pass
    if sys.stdout is not None:
        try:
            sys.stdout.write(text)
        except Exception:  # noqa: BLE001
            pass
    return 0 if ok_all else 1

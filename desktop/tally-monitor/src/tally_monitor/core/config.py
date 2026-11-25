"""Rutas de datos de la aplicación."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

ENV_HOME = "TALLY_MONITOR_HOME"


@dataclass(frozen=True)
class AppPaths:
    home: Path

    @property
    def library_db(self) -> Path:
        return self.home / "library.db"

    @property
    def cache_db(self) -> Path:
        return self.home / "cache.db"

    @property
    def credentials(self) -> Path:
        return self.home / "credentials.dat"

    @property
    def language_file(self) -> Path:
        return self.home / "language.txt"

    @property
    def backups_dir(self) -> Path:
        return self.home / "backups"

    @property
    def logs_dir(self) -> Path:
        return self.home / "logs"

    @property
    def reports_dir(self) -> Path:
        return self.home / "informes-prueba"

    def ensure(self) -> None:
        for d in (self.home, self.backups_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)


def resolve_paths(home: str | os.PathLike | None = None) -> AppPaths:
    """TALLY_MONITOR_HOME (solo pruebas) > %LOCALAPPDATA%\\TallyMonitor (Windows) > ~/Library/Application Support (macOS)
    > $XDG_DATA_HOME o ~/.local/share (Linux)."""
    if home is not None:
        return AppPaths(Path(home))
    env = os.environ.get(ENV_HOME)
    if env:
        return AppPaths(Path(env))
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return AppPaths(Path(base) / "TallyMonitor")
    if sys.platform == "darwin":
        return AppPaths(Path.home() / "Library" / "Application Support" / "TallyMonitor")
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg and os.path.isabs(xdg) else Path.home() / ".local" / "share"
    return AppPaths(base / "TallyMonitor")

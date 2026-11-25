"""Instancia única: un archivo de bloqueo que el sistema libera solo si el programa se cae."""
from __future__ import annotations

import os
import sys
from pathlib import Path


class SingleInstance:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._fh = None

    def acquire(self) -> bool:
        """True si somos la única instancia. Si no se puede comprobar, deja arrancar (nunca bloquea de más)."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fh = open(self._path, "a+b")
        except OSError:
            return True
        try:
            if sys.platform == "win32":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._fh = fh
        return True

    def release(self) -> None:
        fh, self._fh = self._fh, None
        if fh is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        fh.close()

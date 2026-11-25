"""Copias de seguridad de library.db con la API de backup de SQLite.

Las credenciales NO están en library.db (viven en credentials.dat), así que
ninguna copia las incluye. Este módulo solo escribe archivos `library_*.db`.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..core.clock import Clock
from ..core.errors import BackupError, BackupTooNewError, RestoreFailedError
from ..core.language import pick as _t
from .database import Database

log = logging.getLogger(__name__)

REASONS = ("auto", "manual", "pre_migracion", "pre_restauracion", "pre_reconciliacion")
# Cuántas copias automáticas se conservan por motivo (manual: ninguna se borra sola).
DEFAULT_RETENTION: dict[str, int | None] = {
    "auto": 7, "manual": None, "pre_migracion": 5, "pre_restauracion": 3, "pre_reconciliacion": 5,
}
_NAME_RE = re.compile(
    r"^library_(\d{8})_(\d{6})_(auto|manual|pre_migracion|pre_restauracion|pre_reconciliacion)"
    r"_v(\d+)(?:_(\d+))?\.db$")


@dataclass(frozen=True)
class BackupInfo:
    filename: str
    path: Path
    created_at: datetime       # UTC
    reason: str
    schema_version: int
    size_bytes: int


def _fsync_file(path: Path) -> None:
    with open(path, "rb+") as f:
        f.flush()
        os.fsync(f.fileno())


class BackupManager:
    def __init__(self, db: Database, backups_dir: Path, *, clock: Clock | None = None,
                 retention: dict[str, int | None] | None = None) -> None:
        self._db = db
        self._dir = Path(backups_dir)
        self._clock = clock or Clock()
        self._retention = dict(DEFAULT_RETENTION if retention is None else retention)

    # ---------- crear ----------
    def create(self, reason: str) -> BackupInfo:
        if reason not in REASONS:
            raise ValueError("motivo de backup inválido")
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp = self._dir / f".tmp_{uuid.uuid4().hex}.partial"
        try:
            with self._db.lock:
                version = self._db.user_version()
                with self._db.connection() as src:
                    dst = sqlite3.connect(tmp)
                    try:
                        src.backup(dst)
                        dst.execute("PRAGMA journal_mode=DELETE")
                        check = dst.execute("PRAGMA integrity_check").fetchone()[0]
                    finally:
                        dst.close()
            if check != "ok":
                raise BackupError(_t("La copia no pasó la verificación de integridad; se descartó.", "The backup failed the integrity check and was discarded."))
            _fsync_file(tmp)
            final = self._unique_name(reason, version)
            os.replace(tmp, final)
        except BackupError:
            raise
        except Exception as exc:
            raise BackupError() from exc
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
        log.info("Backup creado (%s, esquema v%s)", reason, version)
        return self._info_from_path(final)

    def _unique_name(self, reason: str, version: int) -> Path:
        stamp = self._clock.now().astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base = f"library_{stamp}_{reason}_v{version}"
        p = self._dir / f"{base}.db"
        n = 1
        while p.exists():
            n += 1
            p = self._dir / f"{base}_{n}.db"
        return p

    # ---------- listar / verificar ----------
    def _info_from_path(self, p: Path) -> BackupInfo:
        m = _NAME_RE.match(p.name)
        if not m:
            raise BackupError()
        created = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        return BackupInfo(p.name, p, created, m.group(3), int(m.group(4)), p.stat().st_size)

    def list(self) -> list[BackupInfo]:
        if not self._dir.exists():
            return []
        infos = [self._info_from_path(p) for p in self._dir.iterdir()
                 if p.is_file() and _NAME_RE.match(p.name)]
        return sorted(infos, key=lambda i: (i.created_at, i.filename), reverse=True)

    def verify(self, info: BackupInfo) -> int:
        """Abre la copia en solo lectura, comprueba integridad y devuelve su user_version."""
        try:
            conn = sqlite3.connect(f"{info.path.as_uri()}?mode=ro", uri=True)
            try:
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise BackupError(_t("La copia de seguridad está dañada.", "The backup is damaged."))
                return int(conn.execute("PRAGMA user_version").fetchone()[0])
            finally:
                conn.close()
        except sqlite3.DatabaseError as exc:
            raise BackupError(_t("La copia de seguridad está dañada.", "The backup is damaged.")) from exc

    def find(self, filename: str) -> BackupInfo:
        # Solo nombres de archivo del catálogo: nada de rutas.
        if filename != Path(filename).name or not _NAME_RE.match(filename):
            raise BackupError(_t("Nombre de copia inválido.", "Invalid backup name."))
        p = self._dir / filename
        if not p.is_file():
            raise BackupError(_t("La copia no existe.", "The backup does not exist."))
        return self._info_from_path(p)

    # ---------- retención / borrado ----------
    def apply_retention(self) -> list[str]:
        removed: list[str] = []
        by_reason: dict[str, list[BackupInfo]] = {}
        for i in self.list():
            by_reason.setdefault(i.reason, []).append(i)
        for reason, items in by_reason.items():
            keep = self._retention.get(reason)
            if keep is None:
                continue
            for old in items[keep:]:
                old.path.unlink(missing_ok=True)
                removed.append(old.filename)
        return removed

    def delete(self, filename: str) -> None:
        self.find(filename).path.unlink()

    # ---------- restaurar ----------
    def _swap_in(self, source: Path) -> None:
        target = self._db.path
        staging = target.with_name(target.name + ".restoring")
        shutil.copyfile(source, staging)
        _fsync_file(staging)
        for suffix in ("-wal", "-shm"):
            Path(str(target) + suffix).unlink(missing_ok=True)
        os.replace(staging, target)

    def restore(self, filename: str, *, latest_version: int,
                post_restore: Callable[[], None] | None = None) -> BackupInfo:
        info = self.find(filename)
        version = self.verify(info)
        if version > latest_version:
            raise BackupTooNewError()
        with self._db.lock:
            safety: BackupInfo | None = None
            aside: Path | None = None
            if self._db.path.exists():
                try:
                    safety = self.create("pre_restauracion")
                except BackupError:
                    # La base actual no se puede copiar (¿dañada?): se conserva aparte tal cual.
                    stamp = self._clock.now().strftime("%Y%m%d_%H%M%S")
                    aside = self._db.path.with_name(f"{self._db.path.name}.corrupt-{stamp}")
                    shutil.copyfile(self._db.path, aside)
            try:
                self._swap_in(info.path)
                if self._db.quick_check():
                    raise BackupError(_t("La base restaurada no pasó la verificación.", "The restored database failed verification."))
                if post_restore is not None:
                    post_restore()
            except Exception as exc:
                log.error("Restauración falló (%s); volviendo al estado anterior", type(exc).__name__)
                try:
                    if safety is not None:
                        self._swap_in(safety.path)
                    elif aside is not None:
                        self._swap_in(aside)
                except Exception:
                    log.error("No se pudo volver al estado anterior")
                raise RestoreFailedError() from exc
            self.apply_retention()
        log.info("Restauración completada desde %s", info.filename)
        return info

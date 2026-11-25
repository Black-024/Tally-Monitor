"""Almacén de credenciales cifradas (una por cuenta).

Cada registro es un JSON {api_key, tally_user_id} cifrado con el protector (DPAPI o llavero)
y guardado en credentials.dat. La API Key y el id de usuario de Tally NO van a las
bases de datos ni a los backups.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from ..core.clock import Clock
from ..core.errors import CredentialError, CredentialUnreadableError
from ..core.secret import SecretStr
from .protector import CredentialProtector

log = logging.getLogger(__name__)
_FORMAT = 1


@dataclass(frozen=True)
class StoredCredential:
    api_key: SecretStr
    tally_user_id: str | None

    def __repr__(self) -> str:
        return "StoredCredential(api_key=SecretStr('***'), tally_user_id=<oculto>)"


class CredentialStore:
    def __init__(self, path: Path, protector: CredentialProtector, clock: Clock | None = None) -> None:
        self._path = Path(path)
        self._protector = protector
        self._clock = clock or Clock()
        self._lock = threading.RLock()
        self.last_quarantine: Path | None = None

    # ---------- archivo ----------
    def _read(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            entries = data["entries"]
            if data.get("format") != _FORMAT or not isinstance(entries, dict):
                raise ValueError
            for v in entries.values():
                if not isinstance(v, dict) or not isinstance(v.get("blob"), str):
                    raise ValueError
            return entries
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            # No se sobrescribe un archivo ilegible: se aparta para poder recuperarlo.
            stamp = self._clock.now().strftime("%Y%m%d_%H%M%S")
            dest = self._path.with_name(f"{self._path.name}.corrupt-{stamp}")
            os.replace(self._path, dest)
            self.last_quarantine = dest
            log.error("credentials.dat ilegible; se movió a %s", dest.name)
            return {}

    def _write(self, entries: dict) -> None:
        payload = json.dumps({"format": _FORMAT, "entries": entries}, indent=1, sort_keys=True)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(f".{self._path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._path)
        finally:
            tmp.unlink(missing_ok=True)

    def _discard(self, entry: dict | None) -> None:
        """Si el protector guarda el secreto fuera del archivo (llavero), lo borra también de allí."""
        discard = getattr(self._protector, "discard", None)
        if discard is None or not entry:
            return
        try:
            discard(base64.b64decode(entry["blob"], validate=True))
        except Exception:  # noqa: BLE001 - limpiar es un esfuerzo extra: nunca debe impedir la operación
            pass

    # ---------- API ----------
    def save(self, account_id: str, api_key: SecretStr, tally_user_id: str | None) -> None:
        plain = json.dumps({"api_key": api_key.reveal(), "tally_user_id": tally_user_id}).encode("utf-8")
        blob = self._protector.protect(plain)
        now = self._clock.iso()
        with self._lock:
            entries = self._read()
            previous = entries.get(account_id)
            created = (previous or {}).get("created_at", now)
            entries[account_id] = {"blob": base64.b64encode(blob).decode("ascii"),
                                   "created_at": created, "updated_at": now}
            self._write(entries)
            self._discard(previous)

    def load(self, account_id: str) -> StoredCredential | None:
        """None si no hay registro. CredentialUnreadableError si existe pero no se puede descifrar."""
        with self._lock:
            entry = self._read().get(account_id)
        if entry is None:
            return None
        return self._decode(entry)

    def _decode(self, entry: dict) -> StoredCredential:
        try:
            blob = base64.b64decode(entry["blob"], validate=True)
            plain = self._protector.unprotect(blob)
            obj = json.loads(plain.decode("utf-8"))
            return StoredCredential(SecretStr(obj["api_key"]), obj.get("tally_user_id"))
        except CredentialError:
            raise
        except (binascii.Error, ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
            raise CredentialUnreadableError() from exc

    def has(self, account_id: str) -> bool:
        with self._lock:
            return account_id in self._read()

    def ids(self) -> set[str]:
        with self._lock:
            return set(self._read())

    def delete(self, account_id: str) -> None:
        with self._lock:
            entries = self._read()
            if account_id in entries:
                gone = entries.pop(account_id)
                self._write(entries)
                self._discard(gone)

    def iter_credentials(self) -> Iterator[tuple[str, StoredCredential]]:
        """Recorre las credenciales legibles (omite las que no se pueden descifrar)."""
        with self._lock:
            entries = self._read()
        for aid, entry in entries.items():
            try:
                yield aid, self._decode(entry)
            except CredentialError:
                continue

    def purge_orphans(self, valid_ids: set[str]) -> list[str]:
        with self._lock:
            entries = self._read()
            orphans = sorted(set(entries) - valid_ids)
            if orphans:
                gone = [entries.pop(a) for a in orphans]
                self._write(entries)
                for g in gone:
                    self._discard(g)
        return orphans

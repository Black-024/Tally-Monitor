"""Reloj inyectable (permite probar retenciones y fechas)."""
from __future__ import annotations

from datetime import datetime, timezone


class Clock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def iso(self) -> str:
        return self.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

"""Informe de diagnóstico para copiar y pegar: sin claves, sin textos de respuestas, sin nombres."""
from __future__ import annotations

import json
import platform
from pathlib import Path

from ..core.redact import redact
from ..core.language import pick as _t


def tail_log(logs_dir: Path, lines: int = 40) -> list[str]:
    path = Path(logs_dir) / "tally_monitor.log"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return [redact(x.rstrip()) for x in fh.readlines()[-lines:]]
    except OSError:
        return []


def build_report(version: str, snapshot: dict | None, logs_dir: Path) -> str:
    data = {
        "app": version, "python": platform.python_version(),
        _t("sistema", "system"): f"{platform.system()} {platform.version()}",
        _t("arquitectura", "architecture"): platform.machine(),
        _t("estado", "status"): snapshot if snapshot is not None else _t("no disponible", "not available"),
    }
    body = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    log = "\n".join(tail_log(logs_dir)) or _t("(sin registros)", "(no records)")
    head = _t("Informe de diagnóstico de Tally Monitor", "Tally Monitor diagnostic report")
    tail = _t("Últimas líneas del registro:", "Last lines of the log:")
    return redact(f"{head}\n\n{body}\n\n{tail}\n{log}\n")

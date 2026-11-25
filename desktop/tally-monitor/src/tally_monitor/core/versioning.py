"""Comparación de versiones «1.2.3» (con o sin «v»). Sin dependencias."""
from __future__ import annotations

import re

_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(text: str) -> tuple[int, int, int] | None:
    m = _RE.match((text or "").strip())
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def is_newer(candidate: str, current: str) -> bool:
    a, b = parse_version(candidate), parse_version(current)
    return a is not None and b is not None and a > b

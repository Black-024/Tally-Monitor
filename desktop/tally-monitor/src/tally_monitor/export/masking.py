"""Enmascarado de posibles datos personales en textos libres. Es una ayuda, NO una garantía."""
from __future__ import annotations

import re

MASK = "[oculto]"
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_HANDLE = re.compile(r"(?<![\w@])@\w{3,}")
_NUMBERISH = re.compile(r"(?<![\w])\+?\d[\d\s().-]{5,}\d(?![\w])")
_DATE = re.compile(r"^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}$")


def _mask_number(m: re.Match) -> str:
    s = m.group(0).strip()
    if _DATE.match(s):                      # fechas no son datos de contacto
        return m.group(0)
    return MASK if sum(c.isdigit() for c in s) >= 7 else m.group(0)


def mask_text(text: str) -> str:
    """Oculta correos, direcciones web, usuarios (@nombre) y números largos (teléfonos, DNI, tarjetas)."""
    if not text:
        return text
    out = _EMAIL.sub(MASK, text)
    out = _URL.sub(MASK, out)
    out = _HANDLE.sub(MASK, out)
    return _NUMBERISH.sub(_mask_number, out)

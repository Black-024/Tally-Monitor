"""Etiquetas «Usuario NNN».

1–9999        → Usuario 001 … Usuario 9999   (mínimo 3 dígitos)
10000–19998   → Usuario A001 … Usuario A9999
19999–29997   → Usuario B001 … Usuario B9999 … y así con Z, luego AA, AB…
El número interno es siempre un entero; la etiqueta es solo presentación.
"""
from __future__ import annotations

import re

from ..core.language import pick as _t

PER_BLOCK = 9999
FIRST_LETTER_NUMBER = 10000


def _letters(index: int) -> str:
    """0→A, 25→Z, 26→AA, 27→AB …"""
    s = ""
    index += 1
    while index > 0:
        index, rem = divmod(index - 1, 26)
        s = chr(65 + rem) + s
    return s


def _letters_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _user_word() -> str:
    return _t("Usuario", "User")


def format_user_label(number: int) -> str:
    if not isinstance(number, int) or number < 1:
        raise ValueError("El número de usuario debe ser un entero positivo")
    if number < FIRST_LETTER_NUMBER:
        return f"{_user_word()} {number:03d}"
    k = number - FIRST_LETTER_NUMBER
    return f"{_user_word()} {_letters(k // PER_BLOCK)}{k % PER_BLOCK + 1:03d}"


_NUM_RE = re.compile(r"^\s*(?:(?:usuario|user)\s+)?(\d{1,4})\s*$", re.I)
_LET_RE = re.compile(r"^\s*(?:(?:usuario|user)\s+)?([A-Za-z]{1,4})(\d{3,4})\s*$", re.I)


def parse_user_label(text: str) -> int | None:
    """Inversa de format_user_label (para buscar «Usuario 012» o «A001»). None si no es una etiqueta."""
    m = _NUM_RE.match(text)
    if m:
        n = int(m.group(1))
        return n if 1 <= n <= PER_BLOCK else None
    m = _LET_RE.match(text)
    if m:
        within = int(m.group(2))
        if not 1 <= within <= PER_BLOCK:
            return None
        return FIRST_LETTER_NUMBER + _letters_index(m.group(1).upper()) * PER_BLOCK + within - 1
    return None

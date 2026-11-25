"""Comprobación de forma de una API Key de Tally (sin revelar nada del valor)."""
import re

# Empieza con «tly-», solo caracteres ASCII imprimibles sin espacios, longitud mínima razonable.
_RE = re.compile(r"^tly-[\x21-\x7e]{4,}$")


def looks_like_api_key(value: str) -> bool:
    return bool(_RE.match(value)) and len(value) <= 200

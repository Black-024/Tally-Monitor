"""Redacción de claves de Tally en cualquier texto."""
import re

_KEY_RE = re.compile(r"tly-[A-Za-z0-9_\-]{4,}")


def redact(text: str) -> str:
    """Reemplaza cualquier cadena con forma de API Key de Tally por '***'."""
    return _KEY_RE.sub("***", text)

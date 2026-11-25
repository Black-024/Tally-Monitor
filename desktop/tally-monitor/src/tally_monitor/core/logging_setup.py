"""Logging con redacción automática de claves de Tally."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .redact import redact


class RedactingFilter(logging.Filter):
    """Redacta claves `tly-…` en el mensaje, los argumentos y la traza."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(record.getMessage())
            record.args = None
            if record.exc_info:
                # La traza se formatea y redacta; se descarta el objeto original.
                formatted = logging.Formatter().formatException(record.exc_info)
                record.exc_text = redact(formatted)
                record.exc_info = None
            elif record.exc_text:
                record.exc_text = redact(record.exc_text)
            if record.stack_info:
                record.stack_info = redact(record.stack_info)
        except Exception:  # nunca romper por logging
            record.msg = "(mensaje omitido por seguridad)"
            record.args = None
            record.exc_info = None
            record.exc_text = None
        return True


def setup_logging(logs_dir: Path, level: str = "INFO") -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("tally_monitor")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    handler = RotatingFileHandler(logs_dir / "tally_monitor.log", maxBytes=1_000_000,
                                  backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter())
    logger.addHandler(handler)
    return logger

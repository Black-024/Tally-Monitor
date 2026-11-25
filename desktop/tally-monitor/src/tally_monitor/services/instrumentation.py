"""Envoltorio de los servicios para el «modo prueba»: registra cada llamada (qué, con qué clase de datos, cuánto
tardó y cómo terminó) SIN guardar valores sensibles. Fuera del modo prueba no se usa."""
from __future__ import annotations

import dataclasses
import inspect
import re
from typing import Any

from ..core.secret import SecretStr
from ..core.session_report import safe_value, scrub_text

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_RESULT_STR_KEYS = {"status", "result", "mode", "reason", "category", "warnings", "unknown_fields", "origin", "kind"}
_MAX_DEPTH = 2
_ARG_ENUMS = {"kind": {"all", "24h", "7d", "30d", "custom"}}     # argumentos de texto corto y no sensible


def summarize_args(recorder, bound: dict[str, Any]) -> dict:
    out: dict[str, Any] = {}
    for name, value in bound.items():
        if name == "self":
            continue
        if name == "account_id" and isinstance(value, str):
            out[name] = recorder.mask_account(value)
        elif name == "form_id":
            out[name] = value if isinstance(value, str) and _ID_RE.match(value) else "<id inválido>"
        elif isinstance(value, str) and name in _ARG_ENUMS:
            out[name] = value if value in _ARG_ENUMS[name] else "<valor desconocido>"
        elif isinstance(value, SecretStr):
            out[name] = "<clave>"
        elif isinstance(value, str):
            out[name] = f"<texto de {len(value)} caracteres>"      # nombres, claves, etc.: nunca el valor
        elif callable(value):
            out[name] = "<función>"
        else:
            out[name] = safe_value(value)
    return out


def summarize_result(value: Any, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return {"len": len(value)}
    if dataclasses.is_dataclass(value) and not isinstance(value, type) and depth < _MAX_DEPTH:
        out = {}
        for f in dataclasses.fields(value):
            v = getattr(value, f.name)
            if f.name in _RESULT_STR_KEYS and isinstance(v, str):
                out[f.name] = scrub_text(v, 60)
            elif f.name in ("warnings", "unknown_fields") and isinstance(v, (tuple, list)):
                out[f.name] = [scrub_text(x, 80) for x in v][:20]
            elif isinstance(v, (bool, int)) or v is None:
                out[f.name] = v
            elif dataclasses.is_dataclass(v):
                out[f.name] = summarize_result(v, depth + 1)
        return out
    return f"<{type(value).__name__}>"


class _Proxy:
    """Reenvía todo al servicio real; los métodos públicos se registran. Lo privado pasa sin tocar."""

    def __init__(self, target: Any, label: str, recorder) -> None:
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_label", label)
        object.__setattr__(self, "_rec", recorder)

    def __getattr__(self, name: str):
        attr = getattr(self._target, name)
        if name.startswith("_") or not callable(attr):
            return attr
        rec, label = self._rec, self._label
        try:
            sig = inspect.signature(attr)
        except (TypeError, ValueError):
            sig = None

        def wrapper(*args, **kwargs):
            try:
                bound = dict(sig.bind(*args, **kwargs).arguments) if sig else {}
            except TypeError:
                bound = {}
            a = summarize_args(rec, bound)
            cid = rec.call_started(label, name, a)
            t0 = rec.now()
            try:
                result = attr(*args, **kwargs)
            except BaseException as exc:
                rec.call_finished(cid, label, name, a, t0, error=exc)
                raise
            rec.call_finished(cid, label, name, a, t0, result=summarize_result(result))
            return result

        wrapper.__name__ = name
        return wrapper


def instrument(service: Any, label: str, recorder) -> Any:
    return _Proxy(service, label, recorder)

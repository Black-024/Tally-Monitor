"""Tema activo de la aplicación («dark» o «light»). Los widgets dibujados a mano leen sus colores de aquí."""
from __future__ import annotations

from .tokens import THEME_NAMES, palette

_state = {"name": "dark"}


def name() -> str:
    return _state["name"]


def set_name(value: str) -> str:
    _state["name"] = value if value in THEME_NAMES else "dark"
    return _state["name"]


def colors() -> dict:
    return palette(_state["name"])

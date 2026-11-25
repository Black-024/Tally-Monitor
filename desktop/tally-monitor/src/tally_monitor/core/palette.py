"""Paletas de colores (oscuro y claro). Las usan la interfaz y los exportadores (PDF e imagen), así el archivo
exportado puede tener el mismo estilo que la aplicación o el contrario.

Roles: fondo (bg/bg2/surface/surface2), texto (text/muted/dim), `accent` = detalles semi-importantes
(violeta en oscuro, verde aqua en claro) y `action` = botones y lo que hay que ver (dorado en oscuro, café en claro).
"""
from __future__ import annotations

DARK = {
    "bg": "#0b0b0f", "bg2": "#121218", "surface": "#17171f", "surface2": "#1f1f2b", "border": "#2e2b45",
    "text": "#f4f2ff", "muted": "#aaa5c4", "dim": "#827d9c",
    "accent": "#8b7bff", "accent_hover": "#a79bff", "accent_text": "#0b0b0f",
    "action": "#e6b84a", "action_hover": "#f3c964", "action_text": "#1a1405",
    "ok": "#4ee0a8", "warn": "#e6b84a", "danger": "#ff6b81", "neutral": "#aaa5c4",
    "ok_bg": "#10302a", "warn_bg": "#33280f", "danger_bg": "#3b1520", "neutral_bg": "#1f1f2b",
}
LIGHT = {
    "bg": "#ffffff", "bg2": "#f2f8f7", "surface": "#f7fbfa", "surface2": "#e6f2f0", "border": "#c8dfdb",
    "text": "#1b2b29", "muted": "#4d6965", "dim": "#7a948f",
    "accent": "#12a198", "accent_hover": "#0c837b", "accent_text": "#ffffff",
    "action": "#8a5a3b", "action_hover": "#734a2f", "action_text": "#ffffff",
    "ok": "#17855d", "warn": "#9a6410", "danger": "#bf3249", "neutral": "#4d6965",
    "ok_bg": "#dcf2e8", "warn_bg": "#faeed6", "danger_bg": "#fbe0e4", "neutral_bg": "#e6f2f0",
}
THEMES = {"dark": DARK, "light": LIGHT}
THEME_NAMES = ("dark", "light")


def palette(name: str) -> dict:
    return THEMES.get(name, DARK)

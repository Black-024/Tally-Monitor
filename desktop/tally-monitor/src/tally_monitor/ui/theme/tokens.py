"""Tokens de diseño: colores (de `core.palette`), radios y tipografía. Todo color de la interfaz sale de aquí."""
from ...core.palette import DARK, LIGHT, THEME_NAMES, THEMES, palette  # noqa: F401

RADIUS = 14
# Primera tipografía disponible en el sistema: Windows, macOS, Ubuntu/Mint, GNOME, KDE y genéricas de Linux.
FONT_FAMILIES = ("Segoe UI", ".AppleSystemUIFont", "Helvetica Neue", "Ubuntu", "Cantarell", "Noto Sans", "DejaVu Sans",
                 "Liberation Sans", "sans-serif")
FONT_FAMILY = FONT_FAMILIES[0]
FONT_SIZE = 10          # puntos

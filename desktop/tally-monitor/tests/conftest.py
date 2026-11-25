"""Los tests comprueban los textos en español: se fija el idioma ANTES de que se importe cualquier módulo de la app."""
import os

os.environ["TALLY_MONITOR_LANG"] = "es"

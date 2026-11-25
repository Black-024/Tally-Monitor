"""Cuando PySide6 NO está instalado, ejecuta los flujos de la interfaz con un sustituto de Qt (solo lógica Python)."""
import subprocess
import sys
from pathlib import Path

import pytest

try:
    import PySide6  # noqa: F401
    HAVE_QT = True
except ImportError:
    HAVE_QT = False


@pytest.mark.skipif(HAVE_QT, reason="con PySide6 real se usan las pruebas de test_ui_qt.py")
def test_ui_flows_with_qt_shim():
    script = Path(__file__).resolve().parents[1] / "support" / "ui_shim_smoke.py"
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr

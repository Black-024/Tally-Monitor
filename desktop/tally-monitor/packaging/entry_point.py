"""Punto de entrada que usa PyInstaller para generar TallyMonitor.exe."""
import sys

from tally_monitor.__main__ import main

if __name__ == "__main__":
    sys.exit(main())

# -*- mode: python ; coding: utf-8 -*-
# Se ejecuta con:  py -m PyInstaller --noconfirm --clean packaging\TallyMonitor.spec   (Windows: scripts\crear_release.bat; Linux: scripts/linux/crear_release.sh)
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

# Las migraciones SQL son datos del paquete: sin ellas la app no puede crear sus bases.
# Se copia la carpeta completa de forma explícita (más fiable que collect_data_files con patrones).
SQL_SRC = os.path.join(ROOT, "src", "tally_monitor", "storage", "migrations_sql")
assert os.path.isdir(os.path.join(SQL_SRC, "library")), "No se encontró " + SQL_SRC
datas = [(SQL_SRC, os.path.join("tally_monitor", "storage", "migrations_sql"))]
# Logos opcionales (si no hay ninguno, la carpeta igual se incluye y el programa funciona sin logo).
ASSETS_SRC = os.path.join(ROOT, "src", "tally_monitor", "assets")
datas.append((ASSETS_SRC, os.path.join("tally_monitor", "assets")))
# Textos legales: se leen desde dentro del programa (botones «Licencia y terceros» y «Privacidad» de Ajustes).
for legal in ("LICENSE", "PRIVACIDAD.md", "THIRD_PARTY_LICENSES.md"):
    datas.append((os.path.join(ROOT, legal), os.path.join("tally_monitor", "legal")))
ICON = os.path.join(ASSETS_SRC, "logo.ico")
ICON = ICON if (sys.platform == "win32" and os.path.isfile(ICON)) else None   # .ico solo en Windows

hidden = ['openpyxl', 'reportlab.graphics.barcode', 'reportlab.pdfbase._fontdata']
extra_binaries = []
if sys.platform != "win32":
    # Llavero del sistema (Linux: Secret Service / KWallet; macOS: Llavero). Se importa por nombre, así que se incluye explícito.
    from PyInstaller.utils.hooks import collect_submodules
    hidden += collect_submodules("keyring.backends") + ["secretstorage", "jeepney"] * (sys.platform.startswith("linux"))
if sys.platform.startswith("linux"):
    # Qt 6 en X11 necesita libxcb-cursor, que muchas distribuciones no traen instalada: se incluye en el paquete.
    for d in ("/usr/lib/x86_64-linux-gnu", "/usr/lib/aarch64-linux-gnu", "/usr/lib64", "/usr/lib"):
        lib = os.path.join(d, "libxcb-cursor.so.0")
        if os.path.isfile(lib):
            extra_binaries.append((lib, "."))
            break

a = Analysis(
    [os.path.join(SPECPATH, "entry_point.py")],
    pathex=[os.path.join(ROOT, "src")],
    datas=datas,
    binaries=extra_binaries,
    hiddenimports=hidden,
    excludes=["tkinter", "pytest", "pytest_qt"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,         # carpeta (onedir): arranca más rápido y asusta menos al antivirus que un único .exe
    name="TallyMonitor",
    console=False,                 # app normal: sin ventana negra
    disable_windowed_traceback=False,
    upx=False,
    icon=ICON,
)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="TallyMonitor")

if sys.platform == "darwin":
    # macOS: aplicación «TallyMonitor.app» (carpeta onedir dentro de un paquete .app).
    import re
    with open(os.path.join(ROOT, "src", "tally_monitor", "_version.py"), encoding="utf-8") as fh:
        VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', fh.read()).group(1)
    ICNS = os.path.join(ASSETS_SRC, "logo.icns")
    app = BUNDLE(
        coll,
        name="TallyMonitor.app",
        icon=ICNS if os.path.isfile(ICNS) else None,
        bundle_identifier="ar.tallymonitor.app",
        version=VERSION,
        info_plist={
            "CFBundleName": "Tally Monitor",
            "CFBundleDisplayName": "Tally Monitor",
            "CFBundleShortVersionString": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": "MIT. Valentín Mangano Failde",
        },
    )

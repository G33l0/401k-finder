# PyInstaller specification for 401K Finder Pro.
#
#   pyinstaller installer/401k-finder.spec --noconfirm
#
# Produces a one-folder Windows application under dist/401K Finder Pro/.
# A one-folder build is used rather than --onefile because the vendored DOL
# layouts and the Qt runtime would otherwise be unpacked to a temp directory on
# every launch, adding seconds to start-up for no benefit.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = Path(SPECPATH).resolve()
PROJECT_ROOT = SPEC_DIR.parent

APP_NAME = "401K Finder Pro"
ENTRY_POINT = str(PROJECT_ROOT / "app" / "main.py")
ICON = PROJECT_ROOT / "app" / "ui" / "resources" / "app.ico"

# The vendored DOL layouts are read through importlib.resources, so PyInstaller
# cannot discover them by following imports. Without this the application starts
# and then fails on the first search.
datas = [
    (str(PROJECT_ROOT / "app" / "dol" / "layouts" / "data"), "app/dol/layouts/data"),
]

for extra in ("app.qss",):
    candidate = PROJECT_ROOT / "app" / "ui" / "resources" / extra
    if candidate.exists():
        datas.append((str(candidate), "app/ui/resources"))

hiddenimports = [
    "sqlalchemy.dialects.sqlite",
    # SQLAlchemy resolves these lazily at runtime.
    *collect_submodules("sqlalchemy.sql"),
]

# Qt modules the application never touches. Excluding them removes roughly
# 150 MB from the build.
excludes = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtOpenGL",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtTest",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "matplotlib",
    "numpy",
    "pandas",
    "tkinter",
]

block_cipher = None

analysis = Analysis(
    [ENTRY_POINT],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="401KFinderPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # console=False gives a windowed application with no terminal behind it.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.exists() else None,
)

collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

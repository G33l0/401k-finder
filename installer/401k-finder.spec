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
GUI_ENTRY_POINT = str(PROJECT_ROOT / "app" / "main.py")
CLI_ENTRY_POINT = str(PROJECT_ROOT / "app" / "cli.py")
ICON = PROJECT_ROOT / "app" / "ui" / "resources" / "app.ico"
ICON_PATH = str(ICON) if ICON.exists() else None

# The vendored DOL layouts are read through importlib.resources, so PyInstaller
# cannot discover them by following imports. Without this the application starts
# and then fails on the first search.
datas = [
    (str(PROJECT_ROOT / "app" / "dol" / "layouts" / "data"), "app/dol/layouts/data"),
    # Help -> User guide reads this at runtime, so it has to travel with the build.
    (str(PROJECT_ROOT / "docs" / "USER_GUIDE.md"), "docs"),
]

# Branding assets are loaded by path at runtime, not imported, so they need the
# same explicit treatment as the layouts. Any that are absent are simply not
# bundled -- the application falls back to Qt's defaults. See docs/DEPLOY.md.
RESOURCE_DIR = PROJECT_ROOT / "app" / "ui" / "resources"

for asset in ("app.ico", "app.png", "logo.png", "app.qss"):
    candidate = RESOURCE_DIR / asset
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

def build_analysis(entry_point):
    return Analysis(
        [entry_point],
        pathex=[str(PROJECT_ROOT)],
        binaries=[],
        datas=datas,
        hiddenimports=hiddenimports,
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[],
        excludes=excludes,
        noarchive=False,
    )


# Two executables share one folder: the windowed application, and a console
# build of the same code base exposing the command line. Without the second
# one, `401k-finder sync` and the rest of the CLI are unavailable to anyone who
# installed the packaged application rather than the source.
gui_analysis = build_analysis(GUI_ENTRY_POINT)
cli_analysis = build_analysis(CLI_ENTRY_POINT)

gui_pyz = PYZ(gui_analysis.pure)
cli_pyz = PYZ(cli_analysis.pure)

gui_executable = EXE(
    gui_pyz,
    gui_analysis.scripts,
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
    icon=ICON_PATH,
)

cli_executable = EXE(
    cli_pyz,
    cli_analysis.scripts,
    [],
    exclude_binaries=True,
    name="401k-finder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # The CLI needs a console to print to.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH,
)

collection = COLLECT(
    gui_executable,
    gui_analysis.binaries,
    gui_analysis.datas,
    cli_executable,
    cli_analysis.binaries,
    cli_analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

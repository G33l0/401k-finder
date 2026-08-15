# Packaging 401K Finder Pro as a Windows application

How to turn this repository into a Windows program a non-technical user can
install and run — a Start-menu entry, a desktop icon, no Python, no terminal.

There are two artefacts:

1. **A standalone application folder** — `dist\401K Finder Pro\`, containing
   `401KFinderPro.exe` and everything it needs. Copy it anywhere and run it.
2. **An installer** — `401KFinderPro-Setup-<version>.exe`, which puts that
   folder in Program Files, creates shortcuts, and registers an uninstaller.

`build.ps1` produces both.

---

## Quick start

On a Windows machine with Python 3.11–3.13 installed:

```powershell
git clone https://github.com/g33l0/401k-finder.git
cd 401k-finder

# Application only
.\build.ps1

# Application and installer
.\build.ps1 -Clean -Installer
```

Output:

```
dist\401K Finder Pro\401KFinderPro.exe
dist\installer\401KFinderPro-Setup-2.0.0.exe
```

If PowerShell refuses to run the script:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

That relaxes the policy for the current window only.

---

## Prerequisites

### Python 3.11, 3.12 or 3.13

From [python.org](https://www.python.org/downloads/windows/). During
installation tick **"Add python.exe to PATH"** — `build.ps1` fails immediately
without it.

Python 3.14 is not yet supported: PySide6 wheels lag new releases, and the
build pins `>=3.11,<3.14` to avoid producing something that installs and then
fails at start-up.

### Inno Setup 6 (only for `-Installer`)

From [jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php). `build.ps1`
finds `ISCC.exe` on `PATH` or in its default install location.

### Nothing else

PyInstaller is installed into the build's virtual environment automatically. The
end user needs nothing at all — not Python, not the Visual C++ redistributable
(the Qt runtime is bundled).

---

## What the build does

`build.ps1` runs these steps and stops at the first failure:

1. **Checks Python** is present and in the supported range.
2. **Creates `.venv`** and installs `requirements.txt` plus PyInstaller.
3. **Runs the test suite.** A release build with failing tests is a bug you are
   about to ship; pass `-SkipTests` only when iterating on packaging itself.
4. **Verifies the vendored DOL layouts load.** See the warning below — this is
   the single most common packaging failure.
5. **Runs PyInstaller** against `installer\401k-finder.spec`.
6. **Smoke-tests** that the layouts survived packaging.
7. **Runs Inno Setup**, if `-Installer` was passed.

### Options

| Flag | Effect |
|---|---|
| `-Clean` | Delete `build\` and `dist\` first. Use for release builds. |
| `-SkipTests` | Skip the test suite. |
| `-Installer` | Also build the setup executable. |

---

## The one thing that breaks packaging

The DOL record layouts in `app\dol\layouts\data\*.json` are loaded through
`importlib.resources`, not by an `import` statement. **PyInstaller cannot see
them by following imports.** A build that omits them produces an application
that starts, shows its window, and then fails on the first search with a
`KeyError` about a missing form year.

The spec file handles this explicitly:

```python
datas = [
    (str(PROJECT_ROOT / "app" / "dol" / "layouts" / "data"), "app/dol/layouts/data"),
]
```

`build.ps1` verifies it twice — before packaging and after — so the failure
surfaces during the build rather than in front of a user. If you change where
the layouts live, change both.

---

## Where the application keeps its data

Not in Program Files. The application data directory is:

```
%LOCALAPPDATA%\401K Finder Pro\
    database\401k_finder.sqlite3     the plan database
    dol_data\<year>\<dataset>\       extracted CSV files
    downloads\<year>\                downloaded ZIP archives
    exports\                         CSV, JSON and evidence reports
    logs\application.log             rotating log, 5 files x 5 MB
    settings.json
```

This matters for three reasons:

- **Program Files is read-only** for a standard user, so a database written
  beside the executable would fail on a managed workstation.
- **A per-user install needs no administrator prompt.** The installer defaults
  to `PrivilegesRequired=lowest`.
- **Uninstalling does not delete the data.** A full form year takes hours to
  download and import; discarding it silently on uninstall would be hostile.
  The uninstaller asks, and defaults to keeping it.

Users can reach this folder from **File → Open data folder** in the application.

### Disk space

Plan for **20–60 GB** for a single form year with the core datasets: the
archives, the extracted CSVs, and the database built from them. The application
deletes extracted CSVs after a successful import by default (`keep_extracted`
in `settings.json`) but keeps the archives so a re-import needs no re-download.

### Portable installs

Set `FINDER_401K_DATA_DIR` to keep everything beside the executable — useful for
a USB stick or a locked-down machine:

```bat
set FINDER_401K_DATA_DIR=%~dp0data
start "" "%~dp0401KFinderPro.exe"
```

Save that as `Run-Portable.bat` next to the executable.

---

## Build size

Expect roughly **250–400 MB** for the application folder. Qt is most of it.

The spec file already excludes the Qt modules the application never touches —
3D, multimedia, QML/Quick, WebEngine, charts, sensors — which removes about
150 MB. Removing more means removing features.

A one-folder build is used rather than `--onefile` deliberately: a one-file
build unpacks the whole Qt runtime and all 448 layout files to a temp directory
on **every launch**, adding several seconds to start-up and confusing antivirus
software. The folder is larger on disk but starts instantly.

---

## Code signing

Unsigned Windows applications trigger a SmartScreen warning: *"Windows protected
your PC"*. Users can click through via **More info → Run anyway**, but for
anything distributed beyond a handful of people, sign it.

You need an Authenticode certificate from a CA (DigiCert, Sectigo, SSL.com). An
**EV** certificate establishes SmartScreen reputation immediately; a standard OV
certificate builds reputation over time and downloads.

Sign the executable, then the installer:

```powershell
$signtool = "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
$timestamp = "http://timestamp.digicert.com"

& $signtool sign /fd SHA256 /td SHA256 /tr $timestamp `
    /n "Your Company Name" `
    "dist\401K Finder Pro\401KFinderPro.exe"

& $signtool sign /fd SHA256 /td SHA256 /tr $timestamp `
    /n "Your Company Name" `
    "dist\installer\401KFinderPro-Setup-2.0.0.exe"
```

Always timestamp (`/tr`). Without it, the signature stops validating the day the
certificate expires, rather than remaining valid for what was signed while it
was live.

To sign as part of the build, add a `[Setup]` directive to the `.iss` file:

```ini
SignTool=mysigntool
SignedUninstaller=yes
```

and register `mysigntool` in Inno Setup's IDE under **Tools → Configure Sign
Tools**.

---

## An application icon

The build works without one — PyInstaller uses a default. To use your own, put a
multi-resolution `.ico` (16, 32, 48, 64, 128, 256 px) at:

```
app\ui\resources\app.ico
```

The spec file picks it up automatically, and Inno Setup uses the executable's
icon for its shortcuts.

---

## Testing the build before shipping

The build machine has Python, the source tree, and every dependency already
present, so it is the worst possible place to judge whether the package works.
Test on a clean Windows VM with no Python installed:

1. Copy `dist\401K Finder Pro\` across (or run the installer).
2. Launch it. The window should open and the status bar should report no data
   imported.
3. **Open the Data tab and download a year.** This is the real test — it
   exercises TLS, the DOL download, ZIP extraction, the layouts, the importer
   and the database in one go. If the layouts were dropped from the package,
   this is where it fails.
4. Search for something and open a plan's Evidence tab.
5. Uninstall, and confirm it offers to keep the downloaded data.

For a faster check that does not download anything, generate synthetic files on
the build machine and copy them over:

```powershell
python -m scripts.make_test_data --year 2023 --plans 48
```

Then use **Data → Import files already on this computer** and point it at the
`test_data` folder.

---

## Antivirus false positives

PyInstaller applications are flagged by some scanners, because packers are also
what malware uses. If it happens:

- **Sign the executable.** This resolves most cases.
- **Do not use UPX.** The spec sets `upx=False` for exactly this reason;
  UPX-compressed binaries are flagged far more often.
- **Submit a false-positive report** to the vendor. Microsoft's is at
  <https://www.microsoft.com/en-us/wdsi/filesubmission>.

---

## Automating it

A GitHub Actions workflow that builds on every tag:

```yaml
name: Build Windows application

on:
  push:
    tags: ["v*"]
  workflow_dispatch:

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Inno Setup
        run: choco install innosetup --no-progress -y

      - name: Build
        shell: pwsh
        run: .\build.ps1 -Clean -Installer

      - uses: actions/upload-artifact@v4
        with:
          name: 401k-finder-windows
          path: dist/installer/*.exe
```

Signing in CI requires the certificate as an encrypted secret; for EV
certificates stored on a hardware token, signing generally has to happen on a
machine with the token attached.

---

## Updating an installed copy

The Inno Setup script uses a fixed `AppId`, so re-running a newer installer
upgrades in place: same install directory, same shortcuts, one entry in
Apps & features. The user's database and downloaded data are untouched.

Schema changes are handled by the application itself. `app/database/schema.py`
keeps a `schema_version` table and applies outstanding steps on start-up, so an
upgraded build opens an older database and migrates it. Opening a database
written by a *newer* build raises a clear error naming both versions rather than
corrupting it.

Bump the version in `app/__init__.py` before building — `build.ps1` reads it
from there and passes it to Inno Setup, so the two never disagree.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Python was not found on PATH` | Python not installed, or installed without the PATH option. Reinstall and tick "Add python.exe to PATH". |
| `build.ps1 cannot be loaded` | Execution policy. Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. |
| Application opens, first search errors about a missing form year | The layouts were dropped from the package. Confirm the `datas` entry in the spec file and rebuild with `-Clean`. |
| `ImportError: DLL load failed` for PySide6 | A mismatched or partial PySide6 install. Delete `.venv` and rebuild. |
| Window opens then closes immediately | Run `401KFinderPro.exe` from a terminal to see the error, or read `%LOCALAPPDATA%\401K Finder Pro\logs\application.log`. |
| Inno Setup not found | Install Inno Setup 6, or build without `-Installer`. |
| Downloads fail behind a corporate proxy | Set `HTTPS_PROXY` before launching; httpx honours it. TLS-inspecting proxies may also need the corporate CA in the system trust store. |
| Build succeeds but the executable is ~1 GB | Qt modules were not excluded — this happens if the spec file was replaced by a generated one. Restore `installer\401k-finder.spec`. |

Logs are the first place to look: `%LOCALAPPDATA%\401K Finder Pro\logs\application.log`.

---

## Building on non-Windows machines

You cannot. PyInstaller does not cross-compile — it bundles the interpreter and
libraries of the machine it runs on, so a Windows executable requires Windows.

Options:

- A Windows VM (Hyper-V, VirtualBox, Parallels, or a cloud instance).
- GitHub Actions with `runs-on: windows-latest`, as above. This is the least
  effort if you already use GitHub.
- Wine is not viable for this. It can sometimes produce a binary, but the result
  is unreliable and untestable in any meaningful way.

The application itself runs fine on Linux and macOS from source — only the
packaged `.exe` needs Windows to build.

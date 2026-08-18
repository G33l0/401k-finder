# Packaging 401K Finder Pro as a Windows application

How to turn this repository into a Windows program a non-technical user can
install and run: a Start-menu entry, a desktop icon, no Python, no terminal.

There are two artefacts:

1. **A standalone application folder**, `dist\401K Finder Pro\`, containing
   `401KFinderPro.exe`, `401k-finder.exe` and everything they need. Copy it
   anywhere and run it.
2. **An installer**, `401KFinderPro-Setup-<version>.exe`, which puts that
   folder in Program Files, creates shortcuts, and registers an uninstaller.

`build.ps1` produces both. `build.cmd` is a thin wrapper around it that
PowerShell's execution policy does not apply to; the two take the same
arguments.

> **New to this?** [`DEPLOY.md`](DEPLOY.md) is a step-by-step walkthrough that
> assumes nothing: installing the tools, adding your icon and logo, building,
> testing and distributing. This document is the reference behind it: how the
> packaging works and what to do when it does not.

---

## Quick start

On a Windows machine with Python 3.11 to 3.13 installed:

```powershell
git clone https://github.com/g33l0/401k-finder.git
cd 401k-finder

# Application only
.\build.cmd

# Application and installer
.\build.cmd -Clean -Installer
```

Output:

```
dist\401K Finder Pro\401KFinderPro.exe     the desktop application
dist\401K Finder Pro\401k-finder.exe       the command line
dist\installer\401KFinderPro-Setup-2.0.0.exe
```

Both executables share the one folder and the one bundled runtime, so shipping
the command line alongside the window costs about 11 MB rather than a second
copy of Qt. `401KFinderPro.exe` is windowed; `401k-finder.exe` is a console
build of the same code, so `401k-finder sync --year 2023` works on a machine
that only ever ran the installer.

If PowerShell refuses to run the script, with either *"running scripts is
disabled"* or *"is not digitally signed"*, use the `.cmd` wrapper instead. It is
not subject to the execution policy and takes the same arguments:

```powershell
.\build.cmd -Clean -Installer
```

To stay in PowerShell, relax the policy for the current window only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

That command can itself be refused on a machine where Group Policy locks the
setting; `build.cmd`, or `powershell -ExecutionPolicy Bypass -File .\build.ps1`,
works there. A *"not digitally signed"* message that survives a relaxed policy
means the files came from a downloaded ZIP and carry Windows' internet mark:
clear it with `Get-ChildItem -Recurse | Unblock-File`.

---

## Prerequisites

### Python 3.11, 3.12 or 3.13

From [python.org](https://www.python.org/downloads/windows/). During
installation tick **"Add python.exe to PATH"**. `build.ps1` fails immediately
without it.

Python 3.14 is not yet supported: PySide6 wheels lag new releases, and the
build pins `>=3.11,<3.14` to avoid producing something that installs and then
fails at start-up.

### Inno Setup 6 (only for `-Installer`)

From [jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php). `build.ps1`
finds `ISCC.exe` on `PATH` or in its default install location.

### Nothing else

PyInstaller is installed into the build's virtual environment automatically. The
end user needs nothing at all: not Python, not the Visual C++ redistributable
(the Qt runtime is bundled).

---

## What the build does

`build.ps1` runs these steps and stops at the first failure:

1. **Checks Python** is present and in the supported range.
2. **Creates the environment** and installs `requirements.txt` (what the
   application needs to run) plus `requirements-dev.txt` (pytest for the test
   step, PyInstaller for the packaging step), then confirms each tool it is
   about to invoke is importable.
3. **Runs the test suite.** A release build with failing tests is a bug you are
   about to ship; pass `-SkipTests` only when iterating on packaging itself.
4. **Verifies the vendored DOL layouts load.** See the warning below, because this is
   the single most common packaging failure.
5. **Runs PyInstaller** against `installer\401k-finder.spec`.
6. **Smoke-tests the built application.** It checks the layout files are present
   under `_internal`, then runs the packaged `401k-finder.exe` to confirm it
   starts, reads those layouts and creates a database. This runs the frozen
   executable, not the source tree, so it actually catches a bad `datas` entry.
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

`build.ps1` verifies this twice: once in the source tree before packaging, and
once against the built folder afterwards by running the packaged
`401k-finder.exe`. The second check is the one that matters, because a check that
imports from the source tree would pass even if PyInstaller dropped every
layout file. If you change where the layouts live, update the spec and the
`$LayoutDir` path in `build.ps1` together.

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

Plan for **20 to 60 GB** for a single form year with the core datasets: the
archives, the extracted CSVs, and the database built from them. The application
deletes extracted CSVs after a successful import by default (`keep_extracted`
in `settings.json`) but keeps the archives so a re-import needs no re-download.

All seventeen published years is several hundred gigabytes, which no ordinary
system disk will take. See **External and removable drives** below.

### External and removable drives

The bulk data (`database`, `dol_data`, `downloads` and `exports`) can be moved
to any other drive. The **Data** tab has the controls under *Where the data is
kept*; the command line is `401k-finder storage set E:\401k-data`, with
`storage`, `storage list` and `storage reset` alongside it. Changing the
location moves what is already there rather than starting over.

What deliberately does **not** move: `settings.json`, `logs`, the licence, and
`storage.json`, the one-line file recording where the data went. All four are
per-machine, and all four have to be readable before anyone knows whether the
other drive is connected. A pointer stored on the drive it points at would leave
with the drive.

Three Windows-specific things the code handles rather than leaving to the user:

| Situation | What happens |
| --- | --- |
| Drive formatted FAT32 | **Refused.** FAT32 caps a single file at 4 GB and a form year's database passes that, so the import would fail part-way with a misleading disk-full error. The dialog says to reformat as exFAT or NTFS, and warns that reformatting erases the drive. |
| Mapped network drive or UNC path | **Allowed, with a warning.** SQLite's write-ahead journal needs a shared-memory file that SMB does not implement, so the database falls back to the rollback journal (`PRAGMA journal_mode = DELETE`). It works; it is slower. |
| Drive not connected at start-up | **Reported.** A dialog offers *Try again*, *Choose the folder…*, *Use internal storage* or *Quit*, before the main window is built. The application never creates an empty database at the mount point, because an empty search result looks exactly like losing everything. |

Drive letters change. If Windows reassigns the stick from `E:` to `F:`, the
start-up dialog is what you get, and *Choose the folder…* points it at the new
letter without moving anything.

`PRAGMA busy_timeout` is set to 60 seconds rather than the usual few: a USB
drive under a long write can leave another connection waiting far longer than an
internal SSD would.

Tell users to connect the drive before opening the application, and to close the
application before ejecting it.

### Portable installs

Set `FINDER_401K_DATA_DIR` to keep everything beside the executable, which suits
a USB stick or a locked-down machine:

```bat
set FINDER_401K_DATA_DIR=%~dp0data
start "" "%~dp0401KFinderPro.exe"
```

Save that as `Run-Portable.bat` next to the executable.

---

## Build size

Expect roughly **200 MB** for the application folder, of which Qt is most.
A Linux build of the same spec measures 198 MB; Windows lands in the same range.

The spec file already excludes the Qt modules the application never touches:
3D, multimedia, QML/Quick, WebEngine, charts and sensors. That removes about
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

# Both executables in the folder, then the installer that wraps them.
& $signtool sign /fd SHA256 /td SHA256 /tr $timestamp `
    /n "Your Company Name" `
    "dist\401K Finder Pro\401KFinderPro.exe" `
    "dist\401K Finder Pro\401k-finder.exe"

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

## Branding assets

All optional. With an empty `app\ui\resources\` the application builds and runs
using Qt's defaults.

| File | Used for |
|---|---|
| `app.ico` | Both executables, the installer, and its shortcuts |
| `logo.png` | The About dialog, and the window icon off Windows |
| `app.png` | Window-icon fallback where `.ico` cannot be read |
| `app.qss` | Optional Qt style sheet applied at start-up |

The spec bundles whichever are present; `app/ui/resources/__init__.py` resolves
them at runtime, handling the fact that a frozen build unpacks data files beside
the executable rather than next to the module.

Verify what a build resolved. This works against the packaged executable too,
and reports paths inside `_internal`:

```powershell
401k-finder.exe status --branding
```

**Exact size and format requirements are in [`DEPLOY.md`](DEPLOY.md), section 4.**

---

## Testing the build before shipping

The build machine has Python, the source tree, and every dependency already
present, so it is the worst possible place to judge whether the package works.
Test on a clean Windows VM with no Python installed:

1. Copy `dist\401K Finder Pro\` across (or run the installer).
2. Launch it. The window should open and the status bar should report no data
   imported. `401k-finder.exe status` from a prompt in that folder should say
   the same thing.
3. **Open the Data tab and download a year.** This is the real test, because it
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

Bump the version in `app/__init__.py` before building. `build.ps1` reads it
from there and passes it to Inno Setup, so the two never disagree.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Python was not found on PATH` | Python not installed, or installed without the PATH option. Reinstall and tick "Add python.exe to PATH". |
| `build.ps1 cannot be loaded`, whether it says *running scripts is disabled* or *is not digitally signed* | Execution policy. Use `.\build.cmd`, which is not subject to it, or run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first. If Group Policy locks that, `powershell -ExecutionPolicy Bypass -File .\build.ps1`. If *not digitally signed* persists, the files carry the mark-of-the-web from a ZIP download: `Get-ChildItem -Recurse | Unblock-File`. |
| Hangs at *Preparing the virtual environment* | Cloud sync or antivirus, not a crash. Move the project off OneDrive-backed Desktop/Documents, or pass `-VenvPath C:\venvs\401k`. Wait 5 minutes before interrupting. |
| Application opens, first search errors about a missing form year | The layouts were dropped from the package. Confirm the `datas` entry in the spec file and rebuild with `-Clean`. |
| `ImportError: DLL load failed` for PySide6 | A mismatched or partial PySide6 install. Delete `.venv` and rebuild. |
| Window opens then closes immediately | Run `401KFinderPro.exe` from a terminal to see the error, or read `%LOCALAPPDATA%\401K Finder Pro\logs\application.log`. |
| Inno Setup not found | Install Inno Setup 6, or build without `-Installer`. |
| Downloads fail behind a corporate proxy | Set `HTTPS_PROXY` before launching; httpx honours it. TLS-inspecting proxies may also need the corporate CA in the system trust store. |
| Build succeeds but the executable is ~1 GB | Qt modules were not excluded. This happens if the spec file was replaced by a generated one. Restore `installer\401k-finder.spec`. |
| `TypeError` about `cipher` or `win_no_prefer_redirects` while reading the spec | An old spec file from PyInstaller 5. Those arguments were removed in PyInstaller 6; the current spec does not use them. |
| `ModuleNotFoundError: No module named 'app'` during the build | `build.ps1` was run from outside the project directory. The project is not pip-installed into the build venv, so the checks run with the project root as the working directory. This is handled, but a hand-run `python -c "import app"` needs `cd` first. |

Logs are the first place to look: `%LOCALAPPDATA%\401K Finder Pro\logs\application.log`.

---

## Building on non-Windows machines

You cannot. PyInstaller does not cross-compile. It bundles the interpreter and
libraries of the machine it runs on, so a Windows executable requires Windows.

Options:

- A Windows VM (Hyper-V, VirtualBox, Parallels, or a cloud instance).
- GitHub Actions with `runs-on: windows-latest`, as above. This is the least
  effort if you already use GitHub.
- Wine is not viable for this. It can sometimes produce a binary, but the result
  is unreliable and untestable in any meaningful way.

The application itself runs fine on Linux and macOS from source. Only the
packaged `.exe` needs Windows to build.

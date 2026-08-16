# Deploying 401K Finder Pro on Windows

A complete, assume-nothing walkthrough: from a bare Windows machine to a signed
installer you can hand to someone else.

If you have never built a desktop application before, follow this top to bottom.
Every command is meant to be copied and pasted exactly as written. Nothing here
requires you to understand Python.

**Related documents**

- [`WINDOWS_APPLICATION.md`](WINDOWS_APPLICATION.md) — the reference on how the
  packaging works, what the spec file does, and how to troubleshoot it.
- [`SELLING.md`](SELLING.md) — putting the installer online, taking payment, and
  licence keys issued by email and tied to the buyer's computer.
- [`../README.md`](../README.md) — what the application does and how to use it.

---

## Contents

1. [What you are building](#1-what-you-are-building)
2. [Install the tools](#2-install-the-tools)
3. [Get the code](#3-get-the-code)
4. [Add your icon and logo](#4-add-your-icon-and-logo)
5. [Build it](#5-build-it)
6. [Check the build before you ship it](#6-check-the-build-before-you-ship-it)
7. [Sign it](#7-sign-it)
8. [Distribute it](#8-distribute-it)
9. [Ship an update](#9-ship-an-update)
10. [If something goes wrong](#10-if-something-goes-wrong)

---

## 1. What you are building

The build produces one folder and one installer:

```
dist\401K Finder Pro\          the application, ~200 MB
    401KFinderPro.exe          the window
    401k-finder.exe            the command line
    _internal\                 Python, Qt and the DOL layouts

dist\installer\
    401KFinderPro-Setup-2.0.0.exe
```

The person you give this to needs **nothing installed** — no Python, no Qt, no
Visual C++ runtime. They run the setup, get a Start-menu entry, and open it.

The application ships with **no data**. On first run it is an empty database;
the user downloads a form year from the Data tab. That download is several
gigabytes and takes 15–60 minutes, so tell them to expect it.

### Time and disk

| | |
|---|---|
| Installing the tools | 15–20 minutes, mostly downloads |
| First build | 5–10 minutes |
| Later builds | 2–4 minutes |
| Disk for building | ~3 GB |
| Disk for a user running it | 20–60 GB per form year |

---

## 2. Install the tools

You need three things. Install them in this order.

### 2.1 Python

1. Go to <https://www.python.org/downloads/windows/>.
2. Download the latest **3.12** or **3.13** release — *"Windows installer
   (64-bit)"*. Do **not** take 3.14 or newer; the UI toolkit does not have
   builds for it yet and the build will refuse to run.
3. Run the installer. On the very first screen, **tick "Add python.exe to
   PATH"** at the bottom. This is the single most common thing people miss, and
   the build cannot find Python without it.
4. Click **Install Now**, then **Close**.

Confirm it worked. Press `Win`, type `powershell`, press Enter, and run:

```powershell
python --version
```

You should see `Python 3.12.x` or `Python 3.13.x`. If you instead see a Microsoft
Store page or `python was not found`, the PATH tick box was missed — re-run the
installer, choose **Modify**, and enable it.

### 2.2 Git

1. Go to <https://git-scm.com/download/win>. The download starts by itself.
2. Run it and accept every default.

Confirm:

```powershell
git --version
```

### 2.3 Inno Setup

This builds the installer. Skip it if you only want the application folder.

1. Go to <https://jrsoftware.org/isdl.php>.
2. Download **innosetup-6.x.x.exe** and run it, accepting the defaults.

You do not need to open Inno Setup. The build finds it automatically.

---

## 3. Get the code

Open PowerShell and pick somewhere to work.

**Avoid Desktop, Documents and OneDrive.** Windows redirects those to OneDrive
by default, and the build creates thousands of small files that cloud sync will
crawl through — it looks like the build has frozen. Use a plain local folder:

```powershell
mkdir C:\dev -Force
cd C:\dev
git clone https://github.com/g33l0/401k-finder.git
cd 401k-finder
```

If you must keep the project in a synced folder, put the build environment
elsewhere instead:

```powershell
.\build.ps1 -Clean -Installer -VenvPath C:\venvs\401k
```

You are now in the project folder. **Every command from here on assumes you are
in this folder.** If you close PowerShell, `cd C:\dev\401k-finder` again before
continuing.

### Allow the build script to run

Windows blocks downloaded scripts by default. Run this once per PowerShell
window:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

`-Scope Process` means it applies only to this window and reverts when you close
it. It does not change your machine's settings.

---

## 4. Add your icon and logo

**This step is optional.** The repository already ships a mark — a stepped
trace climbing to a solid node, in deep teal and amber — and the build picks it
up with no work from you. Read this section when you want to replace it with
your own branding, or when you want to change the one that is there.

Everything goes in one folder:

```
app\ui\resources\
```

The build picks up whatever is there and ignores what is not. Delete the lot
and the application still builds, falling back to Qt's default icon.

### 4.0 Changing the mark that ships

The shipped files are generated from
[`scripts/make_logo.py`](../scripts/make_logo.py) rather than drawn by hand.
To adjust the colours or the geometry, edit the constants at the top of that
file and regenerate:

```powershell
.\.venv\Scripts\python.exe -m pip install pillow
.\.venv\Scripts\python.exe -m scripts.make_logo --preview
```

That rewrites `app.ico`, `app.png`, `logo.png` and `logo.svg`, and with
`--preview` also writes `app\ui\logo_preview.png` — every icon size on a light
and a dark background, which is the only reliable way to tell whether a change
still reads at 16 px. The preview file is not shipped and is git-ignored.

The script sizes and positions the mark itself: it scales the artwork until it
clears the badge's rounded corners by the stated margin, so changing a stroke
weight cannot silently push part of the design outside the icon's silhouette.

If you replace the images by hand instead, delete the
`test_the_mark_is_reproducible_from_its_source` test — it exists to catch the
committed files and the script drifting apart and cannot tell that apart from
a deliberate replacement.

### 4.1 The files

| File | Used for | Required format |
|---|---|---|
| `app.ico` | The `.exe` icon in Explorer and the taskbar, the installer, and Start-menu shortcuts | Windows ICO, **must** contain 16, 32, 48 and 256 px; 64 and 128 px recommended. 32-bit colour with alpha. |
| `logo.png` | The About dialog, and the window icon on macOS and Linux | PNG with transparency, square, **512×512 px** recommended (256 minimum) |
| `app.png` | Window icon fallback where `.ico` cannot be read | PNG with transparency, square, 512×512 px |
| `logo.svg` | Not used at runtime. The vector original, for your store page and print | SVG |
| `app.qss` | Optional. Extra Qt style sheet rules, applied *after* the active theme | UTF-8 text, [Qt Style Sheets syntax](https://doc.qt.io/qt-6/stylesheet-syntax.html) |

Names are exact and case-sensitive on some systems — use lower case.

### 4.2 Icon specification in detail

`app.ico` is not a renamed PNG. It is a container holding several sizes, and
Windows picks whichever fits the context: 16 px in the title bar, 32 px in the
taskbar, 48 px in Explorer's medium view, 256 px for large tiles. Supplying only
one size makes the icon look blurred or jagged everywhere else.

**Required contents**

| Size | Where it shows |
|---|---|
| 16×16 | Title bar, small Explorer lists |
| 32×32 | Taskbar, alt-tab |
| 48×48 | Explorer medium icons, desktop shortcut |
| 64×64 | Recommended. High-DPI taskbar |
| 128×128 | Recommended. Explorer large icons |
| 256×256 | Explorer extra-large, installer header |

**Other requirements**

- 32-bit colour (RGBA) with a real alpha channel, not a magenta key colour.
- The 256 px frame should be PNG-compressed inside the ICO; the smaller ones may
  be either PNG or BMP. Any modern tool does this correctly by default.
- **Square.** A non-square source is stretched, not letterboxed.
- Keep the design readable at 16 px. Fine detail and small text disappear
  entirely — a single bold shape reads far better than a detailed illustration.

**Making one from a PNG**

Start with a square PNG at 1024×1024, then:

- *Online:* <https://redketchup.io/icon-converter> or
  <https://icoconvert.com> — choose the multi-size option, not a single size.
- *ImageMagick:*
  ```powershell
  magick logo.png -define icon:auto-resize=256,128,64,48,32,16 app.ico
  ```
- *GIMP:* open the PNG, `Image → Scale` to each size on its own layer, then
  `File → Export As…` → `app.ico` and tick every layer.

### 4.3 Logo specification in detail

`logo.png` appears in **Help → About**, scaled to 96 px wide.

- Square, 512×512 px recommended. Smaller than 256 px looks soft on a high-DPI
  display; larger than 1024 px only inflates the build.
- PNG with transparency. The dialog background follows the user's Windows theme,
  so a logo on a baked-in white rectangle will show that rectangle on dark mode.
- A wordmark works here even though it would not work as an icon — 96 px is
  wide enough to read text.

### 4.4 Confirm they were picked up

```powershell
python -m app.cli status --branding
```

```
Resource folder: C:\Users\you\Documents\401k-finder\app\ui\resources
  icon:        C:\Users\you\Documents\401k-finder\app\ui\resources\app.ico
  logo:        C:\Users\you\Documents\401k-finder\app\ui\resources\logo.png
  stylesheet:  not set (using Qt default)
```

Anything reading `not set` was not found — check the filename and that it is in
that exact folder.

A corrupt or truncated icon is reported as `not set` rather than being used,
because Windows renders a broken icon as a blank square with no error.

---

## 5. Build it

One command:

```powershell
.\build.ps1 -Clean -Installer
```

- `-Clean` throws away previous build output. Use it for anything you intend to
  distribute.
- `-Installer` also produces the setup executable. Omit it for just the folder.

The first run takes 5–10 minutes because it downloads the Qt libraries. You will
see each stage announced:

```
==> Checking Python
==> Preparing the virtual environment
==> Installing dependencies
==> Running the test suite
==> Verifying the vendored DOL layouts in the source tree
==> Building the application with PyInstaller
==> Smoke-testing the packaged application
==> Building the installer with Inno Setup
==> Done
```

The build **stops at the first failure**, so if it reaches `Done` every stage
passed — including the full test suite and a check that the packaged
application starts and can read its data files.

If you are iterating on the icon and want to skip the tests:

```powershell
.\build.ps1 -SkipTests
```

Do not ship a build made with `-SkipTests`.

---

## 6. Check the build before you ship it

The machine you built on has Python and every dependency already installed,
which makes it the worst possible place to judge whether the package works
standing alone. **Test on a different machine, or a fresh virtual machine, with
no Python on it.**

Windows Sandbox is the quickest option if you have Windows Pro or Enterprise:
enable it under *Turn Windows features on or off*, open it, and drag the
installer in. It gives you a clean, throwaway Windows every time.

Work through this list:

1. **Install.** Run the setup. It should not prompt for an administrator
   password — it installs per-user by default.
2. **Icon.** Check the Start-menu entry and the desktop shortcut show your icon
   rather than a generic one.
3. **It opens.** Launch it. The window appears and the status bar reports that
   no data has been imported.
4. **Branding loaded.** Open a Command Prompt in the install folder and run
   `401k-finder.exe status --branding`. Every asset you supplied should be
   listed with a path inside `_internal`.
5. **About dialog.** Help → About should show your logo.
6. **The real test — download a form year.** Open the Data tab, pick 2023, and
   click *Download and import*. This is the step that exercises everything at
   once: the network, the ZIP extraction, the bundled DOL layouts, the importer
   and the database. **If the layouts failed to package, this is where it
   breaks.** Let it finish.
7. **Search.** Search for a large employer. You should get plans, and selecting
   one should populate the Providers and Evidence tabs.
8. **Uninstall.** Remove it through Apps & features. It should offer to keep the
   downloaded data and default to keeping it.

### A faster check that downloads nothing

On the build machine, generate synthetic files first:

```powershell
python -m scripts.make_test_data --year 2023 --plans 48
```

Copy the `test_data` folder to the test machine, then use **Data → Import files
already on this computer**. This proves the layouts, importer and search all
survived packaging in under a minute — but it does not test the download, so do
step 6 at least once before a real release.

---

## 7. Sign it

Skip this if the application is only for you or a handful of colleagues. They
will see a blue *"Windows protected your PC"* warning and can continue via
**More info → Run anyway**.

For wider distribution, that warning will stop most people, and you need an
Authenticode certificate from a certificate authority such as DigiCert, Sectigo
or SSL.com. Expect a few hundred dollars a year and an identity check.

- An **EV** certificate clears SmartScreen immediately but lives on a hardware
  token, so signing must happen on a machine with that token attached.
- A standard **OV** certificate is cheaper but builds reputation gradually — the
  warning fades after enough people have installed it.

Sign both executables first, then the installer that wraps them:

```powershell
$signtool = "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
$timestamp = "http://timestamp.digicert.com"

& $signtool sign /fd SHA256 /td SHA256 /tr $timestamp /n "Your Company Name" `
    "dist\401K Finder Pro\401KFinderPro.exe" `
    "dist\401K Finder Pro\401k-finder.exe"

& $signtool sign /fd SHA256 /td SHA256 /tr $timestamp /n "Your Company Name" `
    "dist\installer\401KFinderPro-Setup-2.0.0.exe"
```

Always include `/tr` to timestamp the signature. Without it the signature stops
validating the day the certificate expires, instead of remaining valid for
whatever was signed while it was live.

---

## 8. Distribute it

Ship **`dist\installer\401KFinderPro-Setup-2.0.0.exe`** — one file.

Publish a checksum next to it so people can verify the download:

```powershell
Get-FileHash "dist\installer\401KFinderPro-Setup-2.0.0.exe" -Algorithm SHA256
```

### What to tell your users

> Run the installer and open **401K Finder Pro** from the Start menu.
>
> The application starts empty. Open the **Data** tab and download a form year
> from the Department of Labor — a few gigabytes, typically 15–60 minutes. You
> only do this once per year of data, and you can keep using the application
> while it runs.
>
> Everything stays on your computer. Nothing is uploaded.

Worth flagging to anyone on a managed corporate network: downloads go through
`HTTPS_PROXY` if it is set, and a TLS-inspecting proxy also needs the corporate
certificate in the Windows trust store.

---

## 9. Ship an update

1. Open `app\__init__.py` and raise `__version__`, for example from `"2.0.0"` to
   `"2.0.1"`. The build reads it from there and passes it to the installer, so
   they can never disagree.
2. Rebuild: `.\build.ps1 -Clean -Installer`
3. Sign, and distribute the new setup file.

Users run the new installer over the old one. Because the installer keeps a
fixed application ID, it upgrades in place: same folder, same shortcuts, one
entry in Apps & features. **Their downloaded data and database are untouched.**

If a release changes the database structure, the application migrates it on
first launch. Opening a database written by a *newer* build than the one
installed shows a clear message naming both versions rather than damaging it.

---

## 10. If something goes wrong

| What you see | What it means |
|---|---|
| **It stops at *Preparing the virtual environment* and sits there** | Not a crash — it is slow. Creating the environment writes several thousand small files, and both OneDrive sync and antivirus scanning make that crawl. **Give it 5 minutes before assuming it is stuck.** If your project is on the Desktop or in Documents, those are OneDrive-synced by default: move it to `C:\dev\401k-finder`, or run `.\build.ps1 -VenvPath C:\venvs\401k` to keep just the environment out of sync. Pressing Ctrl+C here produces a `KeyboardInterrupt` traceback ending in `stdout.read()`. |
| `Failed to create the virtual environment` | Same causes as above. Delete any half-built `.venv` folder before retrying. |
| `Python was not found` | Python is missing, or was installed without the PATH option. Re-run its installer, choose **Modify**, tick *Add python.exe to PATH*. |
| `build.ps1 cannot be loaded because running scripts is disabled` | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in the same window first. |
| `Python 3.14 found, but this project requires...` | Install 3.12 or 3.13 alongside it. |
| `Inno Setup 6 was not found` | Install it, or build without `-Installer`. |
| `No module named pytest` | An older `build.ps1` that installed only the runtime dependencies. Update to the current version — it installs `requirements-dev.txt`, which carries pytest and PyInstaller. |
| `Tests failed` | Something in the code is broken — the message names which test. Do not ship it. |
| The build stops at *Smoke-testing* | The packaged application could not read its data files. Rebuild with `-Clean`; if it persists, see the layouts section of [`WINDOWS_APPLICATION.md`](WINDOWS_APPLICATION.md). |
| Your icon does not appear | Windows caches icons aggressively. Sign out and back in, or run `ie4uinit.exe -show`. Confirm the file is there with `401k-finder.exe status --branding`. |
| The window opens then vanishes | Read `%LOCALAPPDATA%\401K Finder Pro\logs\application.log`. |
| The download fails on a work network | Set `HTTPS_PROXY` before launching, and make sure the corporate CA is trusted by Windows. |
| Antivirus flags the executable | Common for packaged Python applications. Signing resolves most cases; report a false positive at <https://www.microsoft.com/en-us/wdsi/filesubmission>. |

Logs are the first place to look for anything at runtime:

```
%LOCALAPPDATA%\401K Finder Pro\logs\application.log
```

Paste that path into the Explorer address bar to open it.

---

## Building without a Windows machine

You cannot build a Windows executable on macOS or Linux — the packaging tool
bundles the interpreter of whatever machine it runs on, so it needs Windows to
produce a `.exe`.

The practical options are a Windows virtual machine, or GitHub Actions, which
gives you a Windows build machine free for public repositories.
[`WINDOWS_APPLICATION.md`](WINDOWS_APPLICATION.md) contains a ready-to-use
workflow that builds the installer on every tagged release.

The application itself runs perfectly well from source on macOS and Linux — only
the packaged `.exe` needs Windows.

<#
.SYNOPSIS
    Builds 401K Finder Pro as a Windows application.

.DESCRIPTION
    Creates a virtual environment, installs dependencies, runs the test suite,
    and produces a standalone Windows application with PyInstaller. With
    -Installer it also builds a setup executable with Inno Setup.

.PARAMETER SkipTests
    Skip the test suite. Not recommended for a release build.

.PARAMETER Installer
    Also build the Inno Setup installer. Requires Inno Setup 6 on PATH,
    or installed in its default location.

.PARAMETER Clean
    Delete build/ and dist/ before building.

.PARAMETER VenvPath
    Where to create the build virtual environment. Defaults to .venv inside the
    project. Point this at a plain local folder when the project itself lives in
    OneDrive, Dropbox or a network drive -- creating a virtual environment
    inside a synced folder is extremely slow and often appears to hang.

.EXAMPLE
    .\build.ps1
    Builds dist\401K Finder Pro\401KFinderPro.exe

.EXAMPLE
    .\build.ps1 -Clean -Installer
    Full clean release build, ending with a setup executable.

.EXAMPLE
    .\build.ps1 -VenvPath C:\venvs\401k
    Keeps the virtual environment off a synced folder.
#>

[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$Installer,
    [switch]$Clean,
    [string]$VenvPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# PowerShell 7.3+ can turn a non-zero exit from a native command into a
# terminating error, which would pre-empt this script's own checks and report
# them less usefully. Exit codes are inspected explicitly throughout.
if (Test-Path Variable:\PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$ProjectRoot = $PSScriptRoot

# Only default the environment location when -VenvPath was not supplied.
if ([string]::IsNullOrWhiteSpace($VenvPath)) {
    $VenvPath = Join-Path $ProjectRoot '.venv'
}

$VenvPython  = Join-Path $VenvPath 'Scripts\python.exe'
$DistPath    = Join-Path $ProjectRoot 'dist'
$BuildPath   = Join-Path $ProjectRoot 'build'
$SpecFile    = Join-Path $ProjectRoot 'installer\401k-finder.spec'
$IssFile     = Join-Path $ProjectRoot 'installer\401k-finder.iss'

function Write-Step($Message) {
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok($Message) {
    Write-Host "    $Message" -ForegroundColor Green
}

function Get-AppVersion {
    $initFile = Join-Path $ProjectRoot 'app\__init__.py'
    $content  = Get-Content $initFile -Raw

    if ($content -match '__version__\s*=\s*"([^"]+)"') {
        return $Matches[1]
    }

    throw "Could not read __version__ from $initFile"
}

# ---------------------------------------------------------------------------

Write-Step 'Checking Python'

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    throw 'Python was not found on PATH. Install Python 3.11-3.13 from python.org and tick "Add python.exe to PATH".'
}

$versionRaw = & python -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
$versionText = ($versionRaw | Out-String).Trim()

if ([string]::IsNullOrWhiteSpace($versionText)) {
    throw @"
'python' was found on PATH but produced no version output.

This is almost always the Microsoft Store stub, which does nothing except open
the Store. Install Python from python.org, ticking "Add python.exe to PATH",
then disable the stub under
  Settings > Apps > Advanced app settings > App execution aliases
by switching off "python.exe" and "python3.exe".
"@
}

$version = [version]$versionText

if ($version -lt [version]'3.11' -or $version -ge [version]'3.14') {
    throw "Python $versionText found, but this project requires 3.11, 3.12 or 3.13."
}

Write-Ok "Python $versionText"

$AppVersion = Get-AppVersion
Write-Ok "Building version $AppVersion"

# ---------------------------------------------------------------------------

if ($Clean) {
    Write-Step 'Cleaning previous build output'

    foreach ($path in @($BuildPath, $DistPath)) {
        if (Test-Path $path) {
            try {
                Remove-Item $path -Recurse -Force
            }
            catch {
                throw @"
Could not delete $path

Something is holding a file open in there. The usual causes are a running
401KFinderPro.exe or 401k-finder.exe from a previous build, an Explorer window
sitting in that folder, or an antivirus scan still in progress.

Close them and try again.
"@
            }
            Write-Ok "Removed $path"
        }
    }
}

# ---------------------------------------------------------------------------

Write-Step 'Preparing the virtual environment'

# Creating a virtual environment writes several thousand small files. Two things
# on Windows make that pathologically slow, to the point where it looks frozen:
# a cloud-synced folder (OneDrive redirects Desktop and Documents by default),
# and real-time antivirus scanning each extracted file. Warn before it happens
# rather than leaving the user staring at a stationary cursor.
$SyncedRoots = @('OneDrive', 'Dropbox', 'Google Drive', 'Creative Cloud Files')
$MatchedSync = $SyncedRoots | Where-Object { $VenvPath -like "*\$_\*" } | Select-Object -First 1

if ($MatchedSync) {
    Write-Warning @"
The virtual environment would be created inside a $MatchedSync folder:
    $VenvPath

Cloud sync makes this extremely slow and it often looks like a hang. Either
move the project to a plain local folder such as C:\dev\401k-finder, or keep
just the environment out of sync:

    .\build.ps1 -VenvPath C:\venvs\401k
"@
}

if (-not (Test-Path $VenvPython)) {
    Write-Host '    Creating the environment. This normally takes 30-60 seconds,'
    Write-Host '    but can take several minutes behind antivirus or cloud sync.'
    Write-Host '    Press Ctrl+C only if nothing happens for more than 5 minutes.'

    & python -m venv $VenvPath

    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) {
        throw @"
Failed to create the virtual environment at $VenvPath.

The usual causes, in order of likelihood:
  * The project is in a OneDrive or Dropbox folder. Move it to C:\dev\, or
    pass -VenvPath C:\venvs\401k to keep the environment out of sync.
  * Antivirus is scanning every extracted file. Add an exclusion for the
    project folder, or try again -- the second run is usually faster.
  * A previous attempt left a half-built .venv behind. Delete it and re-run.
"@
    }

    Write-Ok "Created $VenvPath"
} else {
    Write-Ok "Reusing the existing environment at $VenvPath"
}

& $VenvPython -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { throw 'Failed to upgrade pip.' }

Write-Step 'Installing dependencies'

$Requirements    = Join-Path $ProjectRoot 'requirements.txt'
$DevRequirements = Join-Path $ProjectRoot 'requirements-dev.txt'

& $VenvPython -m pip install -r $Requirements --quiet
if ($LASTEXITCODE -ne 0) { throw 'Failed to install the runtime dependencies.' }

# requirements.txt holds only what the application needs at runtime. The build
# additionally needs PyInstaller, and the test suite needs pytest -- both live
# in requirements-dev.txt, which itself includes requirements.txt.
if (Test-Path $DevRequirements) {
    & $VenvPython -m pip install -r $DevRequirements --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install the build and test dependencies.' }
} else {
    & $VenvPython -m pip install pyinstaller pytest --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install PyInstaller and pytest.' }
}

# Confirm the tools this script is about to invoke are actually importable,
# so a missing one is reported here rather than as a bare "No module named X"
# from a later step.
$RequiredModules = @('PySide6', 'sqlalchemy', 'PyInstaller')
if (-not $SkipTests) { $RequiredModules += 'pytest' }

foreach ($module in $RequiredModules) {
    & $VenvPython -c "import $module" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw @"
'$module' is missing from the build environment at $VenvPath.

Try deleting that folder and re-running, which forces a clean install. If it
persists, install it directly to see the real error:

    & '$VenvPython' -m pip install $module
"@
    }
}

Write-Ok "Dependencies installed ($($RequiredModules -join ', ') verified)"

# ---------------------------------------------------------------------------

if (-not $SkipTests) {
    Write-Step 'Running the test suite'

    # Run from the project root: the project is not pip-installed into the
    # environment, so `import app` resolves through the working directory.
    $testsFailed = $false

    Push-Location $ProjectRoot
    try {
        & $VenvPython -m pytest 'tests' -q
        $testsFailed = $LASTEXITCODE -ne 0
    }
    finally {
        Pop-Location
    }

    if ($testsFailed) {
        throw 'Tests failed. Fix them, or pass -SkipTests to build anyway.'
    }

    Write-Ok 'All tests passed'
} else {
    Write-Warning 'Skipping tests (-SkipTests)'
}

# ---------------------------------------------------------------------------

Write-Step 'Verifying the vendored DOL layouts in the source tree'

# The layouts are loaded through importlib.resources, so a build that drops
# them starts fine and then fails on the first search. Check before packaging.
#
# The project is not pip-installed into the venv, only its dependencies are, so
# `import app` resolves via the current directory — which is not necessarily
# where this script lives when it is invoked by absolute path.
Push-Location $ProjectRoot
try {
    $layoutCheck = & $VenvPython -c "from app.dol.layouts import available_years; print(len(available_years()))"
    if ($LASTEXITCODE -ne 0) { throw 'Could not load the vendored DOL layouts.' }
}
finally {
    Pop-Location
}

# Out-String collapses the result whether Python emitted one line or several.
$layoutYears = ($layoutCheck | Out-String).Trim()
Write-Ok "$layoutYears form year(s) of DOL layouts available in the source tree"

# ---------------------------------------------------------------------------

Write-Step 'Checking the licence configuration'

# A release built with licensing switched off gives itself away, and the
# mistake is invisible until someone notices nobody is being asked for a key.
Push-Location $ProjectRoot
try {
    $licenseMode = & $VenvPython -c "from app.licensing.config import get_config; c = get_config(); print('enforced' if c.enforced else 'open')"
    if ($LASTEXITCODE -ne 0) { throw 'Could not read the licence configuration.' }
}
finally {
    Pop-Location
}

if (($licenseMode | Out-String).Trim() -eq 'enforced') {
    Write-Ok 'Licensing is configured; this build will require activation'
} else {
    Write-Warning @"
This build does NOT require a licence key.

That is correct for development and for builds you give away. If you intend to
sell this one, create a signing keypair and paste the public key into
app\licensing\config.py first:

    python -m scripts.issue_license --new-keypair

-- see docs\SELLING.md, section 3.
"@
}

# ---------------------------------------------------------------------------

Write-Step 'Building the application with PyInstaller'

Push-Location $ProjectRoot
try {
    & $VenvPython -m PyInstaller $SpecFile --noconfirm --clean
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
}
finally {
    Pop-Location
}

$AppDir = Join-Path $DistPath '401K Finder Pro'
$AppExe = Join-Path $AppDir '401KFinderPro.exe'
$CliExe = Join-Path $AppDir '401k-finder.exe'

foreach ($required in @($AppExe, $CliExe)) {
    if (-not (Test-Path $required)) {
        throw "PyInstaller reported success but $required is missing."
    }
}

# -File matters: directories have no Length, and asking for it raises an error
# that ErrorActionPreference=Stop would turn into an aborted build.
$sizeMb = [math]::Round(
    (Get-ChildItem $AppDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Ok "Built $AppExe ($sizeMb MB)"
Write-Ok "Built $CliExe"

# ---------------------------------------------------------------------------

Write-Step 'Smoke-testing the packaged application'

# This has to exercise the BUILT application, not the source tree. Running the
# check against the venv would pass even if PyInstaller dropped every layout
# file, which is precisely the failure it is supposed to catch.
$LayoutDir = Join-Path $AppDir '_internal\app\dol\layouts\data'
if (-not (Test-Path $LayoutDir)) {
    throw "The vendored DOL layouts are missing from the build ($LayoutDir). Check the 'datas' entry in the spec file."
}

$LayoutCount = (Get-ChildItem $LayoutDir -Filter '*.json' | Measure-Object).Count
if ($LayoutCount -lt 1) {
    throw "No layout files were packaged into $LayoutDir."
}
Write-Ok "$LayoutCount form year(s) of layouts packaged"

# Run the packaged CLI against a throwaway data directory. This starts the
# frozen executable, loads the layouts through importlib.resources exactly as
# the shipped application does, and creates a database.
$CheckDir = Join-Path $env:TEMP '401k-finder-buildcheck'
if (Test-Path $CheckDir) { Remove-Item $CheckDir -Recurse -Force }

$env:FINDER_401K_DATA_DIR = $CheckDir
try {
    $datasets = & $CliExe datasets --year 2023
    if ($LASTEXITCODE -ne 0) { throw 'The packaged CLI failed to read the vendored layouts.' }

    & $CliExe init | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'The packaged CLI failed to create a database.' }

    # $datasets is an array of output lines. Applying -notmatch to an array
    # filters it rather than returning a boolean, and the filtered result is
    # truthy whenever any single line lacks the text -- so join it first.
    if (($datasets -join "`n") -notmatch 'F_5500') {
        throw 'The packaged CLI did not report the expected datasets for 2023.'
    }

    Write-Ok 'Packaged application starts, reads its layouts and creates a database'
}
finally {
    Remove-Item Env:\FINDER_401K_DATA_DIR -ErrorAction SilentlyContinue
    if (Test-Path $CheckDir) { Remove-Item $CheckDir -Recurse -Force -ErrorAction SilentlyContinue }
}

# ---------------------------------------------------------------------------

if ($Installer) {
    Write-Step 'Building the installer with Inno Setup'

    $iscc = Get-Command iscc -ErrorAction SilentlyContinue

    if (-not $iscc) {
        $candidates = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
        )
        $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

        if (-not $found) {
            throw 'Inno Setup 6 was not found. Install it from https://jrsoftware.org/isdl.php, or omit -Installer.'
        }

        $isccPath = $found
    } else {
        $isccPath = $iscc.Source
    }

    & $isccPath "/DAppVersion=$AppVersion" $IssFile
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed.' }

    $setupExe = Join-Path $DistPath "installer\401KFinderPro-Setup-$AppVersion.exe"
    if (-not (Test-Path $setupExe)) {
        throw "Inno Setup reported success but $setupExe is missing."
    }

    $setupMb = [math]::Round((Get-Item $setupExe).Length / 1MB, 1)
    Write-Ok "Built $setupExe ($setupMb MB)"
}

# ---------------------------------------------------------------------------

Write-Step 'Done'
Write-Host ''
Write-Host "  Application: $AppExe"
if ($Installer) {
    Write-Host "  Installer:   $setupExe"
}
Write-Host ''
Write-Host '  The application starts with an empty database. Open the Data tab'
Write-Host '  and download a form year to begin.'
Write-Host ''

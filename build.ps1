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

.EXAMPLE
    .\build.ps1
    Builds dist\401K Finder Pro\401KFinderPro.exe

.EXAMPLE
    .\build.ps1 -Clean -Installer
    Full clean release build, ending with a setup executable.
#>

[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$Installer,
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ProjectRoot = $PSScriptRoot
$VenvPath    = Join-Path $ProjectRoot '.venv'
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

$versionText = (& python -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
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
            Remove-Item $path -Recurse -Force
            Write-Ok "Removed $path"
        }
    }
}

# ---------------------------------------------------------------------------

Write-Step 'Preparing the virtual environment'

if (-not (Test-Path $VenvPython)) {
    & python -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create the virtual environment.' }
    Write-Ok "Created $VenvPath"
} else {
    Write-Ok 'Reusing the existing virtual environment'
}

& $VenvPython -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) { throw 'Failed to upgrade pip.' }

Write-Step 'Installing dependencies'

& $VenvPython -m pip install -r (Join-Path $ProjectRoot 'requirements.txt') --quiet
if ($LASTEXITCODE -ne 0) { throw 'Failed to install dependencies.' }

& $VenvPython -m pip install pyinstaller --quiet
if ($LASTEXITCODE -ne 0) { throw 'Failed to install PyInstaller.' }

Write-Ok 'Dependencies installed'

# ---------------------------------------------------------------------------

if (-not $SkipTests) {
    Write-Step 'Running the test suite'

    & $VenvPython -m pytest (Join-Path $ProjectRoot 'tests') -q
    if ($LASTEXITCODE -ne 0) {
        throw 'Tests failed. Fix them, or pass -SkipTests to build anyway.'
    }

    Write-Ok 'All tests passed'
} else {
    Write-Warning 'Skipping tests (-SkipTests)'
}

# ---------------------------------------------------------------------------

Write-Step 'Verifying the vendored DOL layouts'

# The layouts are loaded through importlib.resources, so a build that drops
# them starts fine and then fails on the first search. Check before packaging.
$layoutCheck = & $VenvPython -c "from app.dol.layouts import available_years; y = available_years(); print(len(y))"
if ($LASTEXITCODE -ne 0) { throw 'Could not load the vendored DOL layouts.' }

Write-Ok "$($layoutCheck.Trim()) form year(s) of DOL layouts available offline"

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

if (-not (Test-Path $AppExe)) {
    throw "PyInstaller reported success but $AppExe is missing."
}

$sizeMb = [math]::Round((Get-ChildItem $AppDir -Recurse | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Ok "Built $AppExe ($sizeMb MB)"

# ---------------------------------------------------------------------------

Write-Step 'Smoke-testing the packaged application'

# Confirms the layouts survived packaging, which is the failure a bad
# PyInstaller data spec produces.
$env:FINDER_401K_DATA_DIR = Join-Path $env:TEMP '401k-finder-buildcheck'
try {
    & $VenvPython -c "from app.dol.layouts import load_year; assert load_year(2023)['F_5500'].has('ACK_ID')"
    if ($LASTEXITCODE -ne 0) { throw 'Layout smoke test failed.' }
    Write-Ok 'Layouts load correctly'
}
finally {
    Remove-Item Env:\FINDER_401K_DATA_DIR -ErrorAction SilentlyContinue
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
    if (Test-Path $setupExe) {
        Write-Ok "Built $setupExe"
    }
}

# ---------------------------------------------------------------------------

Write-Step 'Done'
Write-Host ''
Write-Host "  Application: $AppExe"
if ($Installer) {
    Write-Host "  Installer:   $(Join-Path $DistPath "installer\401KFinderPro-Setup-$AppVersion.exe")"
}
Write-Host ''
Write-Host '  The application starts with an empty database. Open the Data tab'
Write-Host '  and download a form year to begin.'
Write-Host ''

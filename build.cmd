@echo off
REM  Build 401K Finder Pro without arguing with PowerShell's execution policy.
REM
REM  A .cmd file is not subject to that policy, so this runs build.ps1 through
REM  PowerShell with the policy bypassed for this one invocation. Nothing on the
REM  machine is changed, and no Set-ExecutionPolicy is needed.
REM
REM      build.cmd
REM      build.cmd -Clean -Installer
REM      build.cmd -Clean -Installer -VenvPath C:\venvs\401k
REM
REM  Every argument is passed straight through to build.ps1.

setlocal

REM  Detect a double-click: cmd.exe puts this file's name on its own command
REM  line only when it was launched that way, not when it was typed at a prompt.
set _INTERACTIVE=1
echo "%CMDCMDLINE%" | find /i "%~nx0" >nul 2>&1 && set _INTERACTIVE=0

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
set _EXIT=%ERRORLEVEL%

if not "%_EXIT%"=="0" (
    echo.
    echo Build failed with exit code %_EXIT%.
)

REM  Hold the window open when double-clicked, so the message is readable
REM  instead of vanishing with the console.
if "%_INTERACTIVE%"=="0" pause

exit /b %_EXIT%

# UI resources

Optional assets for the desktop application. The build works without any of
them — this folder exists so a fresh clone has somewhere to put them.

## `app.ico`

The Windows application icon. Drop a multi-resolution `.ico` here (16, 32, 48,
64, 128 and 256 px) and it is picked up automatically by
`installer/401k-finder.spec` for both executables, and by Inno Setup for its
shortcuts. Without it, PyInstaller uses its own default icon.

## `app.qss`

An optional Qt style sheet. If present it is packaged alongside the executable.
The application currently uses the platform's native styling.

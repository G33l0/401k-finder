# UI resources

Optional branding assets. **This folder is empty by design** — the application
builds and runs using Qt's default icon when nothing is here.

Drop your own files in and they are picked up automatically, by both the source
checkout and the packaged Windows build.

| File | Used for |
|---|---|
| `app.ico` | The `.exe` icon, installer and Start-menu shortcuts (Windows) |
| `logo.png` | The About dialog, and the window icon on macOS and Linux |
| `app.png` | Optional window-icon fallback where `.ico` cannot be read |
| `app.qss` | Optional [Qt style sheet](https://doc.qt.io/qt-6/stylesheet-syntax.html) |

**Full specifications — required icon sizes, colour depth, how to produce an
`.ico` from a PNG — are in [`docs/DEPLOY.md`](../../../docs/DEPLOY.md), section 4.**

To check what a build resolved:

```bash
401k-finder status --branding
```

Anything reported as `not set` was not found. A corrupt icon is also reported as
`not set` rather than being used, because Windows draws a broken icon as a blank
square with no error.

# UI resources

The application mark and the optional branding overrides.

`app.ico`, `app.png`, `logo.png` and `logo.svg` are **generated, not
hand-drawn**. Edit the geometry in [`scripts/make_logo.py`](../../../scripts/make_logo.py)
and regenerate — an image edited here directly is overwritten the next time
anyone runs the script, and a test checks the two agree.

```bash
python -m scripts.make_logo            # rewrite the assets
python -m scripts.make_logo --preview  # ...and a contact sheet of every size
```

| File | Used for |
|---|---|
| `app.ico` | The `.exe` icon, installer and Start-menu shortcuts (Windows) |
| `logo.png` | The About dialog, and the window icon on macOS and Linux |
| `app.png` | Window-icon fallback where `.ico` cannot be read |
| `logo.svg` | Vector original, for the web, the store page and print |
| `app.qss` | Optional [Qt style sheet](https://doc.qt.io/qt-6/stylesheet-syntax.html), appended after the active theme |

Every file here is optional. Delete them all and the application still builds
and runs, using Qt's default icon — which is what the accessors are written to
tolerate, and what the tests check.

## Replacing the mark with your own

Drop your files in with the names above; they are picked up automatically by
both the source checkout and the packaged Windows build. **Full specifications
— required icon sizes, colour depth, how to produce an `.ico` from a PNG — are
in [`docs/DEPLOY.md`](../../../docs/DEPLOY.md), section 4.**

If you replace them by hand rather than by editing the generator, delete
`test_the_mark_is_reproducible_from_its_source` in `tests/test_resources.py`;
it exists to catch the assets and the script drifting apart, and it cannot tell
that apart from a deliberate replacement.

## Colours, not branding

The three colour schemes live in [`app/ui/theme.py`](../theme.py), not here.
`app.qss` is layered *after* whichever theme is active, so rules in it win — use
it for small adjustments, and edit the theme module for anything structural.

## Checking what a build resolved

```bash
401k-finder status --branding
```

Anything reported as `not set` was not found. A corrupt icon is also reported as
`not set` rather than being used, because Windows draws a broken icon as a blank
square with no error.

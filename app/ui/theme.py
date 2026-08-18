"""The three colour schemes, and the machinery for applying one."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_THEME = "light"

WIDGET_STYLE = "Fusion"


@dataclass(frozen=True, slots=True)
class Palette:
    """One theme, in semantic roles rather than colour names."""

    key: str
    label: str

    dark: bool

    window: str  #: The application background.
    surface: str  #: Input fields, tables, text panes.
    surface_alt: str
    border: str
    border_strong: str  #: Focus rings and header rules.

    text: str
    text_muted: str  #: Secondary labels, table key columns.
    text_faint: str  #: Citations and source lines.

    accent: str  #: Headings, roles, links, the brand blue.
    accent_hover: str
    accent_soft: str  #: Tag and badge backgrounds.
    on_accent: str  #: Text drawn on top of ``accent``.

    selection: str
    on_selection: str

    high: str  #: Confidence ratings.
    medium: str
    low: str

    danger: str
    success: str

    font_family: str
    mono_family: str

    @property
    def ui_font(self) -> str:
        return self.font_family


_SANS = "'Segoe UI', 'Inter', system-ui, -apple-system, 'Noto Sans', sans-serif"
_MONO = "'Cascadia Mono', 'JetBrains Mono', Consolas, 'DejaVu Sans Mono', monospace"


LIGHT = Palette(
    key="light",
    label="Light",
    dark=False,
    window="#F2F4F7",
    surface="#FFFFFF",
    surface_alt="#FBFCFD",
    border="#D6DDE5",
    border_strong="#B7C2CE",
    text="#1B1F24",
    text_muted="#555B63",
    text_faint="#767D86",
    accent="#1A4F8A",
    accent_hover="#15406F",
    accent_soft="#EAF1F8",
    on_accent="#FFFFFF",
    selection="#CFE3F7",
    on_selection="#0F2A47",
    high="#1A7F37",
    medium="#9A6700",
    low="#8A9099",
    danger="#B3261E",
    success="#1A7F37",
    font_family=_SANS,
    mono_family=_MONO,
)


DARK = Palette(
    key="dark",
    label="Dark",
    dark=True,
    window="#1A1D22",
    surface="#22262D",
    surface_alt="#282D35",
    border="#363C46",
    border_strong="#4A515D",
    text="#E4E7EC",
    text_muted="#A2A9B5",
    text_faint="#7B828E",
    accent="#63ADF2",
    accent_hover="#8AC4FF",
    accent_soft="#233648",
    on_accent="#0E1A24",
    selection="#2E5B87",
    on_selection="#F0F5FA",
    high="#4ADE80",
    medium="#FBBF24",
    low="#8A929E",
    danger="#F87171",
    success="#4ADE80",
    font_family=_SANS,
    mono_family=_MONO,
)


HACKER = Palette(
    key="hacker",
    label="Hacker",
    dark=True,
    window="#070A08",
    surface="#0C120E",
    surface_alt="#111A14",
    border="#1E3A28",
    border_strong="#2F5C3E",
    text="#9CF0BC",
    text_muted="#5FBF86",
    text_faint="#438A61",
    accent="#39FF8A",
    accent_hover="#7BFFB6",
    accent_soft="#123020",
    on_accent="#04160C",
    selection="#16452B",
    on_selection="#C6FFDD",
    high="#39FF8A",
    medium="#FFC940",
    low="#4E8F63",
    danger="#FF6B6B",
    success="#39FF8A",
    font_family=_MONO,
    mono_family=_MONO,
)


THEMES: dict[str, Palette] = {theme.key: theme for theme in (LIGHT, DARK, HACKER)}

_current: Palette = THEMES[DEFAULT_THEME]

_overlay: str = ""


def set_overlay(css: str) -> None:
    """Register extra style sheet rules to append after every theme."""

    global _overlay
    _overlay = css or ""


def available() -> list[Palette]:
    """The themes, in menu order."""

    return list(THEMES.values())


def resolve(name: str | None) -> Palette:
    """Look up a theme, falling back to the default for anything unknown."""

    return THEMES.get((name or "").strip().lower(), THEMES[DEFAULT_THEME])


def current() -> Palette:
    return _current


def qt_palette(palette: Palette):  # -> QPalette
    """Build the QPalette."""

    from PySide6.QtGui import QColor
    from PySide6.QtGui import QPalette as QtPalette

    built = QtPalette()

    def paint(role, colour: str, *groups) -> None:
        value = QColor(colour)
        if groups:
            for group in groups:
                built.setColor(group, role, value)
        else:
            built.setColor(role, value)

    paint(QtPalette.Window, palette.window)
    paint(QtPalette.WindowText, palette.text)
    paint(QtPalette.Base, palette.surface)
    paint(QtPalette.AlternateBase, palette.surface_alt)
    paint(QtPalette.Text, palette.text)
    paint(QtPalette.PlaceholderText, palette.text_faint)
    paint(QtPalette.Button, palette.surface_alt)
    paint(QtPalette.ButtonText, palette.text)
    paint(QtPalette.BrightText, palette.danger)
    paint(QtPalette.ToolTipBase, palette.surface_alt)
    paint(QtPalette.ToolTipText, palette.text)
    paint(QtPalette.Highlight, palette.selection)
    paint(QtPalette.HighlightedText, palette.on_selection)
    paint(QtPalette.Link, palette.accent)
    paint(QtPalette.LinkVisited, palette.accent_hover)

    for role, colour in (
        (QtPalette.WindowText, palette.text_faint),
        (QtPalette.Text, palette.text_faint),
        (QtPalette.ButtonText, palette.text_faint),
    ):
        paint(role, colour, QtPalette.Disabled)

    return built


def stylesheet(palette: Palette) -> str:
    """The application-wide Qt style sheet for a theme."""

    p = palette

    return f"""
* {{
    font-family: {p.font_family};
}}

QWidget {{
    background: {p.window};
    color: {p.text};
    font-size: 10pt;
}}

QMainWindow, QDialog {{
    background: {p.window};
}}

/* --- Menus ------------------------------------------------------- */

QMenuBar {{
    background: {p.window};
    color: {p.text};
    border-bottom: 1px solid {p.border};
}}
QMenuBar::item {{
    background: transparent;
    padding: 5px 10px;
}}
QMenuBar::item:selected {{
    background: {p.selection};
    color: {p.on_selection};
}}
QMenu {{
    background: {p.surface};
    color: {p.text};
    border: 1px solid {p.border};
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 26px 5px 22px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background: {p.selection};
    color: {p.on_selection};
}}
QMenu::separator {{
    height: 1px;
    background: {p.border};
    margin: 4px 8px;
}}

/* --- Tabs -------------------------------------------------------- */

QTabWidget::pane {{
    background: {p.surface};
    border: 1px solid {p.border};
    top: -1px;
}}
QTabBar::tab {{
    background: {p.window};
    color: {p.text_muted};
    border: 1px solid {p.border};
    border-bottom: none;
    padding: 6px 16px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {p.surface};
    color: {p.accent};
    font-weight: bold;
}}
QTabBar::tab:hover:!selected {{
    color: {p.text};
}}

/* --- Inputs ------------------------------------------------------ */

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QDateEdit {{
    background: {p.surface};
    color: {p.text};
    border: 1px solid {p.border};
    border-radius: 3px;
    padding: 4px 6px;
    selection-background-color: {p.selection};
    selection-color: {p.on_selection};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{
    border-color: {p.accent};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
    background: {p.window};
    color: {p.text_faint};
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox QAbstractItemView {{
    background: {p.surface};
    color: {p.text};
    border: 1px solid {p.border};
    selection-background-color: {p.selection};
    selection-color: {p.on_selection};
}}
/* The indicators are deliberately left alone. Styling ::indicator replaces
   Fusion's drawing wholesale, including the check mark, which left a solid
   accent square that gave no clue whether it meant on or off. Fusion draws
   them correctly from the palette. */
QCheckBox, QRadioButton, QLabel {{
    background: transparent;
    color: {p.text};
}}

/* --- Buttons ----------------------------------------------------- */

QPushButton {{
    background: {p.surface_alt};
    color: {p.text};
    border: 1px solid {p.border_strong};
    border-radius: 3px;
    padding: 5px 14px;
}}
QPushButton:hover {{
    border-color: {p.accent};
    color: {p.accent};
}}
QPushButton:pressed {{
    background: {p.selection};
    color: {p.on_selection};
}}
QPushButton:default {{
    background: {p.accent};
    color: {p.on_accent};
    border-color: {p.accent};
}}
QPushButton:default:hover {{
    background: {p.accent_hover};
}}
QPushButton:disabled {{
    color: {p.text_faint};
    border-color: {p.border};
    background: {p.window};
}}

/* --- Tables ------------------------------------------------------ */

QTableView, QTreeView, QListView {{
    background: {p.surface};
    alternate-background-color: {p.surface_alt};
    color: {p.text};
    border: 1px solid {p.border};
    gridline-color: {p.border};
    selection-background-color: {p.selection};
    selection-color: {p.on_selection};
}}
QHeaderView::section {{
    background: {p.surface_alt};
    color: {p.text_muted};
    border: none;
    border-right: 1px solid {p.border};
    border-bottom: 1px solid {p.border_strong};
    padding: 5px 8px;
    font-weight: bold;
}}
QTableCornerButton::section {{
    background: {p.surface_alt};
    border: none;
}}

/* --- Text panes -------------------------------------------------- */

QTextBrowser, QTextEdit {{
    background: {p.surface};
    color: {p.text};
    border: 1px solid {p.border};
    selection-background-color: {p.selection};
    selection-color: {p.on_selection};
}}

/* --- Chrome ------------------------------------------------------ */

QGroupBox {{
    border: 1px solid {p.border};
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 9px;
    padding: 0 4px;
    color: {p.accent};
    font-weight: bold;
}}
QStatusBar {{
    background: {p.window};
    color: {p.text_muted};
    border-top: 1px solid {p.border};
}}
QStatusBar::item {{
    border: none;
}}
QProgressBar {{
    background: {p.surface_alt};
    border: 1px solid {p.border};
    border-radius: 3px;
    text-align: center;
    color: {p.text};
}}
QProgressBar::chunk {{
    background: {p.accent};
    border-radius: 2px;
}}
QSplitter::handle {{
    background: {p.border};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QToolTip {{
    background: {p.surface_alt};
    color: {p.text};
    border: 1px solid {p.border_strong};
    padding: 4px 6px;
}}

/* --- Scroll bars ------------------------------------------------- */

QScrollBar:vertical, QScrollBar:horizontal {{
    background: {p.window};
    border: none;
}}
QScrollBar:vertical {{ width: 11px; }}
QScrollBar:horizontal {{ height: 11px; }}
QScrollBar::handle {{
    background: {p.border_strong};
    border-radius: 5px;
    min-width: 24px;
    min-height: 24px;
}}
QScrollBar::handle:hover {{
    background: {p.accent};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

/* --- Secondary labels -------------------------------------------
   Set with widget.setProperty("role", "muted"). Re-applying the style
   sheet re-polishes every widget, so these follow a theme change. */

QLabel[role="muted"] {{
    color: {p.text_muted};
}}
QLabel[role="faint"] {{
    color: {p.text_faint};
}}
"""


def document_css(palette: Palette) -> str:
    """The ``<style>`` block for the rich-text detail panels."""

    p = palette

    return (
        "<style>"
        f"body{{font-family:{p.font_family};font-size:10pt;color:{p.text};}}"
        f"h2{{margin:0 0 4px 0;font-size:14pt;color:{p.text};}}"
        f"h3{{margin:16px 0 6px 0;font-size:11pt;color:{p.accent};"
        f"border-bottom:1px solid {p.border};padding-bottom:3px;}}"
        "table{border-collapse:collapse;width:100%;margin:4px 0;}"
        "td{padding:3px 8px 3px 0;vertical-align:top;}"
        f"td.k{{color:{p.text_muted};width:170px;}}"
        f"a{{color:{p.accent};}}"
        f"p.sub,.sub{{color:{p.text_muted};margin:0 0 10px 0;}}"
        f".tag{{background:{p.accent_soft};color:{p.accent};padding:1px 7px;"
        "font-size:9pt;}"
        f".role{{font-weight:bold;color:{p.accent};}}"
        f".src{{color:{p.text_faint};font-size:9pt;}}"
        f".hi{{color:{p.high};font-weight:bold;}}"
        f".med{{color:{p.medium};}}"
        f".low{{color:{p.low};}}"
        f"table.card{{width:100%;margin:8px 0;background:{p.surface_alt};"
        f"border:1px solid {p.border};}}"
        "table.card td{padding:8px 11px;}"
        f".empty{{padding:24px;color:{p.text_muted};}}"
        "</style>"
    )


def apply(app, name: str | None) -> Palette:
    """Apply a theme to a running QApplication and return the palette used."""

    global _current

    palette = resolve(name)
    _current = palette

    app.setStyle(WIDGET_STYLE)
    app.setPalette(qt_palette(palette))
    app.setStyleSheet(stylesheet(palette) + ("\n" + _overlay if _overlay else ""))

    return palette

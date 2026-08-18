"""The colour schemes."""

from __future__ import annotations

import re

import pytest

from app.core.config import Settings
from app.ui import theme

HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b")


@pytest.fixture(params=[palette.key for palette in theme.available()])
def palette(request) -> theme.Palette:
    """Runs each test against every scheme."""

    return theme.THEMES[request.param]


def test_the_advertised_themes_exist():
    assert [p.key for p in theme.available()] == [
        "light",
        "sepia",
        "dark",
        "midnight",
        "amber",
        "hacker",
        "contrast",
    ]


def test_the_menu_runs_light_to_dark():
    """Two light schemes first, then the darks. A jumbled menu reads as a bug."""

    flags = [p.dark for p in theme.available()]
    assert flags == sorted(flags), "light schemes must come before dark ones"
    assert flags.count(False) == 2


def test_each_scheme_declares_its_own_brightness():
    """A palette that lies about `dark` gets the wrong Qt icon set."""

    for palette in theme.available():
        assert palette.dark is (_luminance(palette.window) < 0.5), palette.key


@pytest.mark.parametrize(
    "stored", ["", "  ", None, "Dark", "HACKER", "solarized", "light ", "../../etc"]
)
def test_any_stored_value_resolves_to_a_real_theme(stored):
    assert theme.resolve(stored) in theme.available()


def test_case_and_padding_are_tolerated():
    assert theme.resolve("  DaRk  ") is theme.DARK


def test_unknown_names_fall_back_to_the_default():
    assert theme.resolve("nonsense") is theme.THEMES[theme.DEFAULT_THEME]


def test_the_default_setting_names_a_real_theme():
    """The dataclass default and the theme module must not drift apart."""

    assert theme.resolve(Settings().theme).key == Settings().theme


def test_settings_round_trip_a_theme(tmp_path):
    path = tmp_path / "settings.json"
    Settings(theme="hacker").save(path)

    assert Settings.load(path).theme == "hacker"


def test_every_palette_role_is_filled(palette):
    for name in theme.Palette.__slots__:
        value = getattr(palette, name)
        assert value not in (None, ""), f"{palette.key}.{name} is empty"


def test_style_sheet_carries_no_colour_the_palette_did_not_supply(palette):
    """Guards against a colour being pasted straight into the style sheet."""

    allowed = {
        getattr(palette, name).upper()
        for name in theme.Palette.__slots__
        if isinstance(getattr(palette, name), str) and getattr(palette, name).startswith("#")
    }

    for found in HEX.findall(theme.stylesheet(palette)):
        assert found.upper() in allowed, f"{found} is not a {palette.key} palette colour"


def test_document_css_carries_no_colour_the_palette_did_not_supply(palette):
    allowed = {
        getattr(palette, name).upper()
        for name in theme.Palette.__slots__
        if isinstance(getattr(palette, name), str) and getattr(palette, name).startswith("#")
    }

    for found in HEX.findall(theme.document_css(palette)):
        assert found.upper() in allowed, f"{found} is not a {palette.key} palette colour"


def test_schemes_actually_differ(palette):
    others = [other for other in theme.available() if other.key != palette.key]
    for other in others:
        assert theme.stylesheet(palette) != theme.stylesheet(other)
        assert theme.document_css(palette) != theme.document_css(other)


def test_document_css_styles_every_class_the_detail_panel_emits(palette):
    """The detail panel's HTML and this CSS have to agree."""

    css = theme.document_css(palette)
    for name in ("tag", "role", "src", "hi", "med", "low", "card", "empty", "sub"):
        assert f".{name}{{" in css or f".{name}," in css, f"{name} is unstyled"


def test_cards_are_tables_not_divs(palette):
    """
    Qt's rich-text engine paints a div's background behind its first line only,
    which left cards as a stripe with their contents hanging underneath.
    """

    assert "table.card{" in theme.document_css(palette)


def test_detail_panel_holds_no_colours_of_its_own():
    """The panel must take every colour from the theme, not from its markup."""

    from pathlib import Path

    source = Path(theme.__file__).parent / "widgets" / "plan_detail.py"
    assert not HEX.findall(source.read_text(encoding="utf-8"))


def test_overlay_defaults_to_empty():
    theme.set_overlay(None)
    assert theme._overlay == ""


@pytest.fixture(scope="module")
def qt_app():
    """An offscreen QApplication, or a skip when Qt cannot start."""

    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication

    application = QApplication.instance() or QApplication([])
    yield application


def test_apply_switches_scheme_and_reports_it(qt_app):
    for key in ("dark", "hacker", "light"):
        assert theme.apply(qt_app, key).key == key
        assert theme.current().key == key


class RecordingApp:
    """Stands in for QApplication, to see what apply() actually asks for."""

    def __init__(self) -> None:
        self.style_name: str | None = None
        self.palette = None
        self.sheet = ""

    def setStyle(self, name):  # noqa: N802 - matching Qt's spelling
        self.style_name = name

    def setPalette(self, palette):  # noqa: N802
        self.palette = palette

    def setStyleSheet(self, sheet):  # noqa: N802
        self.sheet = sheet


def test_apply_forces_fusion(qt_app):
    """
    The native Windows style ignores a custom palette, so without this a dark theme
    comes out with light chrome around it.
    """

    recorder = RecordingApp()
    theme.apply(recorder, "dark")

    assert recorder.style_name == theme.WIDGET_STYLE == "Fusion"
    assert recorder.palette is not None
    assert recorder.sheet


def test_apply_paints_the_qt_palette(qt_app):
    from PySide6.QtGui import QColor, QPalette

    for key in ("light", "dark", "hacker"):
        palette = theme.apply(qt_app, key)
        assert qt_app.palette().color(QPalette.Window) == QColor(palette.window)
        assert qt_app.palette().color(QPalette.Base) == QColor(palette.surface)


def test_overlay_survives_a_theme_change(qt_app):
    """
    A deployment's own app.qss is appended after the theme's rules. Applying a
    theme replaces the whole style sheet, so the overlay has to be re-applied
    each time rather than set once at start-up.
    """

    theme.set_overlay("QStatusBar { qproperty-objectName: overlayMarker; }")
    try:
        for key in ("light", "dark", "hacker"):
            theme.apply(qt_app, key)
            assert "overlayMarker" in qt_app.styleSheet(), f"overlay lost switching to {key}"
    finally:
        theme.set_overlay("")
        theme.apply(qt_app, theme.DEFAULT_THEME)


def test_the_window_applies_its_stored_theme_when_built_directly(qt_app, tmp_path):
    """
    Constructed outside app.main there is nothing else to apply the theme, so the window
    would show a stored scheme in the menu while being painted in the default one.
    """

    from app.ui.windows.main_window import MainWindow

    theme.apply(qt_app, "light")
    window = MainWindow(Settings(theme="hacker"))
    try:
        assert theme.current().key == "hacker"

        checked = [action.text() for action in window._theme_group.actions() if action.isChecked()]
        assert checked == ["&Hacker"]
    finally:
        window.close()
        theme.apply(qt_app, theme.DEFAULT_THEME)


def test_switching_theme_moves_the_menu_mark(qt_app, tmp_path, monkeypatch):
    from app.ui.windows.main_window import MainWindow

    monkeypatch.setattr(
        "app.core.config.get_settings_path", lambda: tmp_path / "settings.json"
    )

    window = MainWindow(Settings(theme="light"))
    try:
        window.apply_theme("dark")

        assert theme.current().key == "dark"
        assert window.settings.theme == "dark"

        checked = [action.text() for action in window._theme_group.actions() if action.isChecked()]
        assert checked == ["&Dark"]
    finally:
        window.close()
        theme.apply(qt_app, theme.DEFAULT_THEME)


def test_detail_panel_rerenders_on_a_theme_change(qt_app):
    """
    The panel's colours are baked into its HTML, so unlike an ordinary widget
    it does not follow a style-sheet change on its own.
    """

    from app.ui.widgets.plan_detail import PlanDetailPanel

    panel = PlanDetailPanel()

    theme.apply(qt_app, "light")
    panel.retheme()
    light = panel.overview.toHtml()

    theme.apply(qt_app, "hacker")
    panel.retheme()

    assert panel.overview.toHtml() != light
    theme.apply(qt_app, theme.DEFAULT_THEME)


def test_the_ui_shows_no_web_addresses():
    """
    The application names its source rather than linking to it. A URL rendered on screen
    invites the reader to go and use the website instead, and makes a paid product look
    like a shim over a free one.
    """

    import re
    from pathlib import Path

    import app.ui

    address = re.compile(r"https?://")
    allowed = {"doc.qt.io"}  # a comment pointing at Qt's own documentation

    for source in Path(app.ui.__file__).parent.rglob("*.py"):
        for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            if address.search(line) and not any(host in line for host in allowed):
                raise AssertionError(f"{source.name}:{number} renders a web address: {line.strip()}")


def test_exports_name_the_source_rather_than_linking_to_it():
    import re
    from pathlib import Path

    import app.services.export as export_module

    text = Path(export_module.__file__).read_text(encoding="utf-8")

    assert "SOURCE_LABEL" in text
    assert not re.search(r'"https?://', text)


def test_the_source_label_is_the_one_the_product_uses():
    from app.core.constants import SOURCE_LABEL

    assert SOURCE_LABEL == "Department of Labour Database, USA"


def _channel(value: int) -> float:
    ratio = value / 255
    return ratio / 12.92 if ratio <= 0.04045 else ((ratio + 0.055) / 1.055) ** 2.4


def _luminance(colour: str) -> float:
    """Relative luminance per WCAG 2.1."""

    red, green, blue = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast_ratio(foreground: str, background: str) -> float:
    first, second = _luminance(foreground), _luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize(
    ("foreground", "background", "floor"),
    [
        ("text", "window", 7.0),
        ("text", "surface", 7.0),
        ("text_muted", "surface", 4.5),
        ("text_faint", "surface", 3.0),
        ("accent", "surface", 4.5),
        ("on_accent", "accent", 4.5),
        ("on_selection", "selection", 4.5),
        ("high", "surface", 3.0),
        ("medium", "surface", 3.0),
        ("danger", "surface", 3.0),
    ],
)
def test_every_scheme_is_readable(palette, foreground, background, floor):
    """
    Body text clears WCAG AAA, secondary text clears AA, and the coloured
    ratings clear the large-text threshold. Someone reads these reports for an
    hour at a time.
    """

    ratio = contrast_ratio(getattr(palette, foreground), getattr(palette, background))
    assert ratio >= floor, (
        f"{palette.key}: {foreground} on {background} is {ratio:.1f}:1, "
        f"below the {floor}:1 floor"
    )


def test_the_high_contrast_scheme_earns_its_name():
    """It exists for low vision, so AAA everywhere is the whole point."""

    palette = theme.CONTRAST

    for role in ("text", "text_muted", "text_faint", "accent"):
        ratio = contrast_ratio(getattr(palette, role), palette.window)
        assert ratio >= 7.0, f"contrast.{role} is only {ratio:.1f}:1"

    assert contrast_ratio(palette.text, palette.window) >= 20.0


def test_borders_are_visible_against_their_background(palette):
    """An invisible border turns grouped panels into one undivided slab."""

    assert contrast_ratio(palette.border, palette.window) >= 1.2, palette.key
    assert contrast_ratio(palette.border_strong, palette.surface) >= 1.3, palette.key


def test_every_theme_gets_its_own_accelerator_key():
    """Hacker and High contrast both wanted Alt+H; the second one never fired."""

    marked = theme.accelerated([p.label for p in theme.available()])

    keys = [label[label.index("&") + 1].lower() for label in marked if "&" in label]
    assert len(keys) == len(set(keys)), f"duplicate accelerator in {marked}"
    assert len(marked) == len(theme.available())


def test_an_accelerator_keeps_the_label_readable():
    assert theme.accelerated(["Light"]) == ["&Light"]
    assert theme.accelerated(["Hacker", "High contrast"]) == ["&Hacker", "H&igh contrast"]


def test_a_label_with_no_free_letter_is_left_alone():
    assert theme.accelerated(["Aa", "Aa"]) == ["&Aa", "Aa"]

"""
Branding assets are optional, so the tests cover both states: present and
absent. A build with no logo must start exactly as happily as one with a logo.
"""

from __future__ import annotations

import pytest

from app.ui import resources


def test_resource_dir_exists():
    assert resources.resource_dir().is_dir()


def test_describe_reports_every_slot():
    described = resources.describe()
    assert set(described) == {"resource_dir", "icon", "logo", "stylesheet"}


def test_missing_asset_returns_none_rather_than_raising():
    assert resources.resource_path("definitely-not-here.png") is None


def test_missing_stylesheet_yields_empty_string(monkeypatch):
    monkeypatch.setattr(resources, "stylesheet_path", lambda: None)
    assert resources.load_stylesheet() == ""


def test_accessors_are_safe_when_the_folder_is_empty(monkeypatch, tmp_path):
    """The default repository state ships no branding; that must not break."""

    monkeypatch.setattr(resources, "resource_dir", lambda: tmp_path)

    assert resources.icon_path() is None
    assert resources.logo_path() is None
    assert resources.stylesheet_path() is None
    assert resources.load_stylesheet() == ""


def test_corrupt_icon_is_rejected(monkeypatch, tmp_path):
    """
    A truncated icon produces a non-null QIcon carrying no images, which would
    render as a blank square. It must be treated as "no icon" instead.
    """

    pytest.importorskip("PySide6.QtGui")

    broken = tmp_path / "app.ico"
    broken.write_bytes(b"\x00\x00\x01\x00\x01\x00" + b"\x00" * 32)
    monkeypatch.setattr(resources, "resource_dir", lambda: tmp_path)

    assert resources.app_icon() is None


def test_icon_falls_back_to_png(monkeypatch, tmp_path):
    """Platforms that cannot read .ico should still get an icon from a PNG."""

    monkeypatch.setattr(resources, "resource_dir", lambda: tmp_path)
    (tmp_path / "logo.png").write_bytes(b"placeholder")

    found = resources.icon_path()
    assert found is not None and found.name == "logo.png"

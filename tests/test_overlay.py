import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

from desktranslate.settings import Settings
from desktranslate.ui.overlay import Overlay
from desktranslate.ui.subtitles import PRESETS
from desktranslate.ui.theme import apply_theme

pytestmark = pytest.mark.headless_ui


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    apply_theme(application, "dark")
    return application


@pytest.mark.parametrize("origin", [(0, 0), (-1280, -720)])
def test_large_overlay_default_placement_fits_short_workarea(app, monkeypatch, origin):
    from types import SimpleNamespace

    from PySide6.QtCore import QRect

    bounds = QRect(*origin, 640, 360)
    overlay = Overlay(Settings())
    try:
        monkeypatch.setattr(
            QApplication, "primaryScreen", lambda: SimpleNamespace(availableGeometry=lambda: bounds)
        )
        overlay.resize(1400, 1200)
        overlay.place()
        assert bounds.contains(overlay.geometry())
    finally:
        overlay.close()


@pytest.mark.parametrize("size", [(480, 180), (720, 210), (1100, 360)])
@pytest.mark.parametrize(
    "text",
    [
        "Let's meet here again tomorrow.",
        "明日、またここで会おう。\n내일 다시 만나요.",
        "مرحبا بالعالم — hello",
        "A very long translation " * 100,
    ],
)
@pytest.mark.parametrize("preset", list(PRESETS))
def test_overlay_shapes_scripts_bounds_text_and_reuses_glyphs(app, size, text, preset):
    settings = Settings(reduced_motion=True)
    for key, value in PRESETS[preset].items():
        setattr(settings, key, value)
    settings.validate()
    overlay = Overlay(settings)
    try:
        overlay.resize(*size)
        overlay.display("Original", text)
        app.processEvents()
        first = overlay.grab()
        glyphs = overlay.translation.glyphs
        assert glyphs is not None
        overlay.display("Original", text)
        overlay.grab()
        assert overlay.translation.glyphs is glyphs
        assert overlay.translation.text() == text
        assert not first.isNull()
        assert 12 <= overlay.translation.effective_size <= settings.overlay_size
    finally:
        overlay.close()


def test_edit_mode_and_dpi_invalidate_cache(app):
    overlay = Overlay(
        Settings(overlay_click_through=True, overlay_locked=True, reduced_motion=True)
    )
    try:
        assert overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput
        overlay.toggle_edit()
        assert not overlay.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
        assert not overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput
        assert overlay.grip.isVisible()
        overlay.display("Source", "Translation")
        overlay.grab()
        assert overlay.translation.glyphs is not None
        app.sendEvent(overlay.translation, QEvent(QEvent.Type.DevicePixelRatioChange))
        assert overlay.translation.glyphs is None
        overlay.toggle_edit()
        assert overlay.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
        assert overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput
    finally:
        overlay.close()


def test_hiding_mid_fade_restores_opacity_on_show(app):
    overlay = Overlay(Settings())
    try:
        overlay.display("Source", "Translation")
        overlay.fade.setCurrentTime(30)
        overlay.hide_by_user()
        overlay.toggle_visibility()
        assert abs(overlay.windowOpacity() - 0.92) < 0.01
    finally:
        overlay.close()


def test_large_high_dpi_overlay_has_bounded_raster_and_keeps_text(app, monkeypatch):
    from desktranslate.ui.subtitles import SubtitleText

    widget = SubtitleText(Settings(overlay_size=64, overlay_max_lines=12))
    try:
        widget.resize(3840, 2160)
        monkeypatch.setattr(widget, "devicePixelRatioF", lambda: 3.0)
        text = "Long Unicode 日本語 한국어 العربية. " * 700
        widget.setText(text)
        widget.prepare()
        assert widget.text() == text
        assert widget.glyphs.width() * widget.glyphs.height() <= 4_010_000
        assert widget.effective_size == 12
        assert widget.raster_origin.y() > 0
    finally:
        widget.close()


def test_overlay_text_has_static_accessible_role_and_literal_unicode(app):
    from PySide6.QtGui import QAccessible

    overlay = Overlay(Settings())
    try:
        text = "<b>مرحبا 日本語</b>"
        overlay.display("Source", text)
        interface = QAccessible.queryAccessibleInterface(overlay.translation)
        assert interface.role() == QAccessible.Role.StaticText
        assert interface.text(QAccessible.Text.Description) == text
        assert overlay.translation.text() == text
    finally:
        overlay.close()


def test_high_contrast_overlay_preserves_saved_style_and_restores_it(app, monkeypatch):
    settings = Settings(overlay_color="#ffdd22")
    overlay = Overlay(settings)
    try:
        monkeypatch.setattr("desktranslate.ui.overlay.high_contrast_enabled", lambda: True)
        overlay.configure(settings)
        assert overlay.settings.overlay_background_opacity == 100
        assert settings.overlay_color == "#ffdd22"
        monkeypatch.setattr("desktranslate.ui.overlay.high_contrast_enabled", lambda: False)
        overlay.configure(settings)
        assert overlay.settings.overlay_color == "#ffdd22"
    finally:
        overlay.close()

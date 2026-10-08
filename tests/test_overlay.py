import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication

from desktranslate.settings import Settings
from desktranslate.ui.overlay import Overlay
from desktranslate.ui.subtitles import PRESETS
from desktranslate.ui.theme import apply_theme


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    apply_theme(application, "dark")
    return application


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
        assert not overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput
        assert overlay.grip.isVisible()
        overlay.display("Source", "Translation")
        overlay.grab()
        assert overlay.translation.glyphs is not None
        app.sendEvent(overlay.translation, QEvent(QEvent.Type.DevicePixelRatioChange))
        assert overlay.translation.glyphs is None
        overlay.toggle_edit()
        assert overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput
    finally:
        overlay.close()

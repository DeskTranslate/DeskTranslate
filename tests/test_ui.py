import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from desktranslate.settings import Settings, SettingsStore
from desktranslate.ui.window import MainWindow


@pytest.fixture
def window(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path)
    store.save(Settings())
    widget = MainWindow(store, demo=True)
    yield widget
    widget.quit()
    app.processEvents()


def test_all_pages_open_and_plain_text_is_not_markup(window):
    for index in range(6):
        window.navigation.setCurrentRow(index)
        assert window.pages.currentIndex() == index
    window.overlay.display("<b>source</b>", "<script>literal</script>")
    assert window.overlay.translation.text() == "<script>literal</script>"
    window.overlay.copy()
    assert QApplication.clipboard().text() == "<script>literal</script>"


def test_invalid_endpoint_does_not_start_test_or_change_saved_settings(window):
    window.provider_combo.setCurrentIndex(window.provider_combo.findData("custom"))
    window.endpoint_edit.setText("http://remote.example/v1")
    window.test_provider()
    assert not window.jobs.busy
    assert window.settings.provider == "google"
    assert window.store.load().provider == "google"


def test_language_appearance_and_diagnostics_privacy(window):
    window.source_combo.setCurrentIndex(window.source_combo.findData("es"))
    assert window.store.load().source == "es"
    window.theme_combo.setCurrentIndex(window.theme_combo.findData("light"))
    window.save_appearance()
    assert window.store.load().theme == "light"
    window.latest = "PRIVATE_TRANSLATION"
    window.result_source.setText("PRIVATE_SOURCE")
    window.key_edit.setText("PRIVATE_KEY")
    window.copy_diagnostics()
    output = QApplication.clipboard().text()
    assert "PRIVATE" not in output
    assert json.loads(output)["version"]


def test_stop_cancels_queued_start(window, monkeypatch):
    from PySide6.QtTest import QTest

    calls = []
    window.settings.recent_region = [0, 0, 100, 50]
    monkeypatch.setattr(window, "start", lambda once: calls.append(once))
    window.once()
    window.stop()
    QTest.qWait(250)
    assert calls == []


def test_custom_overlay_style_is_validated_and_persisted(window):
    controls = window.overlay_editor.controls
    controls["overlay_color"].setText("#ffdd22")
    controls["overlay_background_opacity"].setValue(60)
    window.save_appearance()
    assert window.store.load().overlay_color == "#ffdd22"
    assert window.store.load().overlay_background_opacity == 60
    controls["overlay_color"].setText("invalid")
    window.save_appearance()
    assert window.store.load().overlay_color == "#ffdd22"

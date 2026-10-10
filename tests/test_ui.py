import json
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from desktranslate.settings import Settings, SettingsStore
from desktranslate.ui.window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(tmp_path, qt_app):
    store = SettingsStore(tmp_path)
    store.save(Settings())
    widget = MainWindow(store, demo=True)
    yield widget
    widget.quit()
    for _ in range(8):
        time.sleep(0.01)
        qt_app.processEvents()
    widget.overlay.deleteLater()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()


def test_all_pages_open_and_plain_text_is_not_markup(window):
    for index in range(window.navigation.count()):
        window.navigation.setCurrentRow(index)
        assert window.pages.currentIndex() == index
    window.overlay.display("<b>source</b>", "<script>literal</script>")
    assert window.overlay.translation.text() == "<script>literal</script>"
    window.overlay.copy()
    assert QApplication.clipboard().text() == "<script>literal</script>"


def test_setup_small_viewport_keeps_buttons_and_scroll_access(window):
    from PySide6.QtWidgets import QWizard

    window.onboarding()
    wizard = window.setup_dialog
    wizard.resize(560, 320)
    app = QApplication.instance()
    assert app is not None
    for _ in range(6):
        app.processEvents()
        page = wizard.currentPage()
        assert page is not None
        assert wizard.width() <= 560 and wizard.height() <= 320
        assert page.scroll_area.horizontalScrollBar().maximum() == 0
        for identifier in (
            QWizard.WizardButton.NextButton,
            QWizard.WizardButton.FinishButton,
            QWizard.WizardButton.CancelButton,
            QWizard.WizardButton.CustomButton1,
        ):
            button = wizard.button(identifier)
            if button.isVisible():
                assert wizard.rect().contains(button.mapTo(wizard, button.rect().bottomRight()))
        page.set_ready(True)
        wizard.next()
    assert not window.settings.onboarding_done
    wizard.reject()


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


def test_runtime_errors_do_not_reopen_main_window(window, monkeypatch):
    from test_pipeline import OCR, Capture, SlowProvider

    from desktranslate.errors import ProviderAuthenticationError
    from desktranslate.pipeline import Pipeline

    opened = []
    monkeypatch.setattr(window, "showNormal", lambda: opened.append(True))
    pipeline = Pipeline(window.settings, Capture, OCR, SlowProvider)
    pipeline.session.start()
    window.pipeline = pipeline
    window.hide()
    pipeline.fail(ProviderAuthenticationError())
    window.poll_pipeline()
    assert not opened
    assert "key" in window.status_label.text().lower()


def test_user_hidden_overlay_stays_hidden_and_explicit_show_recovers(window):
    window.overlay.display("A", "Translated A")
    window.overlay.hide_by_user()
    window.overlay.display("B", "Translated B")
    assert not window.overlay.isVisible()
    window.overlay.configure(window.settings)
    assert not window.overlay.isVisible()
    window.overlay.toggle_visibility()
    assert window.overlay.isVisible()
    window.overlay.hide()  # A blank interval hides automatically rather than by user request.
    window.overlay.toggle_visibility()
    assert window.overlay.isVisible()


def test_session_transcript_is_opt_in_and_cleared_without_persisting_text(window):
    from test_pipeline import OCR, Capture, SlowProvider

    from desktranslate.models import PipelineEvent, SessionState, TranslationResult
    from desktranslate.pipeline import Pipeline

    pipeline = Pipeline(window.settings, Capture, OCR, SlowProvider)
    stamp = pipeline.session.start()
    window.pipeline = pipeline
    pipeline.enqueue(
        PipelineEvent(
            stamp, SessionState.WATCHING, "PRIVATE_SOURCE", TranslationResult("PRIVATE_TRANSLATION")
        )
    )
    window.poll_pipeline()
    assert not window.transcript_page.transcript.entries
    window.transcript_page.enable.setChecked(True)
    pipeline.enqueue(
        PipelineEvent(
            stamp, SessionState.WATCHING, "PRIVATE_SOURCE", TranslationResult("PRIVATE_TRANSLATION")
        )
    )
    window.poll_pipeline()
    assert len(window.transcript_page.transcript.entries) == 1
    window.stop()
    assert not window.transcript_page.transcript.entries
    assert "PRIVATE" not in window.store.path.read_text()


def test_onboarding_requires_a_real_sample_result_and_can_recover(window, monkeypatch):
    from desktranslate.errors import ProviderTimeoutError
    from desktranslate.models import OCRResult, TranslationResult
    from desktranslate.ui.onboarding import Onboarding

    class Engine:
        def __init__(self, *args):
            pass

        def recognize(self, *args, **kwargs):
            return OCRResult("明日、またここで会おう。")

        def close(self):
            pass

        def reap(self):
            pass

    class Provider:
        fail = True

        def translate(self, request):
            if self.fail:
                raise ProviderTimeoutError()
            return TranslationResult("Let's meet here again tomorrow.")

        def close(self):
            pass

    monkeypatch.setattr("desktranslate.ui.onboarding.IsolatedOCR", Engine)
    monkeypatch.setattr(
        "desktranslate.ui.onboarding.ModelManager.installed", lambda *args, **kwargs: True
    )
    provider = Provider()
    wizard = Onboarding(
        lambda: window.settings, window.commit_settings, lambda settings: lambda: provider, window
    )
    wizard.show()
    assert not wizard.test_page.isComplete()
    wizard.accept()
    assert not window.settings.onboarding_done
    assert wizard.isVisible()
    wizard.test()
    for _ in range(40):
        time.sleep(0.025)
        QApplication.processEvents()
        if not wizard.jobs.busy:
            break
    assert wizard.isVisible()
    assert not wizard.test_page.isComplete()
    assert "took too long" in wizard.test_status.text()
    provider.fail = False
    wizard.test()
    for _ in range(40):
        time.sleep(0.025)
        QApplication.processEvents()
        if not wizard.jobs.busy:
            break
    assert wizard.test_page.isComplete()
    assert "明日" in wizard.sample_result.toPlainText()
    wizard.accept()
    assert window.store.load().onboarding_done


def test_passive_restart_preflight_does_not_open_main_window(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window, "showNormal", lambda: calls.append("focus"))
    monkeypatch.setattr(
        "desktranslate.ui.window.ModelManager.installed", lambda *args, **kwargs: False
    )
    window.settings.recent_region = [0, 0, 100, 50]
    window.start(False, False)
    assert calls == []


def test_onboarding_is_singleton_and_waits_for_cancelled_work(window):
    window.onboarding()
    original = window.setup_dialog
    window.onboarding()
    assert window.setup_dialog is original
    original.jobs.busy = True
    original.reject()
    window.onboarding()
    assert window.setup_dialog is original
    original.jobs.busy = False

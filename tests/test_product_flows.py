import copy
import time

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from desktranslate.settings import Settings, SettingsStore
from desktranslate.ui.window import MainWindow

pytestmark = pytest.mark.headless_ui


@pytest.fixture
def product(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = SettingsStore(tmp_path)
    store.save(Settings(onboarding_done=True))
    window = MainWindow(store, demo=True)
    yield window
    if hasattr(window, "setup_dialog"):
        window.setup_dialog.reject()
        window.setup_dialog.deleteLater()
    window.quit()
    for _ in range(8):
        time.sleep(0.01)
        app.processEvents()
    window.overlay.deleteLater()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def test_language_swap_is_one_durable_pair_and_one_transition(product, monkeypatch):
    saved = []
    save = product.store.save

    def record(settings):
        saved.append((settings.source, settings.target))
        save(settings)

    monkeypatch.setattr(product.store, "save", record)
    revision = product.settings_revision
    product.swap_languages()
    assert saved == [("en", "ja")]
    assert product.settings_revision == revision + 1
    assert (product.store.load().source, product.store.load().target) == ("en", "ja")


def test_reopened_guide_preserves_explicit_local_provider_choice(product):
    settings = copy.deepcopy(product.settings)
    settings.provider, settings.model, settings.endpoint = "ollama", "authored-model", ""
    assert product.commit_settings(settings)
    product.onboarding()
    assert product.setup_dialog.method.currentData() == "configured"
    assert product.setup_dialog.snapshot().provider == "ollama"


def test_provider_setup_roundtrip_preserves_draft_languages_and_requires_retest(product):
    product.onboarding()
    guide = product.setup_dialog
    guide.source.setCurrentIndex(guide.source.findData("ko"))
    guide.target.setCurrentIndex(guide.target.findData("es"))
    guide.configure_provider_button.click()
    assert not guide.isVisible()
    assert product.navigation.currentRow() == 1
    assert not product.return_setup_button.isHidden()
    product.provider_combo.setCurrentIndex(product.provider_combo.findData("ollama"))
    product.model_combo.setCurrentText("authored-model")
    assert product.save_provider()
    product.return_setup_button.click()
    assert product.setup_dialog is guide and guide.isVisible()
    assert guide.source.currentData() == "ko" and guide.target.currentData() == "es"
    assert guide.method.currentData() == "configured"
    assert guide.snapshot().provider == "ollama"
    assert not guide.tested and not guide.test_page.isComplete()


def test_stopped_application_has_no_pipeline_polling_and_notices_preserve_capture_state(product):
    product.stop()
    assert not product.timer.isActive()
    assert "not capturing" in product.session_status.text().lower()
    state = product.session_status.text()
    product.notice("Profile saved.")
    assert product.session_status.text() == state
    assert not product.pause_button.isEnabled()


def test_pause_resume_actions_and_persistent_state_follow_actual_session(product):
    from desktranslate.pipeline import Pipeline

    pipeline = Pipeline(product.settings, lambda: None, lambda: None, lambda: None)
    pipeline.session.start()
    product.pipeline = pipeline
    product.refresh_session_view()
    assert product.pause_button.text() == "Pause"
    product.pause()
    assert product.pause_button.text() == "Resume"
    assert product.overlay.pause_button.text() == "Resume"
    assert "paused" in product.session_status.text().lower()
    product.notice("Overlay hidden.")
    assert "paused" in product.session_status.text().lower()
    product.pause()
    assert product.pause_button.text() == "Pause"
    assert pipeline.session.state.value == "watching"


def test_failed_language_swap_keeps_both_languages_and_current_session(product, monkeypatch):
    from desktranslate.pipeline import Pipeline

    pipeline = Pipeline(product.settings, lambda: None, lambda: None, lambda: None)
    pipeline.session.start()
    product.pipeline = pipeline
    revision = product.settings_revision

    def cannot_save(settings):
        raise OSError("authored unavailable storage")

    monkeypatch.setattr(product.store, "save", cannot_save)
    product.swap_languages()
    assert product.pipeline is pipeline and not pipeline.cancel.is_set()
    assert product.settings_revision == revision
    assert (product.settings.source, product.settings.target) == ("ja", "en")
    assert (product.source_combo.currentData(), product.target_combo.currentData()) == ("ja", "en")


def test_local_endpoint_privacy_and_cancelled_setup_are_truthful(product):
    settings = copy.deepcopy(product.settings)
    settings.provider, settings.endpoint = "libre", "http://127.0.0.1:5000"
    assert product.commit_settings(settings)
    product.onboarding()
    guide = product.setup_dialog
    assert "stays on this device" in guide.provider_summary.text()
    guide.configure_provider_button.click()
    guide.reject()
    assert not product.setup_suspended and product.return_setup_button.isHidden()


@pytest.fixture
def pack_download(product, monkeypatch):
    installed, callbacks, starts = [], [], []
    monkeypatch.setattr(
        "desktranslate.ui.window.ModelManager.installed", lambda manager, language: bool(installed)
    )

    def background(operation, callback):
        product.jobs.busy = True
        callbacks.append(callback)

    monkeypatch.setattr(product, "job", background)
    monkeypatch.setattr(product, "queue_start", lambda once: starts.append(once))
    return installed, callbacks, starts


@pytest.mark.parametrize("once", [True, False])
def test_missing_pack_requires_consent_then_continues_requested_action(
    product, pack_download, once
):
    installed, callbacks, starts = pack_download
    product.start(once)
    assert not product.jobs.busy and not starts
    assert product.navigation.currentRow() == 2
    assert "install to continue" in product.session_status.text()
    assert product.stop_button.isEnabled()
    assert ("translate once" if once else "start live") in product.install_button.text()
    product.install_button.click()
    assert "Preparing recognition" in product.session_status.text()
    assert not product.install_button.isEnabled() and not starts
    installed.append(True)
    product.jobs.busy = False
    callbacks[0](None, "")
    assert starts == [once] and product.navigation.currentRow() == 0
    assert product.pending_start is None and product.install_button.isEnabled()


@pytest.mark.parametrize("interruption", ["stop", "cancel", "languages", "appearance", "failure"])
def test_pack_completion_never_starts_after_interruption(product, pack_download, interruption):
    installed, callbacks, starts = pack_download
    product.start(False)
    product.install_button.click()
    if interruption == "stop":
        product.stop_button.click()
    elif interruption == "cancel":
        product.cancel_setup()
    elif interruption == "languages":
        product.source_combo.setCurrentIndex(product.source_combo.findData("ko"))
    elif interruption == "appearance":
        settings = copy.deepcopy(product.settings)
        settings.theme = "dark"
        assert product.commit_settings(settings, activate=False)
    installed.append(True)
    product.jobs.busy = False
    callbacks[0](None, "Download interrupted. Retry." if interruption == "failure" else "")
    assert not starts and product.pending_start is None
    assert product.install_button.isEnabled() and not product.timer.isActive()


def test_old_download_does_not_discard_newer_user_intent(product, pack_download):
    installed, callbacks, starts = pack_download
    product.start(False)
    product.install_button.click()
    product.start(True)
    newer = product.pending_start
    installed.append(True)
    product.jobs.busy = False
    callbacks[0](None, "")
    assert not starts and product.pending_start == newer
    assert "translate once" in product.install_button.text()
    assert "install to continue" in product.session_status.text()


def test_one_shot_completion_drains_events_then_stops_polling_but_error_can_retry(product):
    from desktranslate.errors import ProviderUnavailableError
    from desktranslate.models import SessionState
    from desktranslate.pipeline import Pipeline

    pipeline = Pipeline(product.settings, lambda: None, lambda: None, lambda: None, once=True)
    pipeline.session.start()
    product.pipeline = pipeline
    pipeline.delivered_source = "authored result"
    pipeline.emit(SessionState.WATCHING)
    pipeline.cancel.set()
    product.refresh_session_view()
    assert product.timer.isActive()  # The completion receipt still needs delivering.
    product.poll_pipeline()
    assert not product.timer.isActive()
    assert "complete" in product.session_status.text() and not product.pause_button.isEnabled()
    assert not product.overlay.pause_button.isEnabled()
    pipeline.cancel.clear()
    pipeline.fail(ProviderUnavailableError())
    product.poll_pipeline()
    assert "paused" in product.session_status.text().lower()
    assert product.pause_button.isEnabled() and product.pause_button.text() == "Retry translation"


def test_quit_rejects_late_setup_and_new_background_work(product, monkeypatch):
    def forbidden():
        raise AssertionError("Selection must not open after Quit")

    monkeypatch.setattr("desktranslate.ui.window.RegionSelector", forbidden)
    started = []
    monkeypatch.setattr(product.jobs, "run", lambda operation: started.append(operation) or 1)
    product.show()
    product.quit()
    product.onboarding()  # A first-run singleShot may arrive during worker cleanup.
    product.job(lambda: None, lambda result, error: None)
    product.select("once")
    product.queue_start(True)
    assert not hasattr(product, "setup_dialog")
    assert not started and not product.callbacks
    assert not product.isVisible()


def test_terminal_worker_cleanup_failure_is_visible_before_next_user_action(product, monkeypatch):
    from desktranslate.pipeline import Pipeline

    pipeline = Pipeline(product.settings, lambda: None, lambda: None, lambda: None, once=True)
    pipeline.session.start()
    pipeline.cancel.set()
    pipeline.delivered_source = "authored result"
    product.pipeline = pipeline
    pipeline.cleanup_failure()
    product.refresh_session_view()
    assert product.exit_code == 1 and "Restart required" in product.session_status.text()
    assert "Quit" in product.status_label.text()
    assert not product.pause_button.isEnabled() and not product.live_button.isEnabled()
    product.notice("Profile saved.")
    assert "Restart required" in product.session_status.text()
    product.start(False)
    assert product.pipeline is None and product.pending_start is None
    product.show()

    def forbidden():
        raise AssertionError("Selection must not open after cleanup failure")

    monkeypatch.setattr("desktranslate.ui.window.RegionSelector", forbidden)
    product.once()  # No selected region: refuse before opening a picker.
    assert product.selector is None and product.isVisible()
    product.settings.recent_region = [0, 0, 100, 100]
    product.once()  # Existing region: refuse before hiding to capture.
    assert product.isVisible() and not product.timer.isActive()
    assert "launch it again" in product.status_label.text()


def test_retired_cleanup_failure_stops_a_replacement_live_session(product):
    from desktranslate.pipeline import Pipeline

    retired = Pipeline(product.settings, lambda: None, lambda: None, lambda: None)
    retired.cleanup_failure()
    active = Pipeline(product.settings, lambda: None, lambda: None, lambda: None)
    active.session.start()
    product.retiring.append(retired)
    product.pipeline = active
    product.show()
    product.collect_retired()
    product.refresh_session_view()
    assert active.cancel.is_set() and product.pipeline is None
    assert product.isVisible() and "Restart required" in product.session_status.text()
    assert "Quit" in product.status_label.text()

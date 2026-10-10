"""Guided setup only completes after an actual local OCR/provider sample succeeds."""

from __future__ import annotations

import copy
from collections.abc import Callable
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from desktranslate.algorithms import normalize_text
from desktranslate.errors import DeskTranslateError, OCRInferenceError
from desktranslate.languages import LANGUAGES
from desktranslate.models import TranslationRequest
from desktranslate.ocr import IsolatedOCR, ModelManager
from desktranslate.settings import Settings
from desktranslate.ui.jobs import Jobs

SAMPLES = {
    "ja": ("ja-game.png", "明日、またここで会おう。"),
    "ko": ("ko-subtitle.png", "내일 다시 만나요."),
    "en": ("en-ui.png", "Select a region to translate."),
    "es": ("es-ui.png", "Selecciona una región para traducir."),
    "zh-CN": ("zh-dialogue.png", "明天我们在这里见面。"),
    "zh-TW": ("zh-traditional.png", "明天我們在這裡見面。"),
}


class SetupPage(QWizardPage):
    changed = Signal()

    def __init__(self, title: str, subtitle: str) -> None:
        super().__init__()
        self.setTitle(title)
        self.setSubTitle(subtitle)
        self.content = QVBoxLayout(self)
        self.ready = True

    def isComplete(self) -> bool:
        return self.ready

    def set_ready(self, ready: bool) -> None:
        self.ready = ready
        self.completeChanged.emit()


class Onboarding(QWizard):
    def __init__(
        self,
        get_settings: Callable[[], Settings],
        commit: Callable[[Settings, bool], bool],
        provider_factory: Callable[[Settings], Callable[[], Any]],
        parent: Any,
    ) -> None:
        super().__init__(parent)
        self.get_settings, self.commit, self.provider_factory = (
            get_settings,
            commit,
            provider_factory,
        )
        self.host = parent
        self.setWindowTitle("Your first translation")
        self.resize(640, 600)
        self.setOption(QWizard.WizardOption.HaveCustomButton1)
        self.setButtonText(QWizard.WizardButton.CustomButton1, "Set up later")
        self.customButtonClicked.connect(self.reject)
        self.jobs = Jobs()
        self.jobs.done.connect(self.done_job, Qt.ConnectionType.QueuedConnection)
        self.jobs.progress.connect(self.model_progress, Qt.ConnectionType.QueuedConnection)
        self.pending: Callable[[object, str], None] | None = None
        self.active_provider: Any = None
        self.tested = False
        self.selection_serial = 0
        welcome = SetupPage(
            "Words without the setup maze.",
            "We'll prepare recognition and translate a harmless bundled sample.",
        )
        intro = QLabel(
            "Screenshots stay on your computer. Online providers receive recognized text and configured dialogue context. Local AI keeps text local. There is no telemetry or automatic translation history. Downloads and connection tests run only when you press their buttons."
        )
        intro.setWordWrap(True)
        welcome.content.addWidget(intro)
        self.addPage(welcome)
        languages = SetupPage(
            "Choose your languages",
            "Choose the language you are reading and the language you want to read.",
        )
        form = QFormLayout()
        self.source, self.target = QComboBox(), QComboBox()
        for language in LANGUAGES:
            if language.code != "auto":
                self.source.addItem(language.name, language.code)
                self.target.addItem(language.name, language.code)
        self.source.setCurrentIndex(max(0, self.source.findData(get_settings().source)))
        self.target.setCurrentIndex(max(0, self.target.findData(get_settings().target)))
        self.source.setAccessibleName("Setup source language")
        self.target.setAccessibleName("Setup translation language")
        form.addRow("Read", self.source)
        form.addRow("Translate into", self.target)
        languages.content.addLayout(form)
        self.addPage(languages)
        self.recognition = SetupPage(
            "Prepare recognition",
            "Small language packs let DeskTranslate read locally. No Python or OCR executable setup.",
        )
        self.recognition.set_ready(False)
        self.model_status = QLabel()
        self.model_status.setWordWrap(True)
        self.recognition.content.addWidget(self.model_status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.recognition.content.addWidget(self.progress)
        prepare = QPushButton("Install language pack")
        prepare.clicked.connect(self.install)
        self.recognition.content.addWidget(prepare)
        cancel = QPushButton("Cancel download")
        cancel.clicked.connect(self.jobs.cancel.set)
        self.recognition.content.addWidget(cancel)
        self.addPage(self.recognition)
        provider = SetupPage(
            "Choose translation",
            "Choose where your recognized text goes. Advanced setup remains available in Providers.",
        )
        self.method = QComboBox()
        self.method.addItem("Google · online · no API key", "google")
        self.method.addItem("Use my currently configured provider", "configured")
        self.method.setAccessibleName("Setup translation method")
        provider.content.addWidget(self.method)
        description = QLabel(
            "Google uses a public web endpoint; availability is not guaranteed. For a local model or a paid API, configure and test it in Providers first, then reopen this guide using Preferences. This guide never silently changes your provider."
        )
        description.setWordWrap(True)
        provider.content.addWidget(description)
        self.addPage(provider)
        self.test_page = SetupPage(
            "Try your first translation",
            "The bundled sample is processed by your actual recognition engine and chosen translation provider.",
        )
        self.test_page.set_ready(False)
        self.test_status = QLabel(
            "Press Translate sample. Network use follows your selected provider."
        )
        self.test_status.setWordWrap(True)
        self.test_page.content.addWidget(self.test_status)
        self.sample_preview = QLabel()
        self.sample_preview.setAccessibleName("Bundled foreign-language sample image")
        self.test_page.content.addWidget(self.sample_preview)
        self.sample_result = QPlainTextEdit()
        self.sample_result.setReadOnly(True)
        self.sample_result.setAccessibleName("Recognized sample and translated result")
        self.test_page.content.addWidget(self.sample_result)
        run = QPushButton("Translate sample")
        run.clicked.connect(self.test)
        self.test_page.content.addWidget(run)
        self.addPage(self.test_page)
        success = SetupPage(
            "DeskTranslate is ready.", "You have completed a real sample translation."
        )
        hint = QLabel(
            f"Next: press {get_settings().hotkeys['once']}, drag a tight subtitle area, then press Enter. Escape cancels. Choose an application to keep a region attached to its moving window."
        )
        hint.setWordWrap(True)
        success.content.addWidget(hint)
        self.addPage(success)
        self.source.currentIndexChanged.connect(self.selection_changed)
        self.target.currentIndexChanged.connect(self.selection_changed)
        self.method.currentIndexChanged.connect(self.selection_changed)
        self.currentIdChanged.connect(self.enter_page)
        self.selection_changed()

    def selection_changed(self) -> None:
        self.selection_serial += 1
        self.tested = False
        self.test_page.set_ready(False)
        self.sample_result.clear()
        sample = SAMPLES.get(self.source.currentData())
        if sample:
            pixmap = QPixmap(str(Path(__file__).parents[1] / "assets/samples" / sample[0]))
            self.sample_preview.setPixmap(
                pixmap.scaledToWidth(540, Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self.sample_preview.clear()
        self.update_model_status()

    def enter_page(self, page: int) -> None:
        if page == 2:
            self.update_model_status()

    def update_model_status(self) -> None:
        source = self.source.currentData()
        ready = ModelManager().installed(source)
        self.recognition.set_ready(ready)
        self.model_status.setText(
            f"{self.source.currentText()} · "
            + (
                "Installed. Continue to choose translation."
                if ready
                else "Language pack needed. Install it to continue."
            )
        )

    def run_job(
        self, operation: Callable[[], object], complete: Callable[[object, str], None]
    ) -> None:
        if self.jobs.busy:
            self.test_status.setText("Wait for the current task to finish, or cancel its download.")
            return
        serial = self.jobs.run(operation)
        if serial:
            self.pending = complete

    def done_job(self, serial: int, result: object, error: str) -> None:
        self.jobs.busy = False
        complete, self.pending = self.pending, None
        if complete and self.isVisible():
            complete(result, error)

    def model_progress(self, model: str, done: int, total: int) -> None:
        self.progress.setRange(0, 100 if total else 0)
        if total:
            self.progress.setValue(min(100, int(done * 100 / total)))
        if model.startswith("verifying:"):
            self.model_status.setText("Verifying your language pack…")
            return
        if model.startswith("installed:"):
            self.model_status.setText("Pack verified. Finishing preparation…")
            return
        self.model_status.setText(
            f"Preparing language pack · {done / 1e6:.1f} MB"
            + (f" / {total / 1e6:.1f} MB" if total else "")
        )

    def install(self) -> None:
        language = self.source.currentData()
        self.model_status.setText("Preparing your language pack…")

        def complete(result: object, error: str) -> None:
            self.update_model_status()
            if error:
                self.model_status.setText(error + " Retry when ready.")
            self.progress.setRange(0, 100)

        self.run_job(
            lambda: ModelManager().install(language, self.jobs.cancel, self.jobs.progress.emit),
            complete,
        )

    def snapshot(self) -> Settings:
        updated = copy.deepcopy(self.get_settings())
        updated.source, updated.target = self.source.currentData(), self.target.currentData()
        if self.method.currentData() == "google":
            updated.provider, updated.endpoint, updated.model = "google", "", ""
        updated.ocr = "rapidocr"
        return updated

    def test(self) -> None:
        snapshot = self.snapshot()
        if snapshot.source == snapshot.target:
            self.test_status.setText(
                "Choose different source and translation languages, then try again."
            )
            return
        sample = SAMPLES.get(snapshot.source)
        if sample is None:
            self.test_status.setText(
                "A bundled sample for this language is not qualified yet. Set up later and use a real region, or choose a sample language in Back."
            )
            return
        try:
            factory = self.provider_factory(snapshot)
        except DeskTranslateError as error:
            self.test_status.setText(str(error))
            return
        revision = self.selection_serial
        self.test_status.setText("Reading the sample locally, then translating…")

        def operation() -> object:
            engine = IsolatedOCR("rapidocr", snapshot.source)
            provider = None
            try:
                with Image.open(Path(__file__).parents[1] / "assets/samples" / sample[0]) as image:
                    recognized = engine.recognize(
                        image.convert("RGB"), snapshot.source, cancel=self.jobs.cancel
                    )
                if not normalize_text(recognized.text):
                    raise OCRInferenceError(
                        "The sample wasn't recognized. Reinstall the language pack and retry."
                    )
                if (
                    SequenceMatcher(
                        None, normalize_text(recognized.text), normalize_text(sample[1])
                    ).ratio()
                    < 0.8
                ):
                    raise OCRInferenceError(
                        "The sample recognition did not match closely enough. Reinstall the language pack and retry."
                    )
                provider = factory()
                self.active_provider = provider
                provider.cancelled = self.jobs.cancel
                translated = provider.translate(
                    TranslationRequest(
                        recognized.text,
                        snapshot.source,
                        snapshot.target,
                        snapshot.model,
                        snapshot.style,
                        instructions=snapshot.instructions,
                    )
                )
                return recognized.text, translated.text
            finally:
                engine.close()
                engine.reap()
                if provider:
                    provider.close()
                self.active_provider = None

        def complete(result: object, error: str) -> None:
            if revision != self.selection_serial:
                return
            if error:
                self.test_status.setText(error + " Retry, or go Back to choose another setup.")
            elif isinstance(result, tuple):
                source, translated = result
                self.sample_result.setPlainText(
                    f"Recognized locally:\n{source}\n\nTranslated:\n{translated}"
                )
                self.test_status.setText(
                    "Sample translated. Review the recognized words and translation, then continue."
                )
                self.tested = True
                self.test_page.set_ready(True)
                self.host.overlay.display(source, translated)

        self.run_job(operation, complete)

    def accept(self) -> None:
        if self.tested:
            updated = self.snapshot()
            updated.onboarding_done = True
            if self.commit(updated, True):
                super().accept()

    def reject(self) -> None:
        self.jobs.cancel.set()
        if self.active_provider and hasattr(self.active_provider, "cancel_pending"):
            self.active_provider.cancel_pending()
        super().reject()

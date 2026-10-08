from __future__ import annotations

import copy
import hashlib
import json
import platform
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, fields
from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from desktranslate import __version__
from desktranslate.capture import MSSCapture, physical_monitors, topology_signature
from desktranslate.errors import DeskTranslateError
from desktranslate.hotkeys import Hotkeys, validate_hotkeys
from desktranslate.languages import LANGUAGES
from desktranslate.models import Rect, SessionState, Stamp, TranslationRequest
from desktranslate.ocr import IsolatedOCR, ModelManager
from desktranslate.pipeline import Pipeline
from desktranslate.providers import SPECS, create_provider
from desktranslate.security import CredentialStore, validate_endpoint
from desktranslate.settings import Settings, SettingsStore
from desktranslate.ui.jobs import Jobs
from desktranslate.ui.overlay import Overlay
from desktranslate.ui.overlay_editor import OverlayEditor
from desktranslate.ui.selection import RegionSelector
from desktranslate.ui.theme import apply_theme, icon


def label(text: str, kind: str = "") -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    if kind:
        widget.setObjectName(kind)
    return widget


def button(text: str, callback: Callable[[], object], primary: bool = False) -> QPushButton:
    widget = QPushButton(text)
    if primary:
        widget.setObjectName("primary")
    widget.clicked.connect(callback)
    return widget


def combo(options: list[tuple[str, str]], current: str) -> QComboBox:
    widget = QComboBox()
    for name, value in options:
        widget.addItem(name, value)
    widget.setCurrentIndex(max(0, widget.findData(current)))
    widget.setAccessibleName("Choose an option")
    return widget


def language_combo(current: str, source: bool = False) -> QComboBox:
    widget = combo(
        [
            (language.name, language.code)
            for language in LANGUAGES
            if source or language.code != "auto"
        ],
        current,
    )
    widget.setEditable(True)
    widget.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    completer = widget.completer()
    if completer is not None:
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
    widget.setAccessibleName("Source language" if source else "Translation language")
    return widget


def card(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(14)
    if title:
        layout.addWidget(label(title, "eyebrow"))
    return frame, layout


class MainWindow(QMainWindow):
    def __init__(self, store: SettingsStore, demo: bool = False) -> None:
        super().__init__()
        self.store = store
        self.settings = store.load()
        self.credentials = CredentialStore()
        self.pipeline: Pipeline | None = None
        self.selector: RegionSelector | None = None
        self.latest = ""
        self.errors: list[str] = []
        self.timings: dict[str, float] = {}
        self.closing = False
        self.command_serial = 0
        self.selected_action = "select"
        self.last_provider = self.settings.provider
        self.jobs = Jobs()
        self.callbacks: dict[int, Callable[[object, str], None]] = {}
        self.jobs.done.connect(self.job_done)
        self.jobs.progress.connect(self.download_progress)
        self.setWindowTitle("DeskTranslate 2")
        self.setWindowIcon(icon())
        self.resize(1000, 800)
        self.setMinimumSize(820, 640)
        app = QApplication.instance()
        apply_theme(app, self.settings.theme)  # type: ignore[arg-type]
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(22, 24, 24, 16)
        root_layout.setSpacing(28)
        sidebar = QVBoxLayout()
        sidebar.setSpacing(16)
        sidebar.addWidget(label("▣  DeskTranslate", "brand"))
        sidebar.addWidget(label("VERSION 2  ·  SCREEN TRANSLATION", "eyebrow"))
        self.navigation = QListWidget()
        self.navigation.setFixedWidth(200)
        self.navigation.addItems(
            ["Translate", "Providers", "Recognition", "Appearance", "Preferences", "Diagnostics"]
        )
        self.navigation.setAccessibleName("Navigation")
        for index in range(self.navigation.count()):
            self.navigation.item(index).setSizeHint(QSize(180, 46))
        self.navigation.setSpacing(3)
        sidebar.addWidget(self.navigation, 1)
        sidebar.addWidget(label("Less setup.\nMore understanding.", "muted"))
        sidebar.addWidget(label("No saved screenshots.\nNo telemetry.", "eyebrow"))
        root_layout.addLayout(sidebar)
        self.pages = QStackedWidget()
        root_layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)
        self.build_translate()
        self.build_providers()
        self.build_recognition()
        self.build_appearance()
        self.build_preferences()
        self.build_diagnostics()
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.overlay = Overlay(self.settings)
        self.overlay.pause_requested.connect(self.pause)
        self.overlay.geometry_changed.connect(self.save_overlay_geometry)
        self.overlay.edit_requested.connect(self.edit_overlay)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_pipeline)
        self.timer.start(60)
        self.hotkeys = Hotkeys(
            {
                "once": lambda: self.select("once"),
                "live": lambda: self.select("live"),
                "pause": self.pause,
                "stop": self.stop,
                "select": lambda: self.select("select"),
                "overlay": self.toggle_overlay,
                "copy": self.copy_latest,
                "edit": self.edit_overlay,
            }
        )
        app.installNativeEventFilter(self.hotkeys)  # type: ignore[union-attr]
        conflicts: list[str] = []
        if not demo:
            if not self.settings.onboarding_done:
                values, conflicts = self.hotkeys.register_first_run(self.settings.hotkeys)
                if values != self.settings.hotkeys:
                    self.settings.hotkeys = values
                    self.persist()
                    for key, edit in self.hotkey_edits.items():
                        edit.setText(values[key])
            else:
                conflicts = self.hotkeys.register(self.settings.hotkeys)
        self.shortcut_hint.setText(
            f"{self.settings.hotkeys['once']} · Translate anywhere     {self.settings.hotkeys['pause']} · Pause live"
        )
        self.tray = QSystemTrayIcon(icon(), self)
        self.tray.setToolTip("DeskTranslate 2")
        menu = QMenu()
        for title, callback in [
            ("Open DeskTranslate", self.showNormal),
            ("Translate once", lambda: self.select("once")),
            ("Start live", lambda: self.select("live")),
            ("Pause / resume", self.pause),
            ("Stop", self.stop),
            ("Show / hide overlay", self.toggle_overlay),
            ("Quit", self.quit),
        ]:
            action = QAction(title, self)
            action.triggered.connect(callback)
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: (
                self.showNormal()
                if reason == QSystemTrayIcon.ActivationReason.DoubleClick
                else None
            )
        )
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.update_region()
        self.update_provider_info()
        self.update_ocr_status()
        for screen in QApplication.screens():
            screen.geometryChanged.connect(self.display_changed)
            screen.logicalDotsPerInchChanged.connect(self.display_changed)
        app.screenRemoved.connect(self.display_changed)  # type: ignore[union-attr]
        app.screenAdded.connect(self.display_changed)  # type: ignore[union-attr]
        if conflicts:
            self.notice(
                "Shortcut unavailable: " + ", ".join(conflicts) + ". Change it in Preferences."
            )
        if store.recovered:
            self.notice(
                "Settings were damaged. Defaults restored; your credentials remain in secure storage."
            )
        if demo:
            self.result_source.setText("明日、またここで会おう。")
            self.result_translation.setText("Let's meet here again tomorrow.")
            self.status_label.setText("Preview · synthetic dialogue")
        elif not self.settings.onboarding_done:
            QTimer.singleShot(250, self.onboarding)

    def page(self, title: str, description: str) -> QVBoxLayout:
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 6, 12)
        layout.setSpacing(20)
        layout.addWidget(label(title, "title"))
        layout.addWidget(label(description, "muted"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        self.pages.addWidget(scroll)
        return layout

    def build_translate(self) -> None:
        page = self.page(
            "Understand what's on screen.",
            "Games, subtitles, images, and everything you can't select. Pick a region. We'll take it from there.",
        )
        frame, layout = card("01  /  YOUR LANGUAGES")
        row = QHBoxLayout()
        self.source_combo = language_combo(self.settings.source, True)
        self.target_combo = language_combo(self.settings.target)
        row.addWidget(self.source_combo, 1)
        row.addWidget(button("⇄", self.swap_languages))
        row.addWidget(self.target_combo, 1)
        layout.addLayout(row)
        self.source_combo.currentIndexChanged.connect(self.language_changed)
        self.target_combo.currentIndexChanged.connect(self.language_changed)
        page.addWidget(frame)
        frame, layout = card("02  /  YOUR SCREEN")
        self.region_label = label("Select an area to translate.")
        layout.addWidget(self.region_label)
        row = QHBoxLayout()
        row.addWidget(button("Select region", lambda: self.select("select")))
        row.addWidget(button("Translate once", self.once, True))
        row.addWidget(button("Start live", self.live))
        layout.addLayout(row)
        row = QHBoxLayout()
        self.pause_button = button("Pause / resume", self.pause)
        row.addWidget(self.pause_button)
        row.addWidget(button("Stop", self.stop))
        row.addWidget(button("Clear context", self.clear_context))
        layout.addLayout(row)
        self.privacy_label = label("", "muted")
        layout.addWidget(self.privacy_label)
        page.addWidget(frame)
        frame, layout = card("03  /  YOUR TRANSLATION")
        self.status_label = label("Ready when you are.", "muted")
        self.result_source = label("Recognized text appears here.", "muted")
        self.result_translation = label("A little window into another language.")
        self.result_translation.setStyleSheet("font-size: 23px; font-weight: 550;")
        self.result_translation.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.status_label)
        layout.addWidget(self.result_source)
        layout.addWidget(self.result_translation)
        row = QHBoxLayout()
        row.addWidget(button("Copy translation", self.copy_latest))
        row.addWidget(button("Show / hide overlay", self.toggle_overlay))
        row.addStretch()
        layout.addLayout(row)
        page.addWidget(frame)
        self.shortcut_hint = label(
            "Ctrl + Alt + T  ·  Translate anywhere     Ctrl + Alt + P  ·  Pause live", "eyebrow"
        )
        page.addWidget(self.shortcut_hint)
        page.addStretch()

    def build_providers(self) -> None:
        page = self.page(
            "Choose how to translate.",
            "Quick translation for speed. Contextual AI for dialogue. Local AI for privacy.",
        )
        frame, layout = card("TRANSLATION PROVIDER")
        self.provider_combo = combo(
            [(spec.name, key) for key, spec in SPECS.items()], self.settings.provider
        )
        layout.addWidget(self.provider_combo)
        self.provider_info = label("", "muted")
        layout.addWidget(self.provider_info)
        self.endpoint_edit = QLineEdit(self.settings.endpoint)
        self.endpoint_edit.setPlaceholderText("API base URL · HTTPS or localhost")
        self.endpoint_edit.setAccessibleName("API endpoint")
        layout.addWidget(self.endpoint_edit)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("New API key · leave blank to keep the saved key")
        self.key_edit.setAccessibleName("API key")
        layout.addWidget(self.key_edit)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        model_completer = self.model_combo.completer()
        if model_completer:
            model_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.model_combo.addItem(self.settings.model)
        self.model_combo.setAccessibleName("Translation model")
        self.model_combo.setPlaceholderText("Test connection to discover models")
        layout.addWidget(self.model_combo)
        row = QHBoxLayout()
        self.test_button = button("Save & test connection", self.test_provider, True)
        row.addWidget(self.test_button)
        row.addWidget(button("Provider website", self.open_provider_site))
        row.addWidget(button("Delete saved key", self.delete_key))
        layout.addLayout(row)
        self.provider_status = label("No connection test yet.", "muted")
        layout.addWidget(self.provider_status)
        layout.addWidget(button("Find local AI servers", self.detect_local))
        page.addWidget(frame)
        frame, layout = card("DIALOGUE & TERMINOLOGY")
        self.style_combo = combo(
            [
                ("Natural", "natural"),
                ("Literal", "literal"),
                ("Subtitle", "subtitle"),
                ("Game / visual novel", "game"),
                ("Custom instructions", "custom"),
            ],
            self.settings.style,
        )
        layout.addWidget(self.style_combo)
        self.instructions_edit = QPlainTextEdit(self.settings.instructions)
        self.instructions_edit.setPlaceholderText(
            "Optional style instructions, used only with Custom instructions. Maximum 1500 characters."
        )
        self.instructions_edit.setMaximumHeight(85)
        layout.addWidget(self.instructions_edit)
        self.glossary_edit = QPlainTextEdit(
            "\n".join(f"{key} = {value}" for key, value in self.settings.glossary.items())
        )
        self.glossary_edit.setPlaceholderText(
            "Optional glossary · one source = translation per line"
        )
        self.glossary_edit.setMaximumHeight(100)
        layout.addWidget(self.glossary_edit)
        layout.addWidget(button("Apply translation settings", self.save_provider))
        page.addWidget(frame)
        page.addStretch()
        self.provider_combo.currentIndexChanged.connect(self.provider_changed)

    def build_recognition(self) -> None:
        page = self.page(
            "Text comes into focus.",
            "Recognition runs on this machine. Small, verified models are managed for you.",
        )
        frame, layout = card("RECOGNITION ENGINE")
        self.ocr_combo = combo(
            [
                ("RapidOCR · managed ONNX models", "rapidocr"),
                ("Tesseract · use an existing installation", "tesseract"),
            ],
            self.settings.ocr,
        )
        layout.addWidget(self.ocr_combo)
        self.ocr_status = label("", "muted")
        layout.addWidget(self.ocr_status)
        layout.addWidget(
            label(
                "Install prepares the selected source language plus shared detection models. Typically 15–25 MB; a 100 MB per-file safety limit applies. Downloads go to the application data models folder.",
                "muted",
            )
        )
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        layout.addWidget(self.progress)
        row = QHBoxLayout()
        self.install_button = button("Install recognition models", self.install_models, True)
        row.addWidget(self.install_button)
        row.addWidget(button("Cancel download", self.jobs.cancel.set))
        layout.addLayout(row)
        page.addWidget(frame)
        frame, layout = card("TUNE FOR YOUR CONTENT")
        form = QFormLayout()
        self.quality_combo = combo(
            [
                ("Fast · shortest delay", "fast"),
                ("Balanced · dialogue & subtitles", "balanced"),
                ("Accuracy · longer stabilization", "accuracy"),
            ],
            self.settings.quality,
        )
        self.preprocess_combo = combo(
            [
                ("Original colors · recommended", "original"),
                ("Contrast enhancement", "contrast"),
                ("Small subtitles · contrast & 2× scaling", "subtitle"),
            ],
            self.settings.preprocessing,
        )
        self.vertical_check = QCheckBox("Read vertical columns from right to left")
        self.vertical_check.setChecked(self.settings.vertical)
        form.addRow("Performance", self.quality_combo)
        form.addRow("Image treatment", self.preprocess_combo)
        form.addRow(self.vertical_check)
        layout.addLayout(form)
        layout.addWidget(
            label(
                "For Japanese and Korean, choose the source language explicitly. Auto detection uses the Chinese / Latin model and is not universal. Vertical ordering remains experimental.",
                "muted",
            )
        )
        layout.addWidget(button("Apply recognition settings", self.save_recognition))
        page.addWidget(frame)
        page.addStretch()

    def build_appearance(self) -> None:
        page = self.page(
            "Make room for the words.", "A quiet overlay that stays readable over games and video."
        )
        frame, layout = card("OVERLAY")
        form = QFormLayout()
        self.overlay_mode_combo = combo(
            [
                ("Original + translation", "bilingual"),
                ("Translation only", "translation"),
                ("Subtitle bar", "subtitle"),
                ("Compact", "compact"),
            ],
            self.settings.overlay_mode,
        )
        self.font_spin = QSpinBox()
        self.font_spin.setRange(12, 64)
        self.font_spin.setValue(self.settings.overlay_size)
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(30, 100)
        self.opacity_spin.setSuffix(" %")
        self.opacity_spin.setValue(self.settings.overlay_opacity)
        self.click_check = QCheckBox("Click through the overlay · move it before locking")
        self.click_check.setChecked(self.settings.overlay_click_through)
        self.theme_combo = combo(
            [("Dark · midnight mint", "dark"), ("Light · paper & ink", "light")],
            self.settings.theme,
        )
        form.addRow("Presentation", self.overlay_mode_combo)
        form.addRow("Text size", self.font_spin)
        form.addRow("Opacity", self.opacity_spin)
        form.addRow(self.click_check)
        form.addRow("Application theme", self.theme_combo)
        layout.addLayout(form)
        self.overlay_editor = OverlayEditor(self.settings, self.apply_overlay_preset)
        layout.addWidget(self.overlay_editor)
        layout.addWidget(button("Apply and preview overlay", self.save_appearance, True))
        positioning = QHBoxLayout()
        for title, position in [
            ("Top center", "top"),
            ("Bottom center", "bottom"),
            ("Reset layout", "reset"),
        ]:
            positioning.addWidget(
                button(title, lambda checked=False, value=position: self.overlay.anchor(value))  # type: ignore[misc]
            )
        positioning.addWidget(button("Edit overlay", self.edit_overlay))
        layout.addLayout(positioning)
        layout.addWidget(
            label(
                "Drag the overlay header to move it. Resize using its bottom-right corner. Ctrl + Alt + O hides it even while click-through is enabled. Avoid placing the overlay inside your capture region.",
                "muted",
            )
        )
        page.addWidget(frame)
        page.addStretch()

    def build_preferences(self) -> None:
        page = self.page(
            "Your everyday shortcuts.", "Keep the controls close and the setup out of your way."
        )
        frame, layout = card("GLOBAL HOTKEYS · WINDOWS")
        form = QFormLayout()
        self.hotkey_edits = {}
        names = {
            "once": "Translate region once",
            "live": "Start live translation",
            "pause": "Pause / resume",
            "stop": "Stop",
            "select": "Reselect region",
            "overlay": "Show / hide overlay",
            "copy": "Copy translation",
            "edit": "Edit overlay",
        }
        for key, title in names.items():
            edit = QLineEdit(self.settings.hotkeys[key])
            edit.setAccessibleName(title)
            self.hotkey_edits[key] = edit
            form.addRow(title, edit)
        layout.addLayout(form)
        self.tray_check = QCheckBox("Closing the window keeps DeskTranslate in the system tray")
        self.tray_check.setChecked(self.settings.close_to_tray)
        layout.addWidget(self.tray_check)
        layout.addWidget(button("Apply preferences", self.save_preferences, True))
        page.addWidget(frame)
        frame, layout = card("PROFILES")
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(list(self.settings.profiles))
        layout.addWidget(self.profile_combo)
        row = QHBoxLayout()
        row.addWidget(button("Save current profile", self.save_profile))
        row.addWidget(button("Load profile", self.load_profile))
        row.addWidget(button("Delete profile", self.delete_profile))
        layout.addLayout(row)
        layout.addWidget(button("Reset settings to defaults", self.reset))
        page.addWidget(frame)
        page.addStretch()

    def build_diagnostics(self) -> None:
        page = self.page(
            "A clear view of the app.",
            "Support details include versions and timings. Never API keys, screenshots, or dialogue.",
        )
        self.diagnostics_text = QPlainTextEdit()
        self.diagnostics_text.setReadOnly(True)
        page.addWidget(self.diagnostics_text, 1)
        row = QHBoxLayout()
        row.addWidget(button("Refresh", self.refresh_diagnostics))
        row.addWidget(button("Copy diagnostics", self.copy_diagnostics, True))
        row.addWidget(button("Check for updates", self.check_updates))
        page.addLayout(row)
        page.addWidget(
            label(
                "DeskTranslate 2 beta · built for Windows 10 / 11. Translation history stays in memory and is cleared with the session.",
                "muted",
            )
        )

    def notice(self, text: str) -> None:
        self.statusBar().showMessage(text, 20000)
        self.status_label.setText(text)

    def persist(self) -> bool:
        try:
            self.store.save(self.settings)
            return True
        except (OSError, ValueError):
            self.notice("Settings could not be saved. Check permissions or reset invalid settings.")
            return False

    def job(self, operation: Callable[[], object], callback: Callable[[object, str], None]) -> None:
        serial = self.jobs.run(operation)
        if serial:
            self.callbacks[serial] = callback
        else:
            self.notice("Wait for the current setup task to finish, or cancel its download.")

    def job_done(self, serial: int, result: object, error: str) -> None:
        self.jobs.busy = False
        callback = self.callbacks.pop(serial, None)
        if callback and not self.closing:
            callback(result, error)

    def language_changed(self) -> None:
        if self.source_combo.currentData() and self.target_combo.currentData():
            self.stop()
            self.settings.source = self.source_combo.currentData()
            self.settings.target = self.target_combo.currentData()
            self.persist()
            self.update_ocr_status()

    def swap_languages(self) -> None:
        if self.settings.source != "auto":
            source, target = self.settings.source, self.settings.target
            self.source_combo.setCurrentIndex(self.source_combo.findData(target))
            self.target_combo.setCurrentIndex(self.target_combo.findData(source))

    def update_region(self) -> None:
        region = self.settings.region
        self.region_label.setText(
            f"Locked region · {region.width} × {region.height} px at ({region.x}, {region.y})"
            if region
            else "Select an area to translate."
        )

    def select(self, action: str = "select") -> None:
        if self.selector:
            return
        self.stop()
        self.selected_action = action
        self.hide()
        self.overlay.hide()
        self.selector = RegionSelector()
        self.selector.selected.connect(self.region_selected)
        self.selector.cancelled.connect(self.selection_cancelled)
        # Let the compositor remove our windows before freezing display images.
        QTimer.singleShot(200, self.selector.start)

    def region_selected(self, region: Rect) -> None:
        self.selector = None
        self.settings.recent_region = [region.x, region.y, region.width, region.height]
        self.settings.display_signature = topology_signature()
        self.persist()
        self.update_region()
        if self.selected_action in {"once", "live"}:
            self.queue_start(self.selected_action == "once")
        else:
            self.showNormal()

    def selection_cancelled(self) -> None:
        self.selector = None
        self.showNormal()
        self.notice("Selection cancelled. Your recent region is still available.")

    def once(self) -> None:
        if self.settings.region:
            self.stop()
            self.queue_start(True)
        else:
            self.select("once")

    def live(self) -> None:
        if self.settings.region:
            self.stop()
            self.queue_start(False)
        else:
            self.select("live")

    def queue_start(self, once: bool) -> None:
        serial = self.command_serial
        self.hide()
        self.overlay.hide()

        def begin() -> None:
            if not self.closing and serial == self.command_serial:
                self.start(once)

        QTimer.singleShot(180, begin)

    def credential_account(self, provider: str, endpoint: str) -> str:
        return provider + ":" + hashlib.sha256(endpoint.encode()).hexdigest()[:20]

    def provider_factory(self, settings: Settings) -> Callable[[], Any]:
        endpoint = validate_endpoint(
            settings.endpoint or SPECS[settings.provider].endpoint,
            SPECS[settings.provider].capabilities.local,
        )
        key = ""
        if SPECS[settings.provider].capabilities.requires_key or settings.provider in {
            "custom",
            "libre",
        }:
            key = self.credentials.get(self.credential_account(settings.provider, endpoint))
        return lambda: create_provider(settings.provider, key, endpoint, settings.timeout)

    def start(self, once: bool) -> None:
        if self.closing:
            return
        self.stop()
        try:
            if (
                self.settings.display_signature
                and self.settings.display_signature != topology_signature()
            ):
                self.display_changed()
                return
            if self.settings.ocr == "rapidocr" and not ModelManager().installed(
                self.settings.source
            ):
                self.showNormal()
                self.navigation.setCurrentRow(2)
                self.notice("Install recognition for your source language, then start again.")
                return
            spec = SPECS[self.settings.provider]
            if spec.capabilities.context and not self.settings.model:
                self.showNormal()
                self.navigation.setCurrentRow(1)
                self.notice("Test your provider and choose a model first.")
                return
            snapshot = copy.deepcopy(self.settings)
            if snapshot.region and not self.overlay.avoid_capture(snapshot.region) and not once:
                self.showNormal()
                self.notice(
                    "The region leaves no room for the overlay. Select a smaller area or use one-shot translation."
                )
                return
            provider_factory = self.provider_factory(snapshot)
            self.pipeline = Pipeline(
                snapshot,
                lambda: MSSCapture(snapshot.display_signature),
                lambda: IsolatedOCR(snapshot.ocr, snapshot.source),
                provider_factory,
                once,
            )
            self.pipeline.start()
            self.overlay.status.setText("DESKTRANSLATE  /  STARTING")
            if not self.overlay.suppressed:
                self.overlay.show()
        except (DeskTranslateError, ValueError) as error:
            self.showNormal()
            self.notice(str(error))

    def stop(self) -> None:
        self.command_serial += 1
        if self.pipeline:
            self.pipeline.stop()
            self.pipeline = None
        if hasattr(self, "status_label"):
            self.status_label.setText("Ready when you are.")
        if hasattr(self, "overlay"):
            self.overlay.status.setText("DESKTRANSLATE  /  STOPPED")
            self.overlay.capture_region = None
            self.overlay.suppressed = False

    def pause(self) -> None:
        if self.pipeline:
            if self.pipeline.session.state == SessionState.ERROR:
                self.start(self.pipeline.once)
            elif self.pipeline.paused.is_set():
                self.pipeline.resume()
            else:
                self.pipeline.pause()

    def clear_context(self) -> None:
        if self.pipeline:
            self.pipeline.clear_context()
        self.notice("Dialogue context cleared.")

    def poll_pipeline(self) -> None:
        if not self.pipeline:
            return
        for event in self.pipeline.poll():
            self.status_label.setText(event.error or event.state.value.capitalize())
            self.overlay.status.setText("DESKTRANSLATE  /  " + event.state.value.upper())
            self.overlay.pause_button.setText(
                "Resume" if event.state in {SessionState.PAUSED, SessionState.ERROR} else "Pause"
            )
            if event.clear:

                def clear_if_current(stamp: Stamp = event.stamp) -> None:
                    if self.pipeline and self.pipeline.session.current(stamp):
                        self.overlay.hide()

                QTimer.singleShot(1000, clear_if_current)
            if event.result:
                start = time.perf_counter()
                self.latest = event.result.text
                self.result_source.setText(event.source)
                self.result_translation.setText(event.result.text)
                self.overlay.display(event.source, event.result.text)
                if self.overlay.suppressed:
                    self.showNormal()
                self.timings = {**event.timings, "overlay_ms": (time.perf_counter() - start) * 1000}
                self.status_label.setText(
                    f"Translated · {event.timings.get('total_ms', 0):.0f} ms"
                    + (" · cached" if event.result.cached else "")
                )
            if event.category:
                self.errors = (self.errors + [event.category])[-10:]
                self.showNormal()
                self.notice(event.error)

    def display_changed(self, *args: object) -> None:
        self.stop()
        if self.selector:
            self.selector.cancel()
        self.settings.recent_region = None
        self.persist()
        self.update_region()
        self.notice("Display layout or scaling changed. Select your region again.")

    def toggle_overlay(self) -> None:
        if (
            self.pipeline
            and self.settings.region
            and not self.overlay.avoid_capture(self.settings.region)
        ):
            self.notice(
                "The overlay cannot fit outside this region. Use a smaller region or stop first."
            )
            return
        self.overlay.setVisible(not self.overlay.isVisible())

    def copy_latest(self) -> None:
        QApplication.clipboard().setText(self.latest)
        self.statusBar().showMessage(
            "Translation copied." if self.latest else "Translate some text first.", 4000
        )

    def provider_changed(self) -> None:
        self.stop()
        self.key_edit.clear()
        selected = self.provider_combo.currentData()
        self.last_provider = selected
        self.endpoint_edit.setText(self.settings.provider_endpoints.get(selected, ""))
        self.model_combo.clear()
        self.model_combo.addItem(self.settings.provider_models.get(selected, ""))
        self.update_provider_info()

    def update_provider_info(self) -> None:
        selected = self.provider_combo.currentData()
        spec = SPECS[selected]
        custom = selected in {"custom", "libre", "deepl"}
        self.endpoint_edit.setVisible(custom)
        self.key_edit.setVisible(spec.capabilities.requires_key or selected in {"custom", "libre"})
        self.model_combo.setVisible(spec.capabilities.model_discovery)
        if spec.capabilities.local:
            text = "Local · recognized text stays on this machine. Start the server and load a model, then test. No large models are downloaded automatically."
        elif selected in {"custom", "libre"}:
            text = "Your endpoint determines privacy: localhost stays local; remote HTTPS sends recognized text to that server."
        else:
            text = "Cloud · recognized text is sent to this provider. AI APIs may charge usage fees. Screenshots stay on your machine."
        if selected == "google":
            text += " Quick translation uses Google's public web endpoint; availability is not guaranteed. DeepL is the supported API alternative."
        self.provider_info.setText(text)
        active = self.settings.provider
        active_spec = SPECS[active]
        local = active_spec.capabilities.local or (
            (active in {"libre", "custom"})
            and self.settings.endpoint.startswith(
                ("http://localhost", "http://127.0.0.1", "http://[::1]")
            )
        )
        self.privacy_label.setText(
            (
                "Local · text stays on this machine.  "
                if local
                else "Cloud · only recognized text is sent to the provider.  "
            )
            + active_spec.name
        )

    def save_provider(self) -> bool:
        self.stop()
        try:
            selected = self.provider_combo.currentData()
            spec = SPECS[selected]
            endpoint = validate_endpoint(
                (self.endpoint_edit.text() if selected in {"custom", "libre", "deepl"} else "")
                or spec.endpoint,
                spec.capabilities.local,
            )
            glossary = {}
            for line in self.glossary_edit.toPlainText().splitlines():
                if line.strip():
                    key, sep, value = line.partition("=")
                    if not sep or not key.strip() or not value.strip():
                        raise ValueError("Use source = translation on each glossary line.")
                    glossary[key.strip()] = value.strip()
            updated = copy.deepcopy(self.settings)
            updated.provider = selected
            updated.endpoint = endpoint
            updated.model = self.model_combo.currentText().strip()
            updated.provider_models[selected] = updated.model
            updated.provider_endpoints[selected] = endpoint
            updated.style = self.style_combo.currentData()
            updated.instructions = self.instructions_edit.toPlainText().strip()
            updated.glossary = glossary
            updated.validate()
            if self.key_edit.text().strip():
                self.credentials.set(
                    self.credential_account(selected, endpoint), self.key_edit.text().strip()
                )
                self.key_edit.clear()
            self.settings = updated
            self.persist()
            self.update_provider_info()
            self.notice("Translation settings applied.")
            return True
        except (DeskTranslateError, ValueError) as error:
            self.notice(str(error))
            return False

    def test_provider(self) -> None:
        if not self.save_provider():
            return
        try:
            factory = self.provider_factory(copy.deepcopy(self.settings))
        except DeskTranslateError as error:
            self.provider_status.setText(str(error))
            return
        selected = self.settings.provider
        self.provider_status.setText("Connecting…")

        def operation() -> object:
            provider = factory()
            try:
                if provider.capabilities.model_discovery:
                    return provider.models()
                provider.translate(TranslationRequest("Hello", "en", self.settings.target))
                return []
            finally:
                provider.close()

        def complete(result: object, error: str) -> None:
            if self.provider_combo.currentData() != selected:
                return
            self.provider_status.setText(
                error or "Connected. Choose a model below if you're using AI."
            )
            if not error:
                current = self.model_combo.currentText()
                self.model_combo.clear()
                for model in result if isinstance(result, list) else []:
                    self.model_combo.addItem(model.id)
                    detail = f"{model.name}\nContext: {model.context_length or 'unknown'}\nInput/output price per token: {model.input_price or 'unknown'} / {model.output_price or 'unknown'}"
                    if model.size_bytes:
                        detail += f"\nOn disk: {model.size_bytes / 1e9:.1f} GB"
                    self.model_combo.setItemData(
                        self.model_combo.count() - 1, detail, Qt.ItemDataRole.ToolTipRole
                    )
                if current:
                    self.model_combo.setCurrentText(current)
                self.provider_status.setText(
                    f"Connected · {self.model_combo.count()} models available."
                    if result
                    else "Connected. No model selection needed, or no local models installed yet."
                )

        self.job(operation, complete)

    def open_provider_site(self) -> None:
        url = SPECS[self.provider_combo.currentData()].key_url or "https://translate.google.com"
        QDesktopServices.openUrl(QUrl(url))

    def delete_key(self) -> None:
        try:
            provider = self.provider_combo.currentData()
            endpoint = validate_endpoint(self.endpoint_edit.text() or SPECS[provider].endpoint)
            self.credentials.delete(self.credential_account(provider, endpoint))
            self.key_edit.clear()
            self.provider_status.setText("Saved key deleted.")
        except DeskTranslateError as error:
            self.provider_status.setText(str(error))

    def detect_local(self) -> None:
        def operation() -> object:
            found = []
            for name in ("ollama", "lmstudio"):
                provider = create_provider(name, timeout=3)
                try:
                    models = provider.models()
                    found.append(f"{SPECS[name].name}: running · {len(models)} models")
                except DeskTranslateError:
                    import shutil

                    installed = shutil.which("ollama") if name == "ollama" else None
                    found.append(
                        f"{SPECS[name].name}: {'installed but not reachable' if installed else 'not reachable'} · start the server and load a model"
                    )
                finally:
                    provider.close()
            return "\n".join(found)

        self.job(
            operation, lambda result, error: self.provider_status.setText(error or str(result))
        )

    def update_ocr_status(self) -> None:
        installed = ModelManager().installed(self.settings.source)
        self.ocr_status.setText(
            f"{self.source_combo.currentText()} recognition · "
            + ("installed" if installed else "ready to install")
        )

    def install_models(self) -> None:
        self.stop()
        language = self.settings.source
        manager = ModelManager()
        self.progress.show()
        self.progress.setValue(0)
        self.ocr_status.setText("Downloading verified recognition models…")

        def complete(result: object, error: str) -> None:
            self.progress.hide()
            self.update_ocr_status()
            if error:
                self.ocr_status.setText(error)
            self.notice(error or "Recognition is ready. Select a region and translate.")

        self.job(
            lambda: manager.install(language, self.jobs.cancel, self.jobs.progress.emit), complete
        )

    def download_progress(self, model: str, downloaded: int, total: int) -> None:
        self.progress.setRange(0, 100 if total else 0)
        if total:
            self.progress.setValue(int(downloaded / total * 100))
        self.ocr_status.setText(
            f"Preparing {model} · {downloaded / 1e6:.1f} MB"
            + (f" / {total / 1e6:.1f} MB" if total else "")
        )

    def save_recognition(self) -> None:
        self.stop()
        self.settings.ocr = self.ocr_combo.currentData()
        self.settings.quality = self.quality_combo.currentData()
        self.settings.preprocessing = self.preprocess_combo.currentData()
        self.settings.vertical = self.vertical_check.isChecked()
        self.persist()
        self.notice("Recognition settings applied.")

    def save_appearance(self) -> None:
        try:
            updated = copy.deepcopy(self.settings)
            self.overlay_editor.apply_to(updated)
            self.settings = updated
        except ValueError as error:
            self.notice(str(error))
            return
        self.settings.overlay_mode = self.overlay_mode_combo.currentData()
        self.settings.overlay_size = self.font_spin.value()
        self.settings.overlay_opacity = self.opacity_spin.value()
        self.settings.overlay_click_through = self.click_check.isChecked()
        self.settings.theme = self.theme_combo.currentData()
        self.persist()
        apply_theme(QApplication.instance(), self.settings.theme)  # type: ignore[arg-type]
        self.overlay.configure(self.settings)
        if not self.pipeline:
            self.overlay.display("明日、またここで会おう。", "Let's meet here again tomorrow.")

    def apply_overlay_preset(self) -> None:
        from desktranslate.ui.subtitles import PRESETS

        preset = PRESETS[self.overlay_editor.presets.currentText()]
        if "overlay_size" in preset:
            self.font_spin.setValue(int(str(preset["overlay_size"])))
        self.save_appearance()

    def edit_overlay(self) -> None:
        if not self.overlay.editing and self.pipeline and not self.pipeline.paused.is_set():
            self.pipeline.pause()
        self.overlay.toggle_edit()
        self.notice(
            "Edit with drag and resize. Ctrl + Alt + E finishes editing; resume translation when ready."
        )

    def save_overlay_geometry(self, geometry: list[int]) -> None:
        self.settings.overlay_geometry = geometry
        self.persist()

    def save_preferences(self) -> None:
        try:
            values = {key: edit.text().strip() for key, edit in self.hotkey_edits.items()}
            validate_hotkeys(values)
            conflicts = self.hotkeys.register(values)
            self.settings.hotkeys = values
            self.settings.close_to_tray = self.tray_check.isChecked()
            self.persist()
            self.notice(
                "Unavailable shortcuts: " + ", ".join(conflicts)
                if conflicts
                else "Preferences applied."
            )
            self.shortcut_hint.setText(
                f"{values['once']} · Translate anywhere     {values['pause']} · Pause live"
            )
        except ValueError as error:
            self.notice(str(error))

    def save_profile(self) -> None:
        name, accepted = QInputDialog.getText(self, "Save profile", "Profile name")
        if accepted and name.strip():
            keys = (
                "source",
                "target",
                "provider",
                "endpoint",
                "model",
                "ocr",
                "quality",
                "style",
                "instructions",
                "glossary",
                "preprocessing",
                "vertical",
                "recent_region",
                "display_signature",
                "overlay_mode",
                "overlay_size",
                "overlay_opacity",
            )
            self.settings.profiles[name.strip()[:60]] = {
                key: copy.deepcopy(getattr(self.settings, key))
                for key in set(keys)
                | {f.name for f in fields(Settings) if f.name.startswith("overlay_")}
            }
            self.persist()
            self.profile_combo.clear()
            self.profile_combo.addItems(list(self.settings.profiles))

    def load_profile(self) -> None:
        values = self.settings.profiles.get(self.profile_combo.currentText())
        if values:
            updated = copy.deepcopy(self.settings)
            allowed = {
                "source",
                "target",
                "provider",
                "endpoint",
                "model",
                "ocr",
                "quality",
                "style",
                "instructions",
                "glossary",
                "preprocessing",
                "vertical",
                "recent_region",
                "display_signature",
                "overlay_mode",
                "overlay_size",
                "overlay_opacity",
            }
            allowed |= {f.name for f in fields(Settings) if f.name.startswith("overlay_")}
            try:
                for key, value in values.items():
                    if key in allowed:
                        setattr(updated, key, copy.deepcopy(value))
                updated.validate()
                self.settings = updated
                self.stop()
                self.persist()
                self.sync_controls()
                self.notice("Profile loaded.")
            except (ValueError, TypeError, AttributeError):
                self.notice("This profile is invalid. Delete it and save a new one.")

    def delete_profile(self) -> None:
        self.settings.profiles.pop(self.profile_combo.currentText(), None)
        self.persist()
        self.profile_combo.clear()
        self.profile_combo.addItems(list(self.settings.profiles))

    def sync_controls(self) -> None:
        pairs = [
            (self.source_combo, self.settings.source),
            (self.target_combo, self.settings.target),
            (self.provider_combo, self.settings.provider),
            (self.ocr_combo, self.settings.ocr),
            (self.quality_combo, self.settings.quality),
            (self.style_combo, self.settings.style),
            (self.preprocess_combo, self.settings.preprocessing),
            (self.overlay_mode_combo, self.settings.overlay_mode),
            (self.theme_combo, self.settings.theme),
        ]
        for widget, value in pairs:
            widget.blockSignals(True)
            widget.setCurrentIndex(widget.findData(value))
            widget.blockSignals(False)
        self.endpoint_edit.setText(self.settings.endpoint)
        self.model_combo.setCurrentText(self.settings.model)
        self.glossary_edit.setPlainText(
            "\n".join(f"{key} = {value}" for key, value in self.settings.glossary.items())
        )
        self.instructions_edit.setPlainText(self.settings.instructions)
        self.vertical_check.setChecked(self.settings.vertical)
        self.click_check.setChecked(self.settings.overlay_click_through)
        self.font_spin.setValue(self.settings.overlay_size)
        self.opacity_spin.setValue(self.settings.overlay_opacity)
        self.tray_check.setChecked(self.settings.close_to_tray)
        for key, edit in self.hotkey_edits.items():
            edit.setText(self.settings.hotkeys[key])
        self.hotkeys.register(self.settings.hotkeys)
        self.update_provider_info()
        self.update_region()
        self.update_ocr_status()
        self.overlay.configure(self.settings)
        apply_theme(QApplication.instance(), self.settings.theme)  # type: ignore[arg-type]
        self.overlay_editor.sync(self.settings)

    def reset(self) -> None:
        if (
            QMessageBox.question(
                self,
                "Reset settings",
                "Restore default settings? Saved provider keys stay in secure storage.",
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.stop()
            self.settings = Settings(onboarding_done=True)
            self.persist()
            self.sync_controls()

    def refresh_diagnostics(self) -> None:
        monitors = {name: asdict(region) for name, region in physical_monitors().items()}
        data = {
            "version": __version__,
            "os": platform.system(),
            "os_release": platform.release(),
            "python": platform.python_version(),
            "packaged": bool(getattr(sys, "frozen", False)),
            "capture": "mss",
            "displays_physical": monitors,
            "displays_qt": [
                {"name": s.name(), "dpi": s.logicalDotsPerInch(), "scale": s.devicePixelRatio()}
                for s in QApplication.screens()
            ],
            "ocr": self.settings.ocr,
            "ocr_installed": [
                lang.code for lang in LANGUAGES if ModelManager().installed(lang.code)
            ],
            "provider": self.settings.provider,
            "model": self.settings.model,
            "timings_ms": self.timings,
            "recent_error_categories": self.errors,
            "counters": self.pipeline.counters if self.pipeline else {},
        }
        self.diagnostics_text.setPlainText(json.dumps(data, indent=2, ensure_ascii=False))

    def copy_diagnostics(self) -> None:
        self.refresh_diagnostics()
        QApplication.clipboard().setText(self.diagnostics_text.toPlainText())

    def check_updates(self) -> None:
        from desktranslate.updates import check_release

        def complete(result: object, error: str) -> None:
            if error:
                self.notice(error)
            elif isinstance(result, tuple) and len(result) == 2:
                tag, url = result
                self.notice(f"Latest stable release: {tag}. Opening its release notes.")
                QDesktopServices.openUrl(QUrl(url))
            else:
                self.notice("No newer stable release was found.")

        self.job(check_release, complete)

    def onboarding(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Welcome to DeskTranslate 2")
        dialog.setMinimumWidth(560)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)
        layout.addWidget(label("A world of words.\nOne simple shortcut.", "title"))
        layout.addWidget(
            label(
                "Select the dialogue, subtitle, menu, or image you want to understand. DeskTranslate reads it on your machine and puts the translation in a quiet overlay.",
                "muted",
            )
        )
        source = language_combo(self.settings.source, True)
        target = language_combo(self.settings.target)
        form = QFormLayout()
        form.addRow("Read", source)
        form.addRow("Translate into", target)
        layout.addLayout(form)
        method = combo(
            [
                ("Quick translation · cloud · no API key", "google"),
                ("Local AI · configure Ollama / LM Studio next", "ollama"),
                ("Cloud AI · choose a provider next", "openai"),
            ],
            "google",
        )
        layout.addWidget(method)
        from desktranslate.hardware import recommendation

        layout.addWidget(label(recommendation(), "muted"))
        layout.addWidget(
            label(
                "Cloud translation sends recognized text to your chosen provider. Screenshots are never uploaded. Local AI keeps text on this machine. Nothing is saved to history and there is no telemetry.",
                "muted",
            )
        )
        layout.addWidget(
            label(
                f"Next: install small recognition models, then press {self.settings.hotkeys['once']}. Drag a region and press Enter. Escape cancels.",
                "muted",
            )
        )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Set up recognition")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings.source = source.currentData() or "ja"
            self.settings.target = target.currentData() or "en"
            self.settings.provider = method.currentData()
            self.settings.onboarding_done = True
            self.persist()
            self.sync_controls()
            self.navigation.setCurrentRow(2)

    def quit(self) -> None:
        self.closing = True
        self.stop()
        self.jobs.cancel.set()
        self.hotkeys.close()
        if self.selector:
            self.selector.cleanup()
        self.overlay.close()
        self.tray.hide()
        QApplication.instance().quit()  # type: ignore[union-attr]

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.settings.close_to_tray and self.tray.isVisible() and not self.closing:
            self.hide()
            event.ignore()
        else:
            self.quit()
            event.accept()

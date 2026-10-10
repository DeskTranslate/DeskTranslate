from __future__ import annotations

import copy
import hashlib
import time
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
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

from desktranslate.capture import MSSCapture, physical_monitors, topology_signature
from desktranslate.errors import DeskTranslateError
from desktranslate.hotkeys import Hotkeys, validate_hotkeys
from desktranslate.languages import LANGUAGES
from desktranslate.metrics import LatencyMetrics
from desktranslate.models import PipelineEvent, Rect, SessionState, Stamp, TranslationRequest
from desktranslate.ocr import IsolatedOCR, ModelManager
from desktranslate.pipeline import Pipeline
from desktranslate.providers import SPECS, create_provider
from desktranslate.security import CredentialStore, validate_endpoint
from desktranslate.settings import Settings, SettingsStore
from desktranslate.ui.glossary import editor_content, exchange_controls, parse_editor
from desktranslate.ui.jobs import Jobs
from desktranslate.ui.onboarding import Onboarding
from desktranslate.ui.overlay import Overlay
from desktranslate.ui.overlay_editor import OverlayEditor
from desktranslate.ui.selection import RegionSelector
from desktranslate.ui.theme import apply_theme, icon
from desktranslate.window_capture import (
    Win32Windows,
    WindowCapture,
    normalized_region,
    project_region,
)


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
    widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    widget.setMinimumContentsLength(12)
    for name, value in options:
        widget.addItem(name, value)
    widget.setCurrentIndex(max(0, widget.findData(current)))
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
        self.retiring: list[Pipeline] = []
        self.presentation_serial = 0
        self.selector: RegionSelector | None = None
        self.latest = ""
        self.errors: list[str] = []
        self.timings: dict[str, float] = {}
        self.metrics = LatencyMetrics()
        self.closing = False
        self.exit_code = 0
        self.setup_dialog: Onboarding
        self.command_serial = 0
        self.selected_action = "select"
        self.relative_selection = False
        self.last_provider = self.settings.provider
        self.jobs = Jobs()
        self.callbacks: dict[int, Callable[[object, str], None]] = {}
        self.jobs.done.connect(self.job_done, Qt.ConnectionType.QueuedConnection)
        self.jobs.progress.connect(self.download_progress, Qt.ConnectionType.QueuedConnection)
        self.setWindowTitle("DeskTranslate 2")
        self.setWindowIcon(icon())
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1000, available.width() - 40), min(800, available.height() - 40))
        self.setMinimumSize(min(720, available.width() - 40), min(420, available.height() - 40))
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
            [
                "Translate",
                "Providers",
                "Recognition",
                "Appearance",
                "Profiles",
                "Preferences",
                "Session",
                "Diagnostics",
            ]
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
        self.build_profiles()
        self.build_preferences()
        self.build_transcript()
        self.build_diagnostics()
        for control in self.findChildren(QComboBox):
            control.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            control.setMinimumContentsLength(12)
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
                "select": lambda: self.select("select", self.settings.capture_mode == "window"),
                "overlay": self.toggle_overlay,
                "copy": self.copy_latest,
                "edit": self.edit_overlay,
            },
            self.suspend,
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
        if not demo and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.update_region()
        self.update_provider_info()
        self.update_ocr_status()
        for screen in QApplication.screens():
            screen.geometryChanged.connect(self.display_changed)
            screen.logicalDotsPerInchChanged.connect(self.display_changed)
            screen.setProperty("desktranslate_connected", True)
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
        swap = button("⇄", self.swap_languages)
        swap.setAccessibleName("Swap source and translation languages")
        row.addWidget(swap)
        row.addWidget(self.target_combo, 1)
        layout.addLayout(row)
        targets = QHBoxLayout()
        targets.addWidget(button("Choose application", self.choose_window))
        targets.addWidget(button("Choose monitor", self.choose_monitor))
        layout.addLayout(targets)
        self.window_crop_button = button(
            "Region inside application", lambda: self.select("select", True)
        )
        layout.addWidget(self.window_crop_button)
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
        self.provider_combo.setAccessibleName("Translation provider")
        layout.addWidget(self.provider_combo)
        self.provider_info = label("", "muted")
        layout.addWidget(self.provider_info)
        self.endpoint_edit = QLineEdit(self.settings.endpoint)
        self.endpoint_edit.setPlaceholderText("API base URL · HTTPS or localhost")
        self.endpoint_edit.setAccessibleName("API endpoint")
        self.provider_advanced = QCheckBox("Advanced connection settings")
        layout.addWidget(self.provider_advanced)
        self.advanced_box = QWidget()
        advanced_layout = QVBoxLayout(self.advanced_box)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.addWidget(self.endpoint_edit)
        self.openai_api_combo = combo(
            [
                ("Responses · recommended", "responses"),
                ("Chat Completions · compatibility", "chat"),
            ],
            self.settings.openai_api,
        )
        self.openai_api_combo.setAccessibleName("OpenAI API mode")
        advanced_layout.addWidget(self.openai_api_combo)
        layout.addWidget(self.advanced_box)
        self.advanced_box.hide()
        self.provider_advanced.toggled.connect(self.advanced_box.setVisible)
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
        self.instructions_edit.setAccessibleName("Optional custom translation style instructions")
        layout.addWidget(self.instructions_edit)
        self.glossary_edit = QPlainTextEdit(editor_content(self.settings.glossary))
        self.glossary_edit.setPlaceholderText(
            "Optional glossary · one source = translation per line"
        )
        self.glossary_edit.setMaximumHeight(100)
        self.glossary_edit.setAccessibleName("Optional dialogue glossary")
        layout.addWidget(self.glossary_edit)
        layout.addLayout(exchange_controls(self.glossary_edit, self.notice))
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
        self.ocr_combo.setAccessibleName("Recognition engine")
        self.style_combo.setAccessibleName("Dialogue translation style")
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
        self.update_channel_combo = combo(
            [("Stable releases", "stable"), ("Beta and release candidates", "beta")],
            self.settings.update_channel,
        )
        self.update_channel_combo.setAccessibleName("Update channel")
        layout.addWidget(self.update_channel_combo)
        self.restart_target_check = QCheckBox(
            "Reconnect to the same application after it restarts · exact unique window match required"
        )
        self.restart_target_check.setChecked(self.settings.window_follow_restart)
        layout.addWidget(self.restart_target_check)
        layout.addWidget(button("Guide me through a first translation", self.onboarding))
        layout.addWidget(button("Apply preferences", self.save_preferences, True))
        page.addWidget(frame)
        page.addWidget(button("Reset settings to defaults", self.reset))
        page.addStretch()

    def build_profiles(self) -> None:
        from desktranslate.ui.profiles import ProfilePage

        page = self.page(
            "A setup for every story.",
            "Keep each game's languages, dialogue style, capture target and overlay together.",
        )
        self.profile_page = ProfilePage(lambda: self.settings, self.commit_settings, self.notice)
        page.addWidget(self.profile_page)

    def commit_settings(self, updated: Settings, activate: bool = True) -> bool:
        try:
            self.store.save(updated)
        except (OSError, ValueError, TypeError, RecursionError):
            self.notice("Settings could not be saved. Check their size and file permissions.")
            return False
        if activate:
            self.stop()
        self.settings = updated
        if activate:
            self.sync_controls()
        return True

    def build_diagnostics(self) -> None:
        from desktranslate.ui.support import SupportPage

        page = self.page(
            "A clear view of the app.",
            "Preview privacy-safe support details before copying or exporting.",
        )
        self.support_page = SupportPage(self.diagnostic_metadata, self.check_updates, self.notice)
        self.diagnostics_text = self.support_page.preview
        page.addWidget(self.support_page)

    def build_transcript(self) -> None:
        from desktranslate.ui.transcript import TranscriptPage

        page = self.page(
            "Keep this conversation close.", "An optional, temporary transcript that you control."
        )
        self.transcript_page = TranscriptPage()
        page.addWidget(self.transcript_page)

    def diagnostic_metadata(self, include_model: bool = False) -> dict[str, Any]:
        from desktranslate.diagnostics import diagnostic_metadata

        displays = [
            {
                "name": screen.name(),
                "dpi": screen.logicalDotsPerInch(),
                "scale": screen.devicePixelRatio(),
            }
            for screen in QApplication.screens()
        ]
        return diagnostic_metadata(
            self.settings,
            self.metrics,
            self.errors,
            self.pipeline.counters if self.pipeline else {},
            displays,
            include_model,
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
        self.window_crop_button.setVisible(self.settings.capture_mode == "window")
        region = self.settings.region
        description = (
            f"Locked region · {region.width} × {region.height} px at ({region.x}, {region.y})"
            if region
            else "Select an area to translate."
        )
        if self.settings.capture_mode == "window":
            description = (
                "Following application · "
                + self.settings.window_target.get("executable", "")
                + (
                    " · selected client region"
                    if self.settings.window_region
                    else " · entire client area"
                )
            )
        elif self.settings.capture_mode == "monitor":
            description = "Entire monitor · " + self.settings.monitor_name
        self.region_label.setText(description)

    def choose_window(self) -> None:
        from desktranslate.ui.capture_picker import WindowPicker

        self.stop()
        try:
            windows = Win32Windows().windows()
            picker = WindowPicker(windows, self)
            if picker.exec() == QDialog.DialogCode.Accepted and (target := picker.chosen()):
                self.settings.capture_mode = "window"
                self.settings.window_target = target.binding()
                self.settings.window_region = None
                self.settings.recent_region = [
                    target.client.x,
                    target.client.y,
                    target.client.width,
                    target.client.height,
                ]
                self.settings.display_signature = ""
                self.persist()
                self.update_region()
                self.notice(
                    "Application selected. Choose a region inside it for faster subtitle recognition."
                )
        except DeskTranslateError as error:
            self.notice(str(error))

    def choose_monitor(self) -> None:
        monitors = physical_monitors()
        name, accepted = QInputDialog.getItem(
            self, "Choose monitor", "Capture the entire display", list(monitors), editable=False
        )
        if accepted and name in monitors:
            self.stop()
            region = monitors[name]
            self.settings.capture_mode = "monitor"
            self.settings.monitor_name = name
            self.settings.recent_region = [region.x, region.y, region.width, region.height]
            self.settings.display_signature = topology_signature()
            self.persist()
            self.update_region()
            self.notice(
                "Monitor selected. One-shot results appear in the main window when no safe overlay space remains."
            )

    def select(self, action: str = "select", relative: bool = False) -> None:
        if self.selector:
            return
        if relative and not self.settings.window_target:
            self.notice("Choose an application first, then select a region inside it.")
            return
        self.stop()
        self.relative_selection = relative
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
        if self.relative_selection:
            probe = None
            try:
                probe = WindowCapture(self.settings.window_target, None)
                target = probe.resolve()
                self.settings.window_region = normalized_region(target.client, region)
                self.settings.capture_mode = "window"
            except (DeskTranslateError, ValueError) as error:
                self.showNormal()
                self.notice(str(error))
                return
            finally:
                if probe:
                    probe.close()
        else:
            self.settings.capture_mode = "fixed"
        self.settings.recent_region = [region.x, region.y, region.width, region.height]
        self.settings.display_signature = (
            "" if self.settings.capture_mode == "window" else topology_signature()
        )
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

    def queue_start(self, once: bool, focus_on_error: bool = True) -> None:
        serial = self.command_serial
        self.hide()
        self.overlay.hide()

        def begin() -> None:
            if not self.closing and serial == self.command_serial:
                if focus_on_error:
                    self.start(once)
                else:
                    self.start(once, False)

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
        return lambda: create_provider(
            settings.provider, key, endpoint, settings.timeout, openai_api=settings.openai_api
        )

    def start(self, once: bool, focus_on_error: bool = True) -> None:
        if self.closing:
            return
        self.stop()
        if len(self.retiring) >= 4:
            self.notice("Previous requests are still stopping. Wait a moment, then start again.")
            return
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
                if focus_on_error:
                    self.showNormal()
                self.navigation.setCurrentRow(2)
                self.notice("Install recognition for your source language, then start again.")
                return
            spec = SPECS[self.settings.provider]
            if spec.capabilities.context and not self.settings.model:
                if focus_on_error:
                    self.showNormal()
                self.navigation.setCurrentRow(1)
                self.notice("Test your provider and choose a model first.")
                return
            snapshot = copy.deepcopy(self.settings)
            if snapshot.capture_mode == "window":
                probe = WindowCapture(
                    snapshot.window_target, snapshot.window_region, snapshot.window_follow_restart
                )
                try:
                    actual = project_region(probe.resolve().client, snapshot.window_region)
                    snapshot.recent_region = [actual.x, actual.y, actual.width, actual.height]
                finally:
                    probe.close()
            if snapshot.region and not self.overlay.avoid_capture(snapshot.region) and not once:
                if focus_on_error:
                    self.showNormal()
                self.notice(
                    "The region leaves no room for the overlay. Select a smaller area or use one-shot translation."
                )
                return
            provider_factory = self.provider_factory(snapshot)
            self.pipeline = Pipeline(
                snapshot,
                lambda: (
                    WindowCapture(
                        snapshot.window_target,
                        snapshot.window_region,
                        snapshot.window_follow_restart,
                    )
                    if snapshot.capture_mode == "window"
                    else MSSCapture(snapshot.display_signature)
                ),
                lambda: IsolatedOCR(snapshot.ocr, snapshot.source),
                provider_factory,
                once,
            )
            self.pipeline.start()
            self.overlay.status.setText("DESKTRANSLATE  /  STARTING")
            if not self.overlay.suppressed:
                self.overlay.show()
        except (DeskTranslateError, ValueError) as error:
            if focus_on_error:
                self.showNormal()
            self.notice(str(error))

    def stop(self) -> None:
        self.command_serial += 1
        self.presentation_serial += 1
        if hasattr(self, "transcript_page"):
            self.transcript_page.clear()
        if self.pipeline:
            self.pipeline.stop()
            self.retiring.append(self.pipeline)
            self.pipeline = None
        self.retiring = [p for p in self.retiring if any(t.is_alive() for t in p.threads)]
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
        self.retiring = [p for p in self.retiring if any(t.is_alive() for t in p.threads)]
        pipeline = self.pipeline
        if pipeline is None:
            return
        for event in pipeline.poll():
            with pipeline.session.lock:
                if event.stamp != Stamp(pipeline.session.serial, pipeline.session.generation):
                    continue
                self.handle_pipeline_event(event)

    def handle_pipeline_event(self, event: PipelineEvent) -> None:
        if event.region:
            self.overlay.avoid_capture(event.region)
        self.status_label.setText(event.error or event.state.value.capitalize())
        self.overlay.status.setText("DESKTRANSLATE  /  " + event.state.value.upper())
        self.overlay.pause_button.setText(
            "Resume" if event.state in {SessionState.PAUSED, SessionState.ERROR} else "Pause"
        )
        if event.clear:
            revision = self.presentation_serial

            def clear_if_current(stamp: Stamp = event.stamp, expected: int = revision) -> None:
                if (
                    self.pipeline
                    and self.pipeline.session.current(stamp)
                    and self.presentation_serial == expected
                ):
                    self.overlay.hide()

            QTimer.singleShot(1000, clear_if_current)
        if event.result:
            self.presentation_serial += 1
            start = time.perf_counter()
            self.latest = event.result.text
            self.result_source.setText(event.source)
            self.result_translation.setText(event.result.text)
            self.transcript_page.append(event.source, event.result.text)
            self.overlay.display(event.source, event.result.text)
            if self.overlay.suppressed:
                self.showNormal()
            self.timings = {
                **event.timings,
                "gui_delivery_ms": (time.monotonic() - event.created) * 1000,
                "overlay_schedule_ms": (time.perf_counter() - start) * 1000,
            }
            self.metrics.observe(self.timings)
            if not self.settings.onboarding_done:
                self.settings.onboarding_done = True
                self.persist()
            self.status_label.setText(
                f"Translated · {event.timings.get('total_ms', 0):.0f} ms"
                + (" · cached" if event.result.cached else "")
            )
        if event.category:
            self.errors = (self.errors + [event.category])[-10:]
            self.notice(event.error)
            self.overlay.status.setText("DESKTRANSLATE  /  PAUSED · " + event.error)
            if self.tray.isVisible():
                self.tray.showMessage(
                    "Translation paused", event.error, QSystemTrayIcon.MessageIcon.Warning, 5000
                )

    def display_changed(self, *args: object) -> None:
        follow_window = self.settings.capture_mode == "window"
        was_running = self.pipeline is not None and not self.pipeline.paused.is_set()
        once = self.pipeline.once if self.pipeline else False
        self.stop()
        if self.selector:
            self.selector.cancel()
        if not follow_window:
            self.settings.recent_region = None
        self.persist()
        self.update_region()
        self.overlay.place()
        for screen in QApplication.screens():
            if not screen.property("desktranslate_connected"):
                screen.geometryChanged.connect(self.display_changed)
                screen.logicalDotsPerInchChanged.connect(self.display_changed)
                screen.setProperty("desktranslate_connected", True)
        if follow_window and was_running:
            self.notice("Display changed. Revalidating the chosen application's client area.")
            self.queue_start(once, False)
        else:
            self.notice(
                "Display layout or scaling changed. Select your region again."
                if not follow_window
                else "Display changed. Start again when the chosen window is visible."
            )

    def suspend(self) -> None:
        self.stop()
        self.overlay.hide()
        self.notice(
            "Translation stopped while Windows sleeps. Start again after waking; dialogue context has been cleared."
        )

    def toggle_overlay(self) -> None:
        if (
            self.pipeline
            and self.pipeline.capture_region
            and not self.overlay.avoid_capture(self.pipeline.capture_region)
        ):
            self.notice(
                "The overlay cannot fit outside this region. Use a smaller region or stop first."
            )
            return
        self.overlay.toggle_visibility()

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
        self.openai_api_combo.setVisible(selected == "openai")
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
            glossary = parse_editor(self.glossary_edit.toPlainText())
            updated = copy.deepcopy(self.settings)
            updated.provider = selected
            updated.endpoint = endpoint
            updated.model = self.model_combo.currentText().strip()
            updated.openai_api = self.openai_api_combo.currentData()
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
        manager = ModelManager()
        required = manager.required(self.settings.source)
        installed = manager.installed(self.settings.source)
        estimated = sum(manager.catalog[model].get("bytes", 0) for model in required)
        size = (
            f" · {estimated / 1e6:.1f} MB full pack"
            if all(manager.catalog[model].get("bytes") for model in required)
            else " · download sizes shown during preparation"
        )
        self.ocr_status.setText(
            f"{self.source_combo.currentText()} recognition · "
            + ("installed · checked again on startup" if installed else "language pack needed")
            + size
            + " · CPU compatibility mode"
        )

    def install_models(self) -> None:
        if self.jobs.busy:
            self.notice("Wait for the current setup task, or cancel its download first.")
            return
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
            self.notice(
                error
                or (
                    "Recognition is ready. Select a region and translate."
                    if language == self.settings.source
                    else "The previously selected language pack is ready. Your current language has not changed."
                )
            )

        self.job(
            lambda: manager.install(language, self.jobs.cancel, self.jobs.progress.emit), complete
        )

    def download_progress(self, model: str, downloaded: int, total: int) -> None:
        self.progress.setRange(0, 100 if total else 0)
        if total:
            self.progress.setValue(int(downloaded / total * 100))
        if model.startswith("verifying:"):
            self.ocr_status.setText("Verifying the downloaded language pack…")
            return
        if model.startswith("installed:"):
            self.ocr_status.setText("Language pack verified. Finishing preparation…")
            return
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
            self.settings.update_channel = self.update_channel_combo.currentData()
            self.settings.window_follow_restart = self.restart_target_check.isChecked()
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
        self.glossary_edit.setPlainText(editor_content(self.settings.glossary))
        self.instructions_edit.setPlainText(self.settings.instructions)
        self.vertical_check.setChecked(self.settings.vertical)
        self.click_check.setChecked(self.settings.overlay_click_through)
        self.font_spin.setValue(self.settings.overlay_size)
        self.opacity_spin.setValue(self.settings.overlay_opacity)
        self.tray_check.setChecked(self.settings.close_to_tray)
        self.restart_target_check.setChecked(self.settings.window_follow_restart)
        self.update_channel_combo.setCurrentIndex(
            self.update_channel_combo.findData(self.settings.update_channel)
        )
        self.openai_api_combo.setCurrentIndex(
            self.openai_api_combo.findData(self.settings.openai_api)
        )
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
        self.support_page.refresh()

    def copy_diagnostics(self) -> None:
        self.support_page.copy()

    def check_updates(self) -> None:
        from desktranslate.updates import check_release

        def complete(result: object, error: str) -> None:
            if error:
                self.notice(error)
            elif isinstance(result, tuple) and len(result) == 2:
                tag, url = result
                self.notice(f"Update available: {tag}. Open release notes when ready.")
                self.support_page.update_url = url
                self.support_page.release_notes.setEnabled(True)
            else:
                self.notice("No newer compatible release was found in your chosen channel.")

        self.job(lambda: check_release(self.settings.update_channel, self.jobs.cancel), complete)

    def onboarding(self) -> None:
        if hasattr(self, "setup_dialog"):
            if self.setup_dialog.isVisible():
                self.setup_dialog.raise_()
                self.setup_dialog.activateWindow()
                return
            if self.setup_dialog.jobs.busy:
                self.notice(
                    "Setup is finishing its cancelled task. Reopen the guide when it has closed."
                )
                return
            self.setup_dialog.deleteLater()
        self.setup_dialog = Onboarding(
            lambda: self.settings, self.commit_settings, self.provider_factory, self
        )
        self.setup_dialog.show()

    def quit(self) -> None:
        if self.closing:
            return
        self.closing = True
        self.stop()
        self.timer.stop()
        self.jobs.cancel.set()
        if hasattr(self, "setup_dialog"):
            self.setup_dialog.reject()
        app = QApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self.hotkeys)
        self.hotkeys.close()
        if self.selector:
            self.selector.cleanup()
        self.overlay.close()
        self.tray.hide()
        # Keep the event loop responsive until native process handles are reaped.
        from threading import Thread

        def finish_workers() -> None:
            deadline = time.monotonic() + 35
            for pipeline in self.retiring:
                pipeline.wait_closed(max(0, deadline - time.monotonic()))
            self.jobs.wait_closed(max(0, deadline - time.monotonic()))
            if hasattr(self, "setup_dialog"):
                self.setup_dialog.jobs.wait_closed(max(0, deadline - time.monotonic()))

        worker = Thread(target=finish_workers, name="desktranslate-shutdown", daemon=True)
        worker.start()
        self.shutdown_timer = QTimer(self)

        def finish_shutdown() -> None:
            app = QApplication.instance()
            if app is not None and not worker.is_alive():
                self.shutdown_timer.stop()
                app.exit(self.exit_code)

        self.shutdown_timer.timeout.connect(finish_shutdown)
        self.shutdown_timer.start(50)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.settings.close_to_tray and self.tray.isVisible() and not self.closing:
            self.hide()
            event.ignore()
        else:
            self.quit()
            event.accept()

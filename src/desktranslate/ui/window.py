from __future__ import annotations

import copy
import hashlib
import html
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
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
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from desktranslate.capture import MSSCapture, physical_monitors, topology_signature
from desktranslate.errors import DeskTranslateError
from desktranslate.hotkeys import Hotkeys, validate_hotkeys
from desktranslate.languages import LANGUAGES, source_languages
from desktranslate.metrics import LatencyMetrics
from desktranslate.models import PipelineEvent, Rect, SessionState, Stamp, TranslationRequest
from desktranslate.ocr import IsolatedOCR, ModelManager
from desktranslate.pipeline import Pipeline
from desktranslate.presentation import session_presentation
from desktranslate.providers import SPECS, create_provider
from desktranslate.security import CredentialStore, is_loopback_endpoint, validate_endpoint
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


def language_combo(current: str, source: bool = False, engine: str = "rapidocr") -> QComboBox:
    widget = combo(
        [
            (language.name, language.code)
            for language in (source_languages(engine) if source else LANGUAGES)
            if language.code != "auto" or source
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


@dataclass(frozen=True)
class StartIntent:
    once: bool
    revision: int
    command: int


class MainWindow(QMainWindow):
    def __init__(self, store: SettingsStore, demo: bool = False) -> None:
        super().__init__()
        self.store = store
        self.settings = store.load()
        self.settings_revision = 0
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
        self.pending_start: StartIntent | None = None
        self.selected_action = "select"
        self.setup_suspended = False
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
        self.root_layout = root_layout
        root_layout.setContentsMargins(22, 24, 24, 16)
        root_layout.setSpacing(28)
        self.sidebar_widget = QWidget()
        sidebar = QVBoxLayout(self.sidebar_widget)
        sidebar.setContentsMargins(0, 0, 0, 0)
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
        sidebar.addWidget(label("No saved screenshots.\nNo app analytics.", "eyebrow"))
        root_layout.addWidget(self.sidebar_widget)
        self.compact_navigation = QComboBox()
        self.compact_navigation.addItems(
            [self.navigation.item(index).text() for index in range(self.navigation.count())]
        )
        self.compact_navigation.setAccessibleName("Navigation")
        self.compact_navigation.setToolTip("Choose a DeskTranslate page")
        root_layout.addWidget(self.compact_navigation)
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
        self.navigation.currentRowChanged.connect(self.compact_navigation.setCurrentIndex)
        self.compact_navigation.currentIndexChanged.connect(self.navigation.setCurrentRow)
        self.navigation.setCurrentRow(0)
        for form in self.findChildren(QFormLayout):
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.configure_navigation()
        self.overlay = Overlay(self.settings)
        self.overlay.pause_requested.connect(self.pause)
        self.overlay.geometry_changed.connect(self.save_overlay_geometry)
        self.overlay.edit_requested.connect(self.edit_overlay)
        self.display_relayout = QTimer(self)
        self.display_relayout.setSingleShot(True)
        self.display_relayout.setInterval(100)
        self.display_relayout.timeout.connect(self.overlay.place)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_pipeline)
        self.timer.setInterval(60)
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
            self.system_preferences_changed,
        )
        app.installNativeEventFilter(self.hotkeys)  # type: ignore[union-attr]
        if not demo and not self.hotkeys.watch_session(int(self.winId())):
            self.notice(
                "Windows session notifications are unavailable. Stop capture before locking or disconnecting this session."
            )
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
        self.tray_actions: dict[str, QAction] = {}
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
            self.tray_actions[title] = action
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
        self.refresh_session_view()
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
                "Settings could not be read. The original file is retained; temporary defaults are active. Review it or use Reset settings in Preferences to replace it."
            )
        if demo:
            self.result_source.setText("明日、またここで会おう。")
            self.result_translation.setText("Let's meet here again tomorrow.")
            self.status_label.setText("Preview · synthetic dialogue")
        elif not self.settings.onboarding_done and not store.recovered:
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
        self.source_combo = language_combo(self.settings.source, True, self.settings.ocr)
        self.target_combo = language_combo(self.settings.target)
        for control in (self.source_combo, self.target_combo):
            edit = control.lineEdit()
            if edit is not None:
                edit.editingFinished.connect(self.language_input_valid)
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
        self.live_button = button("Start live", self.live)
        row.addWidget(self.live_button)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.pause_button = button("Pause", self.pause)
        row.addWidget(self.pause_button)
        self.stop_button = button("Stop", self.stop)
        row.addWidget(self.stop_button)
        row.addWidget(button("Clear context", self.clear_context))
        layout.addLayout(row)
        self.privacy_label = label("", "muted")
        layout.addWidget(self.privacy_label)
        page.addWidget(frame)
        frame, layout = card("03  /  YOUR TRANSLATION")
        self.status_label = label("Ready when you are.", "muted")
        self.session_status = label("Ready · not capturing")
        self.session_status.setWordWrap(False)
        self.session_status.setAccessibleName("Capture and translation status")
        self.session_status.setMinimumWidth(0)
        self.session_status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.statusBar().addPermanentWidget(self.session_status, 1)
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
        self.return_setup_button = button("Return to first translation setup", self.resume_setup)
        self.return_setup_button.hide()
        page.addWidget(self.return_setup_button)
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
        self.test_button = button("Save and test connection", self.test_provider, True)
        row.addWidget(self.test_button)
        row.addWidget(button("Provider website", self.open_provider_site))
        row.addWidget(button("Delete saved key", self.delete_key))
        layout.addLayout(row)
        self.provider_status = label("No connection test yet.", "muted")
        layout.addWidget(self.provider_status)
        layout.addWidget(button("Find local AI servers", self.detect_local))
        layout.addWidget(button("Cancel setup task", self.cancel_setup))
        page.addWidget(frame)
        frame, layout = card("DIALOGUE & TERMINOLOGY")
        self.dialogue_options = QCheckBox("Customize dialogue and names · optional")
        layout.addWidget(self.dialogue_options)
        self.dialogue_box = QWidget()
        dialogue_layout = QVBoxLayout(self.dialogue_box)
        dialogue_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.dialogue_box)
        self.dialogue_options.toggled.connect(self.dialogue_box.setVisible)
        self.dialogue_box.hide()
        self.dialogue_options.setChecked(
            bool(
                self.settings.story_context
                or self.settings.glossary
                or self.settings.instructions
                or self.settings.style != "natural"
            )
        )
        outer_layout, layout = layout, dialogue_layout
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
        layout.addWidget(label("Story notes · optional, for contextual AI"))
        self.story_context_edit = QPlainTextEdit(self.settings.story_context)
        self.story_context_edit.setPlaceholderText(
            "Characters, pronouns and world background for this title. Up to 2,000 characters. Saved locally; shared only with your selected contextual provider."
        )
        self.story_context_edit.setAccessibleName("Optional story context for this title")
        self.story_context_edit.setMaximumHeight(95)
        layout.addWidget(self.story_context_edit)
        clear_story = button("Clear story notes", self.story_context_edit.clear)
        clear_story.setToolTip("Clears this draft. Apply translation settings to save it.")
        layout.addWidget(clear_story)
        self.glossary_edit = QPlainTextEdit(editor_content(self.settings.glossary))
        self.glossary_edit.setPlaceholderText(
            "Optional glossary · one source = translation per line"
        )
        self.glossary_edit.setMaximumHeight(100)
        self.glossary_edit.setAccessibleName("Optional dialogue glossary")
        layout.addWidget(self.glossary_edit)
        self.glossary_scope = label("", "muted")
        layout.addWidget(self.glossary_scope)
        layout.addLayout(exchange_controls(self.glossary_edit, self.notice))
        outer_layout.addWidget(button("Apply translation settings", self.save_provider))
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
        row.addWidget(button("Cancel download", self.cancel_setup))
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
        self.vertical_check = QCheckBox("Vertical columns · experimental")
        self.vertical_check.setToolTip(
            "Read columns from right to left. Managed models are optimized for horizontal text; vertical and stylized Japanese remain less accurate."
        )
        self.vertical_check.setChecked(self.settings.vertical)
        form.addRow("Performance", self.quality_combo)
        form.addRow("Image treatment", self.preprocess_combo)
        form.addRow(self.vertical_check)
        layout.addLayout(form)
        layout.addWidget(
            label(
                "For Japanese and Korean, choose the source language explicitly. Auto detection uses the Chinese / Latin model and is not universal. Vietnamese accents, stylized Japanese and vertical columns remain less accurate; try a smaller region or another preprocessing setting.",
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
        self.tray_check = QCheckBox("Close to the system tray")
        self.tray_check.setToolTip(
            "Closing the window keeps DeskTranslate running. Choose Quit from its tray menu to exit."
        )
        self.tray_check.setChecked(self.settings.close_to_tray)
        layout.addWidget(self.tray_check)
        self.update_channel_combo = combo(
            [("Stable releases", "stable"), ("Beta and release candidates", "beta")],
            self.settings.update_channel,
        )
        self.update_channel_combo.setAccessibleName("Update channel")
        layout.addWidget(self.update_channel_combo)
        self.restart_target_check = QCheckBox("Reconnect after application restart")
        self.restart_target_check.setToolTip(
            "Reconnect only when executable identity and title match exactly one window. Missing or ambiguous matches wait safely."
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

    def configure_navigation(self) -> None:
        compact = self.width() < 840
        focused = QApplication.focusWidget()
        restore_focus = focused is self.navigation or focused is self.compact_navigation
        self.sidebar_widget.setVisible(not compact)
        self.compact_navigation.setVisible(compact)
        self.root_layout.setDirection(
            QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
        )
        self.root_layout.setContentsMargins(*((8, 10, 8, 8) if compact else (22, 24, 24, 16)))
        self.root_layout.setSpacing(10 if compact else 28)
        if restore_focus:
            (self.compact_navigation if compact else self.navigation).setFocus()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, "compact_navigation"):
            self.configure_navigation()

    def commit_settings(self, updated: Settings, activate: bool = True) -> bool:
        try:
            self.store.save(updated)
        except (OSError, ValueError, TypeError, RecursionError):
            self.notice(
                "Settings could not be saved. The damaged original is retained; review it or Reset settings in Preferences."
                if self.store.recovered
                else "Settings could not be saved. Check their size and file permissions."
            )
            return False
        if activate:
            self.stop()
        elif self.pending_start:
            self.clear_start_intent()
            self.refresh_session_view()
        self.settings = updated
        self.settings_revision += 1
        if activate:
            self.sync_controls()
        elif hasattr(self, "glossary_scope"):
            self.update_provider_info()
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
        if self.closing:
            return
        serial = self.jobs.run(operation)
        if serial:
            self.callbacks[serial] = callback
        else:
            self.notice("Wait for the current setup task to finish, or cancel its download.")

    def cancel_setup(self) -> None:
        self.clear_start_intent()
        self.refresh_session_view()
        if self.jobs.busy:
            self.jobs.cancel.set()
            self.notice("Setup cancellation requested. Waiting for cleanup…")

    def job_done(self, serial: int, result: object, error: str) -> None:
        self.jobs.busy = False
        callback = self.callbacks.pop(serial, None)
        if callback and not self.closing:
            callback(result, error)

    def language_changed(self) -> None:
        if self.source_combo.currentData() and self.target_combo.currentData():
            updated = copy.deepcopy(self.settings)
            updated.source = self.source_combo.currentData()
            updated.target = self.target_combo.currentData()
            if not self.commit_settings(updated):
                for control, value in (
                    (self.source_combo, self.settings.source),
                    (self.target_combo, self.settings.target),
                ):
                    control.blockSignals(True)
                    control.setCurrentIndex(control.findData(value))
                    control.blockSignals(False)

    def swap_languages(self) -> None:
        if self.source_combo.findData(self.settings.target) < 0:
            self.notice(
                "That translation language is not available in the selected OCR engine. Choose a supported source language in Recognition first."
            )
            return
        if self.settings.source != "auto":
            updated = copy.deepcopy(self.settings)
            updated.source, updated.target = updated.target, updated.source
            self.commit_settings(updated)

    def language_input_valid(self) -> bool:
        valid = True
        for control in (self.source_combo, self.target_combo):
            if control.currentText() != control.itemText(control.currentIndex()):
                matched = control.findText(control.currentText(), Qt.MatchFlag.MatchFixedString)
                if matched >= 0:
                    control.setCurrentIndex(matched)
                else:
                    control.setEditText(control.itemText(control.currentIndex()))
                    valid = False
        if not valid:
            self.notice("Choose a language from the searchable list before starting.")
        return valid

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
                updated = copy.deepcopy(self.settings)
                updated.capture_mode = "window"
                updated.window_target = target.binding()
                updated.window_region = None
                updated.recent_region = [
                    target.client.x,
                    target.client.y,
                    target.client.width,
                    target.client.height,
                ]
                updated.display_signature = ""
                if not self.commit_settings(updated, False):
                    return
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
            updated = copy.deepcopy(self.settings)
            updated.capture_mode = "monitor"
            updated.monitor_name = name
            updated.recent_region = [region.x, region.y, region.width, region.height]
            updated.display_signature = topology_signature()
            if not self.commit_settings(updated, False):
                return
            self.update_region()
            self.notice(
                "Monitor selected. One-shot results appear in the main window when no safe overlay space remains."
            )

    def capture_ready(self) -> bool:
        if self.closing:
            return False
        if self.exit_code:
            self.notice("Quit DeskTranslate, then launch it again before starting translation.")
            return False
        return True

    def select(self, action: str = "select", relative: bool = False) -> None:
        if self.selector or not self.capture_ready():
            return
        if relative and not self.settings.window_target:
            self.notice("Choose an application first, then select a region inside it.")
            return
        self.stop()
        if not self.capture_ready():
            return
        self.relative_selection = relative
        self.selected_action = action
        self.hide()
        self.overlay.hide()
        self.selector = RegionSelector()
        self.selector.selected.connect(self.region_selected)
        self.selector.cancelled.connect(self.selection_cancelled)
        self.refresh_session_view()
        # Let the compositor remove our windows before freezing display images.
        QTimer.singleShot(200, self.selector.start)

    def region_selected(self, region: Rect) -> None:
        self.selector = None
        self.refresh_session_view()
        updated = copy.deepcopy(self.settings)
        if self.relative_selection:
            probe = None
            try:
                probe = WindowCapture(self.settings.window_target, None)
                target = probe.resolve()
                updated.window_region = normalized_region(target.client, region)
                updated.capture_mode = "window"
            except (DeskTranslateError, ValueError) as error:
                self.showNormal()
                self.notice(str(error))
                return
            finally:
                if probe:
                    probe.close()
        else:
            updated.capture_mode = "fixed"
        updated.recent_region = [region.x, region.y, region.width, region.height]
        updated.display_signature = "" if updated.capture_mode == "window" else topology_signature()
        if not self.commit_settings(updated, False):
            self.showNormal()
            return
        self.update_region()
        if self.selected_action in {"once", "live"}:
            self.queue_start(self.selected_action == "once")
        else:
            self.showNormal()

    def selection_cancelled(self) -> None:
        self.selector = None
        self.refresh_session_view()
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
        if not self.capture_ready():
            return
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
        if not self.language_input_valid():
            return
        if self.overlay.editing:
            self.notice("Finish editing the overlay before starting translation.")
            return
        self.stop()
        if not self.capture_ready():
            return
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
                self.pending_start = StartIntent(once, self.settings_revision, self.command_serial)
                self.install_button.setText(
                    "Install pack and translate once" if once else "Install pack and start live"
                )
                self.refresh_session_view()
                self.notice(
                    "This language needs a recognition pack. Review the download size, then install to continue. Stop cancels automatic continuation."
                )
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
            self.refresh_session_view()
            self.overlay.status.setText("DESKTRANSLATE  /  STARTING")
            if not self.overlay.suppressed:
                self.overlay.show()
        except (DeskTranslateError, ValueError) as error:
            if focus_on_error:
                self.showNormal()
            self.notice(str(error))

    def stop(self) -> None:
        self.command_serial += 1
        self.clear_start_intent()
        self.presentation_serial += 1
        if self.selector:
            self.selector.cleanup()
            self.selector = None
        if hasattr(self, "transcript_page"):
            self.transcript_page.clear()
        if self.pipeline:
            self.pipeline.stop()
            self.retiring.append(self.pipeline)
            self.pipeline = None
        self.collect_retired()
        if hasattr(self, "status_label"):
            self.status_label.setText("Ready when you are.")
        if hasattr(self, "overlay"):
            self.overlay.status.setText("DESKTRANSLATE  /  STOPPED")
            self.overlay.capture_region = None
            self.overlay.suppressed = False
        self.refresh_session_view()

    def pause(self) -> None:
        if self.overlay.editing and self.pipeline and self.pipeline.paused.is_set():
            self.notice("Finish editing the overlay before resuming translation.")
            return
        if self.pipeline:
            if self.pipeline.once and (
                self.pipeline.cancel.is_set() or self.pipeline.paused.is_set()
            ):
                self.start(True)
                return
            if self.pipeline.session.state == SessionState.ERROR:
                self.start(self.pipeline.once)
            elif self.pipeline.paused.is_set():
                self.pipeline.resume()
            else:
                self.pipeline.pause()
        self.refresh_session_view()

    def clear_context(self) -> None:
        if self.pipeline:
            self.pipeline.clear_context()
        self.notice("Dialogue context cleared.")

    def collect_retired(self) -> None:
        active = []
        for pipeline in self.retiring:
            if any(thread.is_alive() for thread in pipeline.threads):
                active.append(pipeline)
            elif not pipeline.wait_closed(0):
                self.exit_code = 1
                self.notice(
                    "A worker could not clean up completely. Exit and restart DeskTranslate before continuing."
                )
        self.retiring = active

    def poll_pipeline(self) -> None:
        self.collect_retired()
        pipeline = self.pipeline
        if pipeline is None:
            self.refresh_session_view()
            return
        for event in pipeline.poll():
            with pipeline.session.lock:
                if event.stamp != Stamp(pipeline.session.serial, pipeline.session.generation):
                    continue
                self.handle_pipeline_event(event)
        self.refresh_session_view()

    def refresh_session_view(self) -> None:
        pipeline = self.pipeline
        if pipeline and pipeline.cleanup_failed.is_set() and not self.exit_code:
            self.exit_code = 1
        if self.exit_code and (pipeline or self.selector or self.pending_start):
            # Retire all controller-owned work, including a replacement session
            # when an older worker reports failure. stop() refreshes the now-empty view.
            self.stop()
            self.notice("A worker could not clean up. Quit DeskTranslate, then launch it again.")
            return
        if self.exit_code:
            self.overlay.status.setText("DESKTRANSLATE  /  RESTART REQUIRED")
        completed = bool(pipeline and pipeline.once and pipeline.cancel.is_set())
        view = session_presentation(
            pipeline.session.state if pipeline else None,
            selecting=self.selector is not None,
            retiring=bool(self.retiring),
            completed=completed,
            has_result=bool(pipeline and pipeline.delivered_source),
            preparation=("downloading" if self.jobs.busy else "needed")
            if self.pending_start
            else None,
            restart_required=bool(self.exit_code),
        )
        self.session_status.setText(view.summary)
        self.session_status.setToolTip(view.summary)
        self.session_status.setAccessibleDescription(view.summary)
        self.pause_button.setText(view.pause_text)
        self.pause_button.setEnabled(view.can_pause)
        self.overlay.pause_button.setText(view.pause_text)
        self.overlay.pause_button.setEnabled(view.can_pause)
        self.stop_button.setEnabled(view.can_stop)
        running_live = bool(pipeline and not pipeline.once and not pipeline.cancel.is_set())
        self.live_button.setEnabled(not running_live and not self.exit_code)
        self.live_button.setText("Live is running" if running_live else "Start live")
        if hasattr(self, "tray_actions"):
            self.tray_actions["Pause / resume"].setText(view.pause_text)
            self.tray_actions["Pause / resume"].setEnabled(view.can_pause)
            self.tray_actions["Stop"].setEnabled(view.can_stop)
            self.tray.setToolTip("DeskTranslate 2 · " + view.summary)
        needs_poll = bool(self.retiring) or bool(
            pipeline
            and (
                not pipeline.cancel.is_set()
                or any(thread.is_alive() for thread in pipeline.threads)
                or not pipeline.events.empty()
            )
        )
        if needs_poll and not self.closing:
            interval = 250 if pipeline and pipeline.paused.is_set() else 60
            if self.timer.interval() != interval:
                self.timer.setInterval(interval)
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()

    def handle_pipeline_event(self, event: PipelineEvent) -> None:
        if event.region:
            self.overlay.avoid_capture(event.region)
        self.status_label.setText(event.error or event.state.value.capitalize())
        self.overlay.status.setText("DESKTRANSLATE  /  " + event.state.value.upper())
        self.overlay.pause_button.setText(
            "Resume" if event.state in {SessionState.PAUSED, SessionState.ERROR} else "Pause"
        )
        if event.clear:
            if self.pipeline:
                self.pipeline.delivered_source = ""
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
            one_shot = self.pipeline is not None and self.pipeline.once
            self.presentation_serial += 1
            start = time.perf_counter()
            self.latest = event.result.text
            self.result_source.setText(event.source)
            self.result_translation.setText(event.result.text)
            self.transcript_page.append(event.source, event.result.text, event.replaces_source)
            self.overlay.display(event.source, event.result.text)
            if self.pipeline:
                self.pipeline.delivered_source = event.source
            if self.overlay.suppressed and one_shot:
                self.showNormal()
            self.timings = {
                **event.timings,
                "gui_delivery_ms": (time.monotonic() - event.created) * 1000,
                "overlay_schedule_ms": (time.perf_counter() - start) * 1000,
            }
            self.metrics.observe(self.timings)
            completion_saved = True
            if not self.settings.onboarding_done:
                updated = copy.deepcopy(self.settings)
                updated.onboarding_done = True
                completion_saved = self.commit_settings(updated, activate=False)
            self.status_label.setText(
                f"Translated · {event.timings.get('total_ms', 0):.0f} ms"
                + (" · cached" if event.result.cached else "")
                + (
                    " · overlay cannot fit; reselect a smaller region"
                    if self.overlay.suppressed and not one_shot
                    else ""
                )
                + (
                    " · setup completion could not be saved; check your data folder"
                    if not completion_saved
                    else ""
                )
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
        if self.closing:
            return
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
        # Windows can apply the HWND's DPI-suggested rectangle after Qt emits
        # the screen signals. Refit once that native cascade has settled.
        self.display_relayout.start()
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
            "Translation stopped because Windows suspended, locked or disconnected this session. Start again when it is available; dialogue context has been cleared."
        )

    def system_preferences_changed(self) -> None:
        apply_theme(QApplication.instance(), self.settings.theme)  # type: ignore[arg-type]
        self.overlay.configure(self.settings)

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
        self.notice("Overlay shown." if self.overlay.isVisible() else "Overlay hidden.")

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
            text = "Cloud · recognized text is sent to this provider. Screenshots stay on your machine."
            if spec.capabilities.context:
                text += " AI APIs may charge usage fees."
        if selected == "google":
            text += " Quick translation uses Google's public web endpoint; availability is not guaranteed. DeepL is the supported API alternative."
        self.provider_info.setText(text)
        self.story_context_edit.setEnabled(spec.capabilities.context)
        pair = (self.settings.glossary_source, self.settings.glossary_target)
        current_pair = (self.settings.source, self.settings.target)
        scope = self.settings.active_profile or "current setup"
        self.glossary_scope.setText(
            f"Saved with {scope}. "
            + (
                f"Terms belong to {pair[0]} → {pair[1]}; not applied to the current language pair. "
                if self.settings.glossary and pair != current_pair
                else ""
            )
            + "Apply saves terms for the current language pair. AI receives relevant terms; quick translation uses exact whole-term matches only."
        )
        active = self.settings.provider
        active_spec = SPECS[active]
        local = active_spec.capabilities.local or (
            (active in {"libre", "custom"})
            and is_loopback_endpoint(self.settings.endpoint or active_spec.endpoint)
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
            updated.story_context = self.story_context_edit.toPlainText().strip()
            updated.glossary = glossary
            updated.glossary_source, updated.glossary_target = updated.source, updated.target
            if updated.active_profile:
                from desktranslate.profiles import profile_values

                updated.profiles[updated.active_profile] = profile_values(updated)
            updated.validate()
            new_key = self.key_edit.text().strip()
            account = self.credential_account(selected, endpoint)
            previous_key = ""
            if new_key:
                previous_key = self.credentials.get(account)
                self.credentials.set(account, new_key)
            if not self.commit_settings(updated, False):
                if new_key:
                    try:
                        if previous_key:
                            self.credentials.set(account, previous_key)
                        else:
                            self.credentials.delete(account)
                    except DeskTranslateError:
                        self.notice(
                            "Settings could not be saved and the credential rollback failed. Review your saved key in Providers."
                        )
                return False
            self.key_edit.clear()
            self.stop()
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
        snapshot = copy.deepcopy(self.settings)
        revision = self.settings_revision
        controls = (
            self.endpoint_edit.text(),
            self.openai_api_combo.currentData(),
            self.key_edit.text(),
        )
        self.provider_status.setText("Connecting…")

        def operation() -> object:
            provider = factory()
            provider.cancelled = self.jobs.cancel
            try:
                if provider.capabilities.model_discovery:
                    return provider.models()
                provider.translate(TranslationRequest("Hello", "en", snapshot.target))
                return []
            finally:
                provider.close()

        def complete(result: object, error: str) -> None:
            if (
                self.provider_combo.currentData() != selected
                or self.settings_revision != revision
                or controls
                != (
                    self.endpoint_edit.text(),
                    self.openai_api_combo.currentData(),
                    self.key_edit.text(),
                )
            ):
                self.provider_status.setText(
                    "Setup changed during the test. Test the current configuration again."
                )
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
                        self.model_combo.count() - 1,
                        "<qt>" + html.escape(detail).replace("\n", "<br>") + "</qt>",
                        Qt.ItemDataRole.ToolTipRole,
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
                provider.cancelled = self.jobs.cancel
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
        if self.settings.ocr == "tesseract":
            self.ocr_status.setText(
                "Optional Tesseract recognition · install Tesseract and this language's traineddata separately. Managed downloads apply to RapidOCR."
            )
            return
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
        if self.settings.ocr != "rapidocr":
            self.notice(
                "Select RapidOCR to install a managed language pack. Optional Tesseract uses its own traineddata."
            )
            return
        if self.jobs.busy:
            self.notice("Wait for the current setup task, or cancel its download first.")
            return
        intent = self.pending_start
        if intent and (
            intent.revision != self.settings_revision or intent.command != self.command_serial
        ):
            intent = None
        self.stop()
        if intent:
            self.pending_start = StartIntent(
                intent.once, self.settings_revision, self.command_serial
            )
        continuation = self.pending_start
        language = self.settings.source
        manager = ModelManager()
        self.install_button.setEnabled(False)
        self.progress.show()
        self.progress.setValue(0)
        self.ocr_status.setText("Downloading verified recognition models…")

        def complete(result: object, error: str) -> None:
            self.install_button.setEnabled(True)
            self.progress.hide()
            self.update_ocr_status()
            resume = (
                not error
                and not self.closing
                and continuation is not None
                and self.pending_start == continuation
                and continuation.revision == self.settings_revision
                and continuation.command == self.command_serial
                and manager.installed(language)
            )
            if self.pending_start == continuation:
                self.clear_start_intent()
            self.refresh_session_view()
            if error:
                self.ocr_status.setText(error)
            if resume and continuation is not None:
                self.navigation.setCurrentRow(0)
                self.notice("Recognition is ready. Starting your selected translation.")
                self.queue_start(continuation.once)
                return
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
        self.refresh_session_view()

    def clear_start_intent(self) -> None:
        self.pending_start = None
        self.install_button.setText("Install recognition models")

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
            f"Downloading recognition pack · {downloaded / 1e6:.1f} MB"
            + (f" / {total / 1e6:.1f} MB" if total else "")
        )

    def save_recognition(self) -> None:
        updated = copy.deepcopy(self.settings)
        updated.ocr = self.ocr_combo.currentData()
        updated.quality = self.quality_combo.currentData()
        updated.preprocessing = self.preprocess_combo.currentData()
        updated.vertical = self.vertical_check.isChecked()
        if self.commit_settings(updated):
            self.notice("Recognition settings applied.")

    def save_appearance(self) -> None:
        try:
            updated = copy.deepcopy(self.settings)
            self.overlay_editor.apply_to(updated)
        except ValueError as error:
            self.notice(str(error))
            return
        updated.overlay_mode = self.overlay_mode_combo.currentData()
        updated.overlay_size = self.font_spin.value()
        updated.overlay_opacity = self.opacity_spin.value()
        updated.overlay_click_through = self.click_check.isChecked()
        updated.theme = self.theme_combo.currentData()
        if not self.commit_settings(updated, False):
            return
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
        self.refresh_session_view()
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
            updated = copy.deepcopy(self.settings)
            updated.hotkeys = values
            updated.close_to_tray = self.tray_check.isChecked()
            updated.update_channel = self.update_channel_combo.currentData()
            updated.window_follow_restart = self.restart_target_check.isChecked()
            if not self.commit_settings(updated, False):
                return
            conflicts = self.hotkeys.register(values)
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
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for language in source_languages(self.settings.ocr):
            self.source_combo.addItem(language.name, language.code)
        self.source_combo.blockSignals(False)
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
        self.story_context_edit.setPlainText(self.settings.story_context)
        self.dialogue_options.setChecked(
            bool(
                self.settings.story_context
                or self.settings.glossary
                or self.settings.instructions
                or self.settings.style != "natural"
            )
        )
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
                "Restore default settings? Saved profiles and provider keys are retained. If the settings file is damaged, this replaces it with defaults.",
            )
            == QMessageBox.StandardButton.Yes
        ):
            recovered = self.store.recovered
            self.store.recovered = False
            if not self.commit_settings(Settings(profiles=copy.deepcopy(self.settings.profiles))):
                self.store.recovered = recovered

    def refresh_diagnostics(self) -> None:
        self.support_page.refresh()

    def copy_diagnostics(self) -> None:
        self.support_page.copy()

    def check_updates(self) -> None:
        from desktranslate.updates import check_release

        channel = self.settings.update_channel
        self.support_page.update_url = ""
        self.support_page.release_notes.setEnabled(False)

        def complete(result: object, error: str) -> None:
            if channel != self.settings.update_channel:
                self.notice("Update channel changed. Check the current channel again.")
                return
            if error:
                self.notice(error)
            elif isinstance(result, tuple) and len(result) == 2:
                tag, url = result
                self.notice(f"Update available: {tag}. Open release notes when ready.")
                self.support_page.update_url = url
                self.support_page.release_notes.setEnabled(True)
            else:
                self.notice("No newer compatible release was found in your chosen channel.")

        self.job(lambda: check_release(channel, self.jobs.cancel), complete)

    def onboarding(self) -> None:
        if self.closing:
            return
        if hasattr(self, "setup_dialog"):
            if self.setup_suspended:
                self.resume_setup()
                return
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
        self.setup_dialog.configure_provider_requested.connect(self.configure_setup_provider)
        self.setup_dialog.finished.connect(self.setup_finished)
        self.setup_dialog.show()

    def configure_setup_provider(self) -> None:
        if self.closing:
            return
        self.setup_suspended = True
        self.setup_dialog.hide()
        self.return_setup_button.show()
        self.navigation.setCurrentRow(1)
        self.showNormal()

    def resume_setup(self) -> None:
        if not self.setup_suspended or self.closing:
            return
        self.setup_suspended = False
        self.return_setup_button.hide()
        self.setup_dialog.resume_provider_setup()

    def setup_finished(self, result: int) -> None:
        self.setup_suspended = False
        self.return_setup_button.hide()

    def quit(self) -> None:
        if self.closing:
            return
        self.closing = True
        self.setEnabled(False)
        self.hide()
        self.stop()
        self.timer.stop()
        self.display_relayout.stop()
        self.jobs.cancel.set()
        if hasattr(self, "setup_dialog"):
            self.setup_dialog.reject()
        app = QApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self.hotkeys)
        self.hotkeys.close()
        self.hotkeys.unwatch_session()
        if self.selector:
            self.selector.cleanup()
        self.overlay.close()
        self.tray.hide()
        # Keep the event loop responsive until native process handles are reaped.
        from threading import Thread

        def finish_workers() -> None:
            deadline = time.monotonic() + 35
            for pipeline in self.retiring:
                if not pipeline.wait_closed(max(0, deadline - time.monotonic())):
                    self.exit_code = 1
            if not self.jobs.wait_closed(max(0, deadline - time.monotonic())):
                self.exit_code = 1
            if hasattr(self, "setup_dialog") and not self.setup_dialog.jobs.wait_closed(
                max(0, deadline - time.monotonic())
            ):
                self.exit_code = 1

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

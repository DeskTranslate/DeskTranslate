from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QListWidget, QVBoxLayout, QWidget

from desktranslate.ui.layout import fit_to_screen
from desktranslate.window_capture import WindowInfo


class WindowPicker(QDialog):
    def __init__(self, windows: list[WindowInfo], parent: QWidget) -> None:
        super().__init__(parent)
        self.windows = windows
        self.setWindowTitle("Choose an application")
        fit_to_screen(self, 640, 460)
        layout = QVBoxLayout(self)
        description = QLabel(
            "Choose the exact window to follow. Capture waits while it is minimized or covered. No other application is captured as a fallback."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.list = QListWidget()
        self.list.setAccessibleName("Open application windows")
        for window in windows:
            self.list.addItem(f"{window.title}  ·  {window.executable}")
        layout.addWidget(self.list, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Follow this window")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.list.currentRowChanged.connect(
            lambda row: buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(row >= 0)
        )
        self.list.itemDoubleClicked.connect(self.accept)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if not windows:
            description.setText(
                "No selectable application was found. Open the game or video window, then try again."
            )
        self.list.setFocus(Qt.FocusReason.OtherFocusReason)

    def chosen(self) -> WindowInfo | None:
        row = self.list.currentRow()
        return self.windows[row] if 0 <= row < len(self.windows) else None

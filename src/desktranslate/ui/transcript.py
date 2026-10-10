from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktranslate.transcript import SessionTranscript


class TranscriptPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.transcript = SessionTranscript()
        layout = QVBoxLayout(self)
        description = QLabel(
            "Optional memory of this session. Off by default; enabling it keeps recognized and translated text in memory only. Stop, changing the setup, or quitting clears it. Export is always your explicit choice."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.enable = QCheckBox("Keep this session's transcript in memory")
        self.enable.toggled.connect(self.set_enabled)
        layout.addWidget(self.enable)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search this session")
        self.search.setAccessibleName("Search session transcript")
        self.search.textChanged.connect(self.refresh)
        layout.addWidget(self.search)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setAccessibleName("Session transcript")
        layout.addWidget(self.text, 1)
        row = QHBoxLayout()
        for title, action in (
            (
                "Copy visible lines",
                lambda: QApplication.clipboard().setText(self.text.toPlainText()),
            ),
            ("Export JSON…", self.export),
            ("Clear", self.clear),
        ):
            button = QPushButton(title)
            button.clicked.connect(action)
            row.addWidget(button)
        layout.addLayout(row)

    def set_enabled(self, enabled: bool) -> None:
        self.transcript.set_enabled(enabled)
        self.refresh()

    def clear(self) -> None:
        self.transcript.clear()
        self.refresh()

    def append(self, source: str, translation: str) -> None:
        self.transcript.append(source, translation)
        self.refresh()

    def refresh(self) -> None:
        query = self.search.text().casefold()
        rows = [
            f"{entry.source}\n{entry.translation}"
            for entry in self.transcript.entries
            if query in (entry.source + entry.translation).casefold()
        ]
        self.text.setPlainText("\n\n".join(rows))

    def export(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Preview transcript export")
        dialog.resize(650, 500)
        layout = QVBoxLayout(dialog)
        warning = QLabel(
            "This export contains recognized and translated text from the whole retained session. Review it before saving or sharing. It is never exported automatically."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText(json.dumps(self.transcript.snapshot(), ensure_ascii=False, indent=2))
        layout.addWidget(preview)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save transcript", "DeskTranslate-session.json", "JSON (*.json)"
            )
            if filename:
                try:
                    Path(filename).write_text(preview.toPlainText(), encoding="utf-8")
                except OSError:
                    self.text.setPlainText(
                        "Cannot save this export. Choose a writable location; the session remains in memory."
                    )

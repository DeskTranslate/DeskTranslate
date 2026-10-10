from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SupportPage(QWidget):
    def __init__(
        self,
        metadata: Callable[[bool], dict[str, Any]],
        check_updates: Callable[[], None],
        notice: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.metadata, self.notice = metadata, notice
        self.update_url = ""
        layout = QVBoxLayout(self)
        label = QLabel(
            "Preview exactly what will be exported: versions, Windows build, display layout/scaling, capture and recognition types, expected model hashes, numeric resource/latency measurements and error categories. No screenshots, recognized/translated text, keys, endpoints, prompts, usernames or environment variables."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        self.include_model = QCheckBox(
            "Include the active translation model ID · review before sharing"
        )
        self.include_model.toggled.connect(self.refresh)
        layout.addWidget(self.include_model)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName("Exact diagnostic bundle preview")
        layout.addWidget(self.preview, 1)
        row = QHBoxLayout()
        for title, callback in (
            ("Refresh", self.refresh),
            ("Copy", self.copy),
            ("Export JSON…", self.export),
            ("Check updates", check_updates),
        ):
            button = QPushButton(title)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        self.release_notes = QPushButton("Open update release notes")
        self.release_notes.setEnabled(False)
        self.release_notes.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(self.update_url)) if self.update_url else None
        )
        layout.addWidget(self.release_notes)

    def refresh(self) -> None:
        self.preview.setPlainText(
            json.dumps(self.metadata(self.include_model.isChecked()), indent=2, ensure_ascii=False)
        )

    def copy(self) -> None:
        self.refresh()
        QApplication.clipboard().setText(self.preview.toPlainText())

    def export(self) -> None:
        self.refresh()
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export the previewed diagnostic bundle",
            "DeskTranslate-diagnostics.json",
            "JSON (*.json)",
        )
        if filename:
            try:
                Path(filename).write_text(self.preview.toPlainText(), encoding="utf-8")
                self.notice("Diagnostic bundle saved. Review it before sharing.")
            except OSError:
                self.notice("Cannot write diagnostics. Choose a writable location.")

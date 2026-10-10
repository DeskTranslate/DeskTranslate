"""Explicit, previewed glossary exchange; imported values remain an unapplied draft."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from desktranslate.profiles import export_glossary, import_glossary


def editor_content(glossary: dict[str, str]) -> str:
    if any(
        "=" in key or "\n" in key + value or "\r" in key + value for key, value in glossary.items()
    ):
        return export_glossary(glossary)
    return "\n".join(f"{key} = {value}" for key, value in glossary.items())


def parse_editor(content: str) -> dict[str, str]:
    if content.lstrip().startswith("{"):
        return import_glossary(content)
    result = {}
    for line in content.splitlines():
        if line.strip():
            key, separator, value = line.partition("=")
            if not separator or not key.strip() or not value.strip():
                raise ValueError(
                    "Use source = translation on each glossary line, or a JSON object."
                )
            if key.strip() in result:
                raise ValueError("Duplicate glossary sources are ambiguous")
            result[key.strip()] = value.strip()
    return import_glossary(export_glossary(result))


def exchange_controls(editor: QPlainTextEdit, notice: Callable[[str], None]) -> QHBoxLayout:
    row = QHBoxLayout()

    def load() -> None:
        filename, _ = QFileDialog.getOpenFileName(
            editor, "Import glossary", "", "Glossary (*.json *.csv)"
        )
        if filename:
            try:
                path = Path(filename)
                if path.stat().st_size > 60_000:
                    raise ValueError("Glossary is too large")
                glossary = import_glossary(
                    path.read_text(encoding="utf-8-sig"), path.suffix.lower() == ".csv"
                )
                editor.setPlainText(export_glossary(glossary))
                notice(
                    "Glossary imported into the draft. Review it, then Apply translation settings."
                )
            except (OSError, UnicodeError, ValueError, RecursionError) as error:
                notice(
                    str(error)
                    if isinstance(error, ValueError)
                    else "Cannot read this glossary. Check its format and permissions."
                )

    def save(csv_format: bool = False) -> None:
        try:
            content = export_glossary(parse_editor(editor.toPlainText()), csv_format)
        except (ValueError, RecursionError) as error:
            notice(str(error))
            return
        dialog = QDialog(editor)
        dialog.setWindowTitle("Preview glossary export")
        from desktranslate.ui.layout import fit_to_screen

        fit_to_screen(dialog, 620, 480)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Review glossary terms for private content before sharing."))
        preview = QPlainTextEdit(content)
        preview.setReadOnly(True)
        preview.setAccessibleName("Exact glossary export")
        layout.addWidget(preview)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            suffix = "csv" if csv_format else "json"
            filename, _ = QFileDialog.getSaveFileName(
                editor,
                "Export glossary",
                f"DeskTranslate-glossary.{suffix}",
                f"{suffix.upper()} (*.{suffix})",
            )
            if filename:
                try:
                    Path(filename).write_text(content, encoding="utf-8")
                    notice("Glossary exported to your selected file.")
                except OSError:
                    notice("Cannot write the glossary. Choose a writable location.")

    for title, callback in (
        ("Import glossary", load),
        ("Export JSON", lambda: save()),
        ("Export CSV", lambda: save(True)),
    ):
        button = QPushButton(title)
        button.clicked.connect(callback)
        row.addWidget(button)
    return row

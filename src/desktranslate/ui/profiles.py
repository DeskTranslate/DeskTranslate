from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktranslate.profiles import (
    apply_profile,
    export_profile,
    profile_values,
    read_profile,
    valid_name,
)
from desktranslate.settings import Settings


class ProfilePage(QWidget):
    def __init__(
        self,
        get_settings: Callable[[], Settings],
        commit: Callable[[Settings, bool], bool],
        notice: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.get_settings, self.commit, self.notice = get_settings, commit, notice
        layout = QVBoxLayout(self)
        description = QLabel(
            "Save a setup for each game, show or task. Profiles include languages, recognition, translation, dialogue context, shortcuts, overlay and your locally chosen capture target. Keys remain in the OS vault."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.list = QListWidget()
        self.list.setAccessibleName("Saved profiles")
        self.list.itemDoubleClicked.connect(lambda: self.activate())
        layout.addWidget(self.list, 1)
        for actions in (
            (
                ("Save current", self.save),
                ("Load", self.activate),
                ("Update selected", self.update_selected),
            ),
            (("Duplicate", self.duplicate), ("Rename", self.rename), ("Delete", self.delete)),
            (("Import JSON", self.import_file), ("Export JSON", self.export_file)),
        ):
            row = QHBoxLayout()
            for title, operation in actions:
                button = QPushButton(title)
                button.clicked.connect(operation)
                row.addWidget(button)
            layout.addLayout(row)
        self.refresh()

    def refresh(self, selected: str = "") -> None:
        self.list.clear()
        self.list.addItems(list(self.get_settings().profiles))
        matches = self.list.findItems(selected, Qt.MatchFlag.MatchExactly)
        if matches:
            self.list.setCurrentItem(matches[0])

    def selected(self) -> str:
        item = self.list.currentItem()
        return item.text() if item else ""

    def name(self, initial: str = "") -> str | None:
        text, accepted = QInputDialog.getText(
            self, "Profile name", "Name", QLineEdit.EchoMode.Normal, initial
        )
        if not accepted:
            return None
        try:
            name = valid_name(text)
            if name in self.get_settings().profiles and name != initial:
                self.notice("That profile name already exists. Choose another name.")
                return None
            return name
        except ValueError as error:
            self.notice(str(error))
            return None

    def store(self, settings: Settings, selected: str = "") -> None:
        if self.commit(settings, False):
            self.refresh(selected)

    def save(self) -> None:
        if name := self.name():
            updated = copy.deepcopy(self.get_settings())
            updated.profiles[name] = profile_values(updated)
            self.store(updated, name)

    def update_selected(self) -> None:
        if name := self.selected():
            updated = copy.deepcopy(self.get_settings())
            updated.profiles[name] = profile_values(updated)
            self.store(updated, name)

    def activate(self) -> None:
        if name := self.selected():
            try:
                updated = apply_profile(self.get_settings(), self.get_settings().profiles[name])
                if self.commit(updated, True):
                    self.notice(
                        f"Profile loaded: {name}. Dialogue context cleared; start when ready."
                    )
            except ValueError as error:
                self.notice(str(error))

    def duplicate(self) -> None:
        if (selected := self.selected()) and (name := self.name()):
            updated = copy.deepcopy(self.get_settings())
            updated.profiles[name] = copy.deepcopy(updated.profiles[selected])
            self.store(updated, name)

    def rename(self) -> None:
        if (selected := self.selected()) and (name := self.name(selected)):
            updated = copy.deepcopy(self.get_settings())
            updated.profiles[name] = updated.profiles.pop(selected)
            self.store(updated, name)

    def delete(self) -> None:
        if name := self.selected():
            updated = copy.deepcopy(self.get_settings())
            updated.profiles.pop(name)
            self.store(updated)
            self.notice("Profile deleted. The currently applied settings remain available.")

    def import_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import profile", "", "DeskTranslate profile (*.json)"
        )
        if filename:
            try:
                name, values = read_profile(Path(filename))
                updated = copy.deepcopy(self.get_settings())
                if name in updated.profiles:
                    self.notice("A profile with that name exists. Rename it before importing.")
                    return
                updated.profiles[name] = values
                self.store(updated, name)
                self.notice(
                    "Profile imported. Select a local capture target after loading it; API keys are not imported."
                )
            except (OSError, ValueError, RecursionError):
                self.notice(
                    "Cannot import this profile. Check its format, size and file permissions."
                )

    def export_file(self) -> None:
        if not (name := self.selected()):
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Preview profile export")
        dialog.resize(640, 520)
        layout = QVBoxLayout(dialog)
        description = QLabel(
            "This file includes your glossary and style instructions. Review them for sensitive content. It excludes API keys. Capture coordinates and window identity are excluded unless you choose to include them."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        include = QCheckBox("Include the application/window capture target")
        layout.addWidget(include)
        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setAccessibleName("Exact exported profile JSON")
        layout.addWidget(preview)

        def refresh() -> None:
            preview.setPlainText(
                export_profile(name, self.get_settings().profiles[name], include.isChecked())
            )

        include.toggled.connect(refresh)
        refresh()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export profile", "DeskTranslate-profile.json", "JSON (*.json)"
            )
            if filename:
                try:
                    Path(filename).write_text(preview.toPlainText(), encoding="utf-8")
                    self.notice("Profile exported to the file you selected.")
                except OSError:
                    self.notice("Cannot write the profile. Choose a writable location.")

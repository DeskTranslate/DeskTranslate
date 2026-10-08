from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication


def icon() -> QIcon:
    return QIcon(str(Path(__file__).parents[1] / "assets/icon.svg"))


def apply_theme(app: QApplication, theme: str) -> None:
    # Qt's offscreen platform has no system font discovery on Windows. Load OS fonts
    # explicitly for reproducible previews; the installer does not redistribute fonts.
    if len(QFontDatabase.families()) < 10:
        for filename in ("segoeui.ttf", "seguisb.ttf", "YuGothM.ttc", "malgun.ttf", "msjh.ttc"):
            path = Path("C:/Windows/Fonts") / filename
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    dark = theme == "dark"
    palette = {
        "bg": "#10191e" if dark else "#f2f5f3",
        "surface": "#19262d" if dark else "#ffffff",
        "text": "#eff6f2" if dark else "#172e35",
        "muted": "#a8bdb8" if dark else "#4c6864",
        "border": "#30454b" if dark else "#ccdcd7",
        "input": "#122027" if dark else "#f5f9f7",
        "accent": "#68d8b4" if dark else "#1e735d",
        "arrow_down": (Path(__file__).parents[1] / "assets/chevron-down.svg").as_posix(),
        "arrow_up": (Path(__file__).parents[1] / "assets/chevron-up.svg").as_posix(),
    }
    app.setStyleSheet(
        """
        QWidget { background: %(bg)s; color: %(text)s; }
        QMainWindow, QDialog { background: %(bg)s; }
        QLabel { background: transparent; }
        QLabel#title { font-size: 30px; font-weight: 650; }
        QLabel#brand { font-size: 20px; font-weight: 700; color: %(accent)s; }
        QLabel#eyebrow { color: %(muted)s; font-size: 11px; font-weight: 600; }
        QLabel#muted { color: %(muted)s; }
        QFrame#card { background: %(surface)s; border: 1px solid %(border)s; border-radius: 14px; }
        QPushButton { background: %(surface)s; border: 1px solid %(border)s; border-radius: 8px; padding: 10px 16px; font-weight: 550; }
        QPushButton:hover { border-color: #68d8b4; }
        QPushButton:pressed { background: #315a50; color: #ffffff; }
        QPushButton:focus { border: 2px solid #68d8b4; }
        QPushButton:disabled { color: %(muted)s; }
        QPushButton#primary { background: #68d8b4; color: #102d24; border: 1px solid #68d8b4; font-weight: 650; }
        QPushButton#primary:hover { background: #8ce8ca; }
        QLineEdit, QComboBox, QSpinBox, QPlainTextEdit { background: %(input)s; border: 1px solid %(border)s; border-radius: 7px; padding: 8px; selection-background-color: #3c8270; }
        QComboBox::drop-down { width: 24px; border: none; }
        QComboBox::down-arrow { image: url("%(arrow_down)s"); width: 12px; height: 8px; }
        QSpinBox::up-button, QSpinBox::down-button { width: 24px; background: %(surface)s; border: 1px solid %(border)s; }
        QSpinBox::up-arrow { image: url("%(arrow_up)s"); width: 10px; height: 6px; }
        QSpinBox::down-arrow { image: url("%(arrow_down)s"); width: 10px; height: 6px; }
        QGroupBox { background: %(surface)s; border: 1px solid %(border)s; border-radius: 8px; margin-top: 8px; padding: 12px; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: %(muted)s; }
        QComboBox QAbstractItemView { background: %(surface)s; color: %(text)s; selection-background-color: #315a50; }
        QCheckBox { spacing: 10px; padding: 6px 0; }
        QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 1px solid %(border)s; background: %(input)s; }
        QCheckBox::indicator:checked { background: #68d8b4; border-color: #68d8b4; }
        QListWidget { background: transparent; border: none; outline: none; }
        QListWidget::item { padding: 14px 12px; border-radius: 8px; margin-bottom: 5px; }
        QListWidget::item:selected { background: #284d43; color: #c5f5e5; }
        QScrollArea { border: none; }
        QScrollBar:vertical { width: 9px; background: transparent; }
        QScrollBar::handle:vertical { background: %(border)s; border-radius: 4px; min-height: 24px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QProgressBar { border: 1px solid %(border)s; border-radius: 5px; text-align: center; min-height: 16px; }
        QProgressBar::chunk { background: #68d8b4; }
        QStatusBar { color: %(muted)s; }
        QToolTip { background: %(surface)s; color: %(text)s; border: 1px solid %(border)s; padding: 6px; }
    """
        % palette
    )

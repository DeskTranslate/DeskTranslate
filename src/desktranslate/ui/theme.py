import ctypes
import os
from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPalette
from PySide6.QtWidgets import QApplication


def icon() -> QIcon:
    return QIcon(str(Path(__file__).parents[1] / "assets/icon.svg"))


def high_contrast_enabled() -> bool:
    if os.name != "nt":
        return False

    class HighContrast(ctypes.Structure):
        _fields_ = [("size", ctypes.c_uint), ("flags", ctypes.c_uint), ("scheme", ctypes.c_wchar_p)]

    value = HighContrast()
    value.size = ctypes.sizeof(value)
    user = ctypes.WinDLL("user32")
    return bool(
        user.SystemParametersInfoW(0x42, value.size, ctypes.byref(value), 0) and value.flags & 1
    )


def text_scale() -> float:
    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Accessibility"
            ) as key:
                value, _ = winreg.QueryValueEx(key, "TextScaleFactor")
                return min(3.0, max(1.0, float(value) / 100))
        except (OSError, ValueError, TypeError):
            pass
    return 1.0


def apply_theme(app: QApplication, theme: str) -> None:
    # Qt's offscreen platform has no system font discovery on Windows. Load OS fonts
    # explicitly for reproducible previews; the installer does not redistribute fonts.
    if len(QFontDatabase.families()) < 10:
        for filename in ("segoeui.ttf", "seguisb.ttf", "YuGothM.ttc", "malgun.ttf", "msjh.ttc"):
            path = Path("C:/Windows/Fonts") / filename
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))
    scale = text_scale()
    app.setFont(QFont("Segoe UI", round(10 * scale)))
    high_contrast = high_contrast_enabled()
    style = "Windows" if high_contrast else "Fusion"
    if app.property("desktranslate_base_style") != style:
        app.setStyle(style)
        app.setProperty("desktranslate_base_style", style)
    if high_contrast:
        app.setStyleSheet("")
        if os.name == "nt":
            system_palette = app.palette()
            user = ctypes.WinDLL("user32")
            for role, index in (
                (QPalette.ColorRole.Window, 5),
                (QPalette.ColorRole.Base, 5),
                (QPalette.ColorRole.WindowText, 8),
                (QPalette.ColorRole.Text, 8),
                (QPalette.ColorRole.Button, 15),
                (QPalette.ColorRole.ButtonText, 18),
                (QPalette.ColorRole.Highlight, 13),
                (QPalette.ColorRole.HighlightedText, 14),
            ):
                value = user.GetSysColor(index)
                system_palette.setColor(
                    role, QColor(value & 255, value >> 8 & 255, value >> 16 & 255)
                )
            app.setPalette(system_palette)
        return
    dark = theme == "dark"
    palette = {
        "bg": "#10191e" if dark else "#f2f5f3",
        "surface": "#19262d" if dark else "#ffffff",
        "text": "#eff6f2" if dark else "#172e35",
        "muted": "#a8bdb8" if dark else "#4c6864",
        "border": "#30454b" if dark else "#ccdcd7",
        "input": "#122027" if dark else "#f5f9f7",
        "accent": "#68d8b4" if dark else "#1e735d",
        "title_size": round(30 * scale),
        "brand_size": round(20 * scale),
        "caption_size": round(12 * scale),
        "arrow_down": (Path(__file__).parents[1] / "assets/chevron-down.svg").as_posix(),
        "arrow_up": (Path(__file__).parents[1] / "assets/chevron-up.svg").as_posix(),
    }
    stylesheet = (
        """
        QWidget { background: %(bg)s; color: %(text)s; }
        QMainWindow, QDialog { background: %(bg)s; }
        QLabel { background: transparent; }
        QLabel#title { font-size: %(title_size)dpx; font-weight: 650; }
        QLabel#brand { font-size: %(brand_size)dpx; font-weight: 700; color: %(accent)s; }
        QLabel#eyebrow { color: %(muted)s; font-size: %(caption_size)dpx; font-weight: 600; }
        QLabel#muted { color: %(muted)s; }
        QFrame#card { background: %(surface)s; border: 1px solid %(border)s; border-radius: 14px; }
        QPushButton { background: %(surface)s; border: 1px solid %(border)s; border-radius: 8px; padding: 10px 16px; font-weight: 550; }
        QPushButton:hover { border-color: #68d8b4; }
        QPushButton:pressed { background: #315a50; color: #ffffff; }
        QPushButton:focus { border: 2px solid %(accent)s; }
        QPushButton:disabled { color: %(muted)s; }
        QPushButton#primary { background: #68d8b4; color: #102d24; border: 1px solid #68d8b4; font-weight: 650; }
        QPushButton#primary:hover { background: #8ce8ca; }
        QLineEdit, QComboBox, QSpinBox, QPlainTextEdit { background: %(input)s; border: 1px solid %(border)s; border-radius: 7px; padding: 8px; selection-background-color: #3c8270; }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus { border: 2px solid %(accent)s; }
        QComboBox::drop-down { width: 24px; border: none; }
        QComboBox::down-arrow { image: url("%(arrow_down)s"); width: 12px; height: 8px; }
        QSpinBox::up-button, QSpinBox::down-button { width: 24px; background: %(surface)s; border: 1px solid %(border)s; }
        QSpinBox::up-arrow { image: url("%(arrow_up)s"); width: 10px; height: 6px; }
        QSpinBox::down-arrow { image: url("%(arrow_down)s"); width: 10px; height: 6px; }
        QGroupBox { background: %(surface)s; border: 1px solid %(border)s; border-radius: 8px; margin-top: 8px; padding: 12px; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: %(muted)s; }
        QComboBox QAbstractItemView { background: %(surface)s; color: %(text)s; selection-background-color: #315a50; }
        QCheckBox { spacing: 10px; padding: 6px 0; }
        QCheckBox:focus { border: 1px solid %(accent)s; border-radius: 4px; }
        QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 1px solid %(border)s; background: %(input)s; }
        QCheckBox::indicator:checked { background: #68d8b4; border-color: #68d8b4; }
        QListWidget { background: transparent; border: none; }
        QListWidget::item { padding: 14px 12px; border-radius: 8px; margin-bottom: 5px; }
        QListWidget::item:selected { background: #284d43; color: #c5f5e5; }
        QListWidget::item:focus { border: 1px solid %(accent)s; }
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
    if app.styleSheet() != stylesheet:
        app.setStyleSheet(stylesheet)

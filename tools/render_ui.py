"""Render synthetic UI previews without capturing a desktop or making network calls."""

from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtWidgets import QApplication

from desktranslate.settings import Settings, SettingsStore
from desktranslate.ui.window import MainWindow


def main() -> None:
    app = QApplication([])
    directory = Path("docs/screenshots")
    directory.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        store = SettingsStore(Path(".test-data/previews") / theme)
        store.save(Settings(theme=theme))
        window = MainWindow(store, demo=True)
        window.show()
        for index, name in enumerate(
            ("translate", "providers", "recognition", "appearance", "preferences", "diagnostics")
        ):
            window.navigation.setCurrentRow(index)
            app.processEvents()
            window.grab().save(str(directory / f"{name}-{theme}.png"))
        window.overlay.display("明日、またここで会おう。", "Let's meet here again tomorrow.")
        app.processEvents()
        window.overlay.grab().save(str(directory / f"overlay-{theme}.png"))
        window.quit()
    montage = Image.new("RGB", (1500, 1200), "#263b3c")
    for index, file in enumerate(sorted(directory.glob("*-dark.png"))):
        image = Image.open(file)
        image.thumbnail((495, 395))
        montage.paste(
            ImageOps.expand(image, border=1, fill="#68d8b4"),
            ((index % 3) * 500, (index // 3) * 400),
        )
    montage.save(".audit/ui-review.png")


if __name__ == "__main__":
    main()

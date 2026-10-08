from __future__ import annotations

import argparse
import multiprocessing
import sys
from pathlib import Path


def main() -> int:
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description="DeskTranslate 2 · effortless screen translation")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument(
        "--demo", action="store_true", help="Show synthetic dialogue without capture or network"
    )
    parser.add_argument("--render-preview", type=Path)
    parser.add_argument(
        "--verify-runtime", type=Path, help="Write opt-in release verification metadata"
    )
    parser.add_argument(
        "--ocr-fixture", type=Path, help="Synthetic Japanese fixture for release verification"
    )
    args = parser.parse_args()
    from desktranslate.capture import enable_dpi_awareness

    enable_dpi_awareness()
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from desktranslate.logging import configure_logging
    from desktranslate.settings import SettingsStore, data_dir
    from desktranslate.ui.window import MainWindow

    app = QApplication(sys.argv[:1])
    app.setApplicationName("DeskTranslate")
    app.setOrganizationName("DeskTranslate")
    app.setQuitOnLastWindowClosed(False)
    configure_logging(data_dir() / "logs")
    window = MainWindow(
        SettingsStore(),
        demo=args.demo or args.smoke_test or bool(args.render_preview) or bool(args.verify_runtime),
    )
    window.show()
    if args.verify_runtime:
        from threading import Thread

        def verify() -> None:
            import json
            import uuid

            from desktranslate.security import CredentialStore

            report: dict[str, object] = {
                "qt": True,
                "assets": (Path(__file__).parent / "assets/models.json").is_file(),
            }
            account = "release-probe-" + uuid.uuid4().hex
            credentials = CredentialStore()
            try:
                credentials.set(account, account)
                report["credential_roundtrip"] = credentials.get(account) == account
            except Exception as error:
                report["credential_error"] = type(error).__name__
            finally:
                try:
                    credentials.delete(account)
                except Exception:
                    report["credential_cleanup"] = False
            if args.ocr_fixture:
                from PIL import Image

                from desktranslate.ocr import IsolatedOCR

                engine = None
                try:
                    engine = IsolatedOCR("rapidocr", "ja")
                    result = engine.recognize(Image.open(args.ocr_fixture).convert("RGB"), "ja")
                    report["ocr_exact"] = result.text == "明日、またここで会おう。"
                    report["ocr_ms"] = result.duration_ms
                except Exception as error:
                    report["ocr_error"] = type(error).__name__
                finally:
                    if engine:
                        engine.close()
            args.verify_runtime.parent.mkdir(parents=True, exist_ok=True)
            args.verify_runtime.write_text(json.dumps(report, indent=2), encoding="utf-8")

        thread = Thread(target=verify, daemon=True)
        thread.start()
        timer = QTimer(window)
        timer.timeout.connect(lambda: window.quit() if not thread.is_alive() else None)
        timer.start(100)
    elif args.render_preview:

        def preview() -> None:
            args.render_preview.parent.mkdir(parents=True, exist_ok=True)
            if not window.grab().save(str(args.render_preview)):
                app.exit(1)
                return
            window.quit()

        QTimer.singleShot(400, preview)
    elif args.smoke_test:
        QTimer.singleShot(400, window.quit)
    return app.exec()

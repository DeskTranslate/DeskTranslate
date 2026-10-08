# Contributing

Read the [architecture](docs/architecture.md) and [audit](docs/audit.md). Keep the product centered on understanding screen text, with a simple default path. OCR, capture and translation adapters implement domain protocols; Qt widgets consume accepted events and never perform network/inference work directly.

Use the Python 3.12 Windows setup and quality commands in [README](README.md). `requirements-windows.lock` pins the verified Windows build environment with PyPI artifact hashes. For other platforms use `pip install -e '.[dev,build]'` as an unqualified development environment; do not claim a release build from that command is identical.

Tests use synthetic text only. Put runtime data in an isolated `DESKTRANSLATE_DATA_DIR`; never commit settings, API keys, desktop captures or private dialogue. Tests of provider schemas use HTTP mock transports. Keep queues bounded, preserve request stamps through presentation, and ensure pause/stop/config changes invalidate work. Add regression tests for meaningful race/failure behavior, not assertions that merely repeat an implementation.

For opt-in OCR measurements: `python tools/evaluate.py --generate --install`. These flags generate fixtures from installed OS fonts and explicitly download verified OCR models. `python tools/e2e_desktop.py` displays a temporary synthetic window and contacts the quick translation endpoint only after the recognized fixture matches exactly. `QT_QPA_PLATFORM=offscreen python tools/render_ui.py` renders synthetic UI previews; on PowerShell set the environment variable separately.

Source assets resolve from the package; do not depend on the current directory in runtime code. Keep endpoints validated, redirects disabled, model downloads verified, keys out of JSON, and logs/diagnostics allowlisted. Cap input, response size and context. Features with new privacy implications require an explicit user choice.

Update documentation and the validation report when behavior changes. Run the [release checklist](docs/release-checklist.md) before promotion. Dependency changes require a lock refresh, vulnerability scan and packaged smoke test. Publishing workflows use least privilege and pinned action commits. Do not add unsigned download-and-execute helpers to user flows.

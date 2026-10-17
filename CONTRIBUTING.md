# Contributing

Read the [architecture](docs/architecture.md) and [audit](docs/audit.md). Keep the product centered on understanding screen text, with a simple default path. OCR, capture and translation adapters implement domain protocols; Qt widgets consume accepted events and never perform network/inference work directly.

Use the Python 3.12 Windows setup and quality commands in [README](README.md). `requirements-windows.lock` pins the verified Windows build environment with PyPI artifact hashes. For other platforms use `pip install -e '.[dev,build]'` as an unqualified development environment; do not claim a release build from that command is identical.

Tests use synthetic text only. Put runtime data in an isolated `DESKTRANSLATE_DATA_DIR`; never commit settings, API keys, desktop captures or private dialogue. Tests of provider schemas use HTTP mock transports. Keep queues bounded, preserve request stamps through presentation, and ensure pause/stop/config changes invalidate work. Add regression tests for meaningful race/failure behavior, not assertions that merely repeat an implementation.

For opt-in OCR measurements: `python tools/evaluate.py --generate --install`. These flags generate fixtures from installed OS fonts and explicitly download verified OCR models. `python tools/e2e_desktop.py` displays a temporary synthetic window and contacts the quick translation endpoint only after the recognized fixture matches exactly. `QT_QPA_PLATFORM=offscreen python tools/render_ui.py` renders synthetic UI previews; on PowerShell set the environment variable separately.

The [release checklist](docs/release-checklist.md) lists native window/UI/sample/installer probes and the two-hour or optional overnight soak. Windows asyncio uses a loopback socket internally; restricted sandboxes must allow it to run network deadline/cancellation tests. Keep a single Qt application in UI tests, destroy test windows on the GUI thread, and detach native event filters before their owner is released. Never hide a failing native lifecycle test by merely excluding it.

Source assets resolve from the package; do not depend on the current directory in runtime code. Keep endpoints validated, redirects disabled, model downloads verified, keys out of JSON, and logs/diagnostics allowlisted. Cap input, response size and context. Features with new privacy implications require an explicit user choice.

Update documentation and the validation report when behavior changes. Run the [release checklist](docs/release-checklist.md) before promotion. Dependency changes require a lock refresh, vulnerability scan and packaged smoke test. Publishing workflows use least privilege and pinned action commits. Do not add unsigned download-and-execute helpers to user flows.


Routine checks must not take over the developer's desktop. Use `python tools/validate.py` (or `python -m pytest -q`) for offscreen components, fixtures, mocks and owned loopback/process tests. `python tools/validate.py --predeploy` adds audits and source builds without desktop interaction. Tests isolate credentials/data, substitute global-shortcut calls and fail on real desktop grabs, browser launches or external network access. Keep these boundaries in place; do not skip meaningful state/error tests to make testing quieter.

Read [the testing policy](docs/testing.md) before adding a probe. Long stress, real services, installation and foreground-dependent checks are opt-in tiers outside routine pytest/CI. Native desktop helpers require `--interactive-desktop` and a bounded supervisor; installer checks require `-AllowInstallChanges` in a dedicated account/VM. Never add visible media playback, display changes, global input or prolonged topmost windows to normal development/pre-deployment checks. Exercise underlying capture transforms, picker events, controllers and failures below the native UI first.

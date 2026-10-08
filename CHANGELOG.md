# Changelog

## 2.0.0b1

DeskTranslate 2 rebuilds screen translation on Python 3.12, PySide6/Qt 6 and typed provider boundaries. It replaces mixed Qt generations, CSV globals, worker-to-widget mutation, primary-screen coordinates, fixed Tesseract paths and repeated OCR on unchanged frames.

Added physical MSS capture and monitor-relative DPI transforms; frozen multi-monitor region selection; one-shot/live workflows; bounded mailboxes, explicit session states and stale-result rejection; isolated OCR; managed verified ONNX models and optional detected Tesseract; text reconstruction/stabilization; bounded context/cache; conventional MT and native/compatible cloud/local AI adapters with dynamic catalogs.

Added a new mint/ink visual identity, light/dark themes, editable subtitle presets and detailed overlay styling, click-through/edit mode, shortcuts, profiles, tray controls, onboarding, diagnostics and explicit updates. Credentials use the OS vault, content remains out of logs, and screenshots/history are not persisted.

Windows per-user installer and portable builds include notices, SBOM and hashes. The repository now includes regression tests, lint/type checks, pinned dependency artifacts, CI, security/privacy/developer documentation, measured OCR fixtures and release qualification criteria. This is a beta; see [validation](docs/validation.md) for limits rather than assuming all hardware/providers are qualified.

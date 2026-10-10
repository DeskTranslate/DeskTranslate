# DeskTranslate 2 · window capture and reliability beta

Translate a moving game window, save a setup for each story, and see your first translation during guided setup. **2.0.0b2 is an unsigned Windows x64 prerelease. The stable verdict remains NOT READY.**

## New in this beta

- **Window-following capture.** Choose an application and a subtitle region relative to its client area. The region follows moves and resizing. Covered, minimized, missing or ambiguous targets wait safely. Reconnection after an application restart requires explicit consent. This is visible-screen capture; keep the selected region unobstructed.
- **Complete profiles.** Save, update, duplicate, rename and exchange setups containing languages, recognition, provider/model, context, glossary, overlay and shortcuts. Keys stay in the OS vault. Imported profiles require a fresh local capture selection. JSON/CSV glossaries have a review step before applying them.
- **A real first translation.** Guided setup installs the recognition pack with visible progress and integrity checks, runs actual local OCR on an authored sample, translates through your selected provider and previews the overlay. Back, retry and Set up later are available; success requires a real result.
- **Quieter, safer recovery.** Bounded OCR worker recovery, atomic session transitions, generation checks, cancellation of active HTTP work, complete request deadlines, sleep handling and native event-filter cleanup improve repeated start/stop and shutdown behavior. Runtime failures stay passive over your game.
- **Modern provider setup.** Native OpenAI Responses is recommended for new configurations, with response storage disabled. Existing Chat Completions configurations and compatible servers remain supported. Text-model filtering avoids known incompatible model families; unknown server models stay clearly unverified.
- **Session and support tools.** An optional bounded transcript stays in memory until copied/exported. Diagnostics use a reviewed metadata allowlist. Stable/beta update checks open release notes explicitly. High-contrast, scaling, keyboard focus and accessible field names received additional checks.

## Install or upgrade

Download `DeskTranslate-2.0.0b2-Setup-x64.exe` for per-user installation, or extract the entire `Portable-x64.zip` and keep `_internal` beside `DeskTranslate.exe`. Python and Tesseract are not required. Recognition packs are installed explicitly inside the app.

V2 settings and vault credentials remain compatible with the previous beta. Existing OpenAI configurations keep Chat Completions until you choose Responses. Profiles imported from another machine require local capture selection. V1's JSON settings and plain-text credential layout are not imported automatically; choose your provider in V2 and move keys into the OS vault.

## Verification and limits

The repository's [validation report](https://github.com/DeskTranslate/DeskTranslate/blob/main/docs/validation.md) and [release checklist](https://github.com/DeskTranslate/DeskTranslate/blob/main/docs/release-checklist.md) record automated, native-window, sample translation, packaging and endurance evidence separately from manual gates. Tests and synthetic probes do not establish accuracy for every game or video.

CPU OCR remains the shipped compatibility backend. Auto recognition is a Chinese/Latin family, not universal script detection; choose Japanese or Korean explicitly. Rapid subtitles can outpace CPU OCR. DirectML and Windows Graphics Capture remain research work. Physical mixed-DPI/hot-plug, exclusive fullscreen/HDR, Narrator, clean Windows and real paid/local-model qualification remain open.

**Binaries are unsigned because no publisher certificate is available.** Compare downloads with `SHA256SUMS.txt`; hashes detect file changes and do not establish publisher identity. Separate runtime/build SBOMs, a local build provenance statement and matching LGPL Qt/PySide library sources accompany the release. Hosted artifact attestations, when present, apply only to the exact artifacts built by that workflow. Stable builds enforce version, manual qualification, two-hour source-matched soak and trusted timestamped signing gates.

DeskTranslate application code is MIT. Third-party libraries and OCR models retain their own terms. Screenshots stay in memory; cloud translation sends recognized text and configured context. No telemetry is added, and session history remains off by default.

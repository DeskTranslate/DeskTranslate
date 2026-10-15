# DeskTranslate 2.0.0 — draft release notes

**Unreleased target. Publication is on hold.** These notes describe the intended major release and current engineering work. They do not announce an available stable installer or another beta. The internal package identifier remains a prerelease until stable acceptance passes.

V2 replaces the old Python/Tesseract setup with a bundled Windows application and managed, integrity-checked local OCR. Translation can run once or continuously, follow a chosen visible application's subtitle region, and appear in a configurable click-through overlay. Profiles retain language/provider/model, glossary, context, shortcuts and appearance; imported profiles require fresh local capture consent. Guided setup performs actual recognition and provider work before claiming success.

Translation targets retain v1's 133-language catalog. Ten provider paths include conventional translation, native cloud AI APIs and local Ollama/LM Studio. Recent dialogue and glossaries are optional bounded context, not a persistent history. Credentials use the OS vault; screenshots remain local and in memory. Cloud providers receive recognized text and configured context, not screenshots. No telemetry was added.

The final hardening phase fixes moving-background OCR starvation, stale setup/pipeline results, failed-save activation, cancelled network requests, OCR descendant cleanup, portable-data isolation, overlay focus/fade/geometry errors, long-text rendering cost and compact-window layouts. Latin, Cyrillic and Devanagari recognizers were compared and upgraded; Arabic output retains logical Unicode order. Thin capture regions now have a bounded detector tensor instead of potentially enormous short-side upscaling. LM Studio's silent unknown-model fallback is rejected.

## Installation and upgrade policy

The intended stable artifacts are a per-user Windows x64 installer and a complete portable ZIP. Normal users will need no Python, pip, Visual Studio, mandatory Tesseract or manual DLL installation. Installer data lives under `%LOCALAPPDATA%\DeskTranslate`; portable data lives in adjacent `DeskTranslateData`. Credentials remain in the Windows account's vault. Uninstall retains user data; deleting a portable folder deletes its adjacent data. See [upgrade and retention](upgrade.md).

V1 has language catalogs, not a persisted V2-compatible settings/credential format. V2 does not invent a migration from nonexistent V1 JSON settings or automatically remove the legacy NSIS/Tesseract installation. Earlier V2 settings are validated and migrated deliberately; corrupt settings are retained until an explicit recovery action.

## Qualification and remaining limits

See the [acceptance matrix](validation.md), [issue dispositions](issues-v2.md) and [release checklist](release-checklist.md) for exact evidence. Authored OCR fixtures, real local-server tests and a single native Windows display do not substitute for real games, physical mixed-DPI/hot-plug, clean consumer Windows, screen readers or paid account testing.

Chinese punctuation/Traditional characters, Vietnamese accents, stylized/pixel Japanese and vertical text retain recognition errors. Continuous authored motion works, but can produce noisy extra characters. The small local test model produced JSON/empty-object output rather than consistently usable plain translations; it is not a qualified model recommendation. CPU recognition can lag rapid subtitles. Protected/exclusive fullscreen, HDR and alternate platforms remain unqualified.

**No publisher signing certificate is available.** Internal qualification binaries are unsigned. Hashes establish file integrity, not publisher identity. Stable promotion requires the documented manual gates, current-source steady and fault-injection endurance evidence, clean packaging and trusted timestamped Authenticode signing. No self-signed certificate is substituted.

Build outputs include runtime/build SBOMs, SHA-256 sums, a local provenance statement, notices and exact corresponding LGPL library sources. Hosted attestations, when obtained, apply only to their exact artifact hashes. Application code is MIT; third-party components and OCR weights keep their own licenses.

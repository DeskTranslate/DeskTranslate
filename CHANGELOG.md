# Changelog

## 2.0.0 — unreleased, stable qualification in progress

DeskTranslate 2 replaces the Tesseract-only, Python-dependent desktop workflow with a packaged Windows application, local managed OCR and a Qt 6 interface. Normal users will use the installer or portable ZIP, without installing Python, pip or Tesseract. Publisher signing and the remaining manual acceptance matrix must pass before this section becomes a stable release announcement.

- Explicit region, monitor and application-client capture; monitor-relative physical coordinates; frozen selection with resize handles; invalidation after display/session changes.
- Local hash-verified OCR packs for 19 source languages, optional detected Tesseract, and the 133 translation targets available in V1. Source selection reflects the chosen engine's coverage.
- Conventional translation and native/compatible cloud or local AI adapters, discovered model catalogs, bounded dialogue context, cancellable requests and clear recoverable errors. No cloud fallback.
- One-shot and live translation, styled Unicode overlays, edit/click-through controls, light/dark themes, configurable shortcuts, profiles, guided setup, tray controls and privacy-safe diagnostics.
- Bounded work queues, stale-result rejection, OCR crash recovery, Windows process-tree containment and explicit cleanup failure reporting. Moving backgrounds now receive bounded OCR samples instead of starving recognition indefinitely.
- Cleanup failures retain a clear restart-required state, including after completed one-shot work, rather than leaving an apparent success until the next action.
- Transactional settings/profile changes, safe corrupt-configuration recovery, credential rollback on failed saves and portable data isolation. Installer reinstalls remove obsolete owned runtime files while retaining user data.
- Improved Latin, Cyrillic and Devanagari recognizers, corrected Arabic logical text order, and a47-fixture authored multilingual regression corpus. Chinese punctuation, stylized Japanese and real-media limitations remain documented.
- Faster long-subtitle layout with bounded glyph caches, safer provider parsing and endpoint handling, locked dependency hashes, supply-chain notices/SBOM/provenance, stronger CI and separate steady-worker/fault soak gates.
- Corrected live DPI-transition overlay clipping with a coalesced native-geometry refit; compact navigation keeps smaller workspaces usable. Actual 1080p→720p→1080p capture/reselection checks now complement synthetic coordinate tests.
- Release failed async sessions promptly without waiting for cyclic GC. Routine validation now forces offscreen components, isolates OS/network boundaries and tests picker/coordinate behavior without touching the real desktop; manual and extended probes require explicit opt-in.
- Close the early-cancel Windows pipe-handle leak, and fail endurance commands when measured resource budgets fail. Set process-local ONNX Runtime diagnostic opt-outs before inference and document the upstream Windows ETW limitation accurately.
- Reject endurance evidence with missing start/end/internal observations, including laptop standby gaps. Record verified upstream wheel build metadata separately from private-content findings without exempting changed binaries or credential signatures.
- Wait for observable uninstaller cleanup before reinstall qualification; a missing expected uninstaller now fails. Keep hosted steady and fault endurance independent so an unrelated qualification failure does not suppress their results.
- Reject LM Studio's silent fallback to another model when the selected model is missing or replaced. Bound detector tensors for thin screen regions while preserving ordinary-region OCR pixels and benchmark outputs.
- Recover correctly after pausing an idle OCR worker: resuming onto static changed text now schedules fresh recognition instead of waiting indefinitely for another screen change.
- Preserve configured providers and draft language choices through setup/provider editing. Swap languages with one durable transaction; explicitly install missing packs and continue only while the original request remains current.
- Keep capture status visible across pages and notices, synchronize pause/retry actions in the window, overlay and tray, and stop pipeline polling when no work remains. Remove an unused, unimplemented speech setting without discarding older preferences.
- Prevent competing launches from overwriting the same preferences; relaunch restores the existing window while separate portable data folders stay independent. Reject delayed setup/new jobs after Quit, keep ownership through cleanup, and make verification/startup errors offscreen and non-activating.
- Track bounded dialogue evidence across changing frames, suppress progressive/spacing churn and treat completed text as a revision of its provisional fragment. Revoke pixels captured across pause/resume and sample moving backgrounds sooner while keeping pending work bounded.
- Add optional per-title story notes and locally retrieved, language-bound terminology. Separate recent dialogue from caching; conventional translation uses exact whole-term matches and preserves complete sentences. Retain title-context save/load/delete recovery and explicit privacy controls.
- Recognize Japanese columns and upright captions by region, with conservative ruby annotations and a separately verified recognizer loaded only for eligible word/column regions. All eight authored vertical/mixed/ruby layouts now match. Selective word recognition also fixes the authored pixel, translucent, low-contrast and small-text cases; punctuation/name differences and background false positives remain. Short text and counters keep their original path because global model replacement worsened false positives.

See [validation](docs/validation.md) for actual results and untested configurations. Experimental vertical OCR and provider/model availability are not promises of universal recognition or translation quality. Earlier release entries below remain historical.

## 2.0.0b1

DeskTranslate 2 rebuilds screen translation on Python 3.12, PySide6/Qt 6 and typed provider boundaries. It replaces mixed Qt generations, CSV globals, worker-to-widget mutation, primary-screen coordinates, fixed Tesseract paths and repeated OCR on unchanged frames.

Added physical MSS capture and monitor-relative DPI transforms; frozen multi-monitor region selection; one-shot/live workflows; bounded mailboxes, explicit session states and stale-result rejection; isolated OCR; managed verified ONNX models and optional detected Tesseract; text reconstruction/stabilization; bounded context/cache; conventional MT and native/compatible cloud/local AI adapters with dynamic catalogs.

Added a new mint/ink visual identity, light/dark themes, editable subtitle presets and detailed overlay styling, click-through/edit mode, shortcuts, profiles, tray controls, onboarding, diagnostics and explicit updates. Credentials use the OS vault, content remains out of logs, and screenshots/history are not persisted.

Windows per-user installer and portable builds include notices, SBOM and hashes. The repository now includes regression tests, lint/type checks, pinned dependency artifacts, CI, security/privacy/developer documentation, measured OCR fixtures and release qualification criteria. This is a beta; see [validation](docs/validation.md) for limits rather than assuming all hardware/providers are qualified.

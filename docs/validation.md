# DeskTranslate 2 beta2 validation

## Current hardening pass

The full suite now passes **208 tests**, with Ruff lint/format and mypy over **41 application modules**. New regression coverage includes atomic state interleavings (ten seeded sequences of 300 actions), bounded OCR recovery, stale failure rejection, window binding/crop safety, profile/glossary schemas, semantic update ordering, total request deadlines through slow headers, immediate network cancellation, gzip expansion bounds, malformed/deep JSON, setup retry/completion, transcript privacy, persistent overlay hiding and passive recovery without focus theft. Native UI teardown now detaches its application event filter before destroying its owner; repeated UI lifecycle tests pass. Theme application is idempotent and demo/tests do not create real tray notifications.

[Native window qualification](window-qualification.json) passed ten authored-window checks at physical 125% scale, including movement, resize, minimize, restore, occlusion and replacement/ambiguous-reconnection guards. [Native UI qualification](ui-qualification.json) ran at an effective 200% Qt scale: eight pages have no horizontal overflow, 15 Tab focus targets were reached and all 19 combo boxes expose accessible names. All six setup pages keep navigation controls visible without horizontal overflow in a 560×320 logical viewport; initial dialog size fits the desktop. This is a layout inspection and does not substitute for the actual first-success tests. The Windows high-contrast native-style branch was exercised; an actual screen reader, physical mixed-DPI setup and OS preference changes remain manual gates.

[Six bundled sample checks](sample-qualification.json) use actual isolated OCR and Google's live translation endpoint, with no user content. Recognition fidelity is 1.0 for Japanese/Korean/English/Spanish, 0.947 for Simplified Chinese and 0.842 for Traditional Chinese; every translation is nonempty and differs from the authored source. Paid APIs and loaded local LLMs remain unqualified.

The final two-hour native-resource soak, final binary/installer lifecycle, artifact privacy scan and hosted CI results are recorded after completion in the production report. Partial/interrupted runs do not count. **Stable verdict remains NOT READY:** publisher signing is unavailable and the manual matrix is incomplete. The following beta1 evidence is retained as the baseline, not substituted for beta2 qualification.

## Beta1 baseline

This report distinguishes repeatable checks from unqualified scenarios. It does not certify every game, display layout or model.

## Completed checks

| Area | Evidence |
|---|---|
| Domain and integration regression | 145 pytest cases pass, including real worker threads, stale successes/failures, pause/resume, stop cancellation, bounded queues, cache identity, context budgets, settings recovery, endpoint security and privacy |
| Overlay | 60 scripted size/preset/script/long-output combinations; click-through/edit flags; DPI cache invalidation; full-copy retention; style validation/persistence |
| Static checks | Ruff lint and formatting; mypy on 26 application modules |
| Fresh dependencies | New CPython 3.12 x64 environment installs the 75-distribution Windows lock with artifact hashes; editable installation, startup and the regression suite pass |
| Dependencies | Complete locked environment audited against the vulnerability database: no known vulnerabilities at the time of this run |
| Repository hygiene | Signature scan of the publishable text tree found no suspected credentials; runtime/private/build folders are ignored. This is not a guarantee against every secret pattern |
| Recognition | Verified model installation and corrupt-download cleanup; real isolated Japanese OCR exact match; native process shutdown; nine synthetic fixtures and three preprocessing variants, each repeated three times |
| Provider contracts | Ten adapters exercised with mock transports, discovery schemas, invalid payloads, auth/quota/timeout/redirect errors, scoped prompts and safe error messages |
| Real translation | Google's quick endpoint returns a nonempty translated result for authored synthetic Japanese; no paid credentials or real local LLM were supplied |
| Actual desktop | Guarded synthetic window at 125% Windows scaling; physical crop matches the fixture, OCR is exact, and translation differs from source; cold total about 4.0 s, including process/model startup |
| Native shortcuts | Eight actions register successfully after first-run fallback; four base shortcuts were occupied on this host. Registrations were released after the probe |
| Native credentials | Source and frozen app roundtrip a temporary synthetic Windows Credential Manager entry and delete it; sandbox access denial was tested as a safe error |
| Source packaging | Wheel and source distribution compile successfully; package assets resolve |
| Binary packaging | PyInstaller folder and Inno per-user installer compile; runtime startup, isolated OCR, credential storage and installer lifecycle are checked before upload |

The frozen Qt startup initially failed because an unrelated Poppler ICU DLL on PATH was collected into the app. Build analysis now runs with an isolated Windows/Python PATH and uses system ICU. Development-environment auto-downloaded OCR weights are explicitly excluded; managed resources come from verified application-data models. Qt/PySide corresponding sources and original license texts accompany binaries.

## Measured behavior

The [OCR report](ocr-benchmark.json) contains every fixture and preprocessing result; [the earlier model baseline](ocr-v4-benchmark.json) and [multilingual comparison](ocr-v6-comparison.json) retain unsuccessful alternatives. Seven of nine original-color fixtures have zero whitespace-normalized character error. Korean initially failed because the document angle classifier rotated upright subtitles; disabling classification and selecting its dedicated recognizer corrected it. Simplified Chinese loses punctuation (CER 0.1); Traditional Chinese also confuses a character (CER 0.2). These remaining failures are not hidden.

Warm recognition medians on this host are roughly 0.9–1.4 seconds for the 660×160 fixture corpus. Original RGB remains the default because contrast/upscaling did not consistently improve this sample. A high-confidence settled frame needs one inference; uncertain/accuracy-mode text is confirmed from a fresh captured frame, not by repeating OCR on identical pixels. Idle capture cadence backs off after three unchanged seconds while static OCR remains suppressed.

The [30-second synthetic soak](performance.json) accepted 40 changing lines, retained eight context pairs and 40 cache entries, and observed event queue occupancy at most two, with no pending frames/text at completion. Cached overlay paints measured about 1.1 ms median and 2.0 ms p95. The report's memory values cover Python allocations only, not native Qt/ONNX buffers. Synthetic inference and a brief soak do not validate several hours of real media or native memory growth.

## Remaining qualification

Before calling this stable, complete the [manual release matrix](release-checklist.md): clean supported Windows user account, multiple resolutions, physical mixed-DPI/negative-origin monitors, display hot-plug/rotation, exclusive and borderless games, prolonged media use, stylized/vertical/RTL OCR and real configured cloud/local models. This host supplies one physical 125% configuration; unit transforms cover other geometries without proving their native behavior.

The beta is unsigned. There is no publisher signing certificate in this workspace. Hashes and library/source inventories improve auditability but do not replace signing. CI is configured to rerun Windows quality and packaged startup; release-candidate builds require manual dispatch and do not autonomously publish. Any remote CI result must be checked separately from the local evidence.

Cloud OCR, screenshot/vision upload, GPU OCR, speech, automatic quality routing, persistent history, multi-region sessions and window-relative tracking are not exposed as completed features. Interfaces leave room for them. The beta keeps local OCR independent of its translation adapter and never falls back to cloud silently.

[Actual onboarding qualification](onboarding-qualification.json) exercised native setup buttons at effective 200% scale using a fresh isolated Japanese model directory and live Google translation. Next stayed blocked until pack verification and actual OCR/provider success; Finish saved completion, Set up later saved nothing, and no OCR children remained. This qualifies the onboarding controller and overlay on authored content, rather than a full real-game/user session.

The local source soak uses CPython 3.12.14. Release CI now uses hash-pinned CPython 3.12.15 and has a separate two-hour endurance option for the actual release runtime; final evidence must distinguish the two. A clean-source preflight catches tracked-file rewrites during preparation; the library manifest generator now preserves LF line endings on Windows. Stable gates also reject an interpreter version different from the recorded soak.

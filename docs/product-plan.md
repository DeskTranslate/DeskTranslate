# Product review and implementation plan

2026-10-16, continuing PR38. The objective is a strong Windows screen-translation product, not a completed spreadsheet of release gates. V1 supplies use cases and compatibility history; its globals, worker/widget coupling, executable-path setup and polling assumptions are not templates for V2.

## Product-level reassessment

The key journeys are quick region translation, continuous subtitles/dialogue, following an application window, changing languages/provider without losing a usable setup, recovering from missing models/provider errors, and restarting with sensible preferences. OCR/translation quality must be evaluated through those journeys as well as through engine fixtures.

| Subsystem | Assessment and decision |
|---|---|
| Capture / Windows integration | Keep physical capture, per-monitor transforms and conservative window identity/occlusion checks. They close actual v1 defects. Physical mixed-DPI/session/fullscreen qualification remains required; do not disguise simulations as those results. |
| Recognition | Keep isolated CPU ONNX inference and hash-verified language packs. Existing model/preprocessing trials show cross-case regressions, so do not replace models indiscriminately. Expand text-free/difficult-content evaluation and inspect errors before choosing changes. |
| Translation | Keep explicit local/cloud choice, native adapters, bounded context and cancellable pooled HTTP. No silent fallback. Service connectivity is not model quality; retain measured tiny-model failures and require actual representative generations. |
| Concurrency | Keep bounded mailboxes and owned OCR jobs. The completed source-matched hosted steady/fault runs must be inspected independently. A switch to a new async framework would add migration risk without demonstrated product benefit. |
| Main window / state | The controller still combines UI construction, session coordination and setup. Extract user-facing session presentation into a Qt-free contract where it prevents real status/action inconsistencies; avoid a mechanical file split. Stop routine notices from obscuring capture state and stop idle polling when no work exists. |
| First-run / provider setup | Material friction: existing local-provider choices default back to Google when reopening setup; advanced setup requires leaving/restarting the guide. Preserve explicit provider choice and reuse the existing provider editor with a resumable guide, rather than duplicating key/model logic. |
| Language changes | Swap currently saves two intermediate states, including an unnecessary same-language pair. Make it one durable transaction and one session invalidation. Preserve source-engine capability checks. |
| Missing-model recovery | Starting should lead to an explicit download-and-continue action with size/progress, not an unexplained stop and repeated setup. Cancel/configuration changes must invalidate any continuation. |
| Settings / profiles | Keep atomic validated persistence and secure endpoint-scoped OS credentials. Window placement and finer separation of UI-only from runtime configuration remain review items; do not add unsafe automatic migration or implicit capture consent. |
| Packaging | Portable/installed storage and per-user runtime ownership are sound improvements. Hosted Server build/install evidence is not a clean consumer Windows/no-Python/legacy-upgrade pass. Trusted signing remains unavailable and cannot be simulated. |
| Observability / privacy | Keep content-free numeric diagnostics and metadata-only logging. Operational state needs to be understandable in the UI without enabling persistent screenshots/history. |
| Dependencies / legacy | Qt6, Pillow/MSS, ONNX Runtime and HTTPX have concrete purposes. Retain portable domain boundaries while prioritizing Windows behavior. Audit unused persisted fields and duplicated controller paths; do not add frameworks for cosmetic modernity. |

## Priority order for this pass

1. Verify hosted artifacts/provenance, actual installer report and full resource/latency distributions. Preserve earlier failed evidence.
2. Fix language transaction correctness and first-run provider continuity; cover the full leave/configure/resume/retest flow offscreen.
3. Make capture/session status and available actions truthful and persistent across ordinary notices, pause, error, one-shot completion and shutdown. Remove idle timer work without reducing event delivery.
4. Improve missing-language-pack recovery with explicit install-and-continue consent and cancellation/configuration guards.
5. Measure additional authored positive/negative OCR cases and complete recognition→provider→presentation component flows without desktop capture. Adopt quality changes only when comparative evidence supports them.
6. Run the complete baseline plus new behavioral regressions, lint/types, offscreen previews, build/security checks and updated isolated Windows qualification as appropriate. Re-review the actual flows, then update readiness evidence.

Routine validation stays offscreen with temporary data/vault/input boundaries. Expensive OCR evaluation is an explicit separate command. Installation/endurance belongs on disposable hosted runners. No foreground media, display changes or prolonged desktop interaction is part of this plan.

Signing, consumer-Windows/physical-hardware/accessibility and unconfigured-account evidence are real limitations. They remain visible, but they do not define the product backlog or excuse avoidable workflow defects.

## Findings from executing the product journeys

The offscreen journey exposed a P1 that existing mocked coverage missed: cancelling an idle OCR process during pause could consume the first resumed static frame solely to retire that process. No new frame was requested, so recognition stalled until pixels changed. The deterministic test failed before the root fix; worker retirement now resets capture/stabilization, and actual OCR→HTTP→controller delivery after resume passes.

Provider-preserving/resumable setup, atomic language swap, persistent session actions/status and guarded install-and-continue are implemented and have behavioral regressions. No idle pipeline timer remains after stop or completed one-shot cleanup. The unused `speak` field had no implementation; older preferences load safely while new saves omit it. Core OCR/process/provider boundaries remain deliberately unchanged apart from the measured cancellation fix.

Five real-OCR controller journeys pass. The separate 24-case negative OCR experiment passes flat/gradient/striped/grid backgrounds but produces false short characters on geometric shapes in four languages. Those failures remain visible. Confidence-cutoff changes require comparison with the full positive corpus and short text, not tuning to erase these failures. Do not treat successful HTTP fixture replies as semantic translation qualification.

The previous703ee15 hosted candidate is independently hash/provenance/attestation verified: installer lifecycle, two-hour same-worker and thirty-minute fault workloads pass. The new application changes require fresh qualification; those baseline reports are retained under explicit commit-named paths rather than relabelled as current-source evidence.

The final shutdown review found another P1: a delayed first-run callback could create a guide after Quit, and new setup jobs could start after the shutdown coordinator had inspected its workers. A RED offscreen test reproduces it. Closing now hides/disables the app and rejects late setup/new work. The startup review also found unrestricted concurrent writers to one settings directory; one-owner lifetime locking and bounded user-only activation now replace duplicate windows. Actual offscreen processes verify relaunch/restore, preferences, crash recovery, failed startup, no verification activation, clean unlock and24-cycle native resource bounds.

The first a2a2544 hosted candidate was cancelled during build, before endurance, when the shutdown defect changed application bytes. It must not be treated as a completed candidate. Its ordinary quality job remains separate evidence. Qt tests now retain one offscreen QApplication for the session after notifier lifetime exposed a harness native abort; owned-object cleanup and all behavioral/resource assertions remain active.

The final error-state review found cleanup failures were detected only for retired pipelines. A completed one-shot could therefore display success until the next Start/Stop. A RED controller regression reproduces that omission. Presentation now stops further work and retains a restart-required state, including after ordinary notices; retry/live actions cannot imply recovery is possible. Cleanup still occurs in its owned workers, with no GUI-thread join or forced collection.

The related action review reproduced two additional RED paths: queued selection after Quit and one-shot selection/window hiding after cleanup failure. Both now run the closing/fatal preflight before UI transitions. This guard changes no OCR implementation/model/fixture; the44-case confidence experiment keeps its original full source hashes and is scoped to the unchanged recognition components rather than rerun solely to rewrite its window-controller hash.

A retiring worker failure can arrive after a replacement live session starts. Its RED regression showed capture continuing despite the new failure label. The fatal transition now uses the controller's normal Stop operation, retiring all current work and clearing selection/pending starts before presenting the restart state. It does not merely change the label or stop only the worker that reported the failure.

# DeskTranslate v2.0.0 release-readiness report

Assessment date: 2026-10-16. **Publication HOLD.** Product engineering continues on [draft PR 38](https://github.com/DeskTranslate/DeskTranslate/pull/38). The target is 2.0.0; the internal canonical identifier remains 2.0.0b2 until the stable gates pass. No new beta, stable release, tag or merge was published during this qualification phase. MIT is the selected project license; publisher signing is unavailable.

This report distinguishes current automated evidence, earlier native observations, failed experiments and missing qualification. The [acceptance matrix](validation.md) records test/environment/result/evidence/limitation. The [finding register](production-audit.md) records every meaningful defect, root cause, disposition and regression. PASS refers only to the stated scope.

## Product reassessment and latest changes

The [product review and plan](product-plan.md) starts with quick translation, continuous dialogue, application following, setup/provider continuity, recovery and retained preferences. V1 supplies product intent and compatibility history, not an architecture template. The typed bounded pipeline, isolated CPU inference, managed verified models and explicit provider choice remain deliberate choices. No additional framework or speculative subsystem was added.

- **P1 resume correctness:** the actual OCR→HTTP→controller journey exposed a defect missed by the old mocked suite. Pausing an idle OCR worker left it cancelled; its first resumed static frame retired that worker without scheduling another. A deterministic RED test reproduces the stall. Intentional retirement now requests fresh capture/stabilization without consuming crash allowance. The new regression and real-OCR journey pass. [Preserved pre-fix failure](product-component-before-resume-fix.json).
- **Setup continuity:** reopening the guide preserves a configured local provider. Configure translation opens the existing provider editor; returning retains draft languages and requires a new sample qualification. Local/remote endpoint privacy is shown accurately. Provider keys/model configuration have one implementation.
- **Durable language switching:** swap saves one pair and invalidates the session once. A failed save leaves both controls, stored settings and active work intact.
- **Missing-model recovery:** an explicit Install pack and continue action replaces repeated setup. Size/progress remain visible; Stop, cancel or any successful configuration change invalidates the continuation. An older download cannot restart capture or erase a newer request.
- **Clearer session UX and idle ownership:** capture status remains visible across pages and notices. Main window, overlay and tray share pause/resume/retry actions. Completed one-shots deliver queued results before stopping their timer; stopped sessions have no pipeline polling. Overlay visibility changes give immediate feedback. Synthetic dark/light previews are refreshed.
- **Dead code:** remove the unimplemented `speak` setting. Earlier files still retain useful preferences; no exposed speech feature was removed.

[Current component evidence](product-component-qualification.json) passes five real-OCR main-window journeys and verifies zero surviving OCR children. It uses authored captures and real owned loopback HTTP with fixture replies; it does not establish semantic provider quality, native capture or physical display behavior. Source-mode cold one-shot/start/resume/retry/language-change delivery takes roughly5.4–6.0s on this host; these include process/model loading and are not warm-OCR measurements.

The same command deliberately returns **FAIL** overall:20/24 negative backgrounds remain empty, but authored ellipses/diagonals produce short false characters in Japanese, English, Korean and Chinese. The failure is retained, with actual strings/confidence. The [44-case confidence experiment](ocr-confidence-experiment.json) compares all35 positive fixtures plus nine short-text/digit/punctuation cases. Raising the cutoff to0.8 regresses Arabic mixed digits;0.9 also regresses English digits, Arabic multiline, Japanese vertical/pixel text and Traditional Chinese. No global threshold was changed to erase negative-test failures. Tight crops remain necessary; representative real-media accuracy is still unqualified.

The completed703ee15 candidate has independently verified archive/release hashes, clean provenance and three hosted artifact attestations. Its installer lifecycle,7200.12s same-worker and1800.27s fault workloads pass. [Exact baseline evidence](hosted-candidate-703ee15.json) is retained under commit-named paths. Those reports predate the new product code and do not qualify the changed application. Existing failed/incomplete runs remain preserved.

## Changes made and bugs discovered

The audit covered the application/source tree, tests, dependency locks, OCR assets/downloads, provider implementations, capture/transforms/overlay, settings/profiles/credentials, diagnostics/update handling, build/installer/workflows, user documentation, v1 source/distribution and all 23 historical issues with 35 available comments.

Meaningful production-hardening changes are:

- **Session correctness:** moving backgrounds no longer require indefinite stillness before OCR. Semantic source/blank generations preserve useful in-flight work; stale frame/session/command results remain rejected. Confirmed one-character changes are accepted. Stop/suspend closes selection and ignores late picker callbacks; one-shot/fatal worker retirement preserves the queued result identity.
- **Durable settings:** settings/profile/capture changes validate and save before activation. Failed writes leave active state intact, restore credential state and show an error. Corrupt configuration is retained until explicit recovery. First-success state is committed only after a successful save. Setup/model-catalog/update jobs reject obsolete revisions.
- **Windows worker ownership:** kill-on-close jobs contain OCR descendants; initialization/reap checks and lock-free cancellation handle startup/stop races. Deliberate cancellation does not consume crash-recovery allowance. Cleanup failure is visible, returns failure and releases global slots.
- **Two measured resource defects:** 20 early cancellations reproduced 21 leaked pipe handles because the default Windows connection reducer left a parent-owned duplicate before child unpickling. OCR-local child-owned duplication fixes that regression. A later 30-minute fault run still grew 41 handles: failed asyncio tasks retained tracebacks into retired sessions and their synchronization objects. Sync-boundary exception/task ownership now releases those sessions without forced GC; a GC-disabled weak-reference regression passes. Failed runs and unchanged budgets are retained.
- **Provider reliability:** strict schemas, bounded responses/metadata, total header/body deadlines, cancellation, safe errors and escaped catalog presentation; corrected Traditional Chinese Libre mapping. Real LM Studio silently accepted a missing model and substituted another; current catalog and returned-model checks now reject it. Ollama incomplete/truncated completion responses fail safely. Local server guidance now covers Libre/custom services as well as AI servers.
- **Coordinates and overlays:** signed32-bit rectangle checks, monitor-origin-relative transforms, negative-origin/topology tests and fail-closed display mapping. Coalesced native DPI refit fixes actual transition clipping. Passive/edit focus, workarea fitting, self-capture exclusion, fade recovery and resized geometry are corrected. Full translations remain available when the overlay line limit clips presentation.
- **OCR:** measured Latin/Cyrillic/Devanagari recognizer improvements, Arabic logical-order correction, safer reconstruction and a 4096-pixel detector long-side bound for extreme aspect ratios. Ordinary detector tensors and35×3 OCR outputs remain unchanged by that bound. Model files check expected size/hash before activation; interrupted/corrupt downloads do not become installed models. Clear actionable accuracy/overlong-region messages replace misleading recovery guidance.
- **UX and compatibility:** restore v1's 133 translation targets while keeping the 19 managed OCR sources distinct; engine-aware source selection, aliases/RTL metadata and safe swap. Compact keyboard-accessible navigation keeps eight pages usable in small logical workspaces. Three corrupted language-label characters are corrected. Profiles, first-run flow and saved-state feedback have failure regressions.
- **Performance:** binary font fitting, painted-band glyph caches and a bounded mask area reduce long-subtitle render cost. Capture/OCR suppression for static content remains active; no speculative model routing or extra background polling was added.
- **Distribution:** adjacent portable data, deliberate v1 coexistence/data-retention policy, runtime ownership markers, removal of obsolete owned runtime files and refusal of unknown/junction runtime paths. Hosted installer probing exposed a final uninstall-cleanup race: bounded observable cleanup now precedes reinstall, and missing expected uninstallers fail. No forced deletion manufactures a pass. Isolated hash-locked builds avoid prior Poppler/ICU contamination. PE metadata, notices, matching LGPL sources, separate SBOMs, provenance and SHA-256 sums are checked. Trusted signing remains a hard gate.
- **Privacy/supply chain:** process-local ONNX diagnostic opt-out before native import/session creation; accurate upstream Windows ETW limitation. License archive extraction rejects traversal, drive/ADS/reserved-name tricks. Source/history/artifact scanning preserves content-free reports. A hosted privacy false positive in python-bidi is handled only after exact locked-wheel/RECORD/binary verification; modified files and application paths remain rejected, and credential signatures remain active.
- **Evidence quality:** stable gates require current source/assets/runtime/harness, strict success/cleanup/resource values, two-hour same-worker and30-minute fault workloads. Long commands fail on resource failures. A laptop standby gap exposed an additional weakness: continuous observation through the start/end is now required, with gaps over 90 seconds rejected. No power setting was changed.
- **Documentation and sustainable testing:** V2 README/screenshots, upgrade/privacy/provider/developer/release documentation and issue dispositions replace stale mandatory-Tesseract/source-user instructions. Default tests force offscreen Qt, temporary data, an in-memory credential backend and isolated input/network/capture boundaries. Manual native/installation and extended stress are explicit opt-ins, bounded and excluded from routine validation; prolonged visible media was stopped on maintainer request.

The v1 comparison found no persisted JSON language settings to migrate. V2 retains133 translation targets and offers optional external Tesseract for broader source coverage, but does not claim all69 v1 sources as managed OCR. Linux, OneRing-specific integration and old translation/speech services are not presented as completed Windows features.

## Tests added

Coverage now includes transactional writes/rollback/corrupt recovery; provider malformed/auth/quota/deadline/cancellation/model identity; worker descendant/early-spawn cleanup; failed-session retention without cyclic GC; stale/interleaved/one-shot/pause/stop behavior; model interruption/corruption; overlay Unicode/CJK/RTL/geometry/edit/fade; licensing path attacks; version/signing/stable evidence failure cases.

The non-invasive architecture adds 60 pure geometry combinations (six resolutions/orientations×five scales×positive/negative origins), direct offscreen picker drag/corner/Enter/Escape events, and boundary/CLI/timeout/polling policy cases. Observation-gap/timestamp, exact upstream binary privacy verification and bounded cleanup-polling regressions remain. This product pass adds22 cases for setup/status, atomic swap/failed writes, consent/cancellation/obsolete download completion, static resume, retired configuration and opt-in boundaries. Total routine suite:427 tests. Native boundary simulations remain distinct from physical hardware tests.

## Verification actually performed

Commands below ran from the repository root with the isolated pinned runtime at `.audit/stable-build-venv/Scripts/python.exe`:

| Command | Result |
|---|---|
| `python tools/validate.py --predeploy --junitxml .audit/pytest-product-final.xml` | PASS; exit0,427 tests59.24s, Ruff lint/format86 files, mypy43 modules, source smoke, pip check/audit/history scan and wheel/sdist |
| `python -m pytest -q tests/test_pipeline.py tests/test_product_flows.py tests/test_presentation.py` | PASS;38 cases18.42s after the resume root fix; RED resume case timed out before the fix |
| `python tools/qualify_product.py --component-test --output docs/product-component-qualification.json` | FAIL overall; five real-OCR controller journeys and no-remaining-child check PASS,20/24 negative backgrounds empty, four shape false positives retained |
| `python tools/evaluate_confidence.py --ocr-experiment --output docs/ocr-confidence-experiment.json` | PASS execution of44 authored positives/short cases;0.8/0.9 tradeoff regressions reject a blanket cutoff increase |
| `python tools/render_ui.py` | PASS;18 dark/light authored offscreen previews rendered; Translate, Profiles and Providers visually inspected |
| `python tools/build.py --installer` and `python .audit/qualify_artifacts_current.py` | PASS on the new product source; unsigned portable/setup compiled,20 metadata/hash/runtime/SBOM/notice/content checks pass |
| `python .audit/qualify_portable_headless.py` | PASS on the new portable; nine checks, exact Japanese OCR2113.21ms, real loopback HTTP and temporary vault cleanup, CJK/space paths, system-only PATH and empty working directory |
| `python tools/validate.py --predeploy --frozen dist/DeskTranslate/DeskTranslate.exe --junitxml .audit/pytest-final-installer-wait.xml` | PASS; full command exit0,405 pytest cases in 49.18s, Ruff lint/format (81 files), mypy (42 modules), source/frozen smoke, pip check, vulnerability audit, source/history scan, wheel and sdist |
| `python -m pytest -q -x tests/test_privacy_scan.py tests/test_release.py` | PASS; 42 tests in 2.46s |
| `python -m pytest -q -x tests/test_validation_policy.py` | PASS; 16 tests in 7.13s; hidden PowerShell polling only, no install/uninstall |
| `python tools/privacy_scan.py --history --artifacts --output docs/privacy-scan.json` | PASS on final local binaries;322 tree,581 reachable history blobs,403 runtime files,410 release archive members,1482 frozen modules on the new local artifacts; no findings |
| `python tools/build.py --installer` with the pinned archive digest and isolated build environment | PASS; portable and Inno installer compiled; [20 artifact checks](artifact-qualification.json) pass |
| `python .audit/qualify_portable_headless.py` | PASS; nine isolation/runtime checks plus actual exact Japanese OCR/HTTP/vault deletion; final portable digest matched |
| `python -m pip download --no-deps --only-binary=:all: --dest .audit/vendor-verification python-bidi==0.6.11` followed by wheel/member hashing | PASS; wheel 0608bdd…1a4e47 matches lock, binary 8f286f…d38540 matches installed RECORD |
| `git diff --check` | PASS |

The direct sandboxed targeted-test attempt failed at fixture setup because of environment permissions; it is not a test pass. The approved offscreen targeted/full runs above subsequently passed. Initial automatic-approval usage limits deferred portable/privacy checks; both later executed successfully.

Hosted [Windows quality38752944599](https://github.com/DeskTranslate/DeskTranslate/actions/runs/38752944599) PASS at e504a9a: 403 tests in 39.525s, build/frozen runtime/privacy, zero dependency findings; its [report archive digest and safe fields are verified](hosted-quality-qualification.json). [Internal candidate38752963196](https://github.com/DeskTranslate/DeskTranslate/actions/runs/38752963196) FAIL: final uninstall registry/shortcuts remained; endurance was skipped. [Original failure](installer-hosted-failure.json) is retained. Bounded observable cleanup and required final-uninstaller checks subsequently pass the replacement hosted installer/privacy step. Steady/fault workloads are independent hosted steps when build/models are ready, so an unrelated installer failure cannot suppress their evidence; all failing gates still fail the job. Candidate inputs have empty tag, `stable=false`, `signed=false`, `endurance=true`; the workflow cannot publish. The earlier upstream-bidi privacy failure is also retained.

Replacement baseline703ee15: [quality38755463595](https://github.com/DeskTranslate/DeskTranslate/actions/runs/38755463595) PASS,405 tests35.941s with a [verified report archive](hosted-quality-703ee15.json). [Candidate38755499473](https://github.com/DeskTranslate/DeskTranslate/actions/runs/38755499473) completed PASS, including build/runtime, actual installer lifecycle/privacy and both extended workloads. Archive/release hashes, clean provenance and all three hosted attestations were independently verified against the exact source and signer workflow. [Verified baseline](hosted-candidate-703ee15.json); it does not qualify the subsequent product changes.

## Windows qualification

Actual host: Windows 11 Pro 10.0.26200, Lenovo 82RD, one 1920×1080/165Hz panel at OS 125% (Qt1536×864/DPR1.25), non-RDP. AMD integrated GPU active; NVIDIA RTX 3060 Laptop enumerated. Native observations below predate the non-invasive policy:

- Physical capture/picker equality at 1080p125%: drag/corners/Enter/Escape and exact crop comparison pass. Moving/static/blank authored dialogue produces results, with noisy extra OCR letters retained in evidence.
- Driver-applied1280×720 at observed Qt100%, restored1080p125%: UI/picker/capture and running stop/reselect/overlay checks pass. This uses the same native1080p panel, not a separate720p monitor.
- Driver-applied1080×1920 portrait and restored landscape: running topology/refit/reselection checks pass. The panel was not physically turned by hand.
- Effective Qt100/125/150/175/200% layouts pass. Small available-workspace layouts down to 640×360 fit eight pages. These are overrides/simulations, not five OS scale settings or physical mixed-DPI positioning.

NOT TESTED: physical 1440p/4K/ultrawide, multiple/negative-origin/mixed-DPI monitors, docking/hot-plug/primary changes, actual sleep/lock/RDP workflow recovery, exclusive fullscreen/HDR, GPU routing, real Narrator/OS high-contrast session. The soak's Modern Standby event does not qualify product resume behavior. Real game/anime media remains missing. No further display/focus/playback tests were run after the policy change.

## OCR qualification and performance

[35 authored fixtures](ocr-benchmark.json) run three preprocessing modes×three repeats, across Japanese, Korean, Simplified/Traditional Chinese, English, Spanish, French, German, Italian, Dutch, Polish, Indonesian, Turkish, Russian, Ukrainian, Hindi, Portuguese, Vietnamese and Arabic. Assets are authored/redistributable; font programs and third-party game frames are not bundled.

Clean horizontal JA/KO/EN/ES and authored English outline/shadow/translucent/low-contrast samples are exact. Chinese punctuation and Traditional characters retain errors (representative CER0.10–0.20; difficult Traditional case~0.176). Vietnamese CER~0.278; its setup fidelity0.791 fails the unchanged0.8 guard and prevents transmission. Vertical Japanese CER~0.429/0.583; pixel Katakana~0.364. Arabic logical order is fixed, while mixed/digit/multiline fidelity is imperfect. Alternative model/scale/preprocessing experiments caused cross-case regressions and were not adopted globally.

All 19 installed packs perform real inference with Python connect/DNS/download paths forbidden and zero attempts. That is not a native packet/ETW trace. First-run sample qualification passes 18/19 actual OCR+Google cases; Vietnamese remains FAIL. Real moving-film background has only a historical300.49s authored-subtitle probe (5569frames,19results,five sources), not representative game/anime typography or multi-hour qualification.

Warm original-fixture median1292.96ms across the benchmark, range757.07–2317.64ms under concurrent QA; cold Japanese~3135ms. Current portable first isolated OCR2113.21ms. The source-mode controller journey includes process/model startup and takes5.4–6.0s; these are distinct workloads, not a controlled speedup claim. Hosted steady/fault distributions are reported below. Native subtitle rendering medians improve5000 chars176.2→19.3ms and20000 chars653.6→84.6ms; glyph-cache RGBA storage3.96→1.43MB. Idle CPU is not increased to chase OCR latency.

## Provider qualification

All ten exposed adapters have mock contracts/fault coverage. Real service evidence is narrower:

| Provider | Real result and limit |
|---|---|
| Google quick | PASS authored Spanish/Hebrew/Thai/Czech outputs and18 setup samples; earlier429 retained, no availability guarantee |
| DeepL, OpenAI native/Chat, Claude, Gemini, OpenRouter | NOT TESTED with real accounts; no configured keys, no invented auth/quota/model success |
| LibreTranslate | Public unauthenticated request safely rejected; no successful authenticated/owned-server generation |
| Ollama 0.40.4 |12 service checks PASS with CPU Qwen3:0.6b and Qwen2.5:1.5b: discovery/offline/missing/unload/reload/restart/cancel; semantic quality FAIL |
| LM Studio llmster0.0.25-1 / llama.cpp2.41.0 |13 service checks PASS, context/disconnect included; actual missing-model fallback reproduced/fixed; model output quality FAIL |
| Compatible | Mock/owned loopback PASS; arbitrary external server/account NOT TESTED |

The 0.6B models produced wrappers or empty objects. The 1.5B models omitted meaning or variably added explanation. Repeated temperature/prompt experiments did not justify a global request change. They are test models, not qualified recommendations. Measured cancellation~11.8ms Ollama/~4.2ms LM Studio is service-specific; cold/warm generation varies by model. Owned services were shut down and profiles isolated. No keys were printed/persisted in reports.

## Reliability

An earlier 7200.51s same-worker steady run accepted 504 translations and passed resource budgets, but its source predates the pipe/async fixes; it is superseded. Earlier 30-minute fault runs failed +44.5 and+41 handles and are preserved. Those failures led to the two concrete resource fixes above.

The previous laptop fault run requested1800s and elapsed2009.58s, accepted54<58, sampled only through1050s and failed overall. Windows Kernel-Power events show lid-triggered Modern Standby from10:46:00Z to11:01:36Z. Its observed resource deltas were within budgets, but observations do not establish continuity. The new coverage gate rejects its959.58s end gap. This failure remains preserved.

The independently verified703ee15 hosted baseline now supplies continuous7200.12s steady and1800.27s fault evidence, with observation gaps no larger than30.27s. Steady keeps the same OCR worker, accepts513 results and makes513 HTTP requests, with38590 captures/3779 OCR operations/2773 stale discards. Main RSS/private growth is6.03/17.45MiB, handles+1, threads+0 and Python heap+8.91MiB. Child RSS/private growth is−1.32/+0.97MiB, handles+2 and threads+1. Native/Python queues, workers and sockets stay within the original budgets; zero children remain after cleanup.

Fault mode accepts120 results, injects62 HTTP faults, replaces36 sessions and recovers10 OCR crashes. Main private growth is2.96MiB with zero handle growth. Event queue peaks2/8 in steady/fault modes. Cancellation median/p95 is15/31ms across116 observations. Steady accepted-result total p50/p95 is344/406ms and OCR340/393ms; fault total360/1703ms and OCR356/825ms. Main CPU median is0.208% active and0.052% static of one core in steady mode, excluding worker CPU and including harness overhead. These hosted synthetic figures are not a controlled laptop speedup, clean consumer-Windows or real-media guarantee. Both workloads pass strict coverage/resource/cleanup gates, but their exact source predates the new resume/UX changes and must be refreshed for that application.

## Installer and portable qualification

Current internal local portable SHA-256: `55f62c95a3092b31306a78add32c777bba95ecd0151b78c448d8538db14c2df9`.

Current internal local setup SHA-256: `514c4811775a0656186ab36524a4893592a06b1a075a3e3f711c68d7a595832f`.

Application source digest: `f60562c1b0f139ddda2bf314d70501085d057652f481ed1cf2684c6abab88a50`. Local provenance accurately records an unsigned dirty-tree build; a matching application digest does not rewrite that provenance into a clean hosted claim.

Current portable passes extraction into a CJK/space path, empty CJK working directory, system-only PATH/no Python environment, marker/adjacent settings/model/log isolation, exact Japanese OCR, loopback HTTP and temporary vault roundtrip/deletion. It never takes foreground or captures the desktop.

Previous-artifact native/per-user installer evidence passes install, beta1 upgrade, reinstall, stale runtime removal, Unicode shortcuts, metadata/registry, uninstall/data+model retention and reinstall-after-uninstall. Unknown-runtime/runtime-junction/parent-junction probes refuse with exit 7 and preserved sentinels. These are historical artifact digests. The first hosted candidate passed installation/runtime/first uninstall/reinstall, then failed final cleanup. Inno documents that its temporary clone can continue after original-process exit; the new harness waits for actual EXE/registry/shortcut disappearance before reinstall and fails rather than skipping a missing final uninstaller. [Official lifecycle reference](https://jrsoftware.org/ishelp/topic_uninstexitcodes.htm). The independently verified703ee15 installer lifecycle/privacy report confirms the observable lifecycle fix for that baseline artifact. The new application needs its own hosted installer run. The legacy 1.1a InstallForge 1.4.4 binary was inspected and requires Administrator; it was not installed on the laptop. Clean supported consumer Windows without Python, actual non-ASCII username, standard account, long-path/legacy coexistence and publisher trust remain unqualified. A dedicated interactive consumer-Windows VM and verified unattended legacy protocol were unavailable; no accounts/features/reboots were added.

## Security and privacy

Current source/history/artifact scans report no findings within signature coverage. 76 hash-locked dependencies have no known vulnerability findings in the performed pip-audit query; pip check passes. Runtime uses pinned CPython 3.12.15/OpenSSL 3.5.9, verified archive SHA 11ed9f…abc64a. 42 runtime/78 build SBOM components, 131 notices and matching Qt/python-bidi LGPL sources are present. Inspection finds no prior Poppler/ICU/local-LLM contamination, private/test files or unintentionally bundled OCR weights. SBOM inventory is not a claim of an exhaustive embedded native graph or byte-identical reproducibility.

Screenshots/text/context remain in memory by default; explicit user copy/export is separate. Credential Manager holds provider secrets; logs/diagnostics omit captured content. Endpoint validation, redirects, request/response/download bounds, archive paths and hash activation were reviewed/tested. No automatic local-to-cloud fallback exists. ONNX opt-out is set before native import and disable API before inference; upstream minimal Windows initialization/ETW behavior remains documented rather than falsely claiming zero events. Local AI servers can keep their own logs. A historical local Defender scan completed without detection events; it does not certify this final digest, every AV engine or SmartScreen. No certificate is available and no self-signing was substituted.

## GitHub issues

All 23 bodies and 35 available comments were reviewed. [Individual dispositions and prepared notes](issues-v2.md) remain the authoritative per-issue table. No issue comments/closures were posted.

| Issues | Disposition |
|---|---|
|#22,#20,#32,#5,#7 | Fixed on stated regression/authored managed paths; original reporter content still needs confirmation where noted |
|#33,#30,#29,#26,#19,#15,#6 | Partially fixed; account/model, physical display, stylized OCR or optional-runtime/server qualification remains |
|#31,#21,#17,#25 | Needs reporter/release-specific verification; original#31 attachment unavailable; no blanket AV claim |
|#27,#16,#8 | Old Python/source-install workflow obsolete for intended packaged users; clean-machine packaging still required |
|#28 | Representative pixel Katakana error remains reproducible; original game attachment unavailable |
|#13 | OneRing-specific integration not implemented; future work |
|#18 | Linux request outside qualified Windows scope |
|#14 | No actionable defect/reproduction supplied |

## Remaining blockers and recommendation

No known P0 is intentionally left unresolved; this is not a claim that untested environments have no P0 defects. No P1 qualification gap has an implicit waiver. Required remaining work:

1. Complete passing exact-source/harness hosted quality, final installer and continuous 2h/30min resource runs; review all report distributions and attestations.
2. Qualify physical mixed-DPI/multi-monitor layouts, topology/session transitions, actual supported fullscreen/media workflows and accessibility on a reserved rig/session, without returning invasive tests to the routine laptop loop.
3. Qualify clean supported Windows/no-Python/standard-account/non-ASCII-user and legacy install/coexistence/upgrade paths on a disposable OS.
4. Obtain representative local-model quality and configured cloud/Libre/custom-provider accounts where exposed claims require them; retain observed OCR limitations and complete representative media accuracy testing.
5. Obtain a trusted publisher signing certificate/service and verify Authenticode/timestamps/trust, then regenerate matching final metadata/artifacts/reports. Only after all stable gates pass may the canonical version become 2.0.0 and release promotion be considered.

NOT READY FOR v2.0.0 STABLE

# DeskTranslate v2.0.0 release-readiness report

Assessment date:2026-10-15. **Publication HOLD.** Engineering commits5671e16 and e504a9a are on [draft PR38](https://github.com/DeskTranslate/DeskTranslate/pull/38). The target is2.0.0; the internal canonical identifier remains2.0.0b2 until the stable gates pass. No new beta, stable release, tag or merge was published during this qualification phase. MIT is the selected project license; publisher signing is unavailable.

This report distinguishes current automated evidence, earlier native observations, failed experiments and missing qualification. The [acceptance matrix](validation.md) records test/environment/result/evidence/limitation. The [finding register](production-audit.md) records every meaningful defect, root cause, disposition and regression. PASS refers only to the stated scope.

## Changes made and bugs discovered

The audit covered the application/source tree, tests, dependency locks, OCR assets/downloads, provider implementations, capture/transforms/overlay, settings/profiles/credentials, diagnostics/update handling, build/installer/workflows, user documentation, v1 source/distribution and all23 historical issues with35 available comments.

Meaningful production-hardening changes are:

- **Session correctness:** moving backgrounds no longer require indefinite stillness before OCR. Semantic source/blank generations preserve useful in-flight work; stale frame/session/command results remain rejected. Confirmed one-character changes are accepted. Stop/suspend closes selection and ignores late picker callbacks; one-shot/fatal worker retirement preserves the queued result identity.
- **Durable settings:** settings/profile/capture changes validate and save before activation. Failed writes leave active state intact, restore credential state and show an error. Corrupt configuration is retained until explicit recovery. First-success state is committed only after a successful save. Setup/model-catalog/update jobs reject obsolete revisions.
- **Windows worker ownership:** kill-on-close jobs contain OCR descendants; initialization/reap checks and lock-free cancellation handle startup/stop races. Deliberate cancellation does not consume crash-recovery allowance. Cleanup failure is visible, returns failure and releases global slots.
- **Two measured resource defects:**20 early cancellations reproduced21 leaked pipe handles because the default Windows connection reducer left a parent-owned duplicate before child unpickling. OCR-local child-owned duplication fixes that regression. A later30-minute fault run still grew41 handles: failed asyncio tasks retained tracebacks into retired sessions and their synchronization objects. Sync-boundary exception/task ownership now releases those sessions without forced GC; a GC-disabled weak-reference regression passes. Failed runs and unchanged budgets are retained.
- **Provider reliability:** strict schemas, bounded responses/metadata, total header/body deadlines, cancellation, safe errors and escaped catalog presentation; corrected Traditional Chinese Libre mapping. Real LM Studio silently accepted a missing model and substituted another; current catalog and returned-model checks now reject it. Ollama incomplete/truncated completion responses fail safely. Local server guidance now covers Libre/custom services as well as AI servers.
- **Coordinates and overlays:** signed32-bit rectangle checks, monitor-origin-relative transforms, negative-origin/topology tests and fail-closed display mapping. Coalesced native DPI refit fixes actual transition clipping. Passive/edit focus, workarea fitting, self-capture exclusion, fade recovery and resized geometry are corrected. Full translations remain available when the overlay line limit clips presentation.
- **OCR:** measured Latin/Cyrillic/Devanagari recognizer improvements, Arabic logical-order correction, safer reconstruction and a4096-pixel detector long-side bound for extreme aspect ratios. Ordinary detector tensors and35×3 OCR outputs remain unchanged by that bound. Model files check expected size/hash before activation; interrupted/corrupt downloads do not become installed models. Clear actionable accuracy/overlong-region messages replace misleading recovery guidance.
- **UX and compatibility:** restore v1's133 translation targets while keeping the19 managed OCR sources distinct; engine-aware source selection, aliases/RTL metadata and safe swap. Compact keyboard-accessible navigation keeps eight pages usable in small logical workspaces. Three corrupted language-label characters are corrected. Profiles, first-run flow and saved-state feedback have failure regressions.
- **Performance:** binary font fitting, painted-band glyph caches and a bounded mask area reduce long-subtitle render cost. Capture/OCR suppression for static content remains active; no speculative model routing or extra background polling was added.
- **Distribution:** adjacent portable data, deliberate v1 coexistence/data-retention policy, runtime ownership markers, removal of obsolete owned runtime files and refusal of unknown/junction runtime paths. Hosted installer probing exposed a final uninstall-cleanup race: bounded observable cleanup now precedes reinstall, and missing expected uninstallers fail. No forced deletion manufactures a pass. Isolated hash-locked builds avoid prior Poppler/ICU contamination. PE metadata, notices, matching LGPL sources, separate SBOMs, provenance and SHA-256 sums are checked. Trusted signing remains a hard gate.
- **Privacy/supply chain:** process-local ONNX diagnostic opt-out before native import/session creation; accurate upstream Windows ETW limitation. License archive extraction rejects traversal, drive/ADS/reserved-name tricks. Source/history/artifact scanning preserves content-free reports. A hosted privacy false positive in python-bidi is handled only after exact locked-wheel/RECORD/binary verification; modified files and application paths remain rejected, and credential signatures remain active.
- **Evidence quality:** stable gates require current source/assets/runtime/harness, strict success/cleanup/resource values, two-hour same-worker and30-minute fault workloads. Long commands fail on resource failures. A laptop standby gap exposed an additional weakness: continuous observation through the start/end is now required, with gaps over90seconds rejected. No power setting was changed.
- **Documentation and sustainable testing:** V2 README/screenshots, upgrade/privacy/provider/developer/release documentation and issue dispositions replace stale mandatory-Tesseract/source-user instructions. Default tests force offscreen Qt, temporary data, an in-memory credential backend and isolated input/network/capture boundaries. Manual native/installation and extended stress are explicit opt-ins, bounded and excluded from routine validation; prolonged visible media was stopped on maintainer request.

The v1 comparison found no persisted JSON language settings to migrate. V2 retains133 translation targets and offers optional external Tesseract for broader source coverage, but does not claim all69 v1 sources as managed OCR. Linux, OneRing-specific integration and old translation/speech services are not presented as completed Windows features.

## Tests added

Coverage now includes transactional writes/rollback/corrupt recovery; provider malformed/auth/quota/deadline/cancellation/model identity; worker descendant/early-spawn cleanup; failed-session retention without cyclic GC; stale/interleaved/one-shot/pause/stop behavior; model interruption/corruption; overlay Unicode/CJK/RTL/geometry/edit/fade; licensing path attacks; version/signing/stable evidence failure cases.

The non-invasive architecture adds60 pure geometry combinations (six resolutions/orientations×five scales×positive/negative origins), direct offscreen picker drag/corner/Enter/Escape events, and16 boundary/CLI/timeout/polling policy cases. Latest regressions cover five observation-gap/timestamp failures, exact upstream binary privacy verification and two bounded cleanup-polling cases. Total routine suite:405 tests. Native boundary simulations remain distinct from physical hardware tests.

## Verification actually performed

Commands below ran from the repository root with the isolated pinned runtime at `.audit/stable-build-venv/Scripts/python.exe`:

| Command | Result |
|---|---|
| `python tools/validate.py --predeploy --frozen dist/DeskTranslate/DeskTranslate.exe --junitxml .audit/pytest-final-installer-wait.xml` | PASS; full command exit0,405 pytest cases49.18s, Ruff lint/format81files, mypy42modules, source/frozen smoke, pip check, vulnerability audit, source/history scan, wheel and sdist |
| `python -m pytest -q -x tests/test_privacy_scan.py tests/test_release.py` | PASS;42 tests2.46s |
| `python -m pytest -q -x tests/test_validation_policy.py` | PASS;16 tests7.13s; hidden PowerShell polling only, no install/uninstall |
| `python tools/privacy_scan.py --history --artifacts --output docs/privacy-scan.json` | PASS on final local binaries;300 tree,542 reachable history blobs,403 runtime files,410 release archive members,1481 frozen modules; later source/tool edits also pass the pre-deployment source scan |
| `python tools/build.py --installer` with the pinned archive digest and isolated build environment | PASS; portable and Inno installer compiled; [20 artifact checks](artifact-qualification.json) pass |
| `python .audit/qualify_portable_headless.py` | PASS; nine isolation/runtime checks plus actual exact Japanese OCR/HTTP/vault deletion; final portable digest matched |
| `python -m pip download --no-deps --only-binary=:all: --dest .audit/vendor-verification python-bidi==0.6.11` followed by wheel/member hashing | PASS; wheel0608bdd…1a4e47 matches lock, binary8f286f…d38540 matches installed RECORD |
| `git diff --check` | PASS |

The direct sandboxed targeted-test attempt failed at fixture setup because of environment permissions; it is not a test pass. The approved offscreen targeted/full runs above subsequently passed. Initial automatic-approval usage limits deferred portable/privacy checks; both later executed successfully.

Hosted [Windows quality38752944599](https://github.com/DeskTranslate/DeskTranslate/actions/runs/38752944599) PASS at e504a9a:403 tests39.525s, build/frozen runtime/privacy, zero dependency findings; its [report archive digest and safe fields are verified](hosted-quality-qualification.json). [Internal candidate38752963196](https://github.com/DeskTranslate/DeskTranslate/actions/runs/38752963196) FAIL: final uninstall registry/shortcuts remained; endurance was skipped. [Original failure](installer-hosted-failure.json) is retained. Bounded observable cleanup and required final-uninstaller checks now need a passing replacement hosted run. Steady/fault workloads are independent hosted steps when build/models are ready, so an unrelated installer failure cannot suppress their evidence; all failing gates still fail the job. Candidate inputs have empty tag, `stable=false`, `signed=false`, `endurance=true`; the workflow cannot publish. The earlier upstream-bidi privacy failure is also retained.

## Windows qualification

Actual host: Windows11 Pro10.0.26200, Lenovo82RD, one1920×1080/165Hz panel at OS125% (Qt1536×864/DPR1.25), non-RDP. AMD integrated GPU active; NVIDIA RTX3060 Laptop enumerated. Native observations below predate the non-invasive policy:

- Physical capture/picker equality at1080p125%: drag/corners/Enter/Escape and exact crop comparison pass. Moving/static/blank authored dialogue produces results, with noisy extra OCR letters retained in evidence.
- Driver-applied1280×720 at observed Qt100%, restored1080p125%: UI/picker/capture and running stop/reselect/overlay checks pass. This uses the same native1080p panel, not a separate720p monitor.
- Driver-applied1080×1920 portrait and restored landscape: running topology/refit/reselection checks pass. The panel was not physically turned by hand.
- Effective Qt100/125/150/175/200% layouts pass. Small available-workspace layouts down to640×360 fit eight pages. These are overrides/simulations, not five OS scale settings or physical mixed-DPI positioning.

NOT TESTED: physical1440p/4K/ultrawide, multiple/negative-origin/mixed-DPI monitors, docking/hot-plug/primary changes, actual sleep/lock/RDP workflow recovery, exclusive fullscreen/HDR, GPU routing, real Narrator/OS high-contrast session. The soak's Modern Standby event does not qualify product resume behavior. Real game/anime media remains missing. No further display/focus/playback tests were run after the policy change.

## OCR qualification and performance

[35 authored fixtures](ocr-benchmark.json) run three preprocessing modes×three repeats, across Japanese, Korean, Simplified/Traditional Chinese, English, Spanish, French, German, Italian, Dutch, Polish, Indonesian, Turkish, Russian, Ukrainian, Hindi, Portuguese, Vietnamese and Arabic. Assets are authored/redistributable; font programs and third-party game frames are not bundled.

Clean horizontal JA/KO/EN/ES and authored English outline/shadow/translucent/low-contrast samples are exact. Chinese punctuation and Traditional characters retain errors (representative CER0.10–0.20; difficult Traditional case~0.176). Vietnamese CER~0.278; its setup fidelity0.791 fails the unchanged0.8 guard and prevents transmission. Vertical Japanese CER~0.429/0.583; pixel Katakana~0.364. Arabic logical order is fixed, while mixed/digit/multiline fidelity is imperfect. Alternative model/scale/preprocessing experiments caused cross-case regressions and were not adopted globally.

All19 installed packs perform real inference with Python connect/DNS/download paths forbidden and zero attempts. That is not a native packet/ETW trace. First-run sample qualification passes18/19 actual OCR+Google cases; Vietnamese remains FAIL. Real moving-film background has only a historical300.49s authored-subtitle probe (5569frames,19results,five sources), not representative game/anime typography or multi-hour qualification.

Warm original-fixture median1292.96ms across the benchmark, range757.07–2317.64ms under concurrent QA; cold Japanese~3135ms. The latest observed fault-run OCR p50/p95 is1132/1339ms; total accepted-result p50/p95 is1187/2312ms. Current portable first isolated OCR2277.98ms. These are separate workloads, not a controlled speedup claim. Native subtitle rendering medians improve5000chars176.2→19.3ms and20000chars653.6→84.6ms; glyph-cache RGBA storage3.96→1.43MB. Idle CPU is not increased to chase OCR latency.

## Provider qualification

All ten exposed adapters have mock contracts/fault coverage. Real service evidence is narrower:

| Provider | Real result and limit |
|---|---|
| Google quick | PASS authored Spanish/Hebrew/Thai/Czech outputs and18 setup samples; earlier429 retained, no availability guarantee |
| DeepL, OpenAI native/Chat, Claude, Gemini, OpenRouter | NOT TESTED with real accounts; no configured keys, no invented auth/quota/model success |
| LibreTranslate | Public unauthenticated request safely rejected; no successful authenticated/owned-server generation |
| Ollama0.40.4 |12 service checks PASS with CPU Qwen3:0.6b and Qwen2.5:1.5b: discovery/offline/missing/unload/reload/restart/cancel; semantic quality FAIL |
| LM Studio llmster0.0.25-1 / llama.cpp2.41.0 |13 service checks PASS, context/disconnect included; actual missing-model fallback reproduced/fixed; model output quality FAIL |
| Compatible | Mock/owned loopback PASS; arbitrary external server/account NOT TESTED |

The0.6B models produced wrappers or empty objects. The1.5B models omitted meaning or variably added explanation. Repeated temperature/prompt experiments did not justify a global request change. They are test models, not qualified recommendations. Measured cancellation~11.8ms Ollama/~4.2ms LM Studio is service-specific; cold/warm generation varies by model. Owned services were shut down and profiles isolated. No keys were printed/persisted in reports.

## Reliability

An earlier7200.51s same-worker steady run accepted504 translations and passed resource budgets, but its source predates the pipe/async fixes; it is superseded. Earlier30-minute fault runs failed+44.5 and+41 handles and are preserved. Those failures led to the two concrete resource fixes above.

The latest fault run requested1800s and elapsed2009.58s, accepted54<58, sampled only through1050s and failed overall. Windows Kernel-Power events show lid-triggered Modern Standby from10:46:00Z to11:01:36Z. Its observed post-warmup main RSS/private growth3.16/2.82MiB, handles+0.5, threads−0.5 and Python heap+0.57MiB pass the old numeric budgets; queues/workers/sockets stay bounded and cleanup leaves0children. Those observations do not establish a continuous30-minute pass. New observation continuity gates reject the959.58s end gap.

Observed cancellation median/p95~47/62ms (68 samples); captures5906, OCR359, translations71, injected HTTP faults27,16 session restarts,6 OCR recoveries and208 stale discards. No stale result was counted as accepted. Main CPU medians~5.99% active/~3.80% static of one core include tracemalloc/fault workload overhead and exclude worker CPU. Historical stopped native app sampled0.4167% of one core over30s; neither is a multi-hour idle guarantee. Current-source continuous2h/30min updated-harness qualification remains pending on the hosted runner.

## Installer and portable qualification

Final local portable SHA-256: `ca0cd4a80f090640b025b77a0384d4a94be80062cdaee37217ac7c08f2f21fee`.

Final local setup SHA-256: `5a8ac6a5fc14e46d6cab7eb13f14dc8e1b121a6a86970343645f6e51dc3b22b2`.

Application source digest: `c38414ff9af8ce503cf0a32784c8003ed52612f3e8bd83087feed5ec3d798a80`. Local provenance accurately records an unsigned dirty-tree build; a matching application digest does not rewrite that provenance into a clean hosted claim.

Current portable passes extraction into a CJK/space path, empty CJK working directory, system-only PATH/no Python environment, marker/adjacent settings/model/log isolation, exact Japanese OCR, loopback HTTP and temporary vault roundtrip/deletion. It never takes foreground or captures the desktop.

Previous-artifact native/per-user installer evidence passes install, beta1 upgrade, reinstall, stale runtime removal, Unicode shortcuts, metadata/registry, uninstall/data+model retention and reinstall-after-uninstall. Unknown-runtime/runtime-junction/parent-junction probes refuse with exit7 and preserved sentinels. These are historical artifact digests. The latest hosted installer passes installation, runtime, metadata/shortcuts, first uninstall/retention and reinstall, then fails final cleanup. Inno documents that its temporary clone can continue after original-process exit; the new harness waits for actual EXE/registry/shortcut disappearance before reinstall and fails rather than skipping a missing final uninstaller. [Official lifecycle reference](https://jrsoftware.org/ishelp/topic_uninstexitcodes.htm); the replacement hosted run must confirm the fix. The legacy1.1a NSIS binary was inspected and requires Administrator; it was not installed on the laptop. Clean supported consumer Windows without Python, actual non-ASCII username, standard account, long-path/legacy coexistence and publisher trust remain unqualified. VM tools were unavailable; no accounts/features/reboots were added.

## Security and privacy

Current source/history/artifact scans report no findings within signature coverage.76 hash-locked dependencies have no known vulnerability findings in the performed pip-audit query; pip check passes. Runtime uses pinned CPython3.12.15/OpenSSL3.5.9, verified archive SHA11ed9f…abc64a.42 runtime/78 build SBOM components,131 notices and matching Qt/python-bidi LGPL sources are present. Inspection finds no prior Poppler/ICU/local-LLM contamination, private/test files or unintentionally bundled OCR weights. SBOM inventory is not a claim of an exhaustive embedded native graph or byte-identical reproducibility.

Screenshots/text/context remain in memory by default; explicit user copy/export is separate. Credential Manager holds provider secrets; logs/diagnostics omit captured content. Endpoint validation, redirects, request/response/download bounds, archive paths and hash activation were reviewed/tested. No automatic local-to-cloud fallback exists. ONNX opt-out is set before native import and disable API before inference; upstream minimal Windows initialization/ETW behavior remains documented rather than falsely claiming zero events. Local AI servers can keep their own logs. A historical local Defender scan completed without detection events; it does not certify this final digest, every AV engine or SmartScreen. No certificate is available and no self-signing was substituted.

## GitHub issues

All23 bodies and35 available comments were reviewed. [Individual dispositions and prepared notes](issues-v2.md) remain the authoritative per-issue table. No issue comments/closures were posted.

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

1. Complete passing exact-source/harness hosted quality, final installer and continuous2h/30min resource runs; review all report distributions and attestations.
2. Qualify physical mixed-DPI/multi-monitor layouts, topology/session transitions, actual supported fullscreen/media workflows and accessibility on a reserved rig/session, without returning invasive tests to the routine laptop loop.
3. Qualify clean supported Windows/no-Python/standard-account/non-ASCII-user and legacy install/coexistence/upgrade paths on a disposable OS.
4. Obtain representative local-model quality and configured cloud/Libre/custom-provider accounts where exposed claims require them; retain observed OCR limitations and complete representative media accuracy testing.
5. Obtain a trusted publisher signing certificate/service and verify Authenticode/timestamps/trust, then regenerate matching final metadata/artifacts/reports. Only after all stable gates pass may the canonical version become2.0.0 and release promotion be considered.

NOT READY FOR v2.0.0 STABLE

# Stable-release acceptance matrix

Target: **DeskTranslate v2.0.0**. **Publication HOLD; not qualified as stable.** The canonical identifier remains `2.0.0b2`; no new beta has been published. Results below describe their exact scope. A build or synthetic pass cannot replace physical hardware, account or human qualification.

Host: Windows 11 Pro build26200, Lenovo82RD, single native1920×1080 panel at125% (Qt1536×864), non-RDP. AMD integrated graphics is active and an NVIDIA RTX3060 Laptop GPU is enumerated; GPU-routing compatibility is unqualified. Pinned CPython3.12.15 x64 / OpenSSL3.5.9, fresh76-distribution hash-locked venv. Tests run concurrently with other release QA where stated.

**PASS** means measured success within the stated scope. **FAIL** means an observed failure. **NOT TESTED** means missing evidence. **NOT APPLICABLE** means outside that criterion's purpose. Findings/root causes are in [production-audit.md](production-audit.md); every historical issue is in [issues-v2.md](issues-v2.md).

See [testing.md](testing.md) for the non-invasive routine/pre-deployment path and separate manual tiers. Native observations below were collected before that policy; they are not repeated automatically.

## Automated engineering and security

| Test | Environment | Result | Evidence | Remaining limitation |
|---|---|---|---|---|
| Full regression suite / complete headless pre-deployment gates | Fresh locked Windows runtime, final portable | PASS | 405 tests,49.18s; Ruff lint/format81 files, mypy42 modules, smoke/pip check/audit/history scan/wheel/sdist/frozen smoke all pass; private JUnit retained | Hosted exact-commit checks tracked separately |
| Ruff lint / format, mypy | Same runtime | PASS | 81 files formatted;42 source modules typed | Rerun after further edits |
| Fresh hashed install, pip check, application smoke | Isolated pinned runtime, no system site packages | PASS | Bootstrap4 +76 locked distributions, editable install, smoke | Development OS, not clean consumer Windows |
| Dependency vulnerability audit | Complete Windows lock | PASS | [dependency-audit.json](dependency-audit.json), no known findings | Database coverage finite; refresh before publication |
| Settings/profiles/corruption/write failures/vault rollback | Deterministic regressions | PASS | Core, UI and profile tests; [upgrade.md](upgrade.md) | Legacy installer coexistence remains separate |
| Provider schema/HTTP failure/cancellation/endpoint/model bounds | Mock transports and real loopback | PASS | Ten adapters; malformed/auth/quota/deadline/cancel/model tests | Mock contracts do not qualify real accounts |
| Worker descendants and early-spawn pipe handles | Actual Windows jobs and child processes | PASS | Native descendant test;20 immediate cancellations no handle leak | Actual optional Tesseract binary not tested |
| Non-invasive routine/pre-deployment workflow | Offscreen components, isolated data/vault/shortcuts, mocked/loopback IO | PASS | [testing.md](testing.md);405 tests;60 geometry cases and picker events;16 policy/polling tests | No real desktop/input/media/system changes in default suite |
| Long-soak command and stable gate reject bad evidence | Deterministic negative tests | PASS | Resource-failed command, old source/assets/runtime, missing counters/cleanup, restart/harness/version/manual/signing regressions | Actual extended results below |
| Observation continuity and upstream-wheel privacy regressions | Five timestamp-gap cases and exact locked binary | PASS | Start/end/internal gaps, duplicate/nonfinite time rejected; verified bidi binary accepted only at its exact artifact path; altered binary/app paths rejected | Upstream build metadata is recorded, never a general home-path or secret exemption |
| Source/reachable-history/privacy review | Publishable tree and reachable objects | PASS | No findings in source/history scan | Final current artifact report is [privacy-scan.json](privacy-scan.json); signature scan not exhaustive |
| All existing GitHub issues reviewed | 23 issues,18 open,35 available comments | PASS | [Issue dispositions and drafted notes](issues-v2.md) | Original#28/#31 attachments unavailable; no comments/closures posted |

## Windows coordinates, UX and accessibility

| Test | Environment | Result | Evidence | Remaining limitation |
|---|---|---|---|---|
| Picker drag, corner resize, Enter/Escape, physical crop equality | Actual1920×1080, OS125% | PASS | [selection-motion-qualification.json](selection-motion-qualification.json), pixel mean difference0 | Authored target, not a game |
| Moving/static/blank dialogue and return after blank | Native MSS, isolated OCR, loopback HTTP | PASS | Same report,11 checks; zero stale deliveries/restarts | OCR sometimes adds N/I to moving text; retained |
| 1280×720 rendered mode, UI/picker/capture | Temporary driver mode on the native1080p panel, observed Qt100% | PASS | [windows-resolution-qualification.json](windows-resolution-qualification.json); original mode restored | Not a separate physical720p monitor |
| Running1080p125%→720p100%→1080p | Actual main controller/MSS/OCR/overlay | PASS | [live-resolution-qualification.json](live-resolution-qualification.json):11 checks | Fixed region invalidated; explicit reselection required |
| Running landscape→portrait1080×1920→landscape | Driver-applied orientation, same panel, Qt125% | PASS | [live-portrait-qualification.json](live-portrait-qualification.json):11 checks; original restored | Panel was not physically rotated by hand; no external monitor |
| Effective100/125/150/175/200% layouts | Native Qt overrides on actual OS125% display | PASS | [ui-scale-qualification.json](ui-scale-qualification.json), eight pages each | Not five OS scaling settings or mixed-DPI hardware |
| Compact640×360/720×405/960×540 layouts | Simulated available workspace | PASS | Eight pages, no horizontal overflow, native screenshots reviewed | Dimensions/layout only; simulated desktop positioning not a pass |
| Negative origins/mixed-DPI transforms/topology changes | Synthetic monitor geometry and native message regressions | PASS | Core/window/capture/overlay tests | Physical layouts remain separate |
| Physical1440p/4K/ultrawide, multi-monitor, negative origins, mixed DPI | Required hardware | NOT TESTED | No matching physical rig | Must qualify before stable |
| Hot-plug, docking, primary-display changes, sleep/lock/RDP reconnect | Actual transitions | NOT TESTED | WTS/power handler tests cover messages only | Native registration is not a real transition |
| Long Unicode/CJK/RTL, themes, reduced-motion and contrast branches | Qt tests and native authored UI | PASS | Overlay tests, font profile, reviewed fresh screenshots | Actual Narrator/OS contrast switching separate |
| Real screen reader / high-contrast session | Human-assisted Windows accessibility | NOT TESTED | Accessible names/StaticText roles inspected only | End-user screen-reader qualification absent |
| Actual game/anime/exclusive fullscreen/HDR/multi-GPU routing | Representative applications/hardware | NOT TESTED | No representative application session | Authored borderless windows are weaker evidence |

## OCR and providers

| Test | Environment | Result | Evidence | Remaining limitation |
|---|---|---|---|---|
| 35 authored fixtures ×3 preprocessing modes ×3 repeats | Actual CPU ONNX, current frozen source | PASS | [ocr-benchmark.json](ocr-benchmark.json); all results retained | Execution pass, not universal accuracy; concurrent QA affects timing |
| Clear horizontal JA/KO/EN/ES and difficult English treatments | Native-font authored fixtures | PASS | Exact clean/outlined/shadow/translucent/low-contrast cases | Styled moving media remains less accurate |
| Chinese punctuation / Traditional characters | Authored difficult fixtures | FAIL | CER and output retained in benchmark | Alternative models/scales caused other regressions; default not overfit |
| Vietnamese accents | Authored setup fixture | FAIL | CER~0.278, first-run fidelity0.791 below unchanged0.8 guard | No network translation after fidelity failure; actionable alternatives |
| Vertical/pixel Japanese | Short/long columns, pixel Katakana | FAIL | CER~0.429/0.583 vertical,~0.364 pixel original | Experimental vertical ordering cannot restore missing characters |
| Arabic logical-order correction | Pinned Arabic recognizer | PASS | Native actual inference, no double reversal; regressions | Exact fidelity across mixed/multiline fixtures still fails |
| Exact Arabic mixed/digit/multiline fidelity | Authored native-font fixtures | FAIL | CER and preprocessing differences retained | No universal RTL claim |
| Installed packs operate without Python network/download paths | All19 explicit managed sources, real inference | PASS | [offline-ocr-qualification.json](offline-ocr-qualification.json),0 forbidden attempts | Python hooks, not native packet or OS-ETW tracing; not fidelity pass |
| ONNX diagnostic opt-out ordering | Fresh import + engine-construction regressions | PASS | Process environment before import, API before session | Upstream Windows minimal-init/ETW scope remains explicit in [privacy](privacy.md) |
| First-run OCR and actual Google sample translation | 19 bundled samples | FAIL | [sample-qualification.json](sample-qualification.json):18 pass,Vietnamese fails | Failure retained, corpus/guard unchanged |
| Actual Google target handling | Authored EN→ES/HE/TH/CS | PASS | Live output, Hebrew script verified | Earlier429 retained; no service guarantee or133-language fidelity claim |
| Actual Ollama lifecycle/service | Official0.40.4, CPU Qwen3:0.6b and Qwen2.5:1.5b, owned profile | PASS | [0.6b](ollama-qualification.json), [1.5b](ollama-qualification-1.5b.json),12 service checks each | Offline/discovery/load/unload/missing/restart/cancel tested; quality separate |
| Actual LM Studio lifecycle/service | llmster0.0.25-1 / llama.cpp2.41.0, same CPU model families | PASS | [0.6b](lmstudio-qualification.json), [1.5b](lmstudio-qualification-1.5b.json),13 service checks each | Missing-model fallback reproduced/fixed; quality separate |
| Tested local model translation quality | Actual authored Unicode/context generations | FAIL | Tiny model wrappers/empty output;1.5b omissions or variable explanations | Service success is not semantic/plain-text quality; no model recommendation |
| Public LibreTranslate request without key | Actual HTTPS service, authored greeting | FAIL | [libre-public-qualification.json](libre-public-qualification.json),safe rejection | No successful generation; owned/authenticated server required |
| Paid clouds, owned/authenticated LibreTranslate/custom server | Required accounts/servers | NOT TESTED | No configured paid credentials or relevant server | Contract tests and loopback do not replace accounts |
| Optional external Tesseract | Native executable and language packs | NOT TESTED | Adapter tests and generic descendant containment only | No installed external binary qualified |

## Reliability, performance and distribution

| Test | Environment | Result | Evidence | Remaining limitation |
|---|---|---|---|---|
| Long-text render profile | Native Segoe UI, before/after,3 repeats | PASS | [subtitle-performance.json](subtitle-performance.json):5000 chars176.2→19.3ms;20000 chars653.6→84.6ms | Rendering only, not media end-to-end latency |
| Detector extreme-aspect bound | Actual preprocessing/pixel equality | PASS | Nine cases; ordinary tensors and35×3 outputs unchanged | Thin regions may reduce resolution |
| Superseded two-hour steady run | Before early-spawn pipe fix, same worker | PASS | [preserved report](soak-2h-before-pipe-fix.json),7200.51s,504 accepted,all resource gates | Does not qualify changed source |
| Superseded30min fault soak | Before pipe fix | FAIL | [preserved failure](soak-chaos-before-pipe-fix.json),handle growth44.5>32 | Root cause reproduced/fixed; budget not relaxed |
| Current-source2h same-worker endurance | Optional hosted/background fixture stress | NOT TESTED | Prior current run stopped for the async retention fix; [soak-2h.json](soak-2h.json) incomplete | Prefer hosted runner; not a routine laptop gate |
| Latest source-matched fault workload | Explicitly opted-in offscreen OCR/loopback stress, laptop entered Modern Standby | FAIL | [Original report](soak-chaos.json):2009.58s elapsed,54 accepted<58; [assessment](soak-chaos-assessment.json):samples stop1050s,959.58s end gap | Observed handles+0.5/private+2.82MiB; cleanup0 children. Resource-only PASS does not establish endurance; updated-harness hosted2h/30min required |
| Real moving-film background, five sources, windowed/borderless | Muted licensed Elephants Dream decoded into owned Qt widget; MSS/OCR/loopback | PASS | 300.49s,5569 decoded frames,19 results,zero pipeline errors,cleanup; historical probe before the non-invasive policy | Authored subtitles; no actual game/anime typesetting or model-quality claim |
| Two-hour visible moving-video endurance | Manual desktop tier | NOT TESTED | [media-qualification.json](media-qualification.json),stopped at600s on maintainer request | Excluded from routine validation; no prolonged visible playback resumed |
| Current portable/installer compilation | Locked isolated Windows build, final application digest | PASS | [artifact-qualification.json](artifact-qualification.json):20 checks; portable ca0cd4…21fee, setup5a8ac6…b22b2 | Unsigned internal build; installer execution qualification separate |
| Current portable frozen runtime | Empty CJK/space path, system-only PATH, offscreen Qt | PASS | [packaged-qualification.json](packaged-qualification.json):nine checks; exactJA OCR2277.98ms,HTTP/vault deletion,adjacent data,empty cwd | Same development OS; no current native-foreground or clean-consumer-machine claim |
| Hosted candidate final uninstall after reinstall | Disposable Windows2022 runner, current application source | FAIL | [Original report](installer-hosted-failure.json),install/runtime/first uninstall pass; final registry/shortcuts remain | Harness cleanup wait and missing-uninstaller rejection implemented; passing rerun required, no forced cleanup |
| Previous portable native launch / DLL origins | Owned frozen process before async-retention fix | PASS | [Historical report](packaged-qualification-before-async-fix.json):111 modules from bundle/Windows only | Historical artifact; not an exhaustive worker/native dependency graph |
| Previous stopped main-window idle | Frozen native app,30s, concurrent QA | PASS | CPU0.4167% of one core,0 TCP connections,handles772→771 | Short stopped-idle sample, not active-media CPU |
| Previous install / beta1 upgrade / reinstall / uninstall / data retention | Per-user owned CJK/space directory | PASS | [installer-qualification.json](installer-qualification.json),shortcuts/PE/registry/OCR/vault/HTTP/stale-runtime removal/reinstall-after-uninstall | Same host; beta1 upgrade differs from legacyNSIS |
| Unknown-runtime / runtime-junction / parent-junction refusal | Workspace-owned sentinels | PASS | [installer-refusal-qualification.json](installer-refusal-qualification.json),exit7,no registry/files changed | No malicious concurrent local-user race claim |
| Actual publishedv1.1a installer coexistence | Original installer inspected,not run | NOT TESTED | [legacy-upgrade-qualification.json](legacy-upgrade-qualification.json),requiresAdministrator manifest | Clean VM absent; no machine-wide legacy install on development host |
| Clean supported Windows without Python / non-ASCII username / standard account | Clean OS/account/VM | NOT TESTED | Sandbox/docker/VirtualBox/VMware/Hyper-V tools unavailable | PATH isolation is weaker evidence |
| Notices/SBOM/hash/provenance/content/privacy inspection | Current internal artifacts | PASS | [artifact-qualification.json](artifact-qualification.json):20 checks,131 notices,42 runtime/78 build components; [privacy-scan.json](privacy-scan.json):300 tree/542 history/403 runtime/410 archive members/1481 frozen modules,no findings | Unsigned dirty-tree local provenance; hosted clean build separate; final docs/tool updates also pass source scan |
| Hosted Windows quality at5671e16 | Windows Server2022 runner | FAIL | [Run38721263208](https://github.com/DeskTranslate/DeskTranslate/actions/runs/38721263208):tests/build/frozen runtime pass; artifact privacy finds upstream bidi build path | Locked-wheel verification fix/regression now implemented; subsequent exact-commit rerun required |
| Hosted Windows quality ate504a9a | Disposable Windows2022 runner | PASS | [Verified reports](hosted-quality-qualification.json):403 tests39.525s;all quality/build/frozen OCR/vault/HTTP/privacy steps pass,archive digest verified | Subsequent installer-helper/workflow changes need their own CI; consumer Windows/manual scope separate |
| Local Defender artifact scan | Installed engine/signatures, owned dist directory | PASS | [defender-qualification.json](defender-qualification.json),completion event,no detection events in interval | Not every AV/SmartScreen or publisher identity |
| Trusted publisher signing/timestamp/trust | Publisher certificate/service | NOT TESTED | Maintainer confirmed unavailable; current artifacts accurately unsigned | Signing-ready process is not signing qualification |
| GPU OCR/cloud OCR/speech/persistent history | Outside shipped scope | NOT APPLICABLE | Deliberately deferred | No exposed feature deleted to avoid testing |

## Decision

No known P0 is intentionally left unresolved. Unresolved P1 qualification gaps have no implicit waiver. Physical mixed-DPI/media/accessibility, clean-Windows/legacy install, provider accounts/model quality and publisher signing remain explicit blockers. No stable promotion follows from CI success alone.

Earlier window/onboarding/focus and hosted build reports are historical evidence for their recorded source. Legitimate beta changelog history remains. The canonical prerelease identifier cannot change until stable gates actually pass.

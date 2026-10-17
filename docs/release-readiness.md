# DeskTranslate v2.0.0 release readiness

2026-10-17. **Final application qualification PASS under the approved unsigned release policy.**
Integration and release history: [PR #38](https://github.com/DeskTranslate/DeskTranslate/pull/38).
Canonical version: **2.0.0**. Qualified application commit: `a6eeea3e22c276e368d5f391179a9a1a83b30d89`. Final binaries must identify the exact merged/tagged release commit and retain this qualified application digest; the attached release-verification statement and provenance record that final commit.
The [frozen release plan](stable-release-plan.md) implements the maintainer's final
release policy. Trusted signing, unavailable physical monitor permutations and
unavailable paid accounts are disclosed limitations, not automatic release vetoes.
No known ordinary-workflow P0/P1 defect is being waived.

## Final engineering changes

Paced authored capture exposed a P1 defect missed by string replay: 5 Hz moving
backgrounds repeatedly crossed the moving/static boundary in 0.2-second gaps,
invalidating every in-flight OCR. Motion history now requires a real quiet period
before returning to static suppression. A RED→PASS component regression exercises
actual pipeline scheduling with slow recognition. Sampling/backpressure remain bounded.

A second P1 check found that whole-region averaging missed short static English dialogue and even punctuation-only revisions. The detector now retains a small contrasting change at thumbnail resolution while still rejecting isolated hot pixels and low-amplitude noise. Three authored image regressions were RED before the fix; real OCR now delivers both statement and question. The superseded `287d416` endurance was cancelled, not counted as a pass.

Temporal consolidation time is recorded separately. Numeric metrics retain enough
stage names for capture, preprocessing, regional OCR, context, translation and GUI
presentation. No captured content is added to diagnostic metrics.

The final soak now alternates authored horizontal, pixel, columns and ruby layouts
inside one isolated OCR worker, rather than qualifying only the older three-model
horizontal path. Application, dependency-lock and soak-harness bytes remained frozen throughout final hosted qualification.
Application digest: `12c7ae38c3b56bca39da997c99cc34e3b3bfa57fa7a453f90ad37db9aff8f33b`.

## Media and responsiveness: PASS within authored scope

[Paced media report](media-pipeline-rc.json): actual isolated CPU OCR, wall-clock
authored captures, real loopback HTTP adapter and offscreen overlay rendering.
All required complete dialogue is delivered across moving/fading/returning text,
progressive VN reveal, brief/one-character-changing subtitles and vertical/column/
ruby/caption layouts. Slow-provider work stays bounded and delivers the final line.
All five workloads pass freshness, queue, cleanup and no-post-stop checks; zero
surviving OCR children. [Original failure](media-pipeline-first.json) and
[intermediate measurement](media-pipeline-motion-fix.json), [static-change failure](static-change-failure.json) and [superseded run](superseded-candidate-287d416.json) are preserved. The first duplicate-return probe demanded a redundant result; the current probe exercises actual controller visibility/grace behavior instead.

Current warm timing, milliseconds (actual controller receipt and offscreen paint):

| Workload | New results | Capture→presentation p50/p95 | Source-onset→presentation p50/p95 |
|---|---:|---:|---:|
| vn-moving-fade-return | 5 | 1469.0 / 1593.0 | 1704.0 / 2779.0 |
| brief-small-change-subtitles | 4 | 1015.5 / 1344.0 | 1420.5 / 1672.0 |
| static-one-character | 4 | 1156.5 / 1625.0 | 1437.5 / 2047.0 |
| columns-ruby-captions | 3 | 1641.0 / 1750.0 | 1938.0 / 2047.0 |
| slow-provider-freshness | 2 | 2812.5 / 2844.0 | 3257.5 / 3343.0 |

Cold first presentation includes worker/model startup after constructing the hidden
controller; it is not full application launch time. Each report retains cold timing,
all individual stages, samples and the fixture provider's 120 ms/1800 ms delay. A
correctly retained repeated subtitle needs no new HTTP call; actual controller
blank-grace/visibility is checked, and distinct punctuation/digit revisions must
produce their own exact recognized sources. These are small CPU/authored workloads,
not real-model/cloud latency guarantees. Concurrent local QA may affect timings.

Regional OCR evidence remains 18/20 Japanese cases exact, all eight layouts exact
across three preprocessing modes (24/24), and 9/9 replayed complete lines retained.
Punctuation/name errors and ambiguous shapes producing false text remain bounded
accuracy limitations. No global OCR shortcut was introduced to chase a benchmark.

## Context and providers

Behavioral tests cover recent dialogue/term retrieval, recurring names, pronouns,
honorifics, invented items, progressive revision ownership, bounded budgets, scene
expiry, explicit reset and title/language isolation. Authored reference translations
in these tests verify request construction, not model quality. Recent dialogue is
ephemeral, at most eight entries/2400-byte conservative token bound; relevant terms
are capped at 24 terms/1800 bytes. User story notes remain explicit profile configuration.

[Fresh provider inventory](provider-final-inventory.json): actual Google translations
for Spanish, Hebrew, Thai and Czech PASS. All ten adapters retain contract/fault
coverage. [Current OCR-derived Japanese→English dialogue](google-dialogue-qualification.json) also succeeds: past-tense dialogue, Mika/key question, Aurelia/name and reunion outputs preserve the authored meaning. This is conventional MT, not AI context-quality evidence. No paid API credentials/CI secrets or reachable configured local server
are available. Only tiny test models were previously present and failed semantic
quality checks; they are not recommended as capable translation models. Capable
model/context-quality qualification is NOT TESTED, not a fabricated PASS.

## Final qualification

[Hosted quality](hosted-quality-final-rc.json): PASS, 490 tests, 48.886s, lint/format/types, source smoke/build, exact-lock audit, frozen OCR/vault/HTTP/ownership/crash recovery and privacy. [Independent candidate verification](hosted-candidate-final-rc.json) validates archive/release-file hashes, clean pinned-runtime provenance and three hosted attestations.

[Portable isolation](portable-qualification.json) and [installer lifecycle](installer-qualification.json): PASS on disposable hosted Windows Server 2022. Extracted Unicode/space paths, empty cwd, system-only PATH/no PYTHONPATH, actual OCR/HTTP/temporary vault lifecycle, reinstall, obsolete owned runtime removal, shortcuts/metadata, uninstall/reinstall and retained settings/models pass. This does not claim a consumer VM with Python physically absent, a non-ASCII account name, standard-account qualification or a current V1/beta1 upgrade test.

[Two-hour steady report](soak-2h.json) and [thirty-minute fault report](soak-chaos.json), pinned Python 3.12.15, identical application/assets/lock/soak harness:

- Steady: **PASS**, 7200.41s, 591 accepted results, 0 session replacements, maximum observation gap 30.406s. Main post-warmup RSS/private growth 8.87/18.05 MiB, handles +3, threads +0. Cleanup succeeds; zero surviving OCR children.
- Fault: **PASS**, 1800.23s, 231 accepted results, 50 session replacements, maximum observation gap 30.214s. Main post-warmup RSS/private growth -16.73/4.36 MiB, handles +1, threads -0.5. Cleanup succeeds; zero surviving OCR children.
- One unchanged OCR worker for steady-state: RSS/private growth -31.85/1.29 MiB, handles +0, threads +0; all declared budgets PASS.
- Successful translation counters advance in every 15-minute steady window: 82, 73, 68, 67, 68, 68, 66, 77. Raw samples, CPU/rates/latency distributions, queue/cache/context bounds and Python allocations remain in the reports. RSS is working set; private bytes are private committed memory, not a separately measured private working set.

The main Python heap grew 9.17 MiB within the declared 16 MiB budget. A separate [resource-probe reproduction](resource-probe-overhead.json) identifies approximately 20 KiB retained per explicit Win32 resource probe: ctypes caches dynamically declared pointer types. The soak calls this probe for both processes every 30 seconds, accounting for roughly 9 MiB over two hours. Normal translation does not poll it; the application calls it only when diagnostics are explicitly generated. This low-impact diagnostic allocation is a P2 follow-up, not evidence of a translation-worker leak. Report samples and latency observations also occupy memory. No zero-growth claim is made.

Main-process active/static CPU medians were 0.63%/0.16% of one core; the OCR worker used about 111% of one core averaged across the mixed workload. OCR is CPU work, not free background processing. Steady pipeline capture-to-result p50/p95 was 907/1187 ms, with separate overlay paint 4.48/6.52 ms; fault cancellation p50/p95 was 16/32 ms. These source-mode measurements are distinct from the paced main-window presentation timings above.

These are source-mode native OCR/HTTP/offscreen-overlay workloads. Final frozen artifacts receive their own source-matched build/runtime/installer/privacy checks; this is not a claim that an older executable or a physical film session ran for two hours. Old d5f56dc endurance and cancelled `287d416` results are preserved and do not qualify newer application bytes.

Final release build/verification is a separate controlled step after merging documentation only. The annotated `v2.0.0` tag, binary provenance and [release checksums/verification](https://github.com/DeskTranslate/DeskTranslate/releases/tag/v2.0.0) identify the exact shipped commit and artifacts. No app/lock/soak-harness modification is permitted without affected requalification.

The evidence-only commit initially exposed a [negative-test isolation error](qualification-test-isolation-failure.json): a test expected live repository evidence to remain incomplete forever. It now supplies deliberately incomplete temporary evidence and retains the rejection assertion. The qualified application, lock and endurance harness are unchanged; final hosted checks rerun against the isolated test.

## Security, packaging and limitations

Source/provider/download/archive/credential/privacy boundaries retain focused
regression coverage. Current exact-lock vulnerability and source/history/artifact scans PASS; final merged-source artifacts are checked again before publication. No automatic local-to-cloud fallback;
screenshots/text are not persisted by default; explicit copy/export remains optional.

No legitimate publisher certificate or repository signing secret exists. The
maintainer explicitly approves unsigned stable distribution with SHA-256 and
provenance. Windows/SmartScreen may warn; no publisher trust is claimed.

Hosted Windows Server 2022 is the available disposable runtime. Actual consumer Windows 11
hardware, mixed-DPI/multiple physical monitors, protected/exclusive-fullscreen media,
Narrator and paid-provider/model semantics remain separately NOT TESTED where
unavailable. Geometry simulations retain 100/125/150/175/200%, negative origins,
portrait/landscape and safe topology invalidation. Previous native observations
are supporting evidence only; none is silently upgraded to current physical testing.

All 23 historical issues and 18 still-open reports have individual
[dispositions](issues-v2.md). No reporter-content fix or closure is inferred from
an architectural change. [Historical detailed audit](release-readiness-history.md)
preserves prior root causes, commands, failures, measurements and evidence identities;
its earlier signing/manual release policy is superseded by the final release plan.

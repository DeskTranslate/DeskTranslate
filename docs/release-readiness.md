# DeskTranslate v2.0.0 release readiness

2026-10-17. **Final candidate qualification in progress; publication HOLD.**
Working integration: [PR38](https://github.com/DeskTranslate/DeskTranslate/pull/38).
Canonical version is now2.0.0 for the unpublished final candidate, not a released beta.
The [frozen release plan](stable-release-plan.md) implements the maintainer's final
release policy. Trusted signing, unavailable physical monitor permutations and
unavailable paid accounts are disclosed limitations, not automatic release vetoes.
No known ordinary-workflow P0/P1 defect is being waived.

## Final engineering changes

Paced authored capture exposed a P1 defect missed by string replay:5Hz moving
backgrounds repeatedly crossed the moving/static boundary in0.2-second gaps,
invalidating every in-flight OCR. Motion history now requires a real quiet period
before returning to static suppression. A RED→PASS component regression exercises
actual pipeline scheduling with slow recognition. Sampling/backpressure remain bounded.

A second P1 check found that whole-region averaging missed short static English dialogue and even punctuation-only revisions. The detector now retains a small contrasting change at thumbnail resolution while still rejecting isolated hot pixels and low-amplitude noise. Three authored image regressions were RED before the fix; real OCR now delivers both statement and question. The superseded287d416 endurance was cancelled, not counted as a pass.

Temporal consolidation time is recorded separately. Numeric metrics retain enough
stage names for capture, preprocessing, regional OCR, context, translation and GUI
presentation. No captured content is added to diagnostic metrics.

The final soak now alternates authored horizontal, pixel, columns and ruby layouts
inside one isolated OCR worker, rather than qualifying only the older three-model
horizontal path. Replacement application/lock/harness bytes are now frozen for hosted runs.
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
all individual stages, samples and the fixture provider's120ms/1800ms delay. A
correctly retained repeated subtitle needs no new HTTP call; actual controller
blank-grace/visibility is checked, and distinct punctuation/digit revisions must
produce their own exact recognized sources. These are small CPU/authored workloads,
not real-model/cloud latency guarantees. Concurrent local QA may affect timings.

Regional OCR evidence remains18/20 Japanese cases exact, all eight layouts exact
across three preprocessing modes (24/24), and9/9 replayed complete lines retained.
Punctuation/name errors and ambiguous shapes producing false text remain bounded
accuracy limitations. No global OCR shortcut was introduced to chase a benchmark.

## Context and providers

Behavioral tests cover recent dialogue/term retrieval, recurring names, pronouns,
honorifics, invented items, progressive revision ownership, bounded budgets, scene
expiry, explicit reset and title/language isolation. Authored reference translations
in these tests verify request construction, not model quality. Recent dialogue is
ephemeral, at most eight entries/2400-byte conservative token bound; relevant terms
are capped at24/1800bytes. User story notes remain explicit profile configuration.

[Fresh provider inventory](provider-final-inventory.json): actual Google translations
for Spanish, Hebrew, Thai and Czech PASS. All ten adapters retain contract/fault
coverage. [Current OCR-derived Japanese→English dialogue](google-dialogue-qualification.json) also succeeds: past-tense dialogue, Mika/key question, Aurelia/name and reunion outputs preserve the authored meaning. This is conventional MT, not AI context-quality evidence. No paid API credentials/CI secrets or reachable configured local server
are available. Only tiny test models were previously present and failed semantic
quality checks; they are not recommended as capable translation models. Capable
model/context-quality qualification is NOT TESTED, not a fabricated PASS.

## Remaining blocking evidence

- Full local pre-deployment suite PASS:490 tests80.94s, Ruff99 files, mypy46 modules, smoke, pip check, zero known lock vulnerabilities, source/history privacy scan and wheel/sdist. Current-source hosted Windows CI remains pending.
- Current frozen portable Unicode/space-path isolation, runtime OCR/vault/loopback,
  ownership/crash recovery and installer/reinstall/uninstall/data retention.
- Continuous exact-source two-hour steady and thirty-minute fault workloads,
  native resource budgets, observation coverage, throughput and worker cleanup.
- Independent artifact hashes, clean provenance, attestations, notices/SBOM/library
  sources, and final release build tied to the eventual merged/tagged commit.

Old d5f56dc endurance results qualify old application bytes only. They are not used
to promote this candidate. No desktop, display, power or input changes are made by
routine qualification; expensive work runs on disposable hosted Windows.

## Security, packaging and limitations

Source/provider/download/archive/credential/privacy boundaries retain focused
regression coverage. Exact-lock vulnerability and source/history/artifact scans
must pass again for the final candidate. No automatic local-to-cloud fallback;
screenshots/text are not persisted by default; explicit copy/export remains optional.

No legitimate publisher certificate or repository signing secret exists. The
maintainer explicitly approves unsigned stable distribution with SHA-256 and
provenance. Windows/SmartScreen may warn; no publisher trust is claimed.

Hosted Windows2022 is the available disposable runtime. Actual consumer Windows11
hardware, mixed-DPI/multiple physical monitors, protected/exclusive-fullscreen media,
Narrator and paid-provider/model semantics remain separately NOT TESTED where
unavailable. Geometry simulations retain100/125/150/175/200%, negative origins,
portrait/landscape and safe topology invalidation. Previous native observations
are supporting evidence only; none is silently upgraded to current physical testing.

All23 historical issues and18 still-open reports have individual
[dispositions](issues-v2.md). No reporter-content fix or closure is inferred from
an architectural change. [Historical detailed audit](release-readiness-history.md)
preserves prior root causes, commands, failures, measurements and evidence identities;
its earlier signing/manual release policy is superseded by the final release plan.

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

Temporal consolidation time is recorded separately. Numeric metrics retain enough
stage names for capture, preprocessing, regional OCR, context, translation and GUI
presentation. No captured content is added to diagnostic metrics.

The final soak now alternates authored horizontal, pixel, columns and ruby layouts
inside one isolated OCR worker, rather than qualifying only the older three-model
horizontal path. Application/lock/harness bytes will be frozen before hosted runs.

## Media and responsiveness: PASS within authored scope

[Paced media report](media-pipeline-rc.json): actual isolated CPU OCR, wall-clock
authored captures, real loopback HTTP adapter and offscreen overlay rendering.
All required complete dialogue is delivered across moving/fading/returning text,
progressive VN reveal, brief/one-character-changing subtitles and vertical/column/
ruby/caption layouts. Slow-provider work stays bounded and delivers the final line.
All four workloads pass freshness, queue, cleanup and no-post-stop checks; zero
surviving OCR children. [Original failure](media-pipeline-first.json) and
[intermediate measurement](media-pipeline-motion-fix.json) are preserved.

Warm capture-to-presentation p50/p95 in milliseconds: Japanese1375/2359,
English1148.5/1297, vertical1766/1781, slow fixture provider2836/2875.
Source-onset medians are2064,1898.5,1922 and3117.5ms respectively. Cold first
presentation is5.1–6.9s. Render calls are0–16ms at the host timer resolution.
These are small CPU/authored workloads with120ms or1800ms fixture provider delay,
not real-model/cloud latency or guarantees that every rapidly disappearing line
can be read. Every stage distribution and sample count is in the report.

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
coverage. No paid API credentials/CI secrets or reachable configured local server
are available. Only tiny test models were previously present and failed semantic
quality checks; they are not recommended as capable translation models. Capable
model/context-quality qualification is NOT TESTED, not a fabricated PASS.

## Remaining blocking evidence

- Full local pre-deployment suite PASS:486 tests75.70s, Ruff99 files, mypy46 modules, smoke, pip check, zero known lock vulnerabilities, source/history privacy scan and wheel/sdist. Current-source hosted Windows CI remains pending.
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

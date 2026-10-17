# v2.0.0 final release scope

2026-10-17. Working integration: PR #38, starting at5d17f81 / application4b5a06e.
This plan implements the maintainer's final practical release policy and supersedes
the earlier requirement to wait for purchased signing, a physical monitor lab,
every paid account, or a consumer-Windows VM unavailable to this project.

## Blocking work, in order

1. Run paced authored media through actual capture boundary, isolated OCR,
   temporal/context/provider pipeline and offscreen overlay. Measure complete
   presentation p50/p95, freshness, duplicates/progressive revisions, lifecycle
   invalidation and bounded work. Fix ordinary-workflow failures, not incidental
   punctuation differences. Existing replay/string tests remain supporting evidence.
2. Validate bounded title/context/terminology sequences. Check configured model/key
   availability without exposing secrets; use real available services where possible.
   Missing capable models/paid credentials are documented provider coverage, not
   invented successful semantic tests or an automatic release veto.
3. Freeze application, dependency lock, soak harness and version at one RC. Update
   release tooling to permit explicitly disclosed unsigned stable artifacts while
   retaining strict source/runtime/endurance/cleanup/integrity gates.
4. Qualify that RC on disposable hosted Windows: full routine/security gates,
   standalone portable path with spaces/CJK, installer/reinstall/uninstall/data
   retention, runtime ownership/crash recovery, actual OCR/vault/loopback, two-hour
   steady and thirty-minute fault endurance with continuous native observations.
5. Verify final source/artifact provenance, notices/SBOM/library sources and hashes.
   Preserve failures. Merge with history, tag the exact release commit and publish
   only source-matched verified installer/portable artifacts and honest release notes.

## Accepted limitations, not application passes

- No signing secrets/certificate currently exist; publish unsigned with SHA-256,
  hosted provenance and an explicit Windows/SmartScreen warning. No self-signing.
- Physical mixed-DPI/second-monitor/fullscreen/screen-reader permutations remain
  untested where unavailable. Existing native observations and deterministic scale,
  negative-origin, orientation and fail-closed topology tests remain evidence.
- Bounded non-destructive OCR punctuation/name/background errors remain documented;
  no global confidence/resolution shortcut that regresses legitimate text.
- Hosted Windows is the available disposable qualification OS. Standalone runtime
  must not rely on checkout, Python, developer PATH or preseeded ordinary-user data.
  Consumer-Windows hardware/media composition is not claimed by offscreen tests.

Do not reopen architecture or add major features. A real crash, stall, configuration
loss, stale cross-session result, resource leak, broken first run/installer, serious
privacy issue, final check failure or artifact mismatch blocks publication.

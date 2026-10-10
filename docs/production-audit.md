# V2 production readiness audit

Baseline: `a810027` / 2.0.0b1. This pass preserves the existing Qt/domain/pipeline design.
Checks below are tracked against implementation and measured evidence, not previous marketing.

## P0 findings before implementation

- Runtime failure delivery calls `showNormal()`, interrupting a game or video.
- Overlay Hide is overridden by the next result; window flag changes can hide a visible overlay.
- OCR failures stop the recognition thread without bounded recovery; process termination never joins/closes its process handle.
- Failure/pause/stop races are not atomic, and stale OCR mutates stabilization before checking its generation.
- Repeated session replacement can overlap provider/OCR resources; network reads have per-read timeouts but no total deadline.
- Suspended and reconnected display sessions need explicit invalidation. Unproven Win32/Qt mapping currently falls back to scaling absolute origins.
- Profile payloads are only shallowly checked; there is no safe portable schema or import/export.
- Onboarding marks completion before any recognition/translation succeeds.
- Update checks ignore beta releases and trust weakly validated release metadata.
- Version strings are duplicated in package/build/installer/UI/release assets.
- Release candidates do not verify installer upgrade/uninstall, signatures, artifact privacy or runtime inventory.
- The only recorded soak is 30 seconds and measures Python allocations, not native/process resources.
- Publisher signing is unavailable (maintainer confirmed); physical mixed-DPI/fullscreen and real provider qualification are incomplete.

## P1 work to complete

- Window/client-relative capture with explicit target identity, normalized regions, occlusion/minimize/restart safety and clear backend boundaries.
- First-class profile CRUD/import/export and bounded glossary exchange.
- Guided, recoverable first-translation onboarding and clear active target/provider/model status.
- Provider/model progressive disclosure, native OpenAI API evaluation, usable-model filtering without fabricated claims.
- Opt-in bounded memory transcript and privacy-previewed diagnostic export.
- Keyboard/accessibility pass, model download states, latency percentiles, explicit release channels.
- Maintainable ownership of profile/onboarding/support UI and capture state.

## P2 investigations, with evidence required before exposure

- Windows Graphics Capture and acceleration beyond CPU compatibility: adopt only when reliable and measured on available hardware.
- Automatic language routing beyond explicitly chosen script packs; avoid silently promising universal Auto.
- Optional process profile activation; no implicit application binding.

## Release policy

Implementation has addressed the source P0 findings above: atomic failure/pause/stop and stale guards, bounded global pipeline resources and OCR recovery/reaping, full-request network deadlines/cancellation, focus-safe runtime/display recovery, persistent overlay hiding, fail-closed monitor mapping, validated portable profiles, real first-success onboarding, strict semantic release selection and canonical package/PE/installer versions. Final regression has 207 passing tests. The final review also found an installed native event filter surviving its owner during repeated GUI lifecycles; shutdown now detaches it on the GUI thread. Demo avoids native tray side effects and themes apply idempotently.

The manual/signing findings remain unresolved release gates. Window/UI/sample probes have specific, limited evidence; the two-hour resource soak and final packaging/CI are documented when complete. P1 implementations include dedicated profile/setup/transcript/support/glossary controllers, visible application capture, explicit update channels and numeric latency/resource diagnostics. P2 acceleration/WGC/universal routing decisions are recorded in [the investigation](acceleration-and-dependencies.md), without pretending they shipped.

Stable promotion is prohibited until signing and the documented manual qualification gates pass.
Unsigned development/candidate artifacts remain available and clearly identified. No self-signed certificate
is substituted for trusted publisher signing. Deferred features are recorded separately from failed P0 gates.

The final UI review found fixed-height setup/export dialogs exceeding a 200% desktop. Dialog sizes now use available Qt logical geometry, setup pages scroll independently of navigation buttons, and sample previews adapt to width. Native inspection checks all six pages at 560×320, while completion still requires an actual translated result.

# Media and context engineering checkpoint

2026-10-16. PR38 remains a draft. Target:2.0.0; internal version:2.0.0b2. **Publication HOLD.** This is an implementation checkpoint, not stable qualification. Baseline application d5f56dc and its hosted reports remain intact; they do not qualify the changed architecture.

## Implemented product changes

- Replace the stateless text stabilizer with a bounded temporal service. Six observations/2.5seconds retain text, confidence, geometry and capture times. Progressive prefix growth, complete subtitles, character noise, spacing noise, disappearance and independent geometry have distinct behavior. Proposed text always comes from an observation.
- Separate control-generation ownership from visual revisions. Obsolete pixels may contribute text-growth evidence while the same capture session remains authorized, but cannot produce translation/presentation. Pause, stop, target/context changes revoke that evidence. A new regression reproduces pause during an in-flight capture followed by immediate resume; pre-pause pixels are discarded.
- Reduce the first moving-background sampling interval from1.5seconds to quality-specific bounds:0.45/0.60/0.75seconds. Both mailboxes remain capacity1. The one-second authored subtitle sampling regression exposed an Accuracy-mode timing boundary, which was corrected without weakening the assertion. This is sampling coverage, not an OCR deadline guarantee.
- Explicit progressive revision ownership replaces a provisional fragment in recent dialogue and the optional transcript. It is excluded when translating its completed replacement. Independent similar lines remain separate. Transcript memory stays disabled by default and clears at existing boundaries.
- Separate the context engine, translation cache and approved terminology. Retrieve at most24 relevant terms/1,800 serialized bytes using current text and two recent sources, from at most1,000 entries/50KB. Latin boundaries avoid substring matches inside other words; unspaced CJK names remain eligible. No inferred vocabulary or vector store is persisted.
- Add optional editable story notes, bounded to2,000 characters, with visible title ownership, draft clearing, durable Apply and profile import/export disclosure. Applying translation settings updates the active title snapshot. Legacy partial profiles clear prior title notes, glossary and instructions. Deleting the active title clears these current values; failed saves retain both stored values and the user's draft.
- Bind approved terms to their language pair. Conventional providers get no story/glossary/recent payload; exact case-sensitive whole-term matches resolve locally. Sentences are sent intact, without blind substitutions. A target-language change cannot silently reuse English terms as Spanish translations.
- Collapse optional dialogue settings until needed, reopening them for configured title context. Quick translation no longer shows an irrelevant AI billing warning. Dark/light pages were rendered offscreen and inspected.
- Instrument detector, recognizer, reconstruction, OCR-call/IPC and context lookup separately. Bounded numeric diagnostics retain no text, story notes, profile names or endpoints.

## Measured evidence

| Test / environment | Result | Evidence / limitation |
|---|---|---|
| Deterministic temporal, stale/pause, profile/save/delete and all provider payload contracts | PASS | Routine offscreen regressions. Provider schemas are mocked; this does not establish semantic translation quality. |
| Final non-disruptive pre-deployment gate, pinned Windows runtime | PASS |463 tests in67.39s; lint/format93 files, mypy45 modules, source smoke, pip check, zero known dependency vulnerabilities, privacy scan334 tree/669 reachable blobs with no findings, wheel/sdist. No frozen artifact qualification in this command. |
| Authored changing-frame OCR replay, actual isolated CPU OCR on this Windows11 laptop | FAIL overall | [23 observations](media-sequence-experiment.json):7/7 horizontal complete lines retained,2/2 vertical lines fail exact recognition. Frame timestamps are replayed, not paced; no real-time deadline/provider meaning/physical capture is qualified. |
| Japanese progressive reveal | PASS within replay scope | Five changing prefixes produce one final proposal, rather than five provider candidates; a repeated final frame is suppressed. First final proposal is at capture timestamp0.32s, not0.32s wall-clock latency. |
| English brief complete subtitles / Japanese names | PASS within replay scope | Three English subtitles each produce one proposal; repeated Japanese name produces one proposal. This does not prove the real desktop can process a0.5-second subtitle in time. |
| Korean moving-background spacing variation | PASS within replay scope | Actual OCR previously produced three proposals for two lines. After confirmation guards, the same authored sequence produces two, retaining both complete lines. |
| Real OCR→owned HTTP→offscreen main window/overlay | FAIL overall; five journeys PASS | [Current component report](product-component-media.json): one-shot, pause/resume onto changed text, outage/retry, language swap and cleanup/preferences pass; zero OCR children remain.20/24 negative backgrounds are empty; four geometric backgrounds still produce false characters. No paid or semantic provider qualification. |
| OCR stage comparison | FAIL execution deadline; partial measurements retained privately |44 authored positives/short inputs were written before the300-second supervisor deadline. Natural-scale detection improves10 but regresses5 cases, including digits, low contrast and a Japanese glyph. A two-case cleanup probe subsequently exits0. No detector default changed. |
| Actual local model availability | NOT TESTED for generation | Ollama11434 and LM Studio1234 both time out on loopback discovery. No model is loaded or downloaded. Prior tiny-model semantic failures remain failures. |
| New architecture Windows packages / long endurance / physical media | NOT TESTED | Existing unsigned packages, installer reports and running d5f56dc hosted endurance are baseline evidence only. Do not repeat final packaging/endurance until recognition/media architecture stabilizes. |

The stage measurements locate the main warm bottleneck in detection: representative Japanese input spent about1,399ms detecting and113ms recognizing; small English text spent936ms detecting and138ms recognizing. Natural-scale detection lowers these costs but produces a wrong low-contrast character at0.999 confidence, so confidence alone cannot safely select the fast path. These are individual observations, not representative warm medians.

The current detector can group same-height Japanese characters across separate vertical columns into horizontal rows. A research-only whole-image90-degree rotation improves two vertical samples but damages horizontal/mixed text. It is not applied globally. Vertical/mixed-layout region analysis, ruby handling and representative real-media accuracy still need engineering and qualification.

The sequence report's recorded application hashes precede only the final optional-editor UI change. Its recognition/temporal/pipeline code is unchanged; the original hashes are retained. The product component report matches the subsequent application source. Exact final automated commands/results are recorded in [release-readiness.md](release-readiness.md).

## Remaining product priorities

1. Improve vertical/mixed-layout OCR and adaptive detection without sacrificing short characters, punctuation or low-contrast text. Expand authored layouts and test real media in a reserved/isolated environment.
2. Measure actual capture→recognition→context→translation→overlay sequence latency, calls per completed line and missed brief subtitles. Replay success does not establish real-time throughput; current warm OCR remains around a second on this host.
3. Qualify story/terminology prompts against capable real models with context/no-context sequences. No local model recommendation or cloud-provider quality claim is justified by the current environment.
4. After architecture stabilizes, rebuild/qualify exact Windows artifacts, resource endurance, clean consumer Windows, supported physical layouts and accessibility. Obtain trusted publisher signing before stable promotion. No certificate/service is available here.

No new release, tag, merge, issue closure or stable promotion is authorized by this checkpoint. The broad product task remains in progress.

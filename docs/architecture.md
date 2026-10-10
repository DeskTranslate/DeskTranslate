# Architecture

The installable application is in `src/desktranslate`. Qt owns presentation; domain types have no Qt dependency. `models.py` defines capture, OCR and translation protocols. Settings and dependencies are injected at boundaries.

```
Capture → thumbnail change gate → latest frame mailbox (capacity 1)
  → isolated OCR process → reconstruction / stabilization
  → latest text mailbox (capacity 1) → pooled provider HTTP
  → bounded events → Qt timer → overlay
```

A session has a serial and frame generation. Every meaningful frame change invalidates previous work immediately. Pause, stop and configuration changes also invalidate it. Results retain their original stamp and are checked in workers and presentation. Context receives only accepted results, is bounded by entries, Unicode characters and a conservative UTF-8 byte upper bound for tokens, and is cleared each session. Full request identity is hashed for the bounded memory cache.

The isolated process contains native OCR crashes. A recognition worker can replace a failed native process at most twice per minute; it terminates, joins, kills if necessary and closes the process handle before replacement. Pause/failure/stop transitions are atomic. Stale inference is rejected before it mutates stabilization. Two global OCR slots and two provider slots bound overlapping retired pipelines; setup has one separately owned task per UI controller.

Each HTTP provider keeps the synchronous domain protocol and owns an asyncio loop inside its existing worker. HTTPX AsyncClient reuses connections; `asyncio.wait_for` bounds the complete request, including DNS/connect, response headers and body. Stop schedules cancellation safely into that loop. Bodies and decompression are capped at 8 MB before expansion/allocation, malformed/deep JSON becomes a typed failure, redirects are rejected and rate-limit retry is bounded/cancellable. The Qt loop never runs network awaits or joins workers. Shutdown keeps Qt responsive while a background coordinator waits within a 35-second cleanup budget. There are no unbounded work queues.

Qt logical coordinates are transformed relative to each monitor origin and its physical dimensions. Device names match Win32 monitors to Qt screens. Regions stay within one monitor because a mixed-DPI boundary has no single affine transform. Topology changes invalidate saved regions.

Unproven monitor mapping fails closed rather than multiplying an absolute origin by DPR. `window_capture.py` owns Win32 enumeration, client geometry and a conservative visible-screen compatibility backend. Normalized crops follow move/resize; occlusion/minimize/identity changes are checked on both sides of MSS capture. Optional restart following requires a unique executable-path-hash/title match. Pipeline target movement/rebinding clears context and invalidates generations. Protected/exclusive-fullscreen capture and Windows Graphics Capture are unqualified.

Original RGB is the default OCR input; contrast and subtitle upscaling are explicit alternatives. Structured OCR retains boxes, confidence, language and ordering. Horizontal reconstruction groups rows; experimental vertical ordering reads right-to-left columns.

Claude uses native Messages, Gemini uses generateContent, and Ollama uses /api/chat. Native OpenAI defaults to stateless Responses with storage/streaming disabled and offers explicit Chat Completions compatibility. Existing beta1 OpenAI settings retain Chat mode through migration. OpenAI-compatible servers retain Chat Completions. Model lists are fetched dynamically and known non-text families are removed; unknown capabilities are unverified. OpenRouter price/context metadata is shown only when supplied. JSON source/context data is under a translate-only instruction; there is no general chat UI or tool use.

Credentials are bound to provider and endpoint identity in the OS vault. Remote services require verified HTTPS; HTTP is loopback-only. No redirects or insecure TLS overrides. Logs use a metadata allowlist and discard messages, args, traceback, URLs, headers and dialogue. Diagnostics have a separate allowlist.

Models, settings and logs use OS application data. Assets resolve from the package. `DESKTRANSLATE_DATA_DIR` isolates test data; it never holds credentials. Build and test folders are ignored by Git.

Pure `profiles.py`, `shortcuts.py`, `transcript.py`, `diagnostics.py` and `metrics.py` own validation, bounds and data contracts. Dedicated UI modules own profile CRUD/exchange, glossary exchange, onboarding, transcript and support previews. MainWindow coordinates session/capture state; it remains a substantial controller rather than disguising a mechanical rewrite as a completed architecture migration. Imported profiles never establish capture consent. Session transcript memory is opt-in and clears at boundaries. Metrics retain bounded numeric samples, never content.

`desktranslate.__version__` is the single version source for package, UI, PE metadata, installer and asset names. `tools/release_support.py` enforces tag/manual/soak/signing gates. Build/runtime inventories are separate, provenance identifies commit and source digest, and public metadata contains no absolute build paths. Stable builds fail if qualification/signing is absent.

Subtitle rendering uses Qt Unicode shaping and cached glyph pixmaps per content/style/size/DPI change. Outlines and shadows reuse cached glyphs. Long text shrinks within a bounded range and clips at an explicit line limit. Edit mode restores interaction and pauses capture. A one-second blank-text grace prevents immediate flicker. The document angle classifier is disabled because it rotated upright Korean subtitles incorrectly.

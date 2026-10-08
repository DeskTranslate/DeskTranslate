# Architecture

The installable application is in `src/desktranslate`. Qt owns presentation; domain types have no Qt dependency. `models.py` defines capture, OCR and translation protocols. Settings and dependencies are injected at boundaries.

```
Capture â†’ thumbnail change gate â†’ latest frame mailbox (capacity 1)
  â†’ isolated OCR process â†’ reconstruction / stabilization
  â†’ latest text mailbox (capacity 1) â†’ pooled provider HTTP
  â†’ bounded events â†’ Qt timer â†’ overlay
```

A session has a serial and frame generation. Every meaningful frame change invalidates previous work immediately. Pause, stop and configuration changes also invalidate it. Results retain their original stamp and are checked in workers and presentation. Context receives only accepted results, is bounded by entries, Unicode characters and a conservative UTF-8 byte upper bound for tokens, and is cleared each session. Full request identity is hashed for the bounded memory cache.

The isolated process contains native OCR crashes and terminates on shutdown. HTTP runs in daemon workers with bounded timeouts; the UI never joins them. Clients reuse connections, reject redirects and perform at most one bounded rate-limit retry. Failures become recoverable session errors. There are no unbounded task queues.

Qt logical coordinates are transformed relative to each monitor origin and its physical dimensions. Device names match Win32 monitors to Qt screens. Regions stay within one monitor because a mixed-DPI boundary has no single affine transform. Topology changes invalidate saved regions.

Original RGB is the default OCR input; contrast and subtitle upscaling are explicit alternatives. Structured OCR retains boxes, confidence, language and ordering. Horizontal reconstruction groups rows; experimental vertical ordering reads right-to-left columns.

Claude uses native Messages, Gemini uses generateContent, and Ollama uses /api/chat. OpenAI-compatible providers share wire infrastructure. Model lists are fetched dynamically; OpenRouter includes pricing/context metadata when supplied. JSON source/context data is under a translate-only instruction; there is no general chat UI or tool use.

Credentials are bound to provider and endpoint identity in the OS vault. Remote services require verified HTTPS; HTTP is loopback-only. No redirects or insecure TLS overrides. Logs use a metadata allowlist and discard messages, args, traceback, URLs, headers and dialogue. Diagnostics have a separate allowlist.

Models, settings and logs use OS application data. Assets resolve from the package. `DESKTRANSLATE_DATA_DIR` isolates test data; it never holds credentials. Build and test folders are ignored by Git.

Subtitle rendering uses Qt Unicode shaping and cached glyph pixmaps per content/style/size/DPI change. Outlines and shadows reuse cached glyphs. Long text shrinks within a bounded range and clips at an explicit line limit. Edit mode restores interaction and pauses capture. A one-second blank-text grace prevents immediate flicker. The document angle classifier is disabled because it rotated upright Korean subtitles incorrectly.

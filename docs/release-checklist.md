# Release qualification

## Automated and repeatable

- Run pytest, Ruff check/format, mypy, application smoke and dependency audit.
- Verify package metadata, assets and a wheel build. Inspect Git diff/ignored data for secrets and private content.
- Build the portable app and Inno per-user installer from the Windows lock. Compare source versions, inspect packaged resources, retain notices/SBOM/hashes.
- Run packaged `--smoke-test` with a system-only PATH from a directory containing no source checkout.
- Run `--verify-runtime report.json --ocr-fixture <synthetic-ja-game.png>` with installed verified Japanese models. Require assets, Qt, exact isolated OCR and temporary native-credential roundtrip. Never use real keys in release probes.
- Install to an isolated test directory; smoke the installed app, uninstall, and verify app files were removed while user data remained.
- Run synthetic OCR benchmarks; retain failures and do not cherry-pick preprocessing.
- Run the guarded desktop probe, overlay render/cache/Unicode tests, slow-provider cancellation tests and bounded-queue stress checks.

## Hardware and accounts before stable promotion

Test 720p, 1080p, 1440p, ultrawide and 4K; 100/125/150/175/200% scaling; mixed-DPI negative-origin monitors; portrait rotation; resolution changes; disconnect/reconnect. Check selection corners, overlay placement/reset, click-through, edit mode, font changes, CJK/RTL/long lines, low opacity, gradients, reduced motion, no focus theft and no self-capture.

Exercise real media with bright/dark/moving scenes, outlined/stylized text, rapidly changing subtitles, blank intervals and multi-hour visual-novel dialogue. Record end-to-end median/p95 latency, idle CPU, memory growth and request counts. Use windowed/borderless and document protected/exclusive-fullscreen restrictions.

Use configured test accounts for all cloud adapters; test model discovery, authentication/quota/timeout/deleted-model errors, pricing metadata and translation quality. Test Ollama and LM Studio with actual loaded models, restarts and offline operation. Synthetic wire-contract tests do not prove service/model quality.

Verify a clean supported Windows account without Python. Qualify code signing when a publisher certificate is available. Stable promotion requires this manual matrix; beta notes must explicitly identify uncompleted coverage. Never promise real-time subtitle throughput or universal OCR accuracy from a nine-image corpus.

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
- Run `python tools/qualify_window.py` over authored native windows. Run `python tools/qualify_ui.py` at the intended scale; report Qt accessibility separately from a real screen reader.
- Run `python tools/qualify_samples.py` only with installed verified packs; it sends authored samples to Google's public endpoint. Paid/local providers require their own controlled tests.
- Run `python tools/soak.py --duration 7200 --output docs/soak-2h.json` with verified Japanese models and loopback allowed. It alternates authored frames, injects HTTP failures/native OCR crashes, restarts sessions, paints overlays and samples native resources. Require completion, unchanged source, workload/cleanup and resource gates. A post-test source change invalidates the recorded hashes. Optional overnight use accepts `--duration 28800`; real media remains a separate manual gate.
- The declared resource budget compares the first/last ten post-warmup samples: main RSS/private growth at most 32 MiB, handles at most 32, threads at most 8; one OCR child, bounded mailbox/event/cache/context collections and at most eight TCP connections. Inspect CPU, worker memory and samples as well; a passing threshold does not prove every workload is leak-free.
- Run `tools/qualify_installer.ps1 -PreviousInstaller <verified-beta1-installer>` for same-host install, earlier-version upgrade, reinstall, startup and uninstall in a path containing spaces/CJK. It preserves isolated test settings and refuses to replace a different registered installation. A clean Windows account/VM remains separate.
- Run `python tools/privacy_scan.py --history --artifacts`: reachable Git blobs, publishable files, runtime files and extracted frozen code. Retain public contributor/license attribution; review any findings without printing secret content. This signature scan is not a proof against every possible secret.

## Hardware and accounts before stable promotion

Test 720p, 1080p, 1440p, ultrawide and 4K; 100/125/150/175/200% scaling; mixed-DPI negative-origin monitors; portrait rotation; resolution changes; disconnect/reconnect. Check selection corners, overlay placement/reset, click-through, edit mode, font changes, CJK/RTL/long lines, low opacity, gradients, reduced motion, no focus theft and no self-capture.

Exercise real media with bright/dark/moving scenes, outlined/stylized text, rapidly changing subtitles, blank intervals and multi-hour visual-novel dialogue. Record end-to-end median/p95 latency, idle CPU, memory growth and request counts. Use windowed/borderless and document protected/exclusive-fullscreen restrictions.

Use configured test accounts for all cloud adapters; test model discovery, authentication/quota/timeout/deleted-model errors, pricing metadata and translation quality. Test Ollama and LM Studio with actual loaded models, restarts and offline operation. Synthetic wire-contract tests do not prove service/model quality.

Verify a clean supported Windows account without Python. Stable promotion requires every gate in `manual-qualification.json`, a same-version/source two-hour workload/resource report, exact canonical tag and trusted timestamped publisher signing. `tools/build.py` enforces these for every non-prerelease version, even if `--stable` is omitted. Beta notes must explicitly identify uncompleted coverage. Never promise real-time throughput or universal OCR accuracy from a synthetic corpus.

## Publisher signing

No publisher certificate is currently available; the maintainer confirmed this. Unsigned prerelease builds are clearly identified. Never substitute a self-signed certificate or claim hashes establish publisher identity.

When a trusted code-signing certificate/service is actually available, configure its certificate in the build user's Windows certificate store, set `DESKTRANSLATE_SIGNING_THUMBPRINT`, and install Windows SDK SignTool or set `SIGNTOOL_PATH`. `DESKTRANSLATE_TIMESTAMP_URL` defaults to the HTTPS DigiCert RFC 3161 server. Build with `python tools/build.py --installer --signed --tag v<canonical-version>`; add `--stable` only after actual qualification. The build signs its launcher before ZIP packaging, signs the installer/uninstaller through Inno Setup, and hard-fails on trust/thumbprint/timestamp mismatch. Run installer qualification with `-Signed` to verify installed launcher and uninstaller too.

The manually dispatched GitHub workflow accepts signed/stable/tag inputs. PFX builds use repository secrets `DESKTRANSLATE_SIGNING_PFX_BASE64` and `DESKTRANSLATE_SIGNING_PFX_PASSWORD`; the temporary file is removed and the imported certificate is cleaned up even on failure. Restrict dispatch and signing secrets to trusted maintainers. No private key is committed or attached. The signing path is configured and fails closed; a successful publisher-signing run cannot be claimed until a real certificate exists. Hosted artifact attestation applies only to those artifact hashes.

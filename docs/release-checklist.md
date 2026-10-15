# Qualification checklist for v2.0.0 stable

Publication is held until every required gate has actual evidence. The source remains a prerelease identifier; internal test artifacts are not a new beta release. Read the [acceptance matrix](validation.md) and [finding register](production-audit.md) first. PASS, FAIL, NOT TESTED and NOT APPLICABLE are the only acceptance statuses. Never replace hardware/account evidence with simulated results.

## Non-invasive development and deployment gates

Use `python tools/validate.py` for routine work and `python tools/validate.py --predeploy` before deployment. Both force offscreen Qt and leave the real desktop/input/display settings alone. The default suite blocks real desktop grabs, browser launches, external network, native vault access and real global-shortcut registration while retaining component logic. See [testing.md](testing.md) for isolation, interruption, opt-in categories and costs. Hosted CI uses the same entry point.

Native/manual qualification is a separate acceptance tier, reserved for boundaries that cannot reasonably be validated below the UI. Do not repeat invasive desktop/media tests after unrelated code/docs changes or make them a routine pre-deployment step. Use a dedicated account/VM/session. The maintainer stopped prolonged visible media testing; do not restart it as routine QA.

## Reproducible automated checks

Use the pinned CPython 3.12.15 Windows x64 runtime and fresh venv, with no system site packages:

```powershell
./tools/install_python.ps1
python -m pip install --require-hashes -r requirements-bootstrap.lock
python -m pip install --require-hashes --no-build-isolation -r requirements-windows.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pip check
python -m pytest -q --junitxml=.audit/pytest.xml
python -m ruff check src tests tools
python -m ruff format --check src tests tools
python -m mypy src
python -m desktranslate --smoke-test
python -m pip_audit --require-hashes --disable-pip -r requirements-windows.lock -f json -o .audit/dependency-audit.json
python -m build --no-isolation --outdir dist-python
```

Check every command's exit code; an earlier failure must stop a workflow. Retain JUnit/dependency/build/runtime reports. Inspect wheel/sdist assets and metadata. Run source/reachable-history secret scanning without printing candidate secret values. Review all old issues using [the disposition table](issues-v2.md); do not close them solely because the architecture changed.

## OCR, providers and native desktop

- Run `python tools/evaluate.py --repeats 3 --output docs/ocr-benchmark.json` with verified packs. Retain all 35 fixtures and every preprocessing result, including errors. Regeneration requires installed fonts with glyph verification; do not replace native fixtures with tofu images. Authored assets are redistributable; OS font programs and game/video content are not bundled.
- Run `python tools/qualify_samples.py` for all 19 bundled first-run languages. It preserves partial OCR results, does not send a below-threshold sample, and stops subsequent network requests after a service failure. No paid request is made implicitly.
- Run native `tools/qualify_ui.py --interactive-desktop`, `tools/qualify_window.py --interactive-desktop` and `tools/qualify_selection_motion.py --interactive-desktop --quality balanced`. Record actual OS resolution/scaling separately from Qt scale overrides and fake available-workspace rectangles. The selection/motion probe owns its authored content and performs real MSS capture, isolated OCR and loopback HTTP.
- Use actual configured test accounts for paid providers and actual loaded models for Ollama/LM Studio. Verify missing/deleted models, auth/quota, timeout/cancel, outages/restarts, context, Unicode, long input and output quality. Nonempty output or a successful catalog is not translation quality. Do not print/persist keys, automatically switch providers, or recommend the tiny test model merely because its API works.
- Record manual physical layouts: 720p/1080p/1440p/4K/ultrawide/portrait, all requested OS scales, negative-origin mixed-DPI monitors, hot-plug/docking/primary changes, sleep/lock/RDP and supported GPU arrangements. Exercise focus, selection, editing/click-through, self-capture prevention, screen readers and real media. Missing hardware is NOT TESTED.

## Endurance: two complementary workloads

Prefer the manually opted-in hosted endurance job to running long CPU/RAM work on the laptop. The fixture soak forces offscreen Qt and does not play media or capture the desktop. Freeze application source/assets and `tools/soak.py` before the final run. Changing either invalidates evidence. Verify Japanese and English packs, then run:

```powershell
python tools/soak.py --long-running --mode steady --duration 7200 --stop-file .audit/stop-steady --output docs/soak-2h.json
python tools/soak.py --long-running --mode chaos --duration 1800 --stop-file .audit/stop-chaos --output docs/soak-chaos.json
```

Steady mode retains the same OCR child for two hours and varies authored dialogue, moving/static/blank frames and unique request identities. Chaos additionally exercises rapid pause/resume, stop/start, model/source/profile changes, overlay toggles, forced native worker death, slow headers/deadlines, HTTP429/500 and disconnects. Both use actual isolated CPU OCR, real loopback HTTP and Qt rendering. These are synthetic capture workloads; multi-hour real media remains a separate gate.

Inspect completion, unchanged source/harness hashes, version/runtime identity, stale/pending work, rates/latency/cancellation, process/thread/handle/socket counts, native memory and Python allocations. Require workload/cleanup success and zero surviving children. Observations must span the entire run with no gap over90 seconds, including start/end. A laptop sleep or otherwise unexplained sampling gap cannot establish endurance; do not alter system power settings to force a pass. `--stop-file <owned-path>` supports cooperative interruption; incomplete reports never qualify, regardless of requested duration.

After five-minute warmup, the main resource budget compares first/last ten samples: RSS/private growth ≤32 MiB, handles ≤32, threads ≤8, Python heap ≤16 MiB; bounded one-item mailboxes, 32 events, 256 cache entries, eight context entries, one OCR child and eight TCP connections. The steady child gate additionally requires ≥2 h, ≥200 post-warmup samples, one unchanged PID, RSS/private growth ≤64 MiB, handles ≤16 and threads ≤4. Missing/nonfinite counters fail qualification. Long-run commands return nonzero when these gates fail, even when the workload completes. Early-cancel native handle regressions must pass too. Actual elapsed time determines qualification; restarting a worker periodically cannot mask a same-worker leak.

Inspect all samples and CPU/latency distributions, not just a threshold. Active/static CPU measurements under concurrent QA are not an isolated idle-performance benchmark. Passing one workload does not establish every native library/media workload is leak-free. Use `--duration 28800` for overnight runs when practical.

## Packaging and installation

1. Prepare matching LGPL sources using `python tools/library_sources.py`. Verify pinned runtime/compiler hashes/signatures. Build with `python tools/build.py --installer` only for internal qualification while the canonical version remains prerelease. Build analysis uses an isolated Windows/Python PATH so unrelated Poppler/ICU or local LLM libraries cannot be collected.
2. Inspect binary contents, PE/icon/version, assets, runtime ownership, notices, exact library sources, runtime/build SBOMs, provenance and SHA-256 sums. Internal dirty-tree builds must say so; final hosted candidates require clean tracked source. Provenance must use the actual verified Python archive digest, not a manually transcribed claim.
3. Extract the portable ZIP in a path with spaces/CJK. Remove development PATH/PYTHONPATH and run from an empty directory. Require portable data beside the executable, no installed-AppData pollution, actual isolated OCR, loopback translation and temporary Credential Manager roundtrip **and deletion**.
4. Use `tools/qualify_installer.ps1 -AllowInstallChanges` in a dedicated account/VM for fresh same-host install, earlier V2 upgrade where available, reinstall, obsolete-runtime removal, installed runtime probe, uninstall and user-data retention. Require actual EXE/registry/shortcut cleanup before reinstall; the original uninstaller's exit alone is insufficient. A missing expected final uninstaller fails. Verify metadata and refusals for unknown runtimes/junctions. Do not overwrite a different registered installation. V1 InstallForge/Tesseract coexistence is deliberate, not an invented JSON-settings migration.
5. Repeat on an actual clean supported Windows account/VM without Python, developer PATH or source checkout. Same-host system-only PATH is useful but does not complete that gate. Record non-ASCII username, standard account and long-path coverage separately.
6. Run `python tools/privacy_scan.py --history --artifacts --output docs/privacy-scan.json`. It scans reachable blobs, publishable source, frozen modules/runtime files and checksum-listed release archives. Review every finding without dumping sensitive content. A signature scan is not proof against all secrets.

## Signing and promotion

The maintainer confirmed no publisher certificate/service is available. This remains an explicit stable requirement. Never fake signing or substitute a self-signed certificate; checksums and hosted attestations do not establish the publisher's Authenticode identity.

When a trusted certificate exists, configure `DESKTRANSLATE_SIGNING_THUMBPRINT` and Windows SDK SignTool (`SIGNTOOL_PATH` if needed). `DESKTRANSLATE_TIMESTAMP_URL` defaults to the HTTPS DigiCert RFC3161 service. Build with `--installer --signed --tag v2.0.0` only after updating the canonical version and completing the stable gates. All final-version builds enforce those gates even if `--stable` is omitted. Signing verifies trust, expected thumbprint and timestamp; Inno signs the uninstaller too.

The manually dispatched candidate workflow never publishes a release automatically. It retains reports, checks the lock, tests/lint/types/security, builds, verifies frozen OCR/vault/HTTP, tests installer lifecycle and scans artifacts. Endurance dispatch runs both workloads. PFX secrets are restricted to trusted maintainers and temporary certificate material is removed on every outcome. A configured signing path is not a successful signing qualification.

Before promotion require no known P0, no unresolved P1 without an explicit defensible waiver, passing current-source automated/build/runtime/security checks, representative OCR/provider/manual coverage, sustainable endurance, matching metadata and truthful notes. Update `manual-qualification.json` booleans only when their exact criteria pass. Review the acceptance matrix as a whole; CI success alone cannot authorize stable publication.

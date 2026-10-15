# Testing without taking over your desktop

Routine development and pre-deployment checks must work while the laptop is being used for other work. They do not require visible playback, foreground windows, real desktop pixels, global keyboard/mouse input, display changes or installation. Native hardware qualification is a separate, occasional activity in a reserved session.

## Routine local validation

In the documented development environment:

```powershell
python tools/validate.py
```

This runs Ruff, format checks, mypy, pytest and an offscreen application smoke. `python -m pytest -q` runs the same isolated test suite directly. Qt is forced to `offscreen`, even if a developer inherited `QT_QPA_PLATFORM=windows`; key events and clipboard tests stay inside that backend.

The suite replaces external boundaries rather than skipping application logic:

- Settings/models use temporary test directories; the credential backend is an in-memory test double.
- Global shortcut registration calls are substituted, while shortcut parsing, conflicts, retries and cleanup still execute.
- Real desktop grabs and browser launches fail the test immediately. No screenshot of another application is taken.
- External DNS/connections are blocked. Provider tests use mock transports; deadline/cancellation tests may use an owned loopback server.
- Picker drag/corner resize/Enter/Escape use authored pixmaps in offscreen widgets. Coordinate invariants cover six resolutions/orientations, five scales and positive/negative origins without changing any display.
- Session, stale-result, failure and cleanup tests use injected capture/OCR/provider components. A failed-session weak-reference regression verifies that async exception cycles do not keep retired state/native locks alive until cyclic GC.
- Short native process/job/handle tests use hidden, owned background processes. They do not install software, register input hooks or change the desktop.

This retains correctness, failure-path and rendering coverage. It does not pretend to qualify native DPI messages, actual font/display composition, screen readers or physical hardware. Native observations remain separately labelled in the acceptance matrix.

The validation runner bounds each step, stops on the first failure and preserves command output/JUnit. Ctrl+C or a timeout closes its owned process tree. It does not terminate unrelated applications. Pytest categories `interactive`, `long_running`, `system_changes` and `external_service` are excluded by the default marker expression; manual native probes live outside `tests/`.

## Before deployment

```powershell
python tools/validate.py --predeploy
```

This adds dependency consistency/vulnerability checks, reachable-history/source privacy scanning and wheel/sdist builds. It uses network access for the vulnerability database and more CPU/disk than the routine suite, but does not use the desktop. An existing binary can also be smoke-tested offscreen with `--frozen <path-to-DeskTranslate.exe>`; that does not install it. Packaging/runtime/installer evidence must still match the actual candidate.

Normal GitHub CI uses this headless path on a hosted Windows runner, followed by an offscreen frozen runtime check. It does not invoke foreground capture, visible videos, display changes or an installer. Installer qualification is restricted to the manually dispatched candidate workflow on its disposable runner.

## Extended background qualification

Extended OCR/HTTP/resource stress is opt-in and excluded from routine validation. Prefer a hosted/disposable runner. The fixture soak forces offscreen Qt and uses authored in-memory frames, isolated CPU OCR and loopback HTTP; it never captures the desktop or plays video.

```powershell
$env:DESKTRANSLATE_DATA_DIR = "$PWD/.test-data"
python tools/soak.py --long-running --mode chaos --duration 1800 --stop-file .audit/stop-chaos --output docs/soak-chaos.json
```

Japanese/English packs must already be verified. Extended runs require both `--long-running` and `--stop-file`. Create that stop file to end cooperatively and reap workers; an existing stop request is never silently removed. A direct short smoke defaults to 60 seconds. Any incomplete run remains incomplete; resource failures return a failing exit code. Sampling gaps longer than90 seconds, including the start/end, invalidate endurance; suspended or stalled wall time cannot count as continuous observation. The tool does not prevent sleep or change power settings. Two-hour steady and 30-minute fault workloads retain their strict budgets. Do not add these workloads to the routine laptop test command.

## Manual desktop and installation qualification

Only use this tier when a native boundary cannot reasonably be tested below the UI, and reserve a session where disruption is acceptable. Prior evidence need not be repeated after unrelated logic/docs changes. Never run prolonged foreground/video tests as a development or deployment habit.

`qualify_ui.py`, `qualify_window.py`, `qualify_selection_motion.py`, `qualify_window_loop.py` and `e2e_desktop.py` refuse to start without `--interactive-desktop`. They may display topmost authored windows, capture their pixels or require focus. An owned supervisor imposes a 120-second deadline (explicit `--desktop-timeout` accepts 1–300 seconds); Ctrl+C or timeout closes that probe and its workers. Inspect `--help` without launching the desktop test. These commands are not run as part of routine pytest/CI/pre-deployment validation.

`qualify_installer.ps1` additionally requires `-AllowInstallChanges` because it creates/removes installed files, shortcuts and per-user uninstall registration. Use a dedicated account/VM or the manual hosted workflow. Display rotation/scaling/topology changes, real-media sessions, Narrator and OS-preference checks remain manual acceptance items, not unattended laptop tests.

The installer probe waits for actual executable/registry/shortcut removal before reinstalling; an Inno uninstaller's original process can exit before temporary-clone cleanup finishes. The bounded polling logic has hidden component tests with authored temporary state, so those timing paths can be developed without repeatedly installing the application. Independent hosted steady/fault steps still run after an unrelated installer qualification failure when build/models are ready; each failed gate continues to fail the overall job.

The prolonged visible-media experiment was stopped when the maintainer requested this policy. Its interrupted progress is not a completed endurance pass. No further visible playback or display changes are part of the current routine verification.

# DeskTranslate 1 engineering audit

Audited the complete ZIP snapshot and upstream `main` at `a687ad46c86ff357a2c1eea0c3542ed7280fe3f7`: every Python module, both CSV lists, stylesheet, dependencies, README and asset inventory. Original files remain in upstream Git history and an ignored local baseline archive.

## Baseline and findings

`python main.py` failed with `ModuleNotFoundError: PyQt6` in the supplied environment. There were no tests, build scripts, workflow, persisted settings, or license file. Prototype modules mixed PyQt5, PyQt6 and PySide2.

| Area | Verified legacy behavior | Replacement |
|---|---|---|
| Capture | Primary-screen local coordinates passed to ImageGrab | MSS adapter; physical pixels; Win32 monitor-name matching |
| Selection | Primary available geometry; no negative/mixed-DPI handling; unused alternative | Frozen image per monitor; resize corners; Enter/Escape; one monitor per region |
| OCR | Fixed Program Files Tesseract path; unconditional grayscale; repeated OCR | Managed language-specific ONNX; detected optional Tesseract; RGB default |
| Concurrency | Python thread mutates QLabel; UI joins worker | Bounded pipeline; isolated OCR process; Qt consumer |
| Waste | Empty-text continue bypasses sleep | Thumbnail change gate and debounce before OCR |
| Translation | Scraping wrappers; errors turn into blank output | Typed provider protocol; conventional and native AI adapters |
| Privacy | Recognized, translated and copied text printed | Allowlisted logs; OS vault; memory-only screenshots/context |
| Languages | Spanish absent from OCR CSV; conflated provider codes | Typed registry with recognition families |
| Resources | Relative working-directory paths; 2.5-second splash | Package assets; no artificial startup delay |
| Platforms | Unconditional shell32; primary-monitor assumptions | Windows-first qualification |
| TTS | Voice engine blocks capture | Removed from critical path; speech deferred until voice selection is validated |
| Dependencies | Stale NumPy/OpenCV/Pillow, unused googletrans/PyGetWindow/PyRect/pyperclip | Reduced direct dependencies; pinned tooling; hashes and SBOM |

## Real user reports

Inspected the [open issues](https://github.com/DeskTranslate/DeskTranslate/issues), including details available for [#29 high DPI](https://github.com/DeskTranslate/DeskTranslate/issues/29), [#30 selection](https://github.com/DeskTranslate/DeskTranslate/issues/30), [#28 pixelated Japanese](https://github.com/DeskTranslate/DeskTranslate/issues/28), [#27 Python 3.13 installation](https://github.com/DeskTranslate/DeskTranslate/issues/27), and [#33 AI translation](https://github.com/DeskTranslate/DeskTranslate/issues/33). Titles also identified #20/#32 missing Spanish, #22 remembering languages and #31 startup failure; some bodies were not retrievable.

MSS avoids GPU binding and provides negative physical coordinates with small packaging cost. No measured superiority over DXCam or Windows Graphics Capture is claimed. Those remain replaceable capture adapters. Exclusive fullscreen/protected surfaces and mixed-DPI hardware need qualification.

RapidOCR 3.9.2 uses pinned dedicated language models (including Korean PP-OCRv5) rather than its changing default family. The beta evaluates synthetic fixtures using `tools/evaluate.py`: accuracy, latency, startup and preprocessing. Tesseract comparison requires an installed executable and language packs; no unmeasured OCR quality claim is made. Model hashes come from the pinned upstream manifest.

Upstream had no license file. The owner explicitly selected MIT for DeskTranslate 2 during this rewrite. Third-party notices and their original licenses are retained.

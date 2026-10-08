# DeskTranslate 2 · first public beta

Understand games, subtitles, images and menus with a shortcut and a readable overlay.

This release rebuilds DeskTranslate on Qt 6/PySide6, managed local ONNX recognition and a bounded asynchronous pipeline. It brings one-shot/live translation, monitor-relative physical coordinates, change detection, contextual dialogue, secure credentials and ten local/cloud translation adapters. Choose quick translation without an API key, or connect OpenAI, Claude, Gemini, OpenRouter, Ollama, LM Studio, DeepL, LibreTranslate or a compatible endpoint.

The overlay has editable presets, typography, colors, gradients, outlines, shadows, source/translation layouts, click-through and an edit shortcut. Onboarding, profiles, safe diagnostics, light/dark themes and conflict-aware hotkeys reduce setup work. Screenshots stay in memory; cloud translation sends recognized text only. There is no telemetry or saved history.

Download the per-user Windows x64 installer or extract the entire portable ZIP. Python and Tesseract are not required. Install recognition models in the app on first use. Keep the portable `_internal` folder next to the executable.

Validation includes 145 tests, lint/type checks, a fresh hash-locked installation, vulnerability audit, packaged OCR/credential checks, and a guarded desktop translation test at 125% scaling. See the repository's validation report for OCR errors and measured latency. This is a beta: full mixed-DPI hardware, exclusive-fullscreen, paid-provider/local-model quality and multi-hour media qualification remain open. Rapid subtitles can outpace CPU recognition.

Binaries are unsigned. Compare them against SHA256SUMS.txt. The SBOM describes the build environment, including tooling. THIRD_PARTY_NOTICES are included, and LibrarySources.zip contains the matching unmodified LGPL Qt/PySide sources. DeskTranslate application code is MIT; third-party terms remain intact.

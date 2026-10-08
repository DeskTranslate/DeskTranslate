# Privacy

DeskTranslate captures only the region you select during a translation session. Selection previews are frozen screen images held in memory and released when selection ends. OCR pixels, recognized text, translations, context and cache are memory-only. Stop clears the session by releasing it; no history export is enabled. Explicit developer preview/benchmark commands create synthetic artifacts.

OCR is local. Cloud translation sends recognized text, language choices, configured glossary/style instructions and bounded recent dialogue to the provider. Screenshots are never sent. Local Ollama/LM Studio or compatible loopback services keep this data on the machine; their own configuration determines any downstream behavior. No automatic cloud fallback occurs. Your provider's retention policies apply independently of DeskTranslate.

Keys are bound to provider and endpoint identity in OS credential storage, not settings. Unsupported or plaintext keyring backends fail closed. Remote HTTP is rejected, HTTPS certificate verification remains enabled, and provider redirects are rejected. Network libraries may honor system/environment proxy configuration.

Settings, model files and metadata-only rotating logs use `%LOCALAPPDATA%\DeskTranslate` on Windows. Settings include your explicit glossary, custom instructions, model/endpoint and profiles; treat those files as private if you put private names or terminology there. Logs discard messages, dialogue, URL paths, headers, API keys and exception tracebacks. Copy Diagnostics excludes screen text, credentials and endpoints, but includes model name and display geometry.

There is no telemetry and no periodic update request. Recognition installation fetches the pinned model files only when you click Install. Find local servers sends only discovery requests to loopback. Test connection sends a synthetic greeting for conventional MT, or requests the model catalog for AI. Check for updates explicitly requests GitHub release metadata and may open verified release notes in your browser.

Clipboard copy is explicit; other applications or clipboard-history services may retain what you copy. Uninstall removes the program; settings/models remain for reinstall. Delete `%LOCALAPPDATA%\DeskTranslate` for a clean local reset. Delete saved provider keys through Providers or Windows Credential Manager. DeskTranslate never backs up old configuration containing secret fields.

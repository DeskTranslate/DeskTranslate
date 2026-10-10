# Translation setup

Recognition always runs locally. Choose where recognized text, glossary/style and bounded dialogue context should go. Nothing silently switches your provider, model or local/cloud choice. API prices, free quotas and model access depend on the provider account; DeskTranslate does not promise free credits.

| Choice | Setup and behavior |
|---|---|
| Google quick | Keyless public web endpoint. Simple first-success path; no availability guarantee. |
| DeepL | API key and the appropriate Free/Pro HTTPS endpoint. Conventional translation, without AI dialogue context. |
| LibreTranslate | Local loopback or remote HTTPS base URL. Optional key; languages depend on your server. |
| OpenAI | API key, discovered text model, native Responses recommended. Advanced settings offer Chat Completions. Requests disable storage and streaming. |
| Claude | API key and model access; native Messages. |
| Gemini | API key and discovered compatible model; native generateContent. |
| OpenRouter | API key and chosen text model. Price/context information appears when the catalog supplies it. |
| Ollama | Install/load a model yourself and start Ollama. Find local AI servers discovers the default loopback endpoint. |
| LM Studio | Load a model and start the local API server yourself, then discover/test/select it. |
| Compatible | Loopback HTTP or remote HTTPS base URL, optional key, explicit model. Uses Chat Completions. |

In Providers, choose a service, enter a key if needed, **Save & test connection**, choose a model and **Apply translation settings**. The key is saved in Windows Credential Manager for that provider/endpoint. Leave its field blank to keep the saved key. Delete saved key removes it. Advanced connection settings expose endpoints/API mode only when needed. Changing provider clears dialogue context and requires a fresh session; it does not silently resume capture.

Discovery omits known embedding, image, audio and realtime-only models. A catalog is not proof that a model is usable with your account or server; unknown compatible IDs remain selectable. Reasoning, quotas, costs and speed are not fabricated. Native Responses requires a completed assistant text response; truncated, blocked, malformed or oversized responses fail safely. Custom servers may expose only Chat Completions. Existing beta1 native OpenAI settings retain Chat mode until you explicitly change it.

Natural, Literal, Subtitle and Game styles control AI instructions. Custom instructions are capped. Glossaries accept `source = translation` lines or imported JSON/CSV; review imported draft terms and press Apply. JSON preserves multiline and delimiter-containing terms. CSV export rejects terms that spreadsheets could evaluate as formulas; use JSON for those terms. Recent dialogue stays bounded in memory and clears on Stop, profile/provider/target change or a new session.

If authentication fails, translation pauses: update your key, test and resume. If quota/rate limits occur, one bounded retry is allowed while the request is still current, then translation pauses until you act. For timeout/deleted model/server failures, test the provider or refresh the model list, choose a usable model and resume. Local server failure never sends text to Google or another cloud service. Full requests have a deadline and Stop cancels pending network I/O.

All adapters have contract/fault tests. The six setup fixtures were tested against Google's live endpoint. Paid-account APIs and actual loaded Ollama/LM Studio models still require account/hardware qualification before stable promotion.

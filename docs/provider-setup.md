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

In Providers, choose a service, enter a key if needed, **Save and test connection**, choose a model and **Apply translation settings**. The key is saved in Windows Credential Manager for that provider/endpoint. Leave its field blank to keep the saved key. Delete saved key removes it. Advanced connection settings expose endpoints/API mode only when needed. Changing provider clears dialogue context and requires a fresh session; it does not silently resume capture.

Discovery omits known embedding, image, audio and realtime-only models. A catalog is not proof that a model is usable with your account or server; unknown compatible IDs remain selectable. Reasoning, quotas, costs and speed are not fabricated. Native Responses requires a completed assistant text response; truncated, blocked, malformed or oversized responses fail safely. Custom servers may expose only Chat Completions. Existing beta1 native OpenAI settings retain Chat mode until you explicitly change it.

Natural, Literal, Subtitle and Game styles control AI instructions. Custom instructions are capped. Glossaries accept `source = translation` lines or imported JSON/CSV; review imported draft terms and press Apply. JSON preserves multiline and delimiter-containing terms. CSV export rejects terms that spreadsheets could evaluate as formulas; use JSON for those terms. Recent dialogue stays bounded in memory and clears on Stop, profile/provider/target change or a new session.

If authentication fails, translation pauses: update your key, test and resume. If quota/rate limits occur, one bounded retry is allowed while the request is still current, then translation pauses until you act. For timeout/deleted model/server failures, test the provider or refresh the model list, choose a usable model and resume. Local server failure never sends text to Google or another cloud service. Full requests have a deadline and Stop cancels pending network I/O.

All ten adapters have contract/fault tests. Eighteen of 19 authored first-run samples passed actual OCR and live Google translation; Vietnamese failed the recognition guard, so its text was not sent. A separate Google test returned Spanish, Hebrew, Thai and Czech output. An earlier real 429 remains recorded; public-endpoint availability is not guaranteed.

Actual Ollama 0.40.4 and LM Studio llmster 0.0.25-1 were tested with isolated CPU Qwen3 0.6B and Qwen2.5 1.5B models, including discovery, offline behavior, unload/reload, cancellation and restart; LM Studio also exercised context and mid-generation disconnect. LM Studio now checks the selected model on each request and rejects a different response model, preventing silent fallback. Transport/lifecycle success is separate from quality: the 0.6B model produced JSON-wrapped Spanish or `{}`; 1.5B output omitted meaning or sometimes added explanations. Neither is a qualified translation-model recommendation. A real unauthenticated public LibreTranslate request was safely rejected, with no successful generation. Paid-account APIs, a configured LibreTranslate server and arbitrary custom servers remain NOT TESTED without suitable accounts/servers. See the [acceptance matrix](validation.md).

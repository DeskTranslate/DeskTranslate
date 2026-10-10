import json

import httpx
import pytest

from desktranslate.errors import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    TranslationError,
)
from desktranslate.models import ContextPair, TranslationRequest
from desktranslate.providers import create_provider, prompts


@pytest.mark.parametrize(
    "name,response",
    [
        (
            "openai",
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Translation"}],
                    }
                ],
                "usage": {"input_tokens": 10},
            },
        ),
        ("openrouter", {"choices": [{"message": {"content": "Translation"}}]}),
        ("lmstudio", {"choices": [{"message": {"content": "Translation"}}]}),
        ("custom", {"choices": [{"message": {"content": "Translation"}}]}),
        (
            "anthropic",
            {"content": [{"type": "text", "text": "Translation"}], "usage": {"input_tokens": 10}},
        ),
        (
            "gemini",
            {
                "candidates": [
                    {"content": {"parts": [{"text": "Translation"}]}, "finishReason": "STOP"}
                ]
            },
        ),
        ("ollama", {"message": {"content": "Translation"}, "prompt_eval_count": 10}),
        ("google", [[["Translation", "Source"]]]),
        ("deepl", {"translations": [{"text": "Translation"}]}),
        ("libre", {"translatedText": "Translation"}),
    ],
)
def test_native_translation_contracts(name, response):
    def handler(request):
        assert request.url.scheme in {"https", "http"}
        if name == "openai":
            body = json.loads(request.content)
            assert request.url.path == "/v1/responses"
            assert body["store"] is False and body["stream"] is False
        if name == "anthropic":
            body = json.loads(request.content)
            assert "system" in body
            assert all(m["role"] != "system" for m in body["messages"])
            assert request.headers["x-api-key"] == "test-key"
        if name == "gemini":
            assert request.headers["x-goog-api-key"] == "test-key"
            assert "key" not in request.url.params
        return httpx.Response(200, json=response)

    provider = create_provider(name, "test-key", transport=httpx.MockTransport(handler))
    try:
        assert (
            provider.translate(TranslationRequest("Source", "ja", "en", "test-model")).text
            == "Translation"
        )
    finally:
        provider.close()


@pytest.mark.parametrize(
    "name,payload",
    [
        ("openai", {"data": [{"id": "one"}]}),
        (
            "openrouter",
            {"data": [{"id": "one", "context_length": 10000, "pricing": {"prompt": "0.000001"}}]},
        ),
        ("anthropic", {"data": [{"id": "one", "display_name": "One"}]}),
        (
            "gemini",
            {
                "models": [
                    {"name": "models/one", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/embedding", "supportedGenerationMethods": ["embedContent"]},
                ]
            },
        ),
        ("ollama", {"models": [{"name": "one", "size": 20000}]}),
        ("lmstudio", {"data": [{"id": "one"}]}),
    ],
)
def test_model_discovery(name, payload):
    provider = create_provider(
        name,
        "test",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
    )
    assert [m.id for m in provider.models()] == ["one"]
    provider.close()


@pytest.mark.parametrize(
    "status,error",
    [(401, ProviderAuthenticationError), (429, ProviderRateLimitError), (302, TranslationError)],
)
def test_failures_do_not_leak_raw_response_or_follow_redirects(status, error):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            headers={"Location": "https://evil.example", "Retry-After": "3"},
            json={"error": "private source and secret key"},
        )

    provider = create_provider("openai", "key", transport=httpx.MockTransport(handler))
    with pytest.raises(error) as failure:
        provider.translate(TranslationRequest("Private source", "ja", "en", "model"))
    assert len(calls) == 1
    assert "private source" not in str(failure.value)
    provider.close()


@pytest.mark.parametrize(
    "name", ["openai", "anthropic", "gemini", "ollama", "google", "deepl", "libre"]
)
def test_malformed_responses(name):
    provider = create_provider(
        name, "key", transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    )
    with pytest.raises(TranslationError):
        provider.translate(TranslationRequest("text", "ja", "en", "model"))
    provider.close()


def test_prompt_translates_questions_and_bounds_context():
    request = TranslationRequest(
        "Where did you hide the key?",
        "en",
        "ja",
        context=(ContextPair("Old line", "古い台詞"),),
        glossary=(("Mika", "ミカ"),),
    )
    system, user = prompts(request)
    assert "Do not answer questions" in system
    assert "untrusted" in system
    assert json.loads(user)["current_text"] == request.text
    assert json.loads(user)["glossary"]["Mika"] == "ミカ"


def test_native_openai_chat_retains_compatibility_and_disables_storage():
    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        assert json.loads(request.content)["store"] is False
        return httpx.Response(200, json={"choices": [{"message": {"content": "Translation"}}]})

    provider = create_provider(
        "openai", "test", openai_api="chat", transport=httpx.MockTransport(handler)
    )
    assert provider.translate(TranslationRequest("text", "ja", "en", "model")).text == "Translation"
    provider.close()


def test_gzip_response_limit_is_enforced_before_unbounded_expansion():
    import gzip

    compressed = gzip.compress(b"x" * 8_000_100)
    provider = create_provider(
        "custom",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={"Content-Encoding": "gzip"}, stream=httpx.ByteStream(compressed)
            )
        ),
    )
    with pytest.raises(TranslationError, match="too large"):
        provider.translate(TranslationRequest("text", "ja", "en", "model"))
    provider.close()


def test_catalog_filters_known_non_text_models_and_keeps_unknown_compatibility_ids():
    provider = create_provider(
        "openrouter",
        "test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "text-embedding-3-small"},
                        {"id": "gpt-image-1"},
                        {"id": "mystery-text-model"},
                        {"id": "vision-only", "architecture": {"output_modalities": ["image"]}},
                    ]
                },
            )
        ),
    )
    assert [model.id for model in provider.models()] == ["mystery-text-model"]
    provider.close()

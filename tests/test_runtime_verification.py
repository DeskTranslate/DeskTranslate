from desktranslate.runtime_verification import verify_http_provider


def test_runtime_probe_exercises_real_loopback_async_http() -> None:
    assert verify_http_provider()

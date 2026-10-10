from pathlib import Path

import pytest
from tools import release_support


def test_canonical_versions_and_mismatched_tag() -> None:
    root = Path(__file__).resolve().parents[1]
    release_support.version_gate(root, "v" + release_support.__version__)
    with pytest.raises(ValueError, match="tag"):
        release_support.version_gate(root, "v9.9.9")
    assert release_support.windows_version("2.0.0b2") == "2.0.0.10002"
    assert release_support.windows_version("2.0.0rc1") == "2.0.0.30001"
    assert release_support.windows_version("2.0.0") == "2.0.0.60000"


def test_release_signing_and_stable_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DESKTRANSLATE_SIGNING_THUMBPRINT", raising=False)
    with pytest.raises(ValueError, match="publisher"):
        release_support.Signer()
    with pytest.raises(ValueError, match="prerelease"):
        release_support.stable_gate(
            Path(__file__).resolve().parents[1], "v" + release_support.__version__
        )
    monkeypatch.setattr(release_support, "__version__", "2.0.0")
    with pytest.raises(ValueError, match="qualification"):
        release_support.stable_gate(Path(__file__).resolve().parents[1], "v2.0.0")

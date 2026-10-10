import hashlib
import json
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


@pytest.mark.parametrize("failure", ["duration", "resources", "source", "assets"])
def test_stable_rejects_incomplete_or_changed_soak(tmp_path, monkeypatch, failure):
    root = Path(__file__).resolve().parents[1]
    for name in ["pyproject.toml", "packaging/installer.iss"]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((root / name).read_bytes())
    docs = tmp_path / "docs"
    docs.mkdir()
    manual = json.loads((root / "docs/manual-qualification.json").read_text())
    manual["version"] = "2.0.0"
    manual["gates"] = dict.fromkeys(manual["gates"], True)
    (docs / "manual-qualification.json").write_text(json.dumps(manual))
    source = tmp_path / "src/desktranslate/example.py"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"qualified = True\n")
    evidence = {
        "version": "2.0.0",
        "elapsed_s": 7200,
        "workload_passed": True,
        "source_unchanged": True,
        "resource_qualification": {"qualified": True},
        "source_hashes": {"example.py": hashlib.sha256(source.read_bytes()).hexdigest()},
    }
    monkeypatch.setattr(release_support, "__version__", "2.0.0")
    (docs / "soak-2h.json").write_text(json.dumps(evidence))
    release_support.stable_gate(tmp_path, "v2.0.0")
    if failure == "duration":
        evidence["elapsed_s"] = 7199
    elif failure == "resources":
        evidence["resource_qualification"]["qualified"] = False
    elif failure == "source":
        source.write_bytes(b"qualified = False\n")
    else:
        (source.parent / "new-asset.bin").write_bytes(b"unqualified")
    (docs / "soak-2h.json").write_text(json.dumps(evidence))
    with pytest.raises(ValueError, match="soak|source/assets"):
        release_support.stable_gate(tmp_path, "v2.0.0")

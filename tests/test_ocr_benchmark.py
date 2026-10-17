import json
from pathlib import Path

import pytest
from PIL import Image

from desktranslate.models import OCRResult


@pytest.mark.parametrize("inference_failure", [False, True])
def test_benchmark_reuses_one_model_family_and_preserves_partial_failure(
    monkeypatch, tmp_path, inference_failure
):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    import evaluate

    samples = [{"id": code, "language": code, "text": code} for code in ("fr", "ja", "es")]
    monkeypatch.setattr(evaluate, "SAMPLES", samples)
    for sample in samples:
        Image.new("RGB", (24, 16)).save(tmp_path / (sample["id"] + ".png"))
    active, created, closed = [], [], []

    class Engine:
        def __init__(self, language, directory):
            assert not active, "The previous native model family must close before loading another"
            assert directory == tmp_path / "models"
            active.append(self)
            created.append(language)

        def recognize(self, image, language, vertical):
            if inference_failure and language == "es":
                raise RuntimeError("private inference detail")
            return OCRResult(language, confidence=0.99, duration_ms=2)

        def close(self):
            assert active.pop() is self
            closed.append(self)

    monkeypatch.setattr(evaluate, "RapidEngine", Engine)
    output = tmp_path / "result.json"
    if inference_failure:
        with pytest.raises(RuntimeError):
            evaluate.benchmark(
                tmp_path, "rapidocr", False, 1, models=tmp_path / "models", output=output
            )
    else:
        evaluate.benchmark(
            tmp_path, "rapidocr", False, 1, models=tmp_path / "models", output=output
        )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert created == ["ja", "fr"] and len(closed) == 2 and not active
    assert report["completed"] is not inference_failure
    assert report["source_unchanged"] and report["cleanup_completed"]
    assert [row["id"] for row in report["fixtures"]] == (
        ["ja", "fr"] if inference_failure else ["ja", "fr", "es"]
    )
    assert all(variant["cer"] == 0 for row in report["fixtures"] for variant in row["variants"])
    assert "private inference detail" not in output.read_text(encoding="utf-8")
    assert not list(tmp_path.glob("*.part"))

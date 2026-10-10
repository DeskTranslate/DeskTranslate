"""Research-only fixture benchmark. Run DirectML in a separate environment.

The RapidOCR option conversion and DirectML session constraints are applied only
inside this process. This does not enable acceleration in the shipped application.
"""

import argparse
import json
import statistics
import time
from pathlib import Path

import onnxruntime as ort
from PIL import Image
from rapidocr import RapidOCR
from rapidocr.inference_engine.onnxruntime.main import OrtInferSession
from rapidocr.inference_engine.onnxruntime.provider_config import ProviderConfig

from desktranslate.ocr import RapidEngine

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("mode", choices=("cpu", "directml"))
mode = parser.parse_args().mode
if mode == "directml" and "DmlExecutionProvider" not in ort.get_available_providers():
    raise SystemExit(
        "Use an isolated environment with the official DirectML wheel; never replace the release lock in place."
    )
old_dml = ProviderConfig.dml_ep_cfg
ProviderConfig.dml_ep_cfg = lambda self: dict(old_dml(self))
old_init = RapidOCR.__init__


def configured(self, *args, **kwargs):
    params = kwargs.setdefault("params", {})
    params["EngineConfig.onnxruntime.use_dml"] = mode == "directml"
    params["EngineConfig.onnxruntime.dml_ep_cfg"] = {"device_id": 0}
    old_init(self, *args, **kwargs)


RapidOCR.__init__ = configured
old_opts = OrtInferSession._init_sess_opts


def options(cfg):
    result = old_opts(cfg)
    if mode == "directml":
        result.enable_mem_pattern = False
        result.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return result


OrtInferSession._init_sess_opts = staticmethod(options)
report = {
    "runtime_version": ort.__version__,
    "mode": mode,
    "available_providers": ort.get_available_providers(),
    "primary_environment_unchanged": True,
    "requested_adapter_index": 0 if mode == "directml" else None,
    "fixtures": [],
}
for language, name, expected in [
    ("ja", "ja-game.png", "明日、またここで会おう。"),
    ("ko", "ko-subtitle.png", "내일 다시 만나요."),
    ("en", "en-ui.png", "Select a region to translate."),
]:
    start = time.perf_counter()
    engine = RapidEngine(language)
    startup = (time.perf_counter() - start) * 1000
    providers = engine.engine.text_det.session.session.get_providers()
    if mode == "directml" and providers[0] != "DmlExecutionProvider":
        raise RuntimeError("Requested GPU provider was not actually used")
    image = Image.open(Path("tests/fixtures") / name).convert("RGB")
    timings = []
    for repeat in range(6):
        result = engine.recognize(image, language)
        if repeat:
            timings.append(result.duration_ms)
    report["fixtures"].append(
        {
            "language": language,
            "startup_ms": round(startup, 2),
            "warm_median_ms": round(statistics.median(timings), 2),
            "warm_max_ms": round(max(timings), 2),
            "exact": "".join(result.text.split()) == "".join(expected.split()),
            "providers": providers,
        }
    )
    engine.close()
    del engine
Path(f"docs/ocr-{mode}-{ort.__version__}-investigation.json").write_text(
    json.dumps(report, indent=2), encoding="utf-8"
)
print(json.dumps(report))

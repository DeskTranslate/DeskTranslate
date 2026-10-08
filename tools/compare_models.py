"""Compare upstream's small multilingual model using the same original fixtures."""

import json
import time
from pathlib import Path
from threading import Event

import numpy as np
import yaml
from PIL import Image
from rapidocr import LangDet, ModelType, OCRVersion, RapidOCR

from desktranslate.ocr import ModelManager


def main():
    import rapidocr

    upstream = yaml.safe_load(
        (Path(rapidocr.__file__).parent / "default_models.yaml").read_text(encoding="utf-8")
    )["onnxruntime"]["PP-OCRv6"]
    manager = ModelManager()
    for key, task, name in [
        ("det", "det", "multi_PP-OCRv6_det_small"),
        ("ch", "rec", "multi_PP-OCRv6_rec_small"),
    ]:
        info = upstream[task][name]
        manager.catalog[key] = {
            "filename": info["model_dir"].rsplit("/", 1)[-1],
            "url": info["model_dir"],
            "sha256": info["SHA256"],
        }
    manager.install("auto", Event(), lambda *args: None)
    start = time.perf_counter()
    engine = RapidOCR(
        params={
            "Global.log_level": "critical",
            "Det.model_path": str(manager.path("det")),
            "Det.ocr_version": OCRVersion.PPOCRV6,
            "Det.model_type": ModelType.SMALL,
            "Det.lang_type": LangDet.MULTI,
            "Cls.model_path": str(manager.path("cls")),
            "Rec.model_path": str(manager.path("ch")),
            "Rec.ocr_version": OCRVersion.PPOCRV6,
            "Rec.model_type": ModelType.SMALL,
            "Rec.lang_type": "multi",
            "EngineConfig.onnxruntime.intra_op_num_threads": 2,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        }
    )
    report = {
        "startup_ms": (time.perf_counter() - start) * 1000,
        "models": manager.catalog,
        "fixtures": [],
    }
    samples = json.loads(Path("tests/fixtures/samples.json").read_text(encoding="utf-8"))
    for sample in samples:
        image = Image.open("tests/fixtures/" + sample["id"] + ".png").convert("RGB")
        result = engine(np.asarray(image)[:, :, ::-1], use_cls=False)
        report["fixtures"].append(
            {"id": sample["id"], "text": "\n".join(result.txts or []), "ms": result.elapse * 1000}
        )
    Path("docs/ocr-v6-comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Multilingual comparison complete")


if __name__ == "__main__":
    main()

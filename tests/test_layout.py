from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from desktranslate.layout import from_counterclockwise, resolve_layout, uncovered_lines
from desktranslate.models import OCRLine, Rect
from desktranslate.ocr import RapidEngine


@pytest.mark.parametrize(
    "box",
    [Rect(0, 0, 660, 260), Rect(420, 23, 32, 161), Rect(0, 244, 20, 16), Rect(640, 0, 20, 14)],
)
def test_orientation_roundtrip_preserves_physical_crop_edges(box):
    turned = Rect(box.y, 660 - box.right, box.height, box.width)
    assert from_counterclockwise(turned, 660, 260) == box


def line(text, x, y, w, h):
    return OCRLine(text, Rect(x, y, w, h), 0.99)


def test_mixed_order_keeps_caption_and_columns_but_not_cross_column_fragments():
    caption = line("ミカ：待って！", 29, 6, 140, 20)
    fragment = line("魔ア", 358, 24, 94, 31)
    right, left = line("アルトリア", 420, 26, 31, 199), line("魔導炉", 358, 24, 35, 117)
    retained = uncovered_lines((caption, fragment), (right.box, left.box))
    assert retained == (caption,)
    text, body, annotations = resolve_layout(retained, (left, right))
    assert text == "ミカ：待って！\nアルトリア\n魔導炉"
    assert len(body) == 3 and not annotations


@pytest.mark.parametrize(
    "reading_x,reading_width,scale", [(453, 11, 1), (452, 13, 1), (905, 24, 2)]
)
def test_ruby_is_preserved_as_an_annotation_without_dropping_small_body_text(
    reading_x, reading_width, scale
):
    main = line("魔導炉", 418 * scale, 24 * scale, 35 * scale, 117 * scale)
    ruby = line("まどうろ", reading_x, 29 * scale, reading_width, 67 * scale)
    number = line("101", reading_x, 29 * scale, reading_width, 67 * scale)
    latin = line("MP", reading_x, 29 * scale, reading_width, 67 * scale)
    distant = line("まどうろ", 530 * scale, 29 * scale, reading_width, 67 * scale)
    inside = line("まどうろ", 425 * scale, 29 * scale, reading_width, 67 * scale)
    text, body, annotations = resolve_layout((), (main, ruby))
    assert text == "魔導炉" and body == (main,) and annotations == (ruby,)
    for independent in (number, latin, distant, inside):
        text, body, annotations = resolve_layout((), (main, independent))
        assert independent in body and independent.text in text and not annotations


def test_regional_recognition_preserves_upright_caption_pixels_and_rotates_only_the_column():
    import numpy as np

    engine = RapidEngine.__new__(RapidEngine)
    engine.regional_model = Path("verified-fixture-model.onnx")
    shapes = []

    class Detector:
        text_score = 0.5

        def __call__(self, image, **options):
            assert options["use_rec"] is False and image.shape == (160, 100, 3)
            return SimpleNamespace(boxes=np.array([[[20, 44], [80, 44], [80, 60], [20, 60]]]))

    def recognize(request):
        shapes.extend(image.shape for image in request.img)
        return SimpleNamespace(txts=["魔導炉", "ミカ："], scores=[0.99, 0.99])

    engine.engine = Detector()
    engine.regional_recognizer = recognize
    caption = line("ミカ：", 10, 0, 50, 12)
    text, body, annotations, timings = engine.vertical_layout(
        Image.new("RGB", (160, 100)), (caption,)
    )
    assert shapes == [(20, 64, 3), (14, 54, 3)]
    assert text == "ミカ：\n魔導炉" and body[1].box == Rect(100, 20, 16, 60)
    assert not annotations and "ocr_layout_detect_ms" in timings


def test_no_vertical_columns_preserves_normal_short_text_without_loading_another_model():
    engine = RapidEngine.__new__(RapidEngine)
    engine.regional_model = Path("verified-fixture-model.onnx")
    engine.regional_recognizer = None
    engine.engine = lambda *args, **kwargs: SimpleNamespace(boxes=None)
    short = (line("の", 4, 5, 16, 18),)
    text, body, annotations, _ = engine.vertical_layout(Image.new("RGB", (160, 100)), short)
    assert text is None and body == short and not annotations
    assert engine.regional_recognizer is None


def test_secondary_word_recognition_keeps_short_glyphs_counters_and_failed_candidates():
    engine = RapidEngine.__new__(RapidEngine)
    engine.regional_model = Path("verified-fixture-model.onnx")
    engine.engine = SimpleNamespace(text_score=0.5)
    calls = []

    def recognize(request):
        calls.append(len(request.img))
        return SimpleNamespace(txts=["ドラゴンの城へ行こう！", ""], scores=[0.99, 0.0])

    engine.regional_recognizer = recognize
    glyph, counter = line("の", 0, 0, 16, 18), line("HP 120", 0, 20, 60, 18)
    assert engine.refine_horizontal(Image.new("RGB", (400, 160)), (glyph, counter)) == (
        glyph,
        counter,
    )
    assert not calls
    pixel = line("ドラゴンの城ー行ニラ「", 0, 50, 220, 24)
    uncertain = line("明日の約束です。", 0, 90, 180, 24)
    result = engine.refine_horizontal(
        Image.new("RGB", (400, 160)), (glyph, counter, pixel, uncertain)
    )
    assert calls == [2]
    assert result[0:2] == (glyph, counter)
    assert result[2].text == "ドラゴンの城へ行こう！" and result[3] == uncertain

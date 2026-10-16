"""Sequence behavior, not an assertion that mocked OCR/provider output is accurate."""

import json
from dataclasses import replace

from desktranslate.context import ContextEngine, TranslationContext, cache_key
from desktranslate.models import OCRLine, OCRResult, Rect
from desktranslate.profiles import apply_profile, profile_values
from desktranslate.settings import Settings, SettingsStore
from desktranslate.temporal import TemporalTextTracker


def recognized(text, confidence=0.96, x=10):
    return OCRResult(text, (OCRLine(text, Rect(x, 20, 320, 40), confidence),), confidence, "ja")


def test_single_frame_spacing_noise_needs_confirmation_without_erasing_true_word_changes():
    tracker = TemporalTextTracker()
    assert tracker.observe(recognized("미카,문이열렸어요!"), 0) == "미카,문이열렸어요!"
    assert tracker.observe(recognized("미카, 문이 열렸어요!"), 0.2) is None
    assert tracker.observe(recognized("미카,문이열렸어요!"), 0.4) is None
    assert tracker.observe(recognized("미카, 문이 열렸어요!"), 0.6) is None
    assert tracker.observe(recognized("미카, 문이 열렸어요!"), 0.8) == "미카, 문이 열렸어요!"


def test_moving_background_samples_brief_dialogue_without_growing_pending_work():
    from PIL import Image

    from desktranslate.algorithms import PRESETS, FrameGate

    for preset in PRESETS.values():
        gate = FrameGate(preset.frame_settle, motion_interval=preset.motion_interval)
        sampled = []
        for index in range(30):
            at = index * 0.15
            text = "Brief first line!" if at < 1 else "Next line!"
            frame = Image.new("RGB", (30, 20), ((index * 31) % 256,) * 3)
            if gate.observe(frame, at).ready:
                sampled.append((at, text))
        assert any(text == "Brief first line!" for _, text in sampled)
        assert any(text == "Next line!" for _, text in sampled)
        assert all(
            b[0] - a[0] >= preset.motion_interval - 1e-6
            for a, b in zip(sampled, sampled[1:], strict=False)
        )


def test_progressive_vn_reveal_has_early_and_final_result_without_per_character_requests():
    tracker = TemporalTextTracker()
    frames = ["彼", "彼女", "彼女は", "彼女は昨日", "彼女は昨日ここに来た。"]
    outputs = [
        output
        for index, text in enumerate(frames)
        if (output := tracker.observe(recognized(text), index * 0.08, settled_frame=True))
    ]
    assert outputs == ["彼", frames[-1]]
    assert tracker.replaces_source == "彼"
    assert tracker.observe(recognized(frames[-1]), 0.6, settled_frame=True) is None


def test_progressive_revision_is_one_dialogue_turn_and_not_its_own_context():
    from desktranslate.transcript import SessionTranscript

    recent = TranslationContext()
    recent.accept("明日の予定は？", "What are your plans for tomorrow?")
    recent.accept("彼", "He")
    engine = ContextEngine(recent, {})
    request = engine.request(
        "彼女は昨日ここに来た。", "ja", "en", contextual=True, replaces_source="彼"
    )
    assert [pair.source for pair in request.context] == ["明日の予定は？"]
    recent.accept(request.text, "She came here yesterday.", replaces_source="彼")
    assert [pair.source for pair in recent.snapshot()] == ["明日の予定は？", request.text]
    # Independent similar dialogue stays separate without explicit revision ownership.
    recent.accept("彼女は昨日ここに来た？", "Did she come here yesterday?")
    assert len(recent.snapshot()) == 3
    transcript = SessionTranscript(chars=100)
    transcript.set_enabled(True)
    transcript.append("彼", "He")
    transcript.append(request.text, "She came here yesterday.", replaces_source="彼")
    assert len(transcript.entries) == 1
    assert transcript.size == len(request.text) + len("She came here yesterday.")
    transcript.set_enabled(False)
    assert not transcript.entries and transcript.size == 0


def test_brief_complete_subtitle_needs_one_observation_and_genuine_small_change_can_win():
    tracker = TemporalTextTracker()
    assert tracker.observe(recognized("Wait for me!"), 0) == "Wait for me!"
    assert tracker.observe(recognized("Wait for us!"), 0.2) == "Wait for us!"
    assert tracker.observe(recognized("Wait for us?", 0.90), 0.4) is None
    assert tracker.observe(recognized("Wait for us?", 0.90), 0.6) == "Wait for us?"


def test_repeated_name_agreement_and_geometry_avoid_single_frame_ocr_churn():
    tracker = TemporalTextTracker()
    assert tracker.observe(recognized("アルトリア"), 0) is None
    assert tracker.observe(recognized("アルトリァ", 0.82), 0.1) is None
    assert tracker.observe(recognized("アルトリア"), 0.2) == "アルトリア"
    assert tracker.observe(recognized("アルトリァ", 0.82), 0.3, True) is None
    assert tracker.observe(recognized("アルトリア"), 0.4, True) is None
    # A different region is independent evidence, even when its string is close.
    assert tracker.observe(recognized("アルトリァ", x=700), 0.5, True) == "アルトリァ"
    for index in range(1000):
        tracker.observe(recognized("アルトリァ", x=700), index + 1)
    assert len(tracker.history) <= 6


def test_progressive_no_punctuation_finishes_after_a_short_quiet_period_and_rebases_safely():
    tracker = TemporalTextTracker()
    assert tracker.observe(recognized("The door"), 0, True) == "The door"
    assert tracker.observe(recognized("The door is open"), 0.1, True) is None
    tracker.rebase_delivery("")  # A pixel revision cancelled the first request.
    assert tracker.observe(recognized("The door is open"), 0.2, True) is None
    assert tracker.observe(recognized("The door is open"), 0.4, True) == "The door is open"


def test_context_retrieves_relevant_terms_without_self_context_or_unrelated_dictionary():
    recent = TranslationContext()
    recent.accept("アウレリアは王都へ向かった。", "Aurelia went to the capital.")
    glossary = {f"Unused {index}": f"Unrelated {index}" for index in range(800)}
    glossary.update({"アウレリア": "Aurelia", "魔導炉": "Mana Reactor", "cat": "Cat"})
    engine = ContextEngine(recent, glossary, "Aurelia is female. This is a fantasy RPG.")
    request = engine.request("彼女は魔導炉を止める。", "ja", "en", contextual=True)
    assert dict(request.glossary) == {"魔導炉": "Mana Reactor", "アウレリア": "Aurelia"}
    assert request.context == recent.snapshot() and request.story_context == engine.story
    assert len(json.dumps(dict(request.glossary)).encode()) < 1800
    assert (
        not ContextEngine(recent, {"cat": "Cat"})
        .request("cathedral", "en", "ja", contextual=True)
        .glossary
    )
    recent.accept(request.text, "She will stop the Mana Reactor.")
    repeated = engine.request(request.text, "ja", "en", contextual=True)
    assert all(pair.source != request.text for pair in repeated.context)
    assert cache_key("custom", "loopback", repeated) != cache_key(
        "custom", "loopback", replace(repeated, story_context="A different title")
    )
    assert engine.terminology.exact("魔導炉") == "Mana Reactor"
    assert ContextEngine(recent, {"US": "United States"}).terminology.exact("us") is None
    conventional = engine.request("魔導炉", "ja", "en", contextual=False)
    assert not conventional.context and not conventional.glossary and not conventional.story_context


def test_story_and_glossary_persist_per_title_without_cross_language_or_legacy_contamination(
    tmp_path,
):
    settings = Settings(glossary={"魔導炉": "Mana Reactor"}, story_context="Aurelia is female.")
    settings.profiles["Fantasy"] = profile_values(settings)
    settings.active_profile = "Fantasy"
    store = SettingsStore(tmp_path)
    store.save(settings)
    loaded = store.load()
    assert not store.recovered and loaded.story_context == settings.story_context
    assert (loaded.glossary_source, loaded.glossary_target) == ("ja", "en")
    changed = replace(loaded, target="es")
    assert changed.glossary_target == "en"  # Never silently rebind English preferred terms.
    other = apply_profile(loaded, {"source": "ko", "target": "en"})
    assert not other.glossary and not other.story_context
    restored = apply_profile(other, loaded.profiles["Fantasy"])
    assert (
        restored.glossary == settings.glossary and restored.story_context == settings.story_context
    )

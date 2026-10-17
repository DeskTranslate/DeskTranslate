import pytest

from desktranslate.profiles import export_glossary, import_glossary
from desktranslate.ui.glossary import editor_content, parse_editor


def test_glossary_exchange_preserves_unicode_and_editor_delimiters() -> None:
    glossary = {"兄さん": "big brother", "a=b": "line one\nline two"}
    assert import_glossary(export_glossary(glossary)) == glossary
    assert import_glossary(export_glossary(glossary, True), True) == glossary
    assert parse_editor(editor_content(glossary)) == glossary
    assert parse_editor("兄さん = big brother") == {"兄さん": "big brother"}


@pytest.mark.parametrize(
    "content", ["source,translation\na,b\na,c", 'source,translation\n"unfinished,b']
)
def test_glossary_rejects_ambiguous_or_malformed_csv(content: str) -> None:
    with pytest.raises(ValueError):
        import_glossary(content, True)


def test_glossary_csv_formula_terms_require_lossless_json() -> None:
    glossary = {"normal": "=SUM(1,2)"}
    with pytest.raises(ValueError, match="JSON"):
        export_glossary(glossary, True)
    assert import_glossary(export_glossary(glossary)) == glossary

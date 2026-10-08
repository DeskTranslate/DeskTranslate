from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    tesseract: str
    recognition: str
    script: str = "Latin"
    direction: str = "ltr"


# Recognition families refer to the managed RapidOCR models, not translation language IDs.
LANGUAGES = (
    Language("auto", "Detect automatically", "", "ch", "Auto"),
    Language("ja", "Japanese", "jpn", "japan", "Japanese"),
    Language("en", "English", "eng", "en"),
    Language("ko", "Korean", "kor", "korean", "Hangul"),
    Language("zh-CN", "Chinese · Simplified", "chi_sim", "ch", "Han"),
    Language("zh-TW", "Chinese · Traditional", "chi_tra", "chinese_cht", "Han"),
    Language("es", "Spanish", "spa", "latin"),
    Language("fr", "French", "fra", "latin"),
    Language("de", "German", "deu", "latin"),
    Language("it", "Italian", "ita", "latin"),
    Language("pt", "Portuguese", "por", "latin"),
    Language("nl", "Dutch", "nld", "latin"),
    Language("pl", "Polish", "pol", "latin"),
    Language("vi", "Vietnamese", "vie", "latin"),
    Language("id", "Indonesian", "ind", "latin"),
    Language("tr", "Turkish", "tur", "latin"),
    Language("ru", "Russian", "rus", "cyrillic", "Cyrillic"),
    Language("uk", "Ukrainian", "ukr", "cyrillic", "Cyrillic"),
    Language("ar", "Arabic", "ara", "arabic", "Arabic", "rtl"),
    Language("hi", "Hindi", "hin", "devanagari", "Devanagari"),
)
REGISTRY = {language.code: language for language in LANGUAGES}


def language_name(code: str) -> str:
    return REGISTRY[code].name

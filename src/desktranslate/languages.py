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
MANAGED_LANGUAGES = (
    Language("auto", "Auto · Chinese / Latin recognition", "", "ch", "Auto"),
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
# Translation coverage is independent of OCR coverage. Provider availability varies.
# Keep the 133 v1 targets; target-only entries never fall back to English recognition.
LANGUAGES = MANAGED_LANGUAGES + (
    Language("af", "Afrikaans", "afr", "", direction="ltr"),
    Language("sq", "Albanian", "sqi", "", direction="ltr"),
    Language("am", "Amharic", "amh", "", direction="ltr"),
    Language("hy", "Armenian", "", "", direction="ltr"),
    Language("as", "Assamese", "", "", direction="ltr"),
    Language("ay", "Aymara", "", "", direction="ltr"),
    Language("az", "Azerbaijani", "aze", "", direction="ltr"),
    Language("bm", "Bambara", "", "", direction="ltr"),
    Language("eu", "Basque", "eus", "", direction="ltr"),
    Language("be", "Belarusian", "bel", "", direction="ltr"),
    Language("bn", "Bengali", "ben", "", direction="ltr"),
    Language("bho", "Bhojpuri", "", "", direction="ltr"),
    Language("bs", "Bosnian", "bos", "", direction="ltr"),
    Language("bg", "Bulgarian", "bul", "", direction="ltr"),
    Language("ca", "Catalan", "", "", direction="ltr"),
    Language("ceb", "Cebuano", "ceb", "", direction="ltr"),
    Language("ny", "Chichewa", "", "", direction="ltr"),
    Language("co", "Corsican", "", "", direction="ltr"),
    Language("hr", "Croatian", "hrv", "", direction="ltr"),
    Language("cs", "Czech", "ces", "", direction="ltr"),
    Language("da", "Danish", "dan", "", direction="ltr"),
    Language("dv", "Dhivehi", "", "", direction="rtl"),
    Language("doi", "Dogri", "", "", direction="ltr"),
    Language("eo", "Esperanto", "epo", "", direction="ltr"),
    Language("et", "Estonian", "est", "", direction="ltr"),
    Language("ee", "Ewe", "", "", direction="ltr"),
    Language("tl", "Filipino", "", "", direction="ltr"),
    Language("fi", "Finnish", "fin", "", direction="ltr"),
    Language("fy", "Frisian", "", "", direction="ltr"),
    Language("gl", "Galician", "glg", "", direction="ltr"),
    Language("ka", "Georgian", "kat", "", direction="ltr"),
    Language("el", "Greek", "ell", "", direction="ltr"),
    Language("gn", "Guarani", "", "", direction="ltr"),
    Language("gu", "Gujarati", "guj", "", direction="ltr"),
    Language("ht", "Haitian Creole", "", "", direction="ltr"),
    Language("ha", "Hausa", "", "", direction="ltr"),
    Language("haw", "Hawaiian", "", "", direction="ltr"),
    Language("he", "Hebrew", "heb", "", direction="rtl"),
    Language("hmn", "Hmong", "", "", direction="ltr"),
    Language("hu", "Hungarian", "hun", "", direction="ltr"),
    Language("is", "Icelandic", "isl", "", direction="ltr"),
    Language("ig", "Igbo", "", "", direction="ltr"),
    Language("ilo", "Ilocano", "", "", direction="ltr"),
    Language("ga", "Irish", "gle", "", direction="ltr"),
    Language("jv", "Javanese", "jav", "", direction="ltr"),
    Language("kn", "Kannada", "kan", "", direction="ltr"),
    Language("kk", "Kazakh", "kaz", "", direction="ltr"),
    Language("km", "Khmer", "", "", direction="ltr"),
    Language("rw", "Kinyarwanda", "", "", direction="ltr"),
    Language("gom", "Konkani", "", "", direction="ltr"),
    Language("kri", "Krio", "", "", direction="ltr"),
    Language("ku", "Kurdish (Kurmanji)", "", "", direction="ltr"),
    Language("ckb", "Kurdish (Sorani)", "", "", direction="rtl"),
    Language("ky", "Kyrgyz", "", "", direction="ltr"),
    Language("lo", "Lao", "lao", "", direction="ltr"),
    Language("la", "Latin", "lat", "", direction="ltr"),
    Language("lv", "Latvian", "lav", "", direction="ltr"),
    Language("ln", "Lingala", "", "", direction="ltr"),
    Language("lt", "Lithuanian", "lit", "", direction="ltr"),
    Language("lg", "Luganda", "", "", direction="ltr"),
    Language("lb", "Luxembourgish", "", "", direction="ltr"),
    Language("mk", "Macedonian", "mkd", "", direction="ltr"),
    Language("mai", "Maithili", "", "", direction="ltr"),
    Language("mg", "Malagasy", "", "", direction="ltr"),
    Language("ms", "Malay", "msa", "", direction="ltr"),
    Language("ml", "Malayalam", "mal", "", direction="ltr"),
    Language("mt", "Maltese", "mlt", "", direction="ltr"),
    Language("mi", "Maori", "", "", direction="ltr"),
    Language("mr", "Marathi", "mar", "", direction="ltr"),
    Language("mni-Mtei", "Meiteilon (Manipuri)", "", "", direction="ltr"),
    Language("lus", "Mizo", "", "", direction="ltr"),
    Language("mn", "Mongolian", "", "", direction="ltr"),
    Language("my", "Myanmar", "", "", direction="ltr"),
    Language("ne", "Nepali", "nep", "", direction="ltr"),
    Language("no", "Norwegian", "nor", "", direction="ltr"),
    Language("or", "Odia (Oriya)", "", "", direction="ltr"),
    Language("om", "Oromo", "", "", direction="ltr"),
    Language("ps", "Pashto", "", "", direction="rtl"),
    Language("fa", "Persian", "fas", "", direction="rtl"),
    Language("pa", "Punjabi", "", "", direction="ltr"),
    Language("qu", "Quechua", "", "", direction="ltr"),
    Language("ro", "Romanian", "", "", direction="ltr"),
    Language("sm", "Samoan", "", "", direction="ltr"),
    Language("sa", "Sanskrit", "", "", direction="ltr"),
    Language("gd", "Scots Gaelic", "", "", direction="ltr"),
    Language("nso", "Sepedi", "", "", direction="ltr"),
    Language("sr", "Serbian", "srp", "", direction="ltr"),
    Language("st", "Sesotho", "", "", direction="ltr"),
    Language("sn", "Shona", "", "", direction="ltr"),
    Language("sd", "Sindhi", "", "", direction="rtl"),
    Language("si", "Sinhala", "", "", direction="ltr"),
    Language("sk", "Slovak", "slk", "", direction="ltr"),
    Language("sl", "Slovenian", "slv", "", direction="ltr"),
    Language("so", "Somali", "", "", direction="ltr"),
    Language("su", "Sundanese", "", "", direction="ltr"),
    Language("sw", "Swahili", "swa", "", direction="ltr"),
    Language("sv", "Swedish", "swe", "", direction="ltr"),
    Language("tg", "Tajik", "tgk", "", direction="ltr"),
    Language("ta", "Tamil", "tam", "", direction="ltr"),
    Language("tt", "Tatar", "", "", direction="ltr"),
    Language("te", "Telugu", "tel", "", direction="ltr"),
    Language("th", "Thai", "tha", "", direction="ltr"),
    Language("ti", "Tigrinya", "", "", direction="ltr"),
    Language("ts", "Tsonga", "", "", direction="ltr"),
    Language("tk", "Turkmen", "", "", direction="ltr"),
    Language("ak", "Twi", "", "", direction="ltr"),
    Language("ur", "Urdu", "urd", "", direction="rtl"),
    Language("ug", "Uyghur", "", "", direction="rtl"),
    Language("uz", "Uzbek", "uzb", "", direction="ltr"),
    Language("cy", "Welsh", "cym", "", direction="ltr"),
    Language("xh", "Xhosa", "", "", direction="ltr"),
    Language("yi", "Yiddish", "yid", "", direction="rtl"),
    Language("yo", "Yoruba", "", "", direction="ltr"),
    Language("zu", "Zulu", "", "", direction="ltr"),
)
REGISTRY = {language.code: language for language in LANGUAGES}


def source_languages(engine: str = "rapidocr") -> tuple[Language, ...]:
    return tuple(
        language
        for language in LANGUAGES
        if (language.recognition if engine == "rapidocr" else language.tesseract)
    )


def language_name(code: str) -> str:
    return REGISTRY[code].name

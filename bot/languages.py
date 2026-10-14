"""Languages a video can be translated from / to.

Names are written in the language itself, so they read correctly whatever
interface language the user picked.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str  # ISO 639-1, as understood by Whisper
    flag: str
    native: str
    english: str  # used in prompts to the translation model

    @property
    def label(self) -> str:
        return f"{self.flag} {self.native}"


LANGUAGES: tuple[Language, ...] = (
    Language("ru", "🇷🇺", "Русский", "Russian"),
    Language("en", "🇬🇧", "English", "English"),
    Language("uk", "🇺🇦", "Українська", "Ukrainian"),
    Language("de", "🇩🇪", "Deutsch", "German"),
    Language("fr", "🇫🇷", "Français", "French"),
    Language("es", "🇪🇸", "Español", "Spanish"),
    Language("it", "🇮🇹", "Italiano", "Italian"),
    Language("pt", "🇵🇹", "Português", "Portuguese"),
    Language("pl", "🇵🇱", "Polski", "Polish"),
    Language("tr", "🇹🇷", "Türkçe", "Turkish"),
    Language("kk", "🇰🇿", "Қазақша", "Kazakh"),
    Language("uz", "🇺🇿", "Oʻzbekcha", "Uzbek"),
    Language("ar", "🇸🇦", "العربية", "Arabic"),
    Language("zh", "🇨🇳", "中文", "Chinese (Simplified)"),
    Language("ja", "🇯🇵", "日本語", "Japanese"),
    Language("ko", "🇰🇷", "한국어", "Korean"),
)

BY_CODE: dict[str, Language] = {lang.code: lang for lang in LANGUAGES}

# Whisper's verbose_json reports the detected language by English name.
_BY_ENGLISH_NAME = {lang.english.split(" ")[0].lower(): lang for lang in LANGUAGES}


def get(code: str) -> Language:
    return BY_CODE[code]


def from_whisper(name_or_code: str | None) -> Language | None:
    if not name_or_code:
        return None
    key = name_or_code.strip().lower()
    return BY_CODE.get(key) or _BY_ENGLISH_NAME.get(key)

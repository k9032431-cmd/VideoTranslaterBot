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
    edge_male: str = ""  # Microsoft Edge neural voices (free TTS)
    edge_female: str = ""
    nllb: str = ""  # language code of the local NLLB-200 translation model

    @property
    def label(self) -> str:
        return f"{self.flag} {self.native}"


LANGUAGES: tuple[Language, ...] = (
    Language("ru", "🇷🇺", "Русский", "Russian", "ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural", "rus_Cyrl"),
    Language("en", "🇬🇧", "English", "English", "en-US-AndrewMultilingualNeural", "en-US-EmmaMultilingualNeural", "eng_Latn"),
    Language("uk", "🇺🇦", "Українська", "Ukrainian", "uk-UA-OstapNeural", "uk-UA-PolinaNeural", "ukr_Cyrl"),
    Language("de", "🇩🇪", "Deutsch", "German", "de-DE-ConradNeural", "de-DE-KatjaNeural", "deu_Latn"),
    Language("fr", "🇫🇷", "Français", "French", "fr-FR-HenriNeural", "fr-FR-DeniseNeural", "fra_Latn"),
    Language("es", "🇪🇸", "Español", "Spanish", "es-ES-AlvaroNeural", "es-ES-ElviraNeural", "spa_Latn"),
    Language("it", "🇮🇹", "Italiano", "Italian", "it-IT-DiegoNeural", "it-IT-ElsaNeural", "ita_Latn"),
    Language("pt", "🇵🇹", "Português", "Portuguese", "pt-PT-DuarteNeural", "pt-PT-RaquelNeural", "por_Latn"),
    Language("pl", "🇵🇱", "Polski", "Polish", "pl-PL-MarekNeural", "pl-PL-ZofiaNeural", "pol_Latn"),
    Language("tr", "🇹🇷", "Türkçe", "Turkish", "tr-TR-AhmetNeural", "tr-TR-EmelNeural", "tur_Latn"),
    Language("kk", "🇰🇿", "Қазақша", "Kazakh", "kk-KZ-DauletNeural", "kk-KZ-AigulNeural", "kaz_Cyrl"),
    Language("uz", "🇺🇿", "Oʻzbekcha", "Uzbek", "uz-UZ-SardorNeural", "uz-UZ-MadinaNeural", "uzn_Latn"),
    Language("ar", "🇸🇦", "العربية", "Arabic", "ar-SA-HamedNeural", "ar-SA-ZariyahNeural", "arb_Arab"),
    Language("zh", "🇨🇳", "中文", "Chinese (Simplified)", "zh-CN-YunxiNeural", "zh-CN-XiaoxiaoNeural", "zho_Hans"),
    Language("ja", "🇯🇵", "日本語", "Japanese", "ja-JP-KeitaNeural", "ja-JP-NanamiNeural", "jpn_Jpan"),
    Language("ko", "🇰🇷", "한국어", "Korean", "ko-KR-InJoonNeural", "ko-KR-SunHiNeural", "kor_Hang"),
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

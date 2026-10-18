import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Defaults per provider: (base_url, transcribe model, translate model, reasoning effort, tts engine)
PROVIDER_DEFAULTS = {
    # Free: Groq (Whisper large-v3 + GPT-OSS) and Microsoft Edge voices.
    "free": (GROQ_BASE_URL, "whisper-large-v3", "openai/gpt-oss-120b", "low", "edge"),
    "openai": (None, "whisper-1", "gpt-5.4", "", "openai"),
    # Local: everything runs on the server (faster-whisper + NLLB-200), voices from Microsoft Edge.
    "local": (None, "small", "JustFrederik/nllb-200-distilled-600M-ct2-int8", "", "edge"),
}


def _int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    return int(value) if value else default


def _float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    return float(value) if value else default


def _str(name: str, default: str) -> str:
    return os.getenv(name, "").strip() or default


def _ids(name: str) -> frozenset[int]:
    raw = os.getenv(name, "")
    return frozenset(int(x) for x in raw.replace(";", ",").split(",") if x.strip())


@dataclass(frozen=True)
class Config:
    bot_token: str
    provider: str  # local | free | openai
    ai_api_key: str
    ai_base_url: str | None

    # Local Telegram Bot API server (lifts the 20 MB download / 50 MB upload limits to 2 GB).
    telegram_api_url: str | None
    telegram_api_local: bool

    transcribe_model: str
    translate_model: str
    translate_reasoning_effort: str  # "" = model default
    tts_engine: str  # edge | openai
    tts_model: str
    tts_voice: str  # OpenAI voice name
    tts_gender: str  # male | female (Edge voices)

    allowed_user_ids: frozenset[int]
    max_video_minutes: int
    max_concurrent_jobs: int
    original_volume: float

    data_dir: Path
    work_dir: Path = field(init=False)
    db_path: Path = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "work_dir", self.data_dir / "jobs")
        object.__setattr__(self, "db_path", self.data_dir / "bot.sqlite3")

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def max_download_bytes(self) -> int:
        return (2000 if self.telegram_api_url else 20) * 1024 * 1024

    @property
    def max_upload_bytes(self) -> int:
        return (2000 if self.telegram_api_url else 50) * 1024 * 1024


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN is not set (see .env.example)")

    provider = _str("PROVIDER", "local").lower()
    if provider not in PROVIDER_DEFAULTS:
        raise SystemExit(f"PROVIDER must be one of: {', '.join(PROVIDER_DEFAULTS)}")
    base_url, transcribe_model, translate_model, effort, tts_engine = PROVIDER_DEFAULTS[provider]

    api_key = ""
    if provider != "local":
        key_name = "GROQ_API_KEY" if provider == "free" else "OPENAI_API_KEY"
        api_key = os.getenv(key_name, "").strip()
        if not api_key:
            raise SystemExit(f"{key_name} is not set (see .env.example)")

    tts_engine = _str("TTS_ENGINE", tts_engine).lower()
    if tts_engine not in ("edge", "openai"):
        raise SystemExit("TTS_ENGINE must be 'edge' or 'openai'")
    if tts_engine == "openai" and provider != "openai":
        raise SystemExit("TTS_ENGINE=openai needs PROVIDER=openai")

    return Config(
        bot_token=token,
        provider=provider,
        ai_api_key=api_key,
        ai_base_url=os.getenv("OPENAI_BASE_URL") or base_url,
        telegram_api_url=os.getenv("TELEGRAM_API_URL") or None,
        telegram_api_local=os.getenv("TELEGRAM_API_LOCAL", "1") == "1",
        transcribe_model=_str("TRANSCRIBE_MODEL", transcribe_model),
        translate_model=_str("TRANSLATE_MODEL", translate_model),
        translate_reasoning_effort=_str("TRANSLATE_REASONING_EFFORT", effort),
        tts_engine=tts_engine,
        tts_model=_str("TTS_MODEL", "gpt-4o-mini-tts"),
        tts_voice=_str("TTS_VOICE", "onyx"),
        tts_gender="female" if _str("TTS_GENDER", "male").lower() == "female" else "male",
        allowed_user_ids=_ids("ALLOWED_USER_IDS"),
        max_video_minutes=_int("MAX_VIDEO_MINUTES", 180),
        max_concurrent_jobs=_int("MAX_CONCURRENT_JOBS", 2),
        original_volume=_float("ORIGINAL_VOLUME", 0.15),
        data_dir=Path(os.getenv("DATA_DIR", "data")).resolve(),
    )

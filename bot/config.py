import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    return int(value) if value else default


def _float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    return float(value) if value else default


def _ids(name: str) -> frozenset[int]:
    raw = os.getenv(name, "")
    return frozenset(int(x) for x in raw.replace(";", ",").split(",") if x.strip())


@dataclass(frozen=True)
class Config:
    bot_token: str
    openai_api_key: str
    openai_base_url: str | None

    # Local Telegram Bot API server (lifts the 20 MB download / 50 MB upload limits to 2 GB).
    telegram_api_url: str | None
    telegram_api_local: bool

    transcribe_model: str
    translate_model: str
    tts_model: str
    tts_voice: str

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
    def max_download_bytes(self) -> int:
        return (2000 if self.telegram_api_url else 20) * 1024 * 1024

    @property
    def max_upload_bytes(self) -> int:
        return (2000 if self.telegram_api_url else 50) * 1024 * 1024


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN is not set (see .env.example)")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set (see .env.example)")

    return Config(
        bot_token=token,
        openai_api_key=api_key,
        openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
        telegram_api_url=os.getenv("TELEGRAM_API_URL") or None,
        telegram_api_local=os.getenv("TELEGRAM_API_LOCAL", "1") == "1",
        transcribe_model=os.getenv("TRANSCRIBE_MODEL", "whisper-1"),
        translate_model=os.getenv("TRANSLATE_MODEL", "gpt-5.4"),
        tts_model=os.getenv("TTS_MODEL", "gpt-4o-mini-tts"),
        tts_voice=os.getenv("TTS_VOICE", "onyx"),
        allowed_user_ids=_ids("ALLOWED_USER_IDS"),
        max_video_minutes=_int("MAX_VIDEO_MINUTES", 180),
        max_concurrent_jobs=_int("MAX_CONCURRENT_JOBS", 2),
        original_volume=_float("ORIGINAL_VOLUME", 0.15),
        data_dir=Path(os.getenv("DATA_DIR", "data")).resolve(),
    )

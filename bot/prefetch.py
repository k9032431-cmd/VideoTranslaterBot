"""Download and check the local-mode models: `python -m bot.prefetch` (run by the installer)."""

import os
from pathlib import Path

from dotenv import load_dotenv

from .config import PROVIDER_DEFAULTS
from .pipeline.local import prefetch

load_dotenv()

_, whisper_default, nllb_default, _, _ = PROVIDER_DEFAULTS["local"]
prefetch(
    os.getenv("TRANSCRIBE_MODEL") or whisper_default,
    os.getenv("TRANSLATE_MODEL") or nllb_default,
    Path(os.getenv("DATA_DIR", "data")).resolve() / "models",
)

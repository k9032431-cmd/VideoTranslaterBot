"""Local mode: speech recognition (faster-whisper) and translation (NLLB-200) run on the server itself.

No accounts, keys or daily limits — only CPU time. Models are downloaded once into DATA_DIR/models
and stay loaded in memory between jobs.
"""

import asyncio
import logging
import os
import subprocess
import threading
from collections.abc import Awaitable, Callable
from pathlib import Path

from ..languages import Language
from .models import Segment
from .transcribe import _keep, _merge_duplicates

log = logging.getLogger(__name__)

TRANSLATE_BATCH = 16
_lock = threading.Lock()
_whisper_cache: dict[str, object] = {}
_nllb_cache: dict[str, tuple[object, object]] = {}


class UnsupportedLanguageError(Exception):
    pass


def _threads() -> int:
    return max(os.cpu_count() or 1, 1)


def _decode_audio(path: Path):
    """16 kHz mono float32 samples via ffmpeg (faster-whisper's own decoder breaks on newer PyAV)."""
    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


def load_whisper(name: str, models_dir: Path):
    from faster_whisper import WhisperModel

    with _lock:
        if name not in _whisper_cache:
            log.info("Loading Whisper model %s", name)
            _whisper_cache[name] = WhisperModel(
                name, device="cpu", compute_type="int8", cpu_threads=_threads(),
                download_root=str(models_dir / "whisper"),
            )
        return _whisper_cache[name]


def load_nllb(repo: str, models_dir: Path):
    import ctranslate2
    import tokenizers
    from huggingface_hub import snapshot_download

    with _lock:
        if repo not in _nllb_cache:
            log.info("Loading translation model %s", repo)
            path = snapshot_download(
                repo, cache_dir=str(models_dir / "nllb"),
                allow_patterns=["model.bin", "config.json", "shared_vocabulary.*", "tokenizer.json"],
            )
            translator = ctranslate2.Translator(path, device="cpu", compute_type="int8", intra_threads=_threads())
            tokenizer = tokenizers.Tokenizer.from_file(os.path.join(path, "tokenizer.json"))
            _nllb_cache[repo] = (translator, tokenizer)
        return _nllb_cache[repo]


async def _run_in_thread(
    work: Callable[[threading.Event, Callable[[float], None]], object],
    on_progress: Callable[[float], Awaitable[None]],
):
    """Run blocking `work` in a thread, forwarding progress; stop it if the job is cancelled."""
    loop = asyncio.get_running_loop()
    stop = threading.Event()

    def report(value: float) -> None:
        asyncio.run_coroutine_threadsafe(on_progress(value), loop)

    try:
        return await asyncio.to_thread(work, stop, report)
    except asyncio.CancelledError:
        stop.set()
        raise


class _Stopped(Exception):
    pass


async def transcribe(
    audio: Path,
    language: str | None,
    model_name: str,
    models_dir: Path,
    on_progress: Callable[[float], Awaitable[None]],
) -> tuple[list[Segment], str | None]:
    def work(stop: threading.Event, report: Callable[[float], None]):
        model = load_whisper(model_name, models_dir)
        segments_iter, info = model.transcribe(
            _decode_audio(audio),
            language=language,
            beam_size=5,
            vad_filter=True,  # skip music/silence: faster, and no phantom phrases
            condition_on_previous_text=False,  # prevents repetition loops on long videos
        )
        result: list[Segment] = []
        for seg in segments_iter:
            if stop.is_set():
                raise _Stopped
            if _keep(seg) and seg.end > seg.start:
                result.append(Segment(float(seg.start), float(seg.end), seg.text.strip()))
            if info.duration:
                report(min(seg.end / info.duration, 1.0))
        return result, info.language

    segments, detected = await _run_in_thread(work, on_progress)
    return merge_sentences(_merge_duplicates(segments)), detected


SENTENCE_END = (".", "!", "?", "…", "。", "！", "？", "»", '"')
MAX_SENTENCE_SECONDS = 15.0
MAX_SENTENCE_CHARS = 250
MAX_PAUSE = 1.5


def merge_sentences(segments: list[Segment]) -> list[Segment]:
    """Join Whisper fragments into whole sentences.

    NLLB translates every piece on its own, without context, so a sentence cut in two
    is translated as two broken halves. Subtitles split long sentences back into cues.
    """
    merged: list[Segment] = []
    for seg in segments:
        last = merged[-1] if merged else None
        if (
            last is not None
            and not last.text.rstrip().endswith(SENTENCE_END)
            and seg.start - last.end <= MAX_PAUSE
            and seg.end - last.start <= MAX_SENTENCE_SECONDS
            and len(last.text) + len(seg.text) < MAX_SENTENCE_CHARS
        ):
            last.text = f"{last.text.rstrip()} {seg.text.lstrip()}"
            last.end = seg.end
        else:
            merged.append(Segment(seg.start, seg.end, seg.text))
    return merged


async def translate(
    segments: list[Segment],
    source: Language,
    target: Language,
    model_repo: str,
    models_dir: Path,
    on_progress: Callable[[float], Awaitable[None]],
) -> None:
    if not source.nllb or not target.nllb:
        raise UnsupportedLanguageError(source.code if not source.nllb else target.code)

    def work(stop: threading.Event, report: Callable[[float], None]) -> None:
        translator, tokenizer = load_nllb(model_repo, models_dir)
        for offset in range(0, len(segments), TRANSLATE_BATCH):
            if stop.is_set():
                raise _Stopped
            batch = segments[offset:offset + TRANSLATE_BATCH]
            sources = [
                [source.nllb] + tokenizer.encode(seg.text, add_special_tokens=False).tokens + ["</s>"]
                for seg in batch
            ]
            results = translator.translate_batch(
                sources,
                target_prefix=[[target.nllb]] * len(batch),
                beam_size=5,
                max_decoding_length=256,
                repetition_penalty=1.1,
                no_repeat_ngram_size=4,  # NLLB sometimes loops on a phrase
            )
            for seg, res in zip(batch, results):
                tokens = res.hypotheses[0][1:]  # drop the target language token
                ids = [tokenizer.token_to_id(tok) for tok in tokens]
                text = tokenizer.decode([i for i in ids if i is not None], skip_special_tokens=True).strip()
                seg.translation = text or seg.text
            report(min(offset + TRANSLATE_BATCH, len(segments)) / len(segments))

    await _run_in_thread(work, on_progress)


def prefetch(whisper_model: str, nllb_repo: str, models_dir: Path) -> None:
    """Download and load both models, and translate a test phrase (used by the installer)."""
    models_dir.mkdir(parents=True, exist_ok=True)
    print(f"Whisper ({whisper_model})…", flush=True)
    load_whisper(whisper_model, models_dir)
    print(f"NLLB ({nllb_repo})…", flush=True)
    translator, tokenizer = load_nllb(nllb_repo, models_dir)
    tokens = ["rus_Cyrl"] + tokenizer.encode("Привет, как дела?", add_special_tokens=False).tokens + ["</s>"]
    result = translator.translate_batch([tokens], target_prefix=[["eng_Latn"]])[0].hypotheses[0][1:]
    ids = [tokenizer.token_to_id(t) for t in result]
    print("Проверка перевода: «Привет, как дела?» →", tokenizer.decode(ids, skip_special_tokens=True), flush=True)

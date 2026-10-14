import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from openai import AsyncOpenAI

from . import media
from .models import Segment

log = logging.getLogger(__name__)

# Whisper "hears" phrases in silence/music. Segments it is unsure contain speech,
# or that are degenerate repetitions, are dropped.
NO_SPEECH_PROB = 0.6
LOW_LOGPROB = -1.0
MAX_COMPRESSION_RATIO = 2.4
PROMPT_CHARS = 200


def _keep(seg: object) -> bool:
    no_speech = getattr(seg, "no_speech_prob", 0.0) or 0.0
    logprob = getattr(seg, "avg_logprob", 0.0) or 0.0
    compression = getattr(seg, "compression_ratio", 1.0) or 1.0
    if no_speech > NO_SPEECH_PROB and logprob < LOW_LOGPROB:
        return False
    if compression > MAX_COMPRESSION_RATIO:
        return False
    return bool((getattr(seg, "text", "") or "").strip())


async def transcribe(
    client: AsyncOpenAI,
    model: str,
    audio: Path,
    work_dir: Path,
    language: str | None,
    on_progress: Callable[[float], Awaitable[None]],
) -> tuple[list[Segment], str | None]:
    """Speech-to-text with timestamps. Returns segments and the (detected) language."""
    total = await media.duration(audio)
    silences = await media.detect_silences(audio)
    chunks = media.plan_chunks(total, silences)

    segments: list[Segment] = []
    detected: str | None = language
    prompt = ""
    for index, (start, end) in enumerate(chunks):
        chunk_path = work_dir / f"chunk_{index:03d}.mp3"
        await media.cut_audio(audio, chunk_path, start, end)

        kwargs: dict = {
            "model": model,
            "response_format": "verbose_json",
            "timestamp_granularities": ["segment"],
            "temperature": 0,
        }
        if detected:
            kwargs["language"] = detected
        if prompt:
            # Previous text keeps names, spelling and punctuation style consistent across chunks.
            kwargs["prompt"] = prompt
        with chunk_path.open("rb") as fh:
            result = await client.audio.transcriptions.create(file=fh, **kwargs)
        chunk_path.unlink(missing_ok=True)

        if detected is None:
            detected = getattr(result, "language", None)
            log.info("Detected language: %s", detected)

        for seg in getattr(result, "segments", None) or []:
            if not _keep(seg):
                continue
            seg_start = start + float(seg.start)
            seg_end = min(start + float(seg.end), end)
            if seg_end <= seg_start:
                continue
            segments.append(Segment(seg_start, seg_end, seg.text.strip()))

        if segments:
            prompt = " ".join(s.text for s in segments[-10:])[-PROMPT_CHARS:]
        await on_progress((index + 1) / len(chunks))

    return _merge_duplicates(segments), detected


def _merge_duplicates(segments: list[Segment]) -> list[Segment]:
    """Drop back-to-back repeats (a typical Whisper loop artifact) and fix overlaps."""
    result: list[Segment] = []
    for seg in segments:
        if result and seg.text == result[-1].text and seg.start - result[-1].end < 1.0:
            result[-1].end = max(result[-1].end, seg.end)
            continue
        if result and seg.start < result[-1].end:
            seg.start = result[-1].end
            if seg.end <= seg.start:
                continue
        result.append(seg)
    return result

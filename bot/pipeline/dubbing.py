"""Voice-over: synthesize every translated line and place it on a timeline in sync with the video."""

import asyncio
import logging
import re
import wave
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import edge_tts
from openai import AsyncOpenAI

from ..languages import Language
from . import media
from .models import Segment

log = logging.getLogger(__name__)

TTS_CONCURRENCY = 4
TTS_ATTEMPTS = 3
# Faster than this sounds unnatural; past it we let the line run slightly late instead.
MAX_TEMPO = 1.35
TAIL_SECONDS = 1.0
BYTES_PER_SAMPLE = 2  # pcm_s16le mono


@dataclass
class Placement:
    silence_before: float
    tempo: float


def plan_timeline(starts: list[float], clip_lengths: list[float], ends: list[float]) -> list[Placement]:
    """Decide where each clip goes and how much to speed it up.

    A clip may use the time until the next line starts. If it is longer, it is sped up
    (up to MAX_TEMPO). If it still doesn't fit, it pushes the next one slightly — the
    gap before later lines absorbs the delay, so drift never accumulates for long.
    """
    placements: list[Placement] = []
    cursor = 0.0
    for i, (start, length) in enumerate(zip(starts, clip_lengths)):
        slot_end = starts[i + 1] if i + 1 < len(starts) else ends[i] + TAIL_SECONDS
        begin = max(start, cursor)
        available = max(slot_end - begin, 0.05)
        tempo = min(max(length / available, 1.0), MAX_TEMPO)
        placements.append(Placement(silence_before=begin - cursor, tempo=tempo))
        cursor = begin + length / tempo
    return placements


def _wav_frames(path: Path) -> bytes:
    with wave.open(str(path), "rb") as wav:
        return wav.readframes(wav.getnframes())


def _silence(seconds: float) -> bytes:
    return b"\x00" * (int(round(seconds * media.AUDIO_RATE)) * BYTES_PER_SAMPLE)


async def _openai_tts(client: AsyncOpenAI, model: str, voice: str, text: str, target: Language, out: Path) -> None:
    kwargs: dict = {"model": model, "voice": voice, "input": text, "response_format": "mp3"}
    if not model.startswith("tts-1"):
        kwargs["instructions"] = (
            f"Speak {target.english} naturally and clearly, like a professional film voice-over "
            "artist. Match a conversational pace; do not over-act."
        )
    response = await client.audio.speech.create(**kwargs)
    out.write_bytes(response.content)


# Turkmen letters a Turkish voice can't pronounce → their closest Turkish sounds.
_TURKMEN_TO_TURKISH = str.maketrans({"ä": "e", "Ä": "E", "ň": "n", "Ň": "N", "ý": "y", "Ý": "Y", "ž": "j", "Ž": "J"})


# Sound notes are for subtitles, not for the narrator: "(музыка)", "[смех]", "♪ la la ♪".
_SOUND_NOTES = re.compile(r"\([^)]*\)|\[[^\]]*\]|\*[^*]*\*|♪[^♪]*♪|[♪♫]")


def speakable(text: str, lang: Language) -> str:
    """What the narrator should say; "" when there is nothing to say."""
    text = " ".join(_SOUND_NOTES.sub(" ", text).split())
    if not any(ch.isalnum() for ch in text):
        return ""
    return text.translate(_TURKMEN_TO_TURKISH) if lang.code == "tk" else text


def _retryable(exc: Exception) -> bool:
    from openai import APIConnectionError, APITimeoutError, InternalServerError

    return isinstance(exc, (APIConnectionError, APITimeoutError, InternalServerError))


async def _edge_tts(voice: str, text: str, out: Path) -> None:
    await edge_tts.Communicate(text, voice).save(str(out))
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError("Edge TTS returned no audio")


async def synthesize(
    client: AsyncOpenAI,
    engine: str,  # edge | openai
    model: str,
    segment_voices: list[str],  # voice for each segment (Edge or OpenAI voice name)
    segments: list[Segment],
    target: Language,
    work_dir: Path,
    total_duration: float,
    on_progress: Callable[[float], Awaitable[None]],
) -> Path:
    """Return a WAV track as long as the video with the voice-over in place."""
    tts_dir = work_dir / "tts"
    tts_dir.mkdir(exist_ok=True)
    semaphore = asyncio.Semaphore(TTS_CONCURRENCY)
    done = 0
    lock = asyncio.Lock()

    failed = 0

    async def one(index: int, seg: Segment) -> Path | None:
        nonlocal done, failed
        raw = tts_dir / f"{index:05d}.mp3"
        voice = segment_voices[index]
        text = speakable(seg.translation, target)
        result: Path | None = None
        if text:
            async with semaphore:
                for attempt in range(1, TTS_ATTEMPTS + 1):
                    try:
                        if engine == "edge":
                            await _edge_tts(voice, text, raw)
                        else:
                            await _openai_tts(client, model, voice, text, target, raw)
                        result = raw
                        break
                    except Exception as exc:
                        if engine == "openai" and not _retryable(exc):
                            raise  # a bad key or an empty balance won't fix itself
                        if attempt == TTS_ATTEMPTS:
                            # One unvoiceable line must not sink a whole film: leave a pause there.
                            log.warning("Could not voice line %d %r: %s", index, text[:60], exc)
                            failed += 1
                        else:
                            await asyncio.sleep(2 * attempt)
        async with lock:
            done += 1
            await on_progress(done / len(segments) * 0.9)
        return result

    raw_clips = await asyncio.gather(*(one(i, s) for i, s in enumerate(segments)))
    if failed and failed == sum(1 for s in segments if speakable(s.translation, target)):
        raise RuntimeError("the voice service did not return audio for any line")

    lengths = [await media.duration(p) if p else 0.0 for p in raw_clips]
    plan = plan_timeline([s.start for s in segments], lengths, [s.end for s in segments])

    track_raw = work_dir / "dub.pcm"
    written = 0.0
    with track_raw.open("wb") as out:
        for index, (clip, place) in enumerate(zip(raw_clips, plan)):
            if clip is None:  # nothing was said here: the gap before the next line covers it
                continue
            wav = tts_dir / f"{index:05d}.wav"
            await media.to_wav(clip, wav, tempo=place.tempo)
            frames = _wav_frames(wav)
            out.write(_silence(place.silence_before))
            out.write(frames)
            written += place.silence_before + len(frames) / BYTES_PER_SAMPLE / media.AUDIO_RATE
            clip.unlink(missing_ok=True)
            wav.unlink(missing_ok=True)
        if written < total_duration:
            out.write(_silence(total_duration - written))

    track = work_dir / "dub.wav"
    await media.ffmpeg(
        "-f", "s16le", "-ar", str(media.AUDIO_RATE), "-ac", "1", "-i", track_raw,
        "-t", f"{total_duration:.3f}", "-c:a", "pcm_s16le", track,
    )
    track_raw.unlink(missing_ok=True)
    await on_progress(1.0)
    return track

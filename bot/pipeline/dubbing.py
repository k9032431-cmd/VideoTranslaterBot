"""Voice-over: synthesize every translated line and place it on a timeline in sync with the video."""

import asyncio
import wave
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import edge_tts
from openai import AsyncOpenAI

from ..languages import Language
from . import media
from .models import Segment

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


def speakable(text: str, lang: Language) -> str:
    return text.translate(_TURKMEN_TO_TURKISH) if lang.code == "tk" else text


async def _edge_tts(voice: str, text: str, out: Path) -> None:
    await edge_tts.Communicate(text, voice).save(str(out))
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError("Edge TTS returned no audio")


async def synthesize(
    client: AsyncOpenAI,
    engine: str,  # edge | openai
    model: str,
    voice: str,  # OpenAI voice
    gender: str,  # male | female, for Edge voices
    segments: list[Segment],
    target: Language,
    work_dir: Path,
    total_duration: float,
    on_progress: Callable[[float], Awaitable[None]],
) -> Path:
    """Return a WAV track as long as the video with the voice-over in place."""
    tts_dir = work_dir / "tts"
    tts_dir.mkdir(exist_ok=True)
    edge_voice = target.edge_female if gender == "female" else target.edge_male
    semaphore = asyncio.Semaphore(TTS_CONCURRENCY)
    done = 0
    lock = asyncio.Lock()

    async def one(index: int, seg: Segment) -> Path:
        nonlocal done
        raw = tts_dir / f"{index:05d}.mp3"
        async with semaphore:
            for attempt in range(1, TTS_ATTEMPTS + 1):
                try:
                    if engine == "edge":
                        await _edge_tts(edge_voice, speakable(seg.translation, target), raw)
                    else:
                        await _openai_tts(client, model, voice, seg.translation, target, raw)
                    break
                except Exception:
                    # The OpenAI client retries on its own; Edge occasionally drops a connection.
                    if engine != "edge" or attempt == TTS_ATTEMPTS:
                        raise
                    await asyncio.sleep(2 * attempt)
        async with lock:
            done += 1
            await on_progress(done / len(segments) * 0.9)
        return raw

    raw_clips = await asyncio.gather(*(one(i, s) for i, s in enumerate(segments)))

    lengths = [await media.duration(p) for p in raw_clips]
    plan = plan_timeline([s.start for s in segments], lengths, [s.end for s in segments])

    track_raw = work_dir / "dub.pcm"
    written = 0.0
    with track_raw.open("wb") as out:
        for index, (clip, place) in enumerate(zip(raw_clips, plan)):
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

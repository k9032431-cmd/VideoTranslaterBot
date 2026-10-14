"""Runs the full translation of one video: audio → text → translation → subtitles / voice-over → video."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from openai import AsyncOpenAI

from .. import languages
from ..config import Config
from ..languages import Language
from . import dubbing, media, render, subtitles, transcribe, translate

log = logging.getLogger(__name__)

# stage key (an i18n key) and progress 0..1 (or None when unknown)
Reporter = Callable[[str, float | None], Awaitable[None]]


class NoSpeechError(Exception):
    pass


class SameLanguageError(Exception):
    pass


@dataclass
class JobParams:
    video: Path
    work_dir: Path
    source: str  # language code or "auto"
    target: str
    mode: str  # subtitles | voice | both


@dataclass
class JobResult:
    source: Language
    srt: Path
    video: Path | None
    audio: Path | None  # voice-over track, provided when the video is too large to send


def _language(code: str | None) -> Language:
    lang = languages.from_whisper(code)
    if lang:
        return lang
    name = (code or "the original language").strip()
    return Language(code=name, flag="🏳️", native=name.capitalize(), english=name.capitalize())


async def run_job(client: AsyncOpenAI, config: Config, params: JobParams, report: Reporter) -> JobResult:
    work = params.work_dir
    target = languages.get(params.target)
    voice = params.mode in ("voice", "both")
    burn_subs = params.mode in ("subtitles", "both")

    await report("stage_audio", None)
    if not await media.has_audio(params.video):
        raise NoSpeechError
    total = await media.duration(params.video)
    speech = work / "speech.mp3"
    await media.extract_speech_audio(params.video, speech)

    await report("stage_transcribe", 0.0)
    segments, detected = await transcribe.transcribe(
        client, config.transcribe_model, speech, work,
        language=None if params.source == "auto" else params.source,
        on_progress=lambda p: report("stage_transcribe", p),
    )
    speech.unlink(missing_ok=True)
    if not segments:
        raise NoSpeechError
    source = _language(detected) if params.source == "auto" else languages.get(params.source)
    if source.code == target.code:
        raise SameLanguageError
    log.info("Transcribed %d segments (%s)", len(segments), source.code)

    await report("stage_translate", 0.0)
    await translate.translate(
        client, config.translate_model, segments, source, target, for_voice=voice,
        reasoning_effort=config.translate_reasoning_effort,
        on_progress=lambda p: report("stage_translate", p),
    )

    srt = work / f"subtitles_{target.code}.srt"
    srt.write_text(subtitles.to_srt(subtitles.build_cues(segments, target.code)), encoding="utf-8")

    dub_track: Path | None = None
    if voice:
        await report("stage_tts", 0.0)
        dub_track = await dubbing.synthesize(
            client, config.tts_engine, config.tts_model, config.tts_voice, config.tts_gender,
            segments, target, work, total,
            on_progress=lambda p: report("stage_tts", p),
        )

    output: Path | None = None
    if await media.has_video(params.video):
        await report("stage_render", 0.0)
        output = work / f"translated_{target.code}.mp4"
        await render.render(
            params.video, output, work, total,
            on_progress=lambda p: report("stage_render", p),
            srt=srt if burn_subs else None,
            dub=dub_track,
            original_volume=config.original_volume,
        )

    audio: Path | None = None
    if dub_track and (output is None or output.stat().st_size > config.max_upload_bytes):
        audio = work / f"voiceover_{target.code}.m4a"
        await render.export_audio(dub_track, audio)

    return JobResult(source=source, srt=srt, video=output, audio=audio)

"""Runs translations in the background, one per user, with a live status message."""

import asyncio
import html
import logging
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile
from openai import APIError, AsyncOpenAI, AuthenticationError, RateLimitError

from . import keyboards, languages
from .config import Config
from .i18n import t
from .pipeline import media
from .pipeline.job import JobParams, NoSpeechError, SameLanguageError, run_job
from .pipeline.local import UnsupportedLanguageError

log = logging.getLogger(__name__)

STATUS_EDIT_INTERVAL = 3.0
UPLOAD_TIMEOUT = 3600


class TooLongError(Exception):
    def __init__(self, minutes: int) -> None:
        self.minutes = minutes


@dataclass
class JobRequest:
    user_id: int
    chat_id: int
    status_message_id: int
    lang: str
    file_id: str
    file_name: str
    source: str
    target: str
    mode: str


class StatusMessage:
    def __init__(self, bot: Bot, chat_id: int, message_id: int, lang: str, header: str) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self.lang = lang
        self.header = header
        self._last_text = ""
        self._last_stage = ""
        self._last_edit = 0.0

    async def stage(self, key: str, progress: float | None = None) -> None:
        now = time.monotonic()
        if key == self._last_stage and now - self._last_edit < STATUS_EDIT_INTERVAL and progress != 1.0:
            return
        text = self.header + t(self.lang, key, progress=f"{int((progress or 0) * 100)}%" if progress is not None else "")
        self._last_stage, self._last_edit = key, now
        await self._edit(text.rstrip(), keyboards.abort_job(self.lang))

    async def final(self, text: str) -> None:
        await self._edit(text, None)

    async def _edit(self, text: str, markup) -> None:
        if text == self._last_text and markup is not None:
            return
        self._last_text = text
        try:
            await self.bot.edit_message_text(
                text=text, chat_id=self.chat_id, message_id=self.message_id, reply_markup=markup
            )
        except TelegramBadRequest as exc:
            if "not modified" not in str(exc):
                log.warning("Status update failed: %s", exc)


class JobManager:
    def __init__(self, bot: Bot, config: Config, client: AsyncOpenAI | None) -> None:
        self.bot = bot
        self.config = config
        self.client = client
        self.semaphore = asyncio.Semaphore(config.max_concurrent_jobs)
        self.running: dict[int, asyncio.Task] = {}

    def is_busy(self, user_id: int) -> bool:
        task = self.running.get(user_id)
        return task is not None and not task.done()

    def start(self, request: JobRequest) -> None:
        task = asyncio.create_task(self._run(request))
        self.running[request.user_id] = task
        task.add_done_callback(lambda _: self.running.pop(request.user_id, None))

    def cancel(self, user_id: int) -> bool:
        task = self.running.get(user_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def _run(self, req: JobRequest) -> None:
        lang = req.lang
        target = languages.get(req.target)
        source_label = t(lang, "auto_detect") if req.source == keyboards.AUTO else languages.get(req.source).label
        status = StatusMessage(
            self.bot, req.chat_id, req.status_message_id, lang,
            t(lang, "processing_header", source=source_label, target=target.label),
        )
        work_dir = self.config.work_dir / f"{req.user_id}_{uuid.uuid4().hex[:8]}"
        try:
            if self.semaphore.locked():
                await status.stage("queued")
            async with self.semaphore:
                work_dir.mkdir(parents=True, exist_ok=True)
                await self._process(req, status, work_dir)
        except asyncio.CancelledError:
            await status.final(t(lang, "cancelled"))
        except NoSpeechError:
            await status.final(t(lang, "no_speech"))
        except SameLanguageError:
            await status.final(t(lang, "same_language", target=target.label))
        except RateLimitError:
            log.warning("API limit reached for user %s", req.user_id)
            await status.final(t(lang, "rate_limited"))
        except AuthenticationError:
            log.error("API key was rejected")
            await status.final(t(lang, "error", error=t(lang, "bad_api_key")))
        except UnsupportedLanguageError:
            await status.final(t(lang, "unsupported_language"))
        except TooLongError as exc:
            await status.final(t(lang, "too_long", minutes=exc.minutes, max_min=self.config.max_video_minutes))
        except Exception as exc:
            log.exception("Job failed for user %s", req.user_id)
            await status.final(t(lang, "error", error=html.escape(_describe(exc, lang))))
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    async def _process(self, req: JobRequest, status: StatusMessage, work_dir: Path) -> None:
        lang = req.lang
        target = languages.get(req.target)

        await status.stage("stage_download")
        suffix = Path(req.file_name).suffix or ".mp4"
        video = work_dir / f"input{suffix}"
        file = await self.bot.get_file(req.file_id)
        await self.bot.download_file(file.file_path, video, timeout=UPLOAD_TIMEOUT)

        minutes = int(await media.duration(video) // 60)
        if minutes >= self.config.max_video_minutes:
            raise TooLongError(minutes)

        result = await run_job(
            self.client, self.config,
            JobParams(video=video, work_dir=work_dir, source=req.source, target=req.target, mode=req.mode),
            status.stage,
        )

        await status.stage("stage_upload")
        limit = self.config.max_upload_bytes
        caption = t(lang, "done", source=result.source.label, target=target.label)
        sent_video = False
        if result.video:
            size = result.video.stat().st_size
            if size <= limit:
                info = await media.probe(result.video)
                vstream = next((s for s in info["streams"] if s.get("codec_type") == "video"), {})
                await self.bot.send_video(
                    req.chat_id,
                    FSInputFile(result.video, filename=f"{Path(req.file_name).stem}_{target.code}.mp4"),
                    caption=caption,
                    duration=int(float(info["format"].get("duration", 0))),
                    width=vstream.get("width"),
                    height=vstream.get("height"),
                    supports_streaming=True,
                    request_timeout=UPLOAD_TIMEOUT,
                )
                sent_video = True
            else:
                await self.bot.send_message(
                    req.chat_id,
                    t(lang, "result_too_big", size_mb=size // (1024 * 1024), max_mb=limit // (1024 * 1024)),
                )
        if result.audio and result.audio.stat().st_size <= limit:
            await self.bot.send_audio(
                req.chat_id,
                FSInputFile(result.audio, filename=f"{Path(req.file_name).stem}_{target.code}.m4a"),
                caption=t(lang, "audio_caption", target=target.label),
                request_timeout=UPLOAD_TIMEOUT,
            )
        await self.bot.send_document(
            req.chat_id,
            FSInputFile(result.srt, filename=f"{Path(req.file_name).stem}_{target.code}.srt"),
            caption=t(lang, "srt_caption", target=target.label) if sent_video else caption,
        )
        await status.final(caption)


def _describe(exc: Exception, lang: str) -> str:
    if isinstance(exc, APIError):
        return f"OpenAI: {exc.message}"[:300]
    if isinstance(exc, media.MediaError):
        return "ffmpeg"
    return t(lang, "error_generic")

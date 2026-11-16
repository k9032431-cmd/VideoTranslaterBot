"""Videos by link: YouTube and the ~1800 other sites yt-dlp supports, or a direct file URL."""

import asyncio
import logging
import re
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
PROBE_TIMEOUT = 60
# Translation doesn't need more; higher resolutions only make burning subtitles slower.
MAX_HEIGHT = 720
FORMAT = (
    f"bv*[height<={MAX_HEIGHT}][ext=mp4]+ba[ext=m4a]/bv*[height<={MAX_HEIGHT}]+ba"
    f"/b[height<={MAX_HEIGHT}]/bv*+ba/b"
)


class SourceError(Exception):
    """`key` is an i18n key explaining the problem to the user."""

    def __init__(self, key: str, detail: str = "") -> None:
        super().__init__(detail or key)
        self.key = key


@dataclass
class SourceInfo:
    url: str
    title: str
    duration: int | None
    site: str


def find_url(text: str | None) -> str | None:
    match = URL_RE.search(text or "")
    return match.group(0).rstrip(".,;:!?)»") if match else None


def _options(cookies: Path | None) -> dict:
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 5,
        "fragment_retries": 5,
    }
    if cookies and cookies.exists():
        opts["cookiefile"] = str(cookies)
    return opts


def _classify(error: Exception) -> SourceError:
    text = str(error)
    lowered = text.lower()
    # Age checks also say "Sign in to confirm…", so they go before the bot check.
    if "confirm your age" in lowered or "age-restricted" in lowered:
        return SourceError("link_private", text)
    if "sign in to confirm" in lowered or "login_required" in lowered or "not a bot" in lowered:
        return SourceError("link_bot_check", text)
    if "unsupported url" in lowered:
        return SourceError("link_unsupported", text)
    if "private" in lowered or "members-only" in lowered:
        return SourceError("link_private", text)
    if "unavailable" in lowered or "404" in lowered or "not found" in lowered:
        return SourceError("link_unavailable", text)
    return SourceError("link_failed", text)


async def probe(url: str, cookies: Path | None) -> SourceInfo:
    import yt_dlp

    def work() -> dict:
        with yt_dlp.YoutubeDL(_options(cookies)) as ydl:
            return ydl.extract_info(url, download=False, process=True)

    try:
        info = await asyncio.wait_for(asyncio.to_thread(work), PROBE_TIMEOUT)
    except asyncio.TimeoutError as exc:
        raise SourceError("link_failed", "timeout") from exc
    except Exception as exc:  # yt-dlp raises DownloadError / ExtractorError with the reason in the text
        raise _classify(exc) from exc
    if info.get("_type") == "playlist":
        raise SourceError("link_playlist")
    if info.get("is_live"):
        raise SourceError("link_live")
    duration = info.get("duration")
    return SourceInfo(
        url=info.get("webpage_url") or url,
        title=(info.get("title") or "video").strip()[:120],
        duration=int(duration) if duration else None,
        site=info.get("extractor_key") or info.get("extractor") or "",
    )


async def download(
    url: str,
    work_dir: Path,
    cookies: Path | None,
    max_bytes: int,
    on_progress: Callable[[float], Awaitable[None]],
) -> Path:
    """Download into work_dir/source.<ext>; return the file."""
    import yt_dlp

    loop = asyncio.get_running_loop()
    stop = threading.Event()

    def hook(status: dict) -> None:
        if stop.is_set():
            raise yt_dlp.utils.DownloadCancelled("cancelled")
        if status.get("status") == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            if total:
                asyncio.run_coroutine_threadsafe(on_progress(min(status["downloaded_bytes"] / total, 1.0)), loop)

    def work() -> Path:
        opts = _options(cookies) | {
            "format": FORMAT,
            "merge_output_format": "mp4",
            "outtmpl": str(work_dir / "source.%(ext)s"),
            "max_filesize": max_bytes,
            "progress_hooks": [hook],
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        files = [p for p in work_dir.glob("source.*") if not p.name.endswith((".part", ".ytdl"))]
        if not files:
            raise SourceError("link_too_big")  # max_filesize makes yt-dlp skip silently
        return max(files, key=lambda p: p.stat().st_size)

    try:
        return await asyncio.to_thread(work)
    except asyncio.CancelledError:
        stop.set()
        raise
    except SourceError:
        raise
    except Exception as exc:
        raise _classify(exc) from exc


def looks_like_cookies(text: str) -> bool:
    """A Netscape cookies.txt with YouTube/Google cookies (what browser extensions export)."""
    lines = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    return any(
        line.count("\t") >= 6 and ("youtube.com" in line or "google.com" in line) for line in lines
    )

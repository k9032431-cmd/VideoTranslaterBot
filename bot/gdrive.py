"""Google Drive links: a video shared as "Anyone with the link" is downloaded directly.

Big files are common here (films), so the download resumes after a dropped connection.
"""

import asyncio
import logging
import re
import urllib.parse
from collections.abc import Awaitable, Callable
from pathlib import Path

import aiohttp

log = logging.getLogger(__name__)

DOWNLOAD_URL = "https://drive.usercontent.google.com/download?id={id}&export=download&confirm=t"
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".wmv", ".ts", ".mts", ".3gp",
                    ".mpg", ".mpeg", ".vob"}
ATTEMPTS = 6
CHUNK = 1024 * 1024

_ID_PATTERNS = (
    re.compile(r"(?:drive|docs)\.google\.com/(?:a/[^/]+/)?file/d/([A-Za-z0-9_-]{10,})"),
    re.compile(r"(?:drive|docs|drive\.usercontent)\.google\.com/.*[?&]id=([A-Za-z0-9_-]{10,})"),
)
_FOLDER_RE = re.compile(r"drive\.google\.com/(?:drive/(?:u/\d+/)?folders|folderview)")


def is_drive(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return host.endswith(("drive.google.com", "docs.google.com", "drive.usercontent.google.com"))


def is_folder(url: str) -> bool:
    return bool(_FOLDER_RE.search(url))


def file_id(url: str) -> str | None:
    for pattern in _ID_PATTERNS:
        if match := pattern.search(url):
            return match.group(1)
    return None


def _filename(disposition: str) -> str | None:
    if match := re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.IGNORECASE):
        return urllib.parse.unquote(match.group(1)).strip('"')
    if match := re.search(r'filename="([^"]+)"', disposition, re.IGNORECASE):
        return match.group(1)
    return None


def _session() -> aiohttp.ClientSession:
    # trust_env: honour HTTPS_PROXY if the server needs one
    return aiohttp.ClientSession(trust_env=True, timeout=aiohttp.ClientTimeout(total=None, sock_read=120))


async def probe(fid: str) -> tuple[str, int]:
    """Name and size of a shared file. Raises ValueError("private" | "not_video")."""
    async with _session() as http:
        async with http.get(DOWNLOAD_URL.format(id=fid), headers={"Range": "bytes=0-0"}) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if resp.status not in (200, 206) or ctype.startswith("text/html"):
                # Google answers with a sign-in or "quota exceeded" page instead of the file.
                raise ValueError("private")
            name = _filename(resp.headers.get("Content-Disposition", "")) or "video.mp4"
            total = resp.headers.get("Content-Range", "").rpartition("/")[2]
            size = int(total) if total.isdigit() else int(resp.headers.get("Content-Length") or 0)
    if not ctype.startswith("video/") and Path(name).suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError("not_video")
    return name, size


async def download(
    fid: str,
    dest: Path,
    size: int,
    on_progress: Callable[[float], Awaitable[None]],
) -> Path:
    """Download to `dest`, resuming where a dropped connection stopped."""
    url = DOWNLOAD_URL.format(id=fid)
    done = dest.stat().st_size if dest.exists() else 0
    async with _session() as http:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                headers = {"Range": f"bytes={done}-"} if done else {}
                async with http.get(url, headers=headers) as resp:
                    if resp.headers.get("Content-Type", "").startswith("text/html"):
                        raise ValueError("private")
                    if done and resp.status != 206:  # server ignored the range: start over
                        done = 0
                    with dest.open("ab" if done else "wb") as out:
                        async for chunk in resp.content.iter_chunked(CHUNK):
                            out.write(chunk)
                            done += len(chunk)
                            if size:
                                await on_progress(min(done / size, 1.0))
                if not size or done >= size:
                    return dest
                raise aiohttp.ClientPayloadError(f"stopped at {done} of {size} bytes")
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt == ATTEMPTS:
                    raise
                log.warning("Drive download interrupted (%s), resuming from %d bytes", exc, done)
                await asyncio.sleep(2 * attempt)
    return dest

"""Download links for results too big for Telegram.

Files live in DATA_DIR/downloads/<random token>/<name> and are served by a small web server inside
the bot. A token is unguessable (128 bits), so a link works only for whoever received it. Everything
older than LINK_TTL_HOURS is deleted automatically.
"""

import asyncio
import logging
import re
import secrets
import shutil
import time
import urllib.parse
from pathlib import Path

from aiohttp import web

log = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
CLEANUP_INTERVAL = 10 * 60


def safe_filename(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", name).strip(" .")
    return name[:150] or "video.mp4"


class FileServer:
    def __init__(self, root: Path, public_url: str, port: int, ttl_hours: float) -> None:
        self.root = root
        self.public_url = public_url.rstrip("/")
        self.port = port
        self.ttl = ttl_hours * 3600
        self._runner: web.AppRunner | None = None
        self._cleanup_task: asyncio.Task | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.public_url)

    async def start(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.cleanup()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        if not self.enabled:
            return
        app = web.Application()
        app.router.add_get("/d/{token}/{name}", self._serve)
        app.router.add_get("/", self._index)
        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        await web.TCPSite(self._runner, "0.0.0.0", self.port).start()
        log.info("Download links: %s (port %d)", self.public_url, self.port)

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._runner:
            await self._runner.cleanup()

    def publish(self, source: Path, filename: str) -> str:
        """Move `source` under a fresh token and return its public link."""
        token = secrets.token_urlsafe(16)
        name = safe_filename(filename)
        folder = self.root / token
        folder.mkdir(parents=True)
        shutil.move(str(source), folder / name)
        return f"{self.public_url}/d/{token}/{urllib.parse.quote(name)}"

    def cleanup(self) -> int:
        """Delete links older than the TTL. Returns how many were removed."""
        if not self.root.exists():
            return 0
        removed = 0
        deadline = time.time() - self.ttl
        for folder in self.root.iterdir():
            try:
                if folder.stat().st_mtime < deadline:
                    shutil.rmtree(folder) if folder.is_dir() else folder.unlink()
                    removed += 1
            except OSError:
                log.warning("Could not delete %s", folder, exc_info=True)
        if removed:
            log.info("Deleted %d expired download(s)", removed)
        return removed

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL)
            try:
                self.cleanup()
            except Exception:
                log.exception("Cleanup failed")

    async def _serve(self, request: web.Request) -> web.StreamResponse:
        token = request.match_info["token"]
        name = request.match_info["name"]
        if not TOKEN_RE.match(token) or "/" in name or name in (".", ".."):
            raise web.HTTPNotFound()
        path = (self.root / token / name).resolve()
        if path.parent != (self.root / token).resolve() or not path.is_file():
            raise web.HTTPNotFound(text="Ссылка устарела или не существует / Link expired or not found")
        if (self.root / token).stat().st_mtime < time.time() - self.ttl:
            raise web.HTTPNotFound(text="Ссылка устарела / Link expired")
        quoted = urllib.parse.quote(name)
        return web.FileResponse(path, headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex",
        })

    async def _index(self, request: web.Request) -> web.Response:
        return web.Response(text="VideoTranslaterBot")

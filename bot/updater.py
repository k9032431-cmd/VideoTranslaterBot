"""Updating the bot from Telegram.

The bot itself runs without root rights, so it only drops a request file into DATA_DIR.
A systemd path unit (installed by install.sh) notices it and runs `vtbot self-update` as root,
which writes the outcome to `update.result`. The bot may be restarted by the update, so the
chat to report to is kept in `update.pending` and picked up again after the restart.
"""

import asyncio
import html
import logging
import time
from pathlib import Path

from aiogram import Bot

from .i18n import t

log = logging.getLogger(__name__)

TRIGGER_TIMEOUT = 30  # seconds for the systemd path unit to pick the request up
RESULT_TIMEOUT = 30 * 60
POLL_INTERVAL = 3


class Updater:
    def __init__(self, bot: Bot, data_dir: Path) -> None:
        self.bot = bot
        self.request = data_dir / "update.request"
        self.pending = data_dir / "update.pending"
        self.result = data_dir / "update.result"
        self.log = data_dir / "update.log"
        self.version_file = data_dir / "version.txt"
        self._task: asyncio.Task | None = None

    def version(self) -> str:
        try:
            return self.version_file.read_text(encoding="utf-8").strip() or "?"
        except OSError:
            return "?"

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, chat_id: int, lang: str) -> None:
        self.result.unlink(missing_ok=True)
        self.pending.write_text(f"{chat_id}\n{lang}\n", encoding="utf-8")
        self.request.write_text(f"{chat_id}\n", encoding="utf-8")
        self._task = asyncio.create_task(self._wait(chat_id, lang, check_trigger=True))

    def resume(self) -> None:
        """After a restart: finish reporting an update that was requested before it."""
        try:
            chat_id, lang = self.pending.read_text(encoding="utf-8").split()[:2]
        except (OSError, ValueError):
            return
        self._task = asyncio.create_task(self._wait(int(chat_id), lang, check_trigger=False))

    async def _wait(self, chat_id: int, lang: str, check_trigger: bool) -> None:
        started = time.monotonic()
        try:
            while time.monotonic() - started < RESULT_TIMEOUT:
                if self.result.exists():
                    await self.bot.send_message(chat_id, self._result_text(lang))
                    return
                if check_trigger and self.request.exists() and time.monotonic() - started > TRIGGER_TIMEOUT:
                    # Nobody picked the request up: the installation predates the update button.
                    self.request.unlink(missing_ok=True)
                    await self.bot.send_message(chat_id, t(lang, "update_unavailable"))
                    return
                await asyncio.sleep(POLL_INTERVAL)
            await self.bot.send_message(chat_id, t(lang, "update_timeout"))
        except Exception:
            log.exception("Update status report failed")
        finally:
            self.pending.unlink(missing_ok=True)
            self.result.unlink(missing_ok=True)

    def _result_text(self, lang: str) -> str:
        fields = {}
        for line in self.result.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            fields[key.strip()] = value.strip()
        status = fields.get("status")
        version = html.escape(fields.get("version") or self.version())
        if status == "updated":
            return t(lang, "update_done", version=version)
        if status == "latest":
            return t(lang, "update_latest", version=version)
        try:
            tail = "\n".join(self.log.read_text(encoding="utf-8", errors="replace").splitlines()[-12:])
        except OSError:
            tail = ""
        return t(lang, "update_failed", log=html.escape(tail[-1500:]))

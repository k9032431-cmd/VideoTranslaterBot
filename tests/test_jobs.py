import asyncio
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from bot import jobs as jobs_module
from bot.i18n import t
from bot.jobs import JobManager, JobRequest

from .test_pipeline_e2e import FakeOpenAI, _config, _make_video

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not installed")


class FakeBot:
    def __init__(self, source: Path) -> None:
        self.source = source
        self.calls: list[tuple[str, dict]] = []

    async def get_file(self, file_id):
        return SimpleNamespace(file_path="videos/file_1.mp4")

    async def download_file(self, file_path, destination, timeout=30):
        shutil.copy(self.source, destination)

    def __getattr__(self, name):
        async def method(*args, **kwargs):
            if name in ("send_video", "send_document", "send_audio"):
                media = args[1]
                kwargs["size"] = Path(media.path).stat().st_size
                kwargs["filename"] = media.filename
            self.calls.append((name, kwargs))
        return method

    def edits(self) -> list[str]:
        return [kw["text"] for name, kw in self.calls if name == "edit_message_text"]


def _request(**overrides) -> JobRequest:
    data = dict(user_id=1, chat_id=1, status_message_id=5, lang="ru", file_id="F", file_name="My film.mkv",
                source="auto", target="en", mode="both")
    data.update(overrides)
    return JobRequest(**data)


async def test_job_sends_video_and_subtitles(tmp_path: Path):
    video = tmp_path / "in.mp4"
    _make_video(video)
    bot = FakeBot(video)
    config = _config(tmp_path)
    manager = JobManager(bot, config, FakeOpenAI(tmp_path))

    manager.start(_request())
    assert manager.is_busy(1)
    await manager.running[1]

    names = [name for name, _ in bot.calls]
    assert "send_video" in names and "send_document" in names
    sent_video = next(kw for name, kw in bot.calls if name == "send_video")
    assert sent_video["filename"] == "My film_en.mp4"
    assert sent_video["size"] > 0
    assert any("📝" in e for e in bot.edits())  # progress was shown
    assert bot.edits()[-1].startswith("✅")
    assert not manager.is_busy(1)
    assert list(config.work_dir.iterdir()) == []  # temp files cleaned up


async def test_job_can_be_cancelled(tmp_path: Path, monkeypatch):
    video = tmp_path / "in.mp4"
    _make_video(video)
    bot = FakeBot(video)
    started = asyncio.Event()

    async def slow_job(*args, **kwargs):
        started.set()
        await asyncio.sleep(60)

    monkeypatch.setattr(jobs_module, "run_job", slow_job)
    manager = JobManager(bot, _config(tmp_path), FakeOpenAI(tmp_path))
    manager.start(_request())
    await started.wait()
    assert manager.cancel(1)
    await asyncio.gather(manager.running.get(1) or asyncio.sleep(0), return_exceptions=True)
    await asyncio.sleep(0)
    assert bot.edits()[-1] == t("ru", "cancelled")
    assert not manager.is_busy(1)


async def test_job_reports_errors(tmp_path: Path, monkeypatch):
    video = tmp_path / "in.mp4"
    _make_video(video)
    bot = FakeBot(video)

    async def broken_job(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(jobs_module, "run_job", broken_job)
    manager = JobManager(bot, _config(tmp_path), FakeOpenAI(tmp_path))
    manager.start(_request())
    await manager.running[1]
    assert bot.edits()[-1] == t("ru", "error", error=t("ru", "error_generic"))

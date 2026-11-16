"""Videos by link (yt-dlp) and download links for big results (built-in web server)."""

import os
import shutil
import socket
import time



import aiohttp
import pytest
from aiohttp import web

from bot import jobs as jobs_module
from bot import sources
from bot.config import Config
from bot.i18n import t
from bot.jobs import JobManager, JobRequest
from bot.webserver import FileServer, safe_filename

from .test_jobs import FakeBot
from .test_pipeline_e2e import FakeOpenAI, _config, _make_video

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not installed")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── finding links ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,url", [
    ("https://www.youtube.com/watch?v=abc", "https://www.youtube.com/watch?v=abc"),
    ("смотри https://youtu.be/xyz123.", "https://youtu.be/xyz123"),
    ("(http://example.com/a.mp4)", "http://example.com/a.mp4"),
    ("просто текст", None),
    (None, None),
])
def test_find_url(text, url):
    assert sources.find_url(text) == url


@pytest.mark.parametrize("message,key", [
    ("Sign in to confirm you're not a bot", "link_bot_check"),
    ("ERROR: Unsupported URL: https://x", "link_unsupported"),
    ("Private video. Sign in", "link_private"),
    ("Sign in to confirm your age", "link_private"),
    ("Video unavailable", "link_unavailable"),
    ("Some page message", "link_failed"),  # "age" inside other words is not an age check
])
def test_errors_are_explained(message, key):
    assert sources._classify(Exception(message)).key == key


def test_cookies_file_check():
    good = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1999999999\tSID\tabc\n"
    assert sources.looks_like_cookies(good)
    assert not sources.looks_like_cookies("hello")
    assert not sources.looks_like_cookies(".example.com\tTRUE\t/\tTRUE\t1\tSID\tabc\n")


# ── yt-dlp against a real (local) web server ─────────────────────────────────────────────────

@pytest.fixture
async def video_site(tmp_path):
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    _make_video(site_dir / "clip.mp4")
    app = web.Application()
    app.router.add_static("/", site_dir)
    runner = web.AppRunner(app)
    await runner.setup()
    port = _free_port()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    yield f"http://127.0.0.1:{port}/clip.mp4"
    await runner.cleanup()


@needs_ffmpeg
async def test_probe_and_download_direct_link(tmp_path, video_site):
    info = await sources.probe(video_site, None)
    assert info.title == "clip"
    work = tmp_path / "work"
    work.mkdir()
    progress = []

    async def report(p):
        progress.append(p)

    path = await sources.download(video_site, work, None, 100 * 1024 * 1024, report)
    assert path.exists() and path.stat().st_size == (tmp_path / "site" / "clip.mp4").stat().st_size


@needs_ffmpeg
async def test_download_respects_size_limit(tmp_path, video_site):
    work = tmp_path / "work"
    work.mkdir()

    async def report(p):
        pass

    with pytest.raises(sources.SourceError) as err:
        await sources.download(video_site, work, None, 1000, report)
    assert err.value.key == "link_too_big"


async def test_unreachable_link_gives_friendly_error():
    with pytest.raises(sources.SourceError) as err:
        await sources.probe(f"http://127.0.0.1:{_free_port()}/nothing.mp4", None)
    assert err.value.key in ("link_failed", "link_unavailable")


# ── download links ───────────────────────────────────────────────────────────────────────────

@pytest.fixture
async def file_server(tmp_path):
    port = _free_port()
    server = FileServer(tmp_path / "downloads", f"http://127.0.0.1:{port}", port, ttl_hours=12)
    await server.start()
    yield server
    await server.stop()


async def test_published_file_can_be_downloaded(tmp_path, file_server):
    source = tmp_path / "result.mp4"
    source.write_bytes(b"0123456789" * 1000)
    url = file_server.publish(source, "Мой фильм_en.mp4")
    assert not source.exists()
    async with aiohttp.ClientSession(trust_env=False) as http:
        async with http.get(url) as resp:
            assert resp.status == 200
            assert await resp.read() == b"0123456789" * 1000
            assert "attachment" in resp.headers["Content-Disposition"]
        async with http.get(url, headers={"Range": "bytes=10-19"}) as resp:  # resumable downloads
            assert resp.status == 206 and await resp.read() == b"0123456789"
        base = url.rsplit("/", 2)[0]
        for bad in ("/AAAAAAAAAAAAAAAAAAAAAA/x.mp4", "/../../etc/passwd", "/short/x.mp4"):
            async with http.get(base + bad) as resp:
                assert resp.status == 404


async def test_links_expire_and_files_are_deleted(tmp_path, file_server):
    source = tmp_path / "result.mp4"
    source.write_bytes(b"data")
    url = file_server.publish(source, "a.mp4")
    folder = next((tmp_path / "downloads").iterdir())
    old = time.time() - 13 * 3600
    os.utime(folder, (old, old))
    async with aiohttp.ClientSession(trust_env=False) as http:
        async with http.get(url) as resp:
            assert resp.status == 404
    assert file_server.cleanup() == 1
    assert not folder.exists()


def test_safe_filename():
    assert safe_filename('a/b\\c:"d"?.mp4') == "a_b_c_d_.mp4"
    assert safe_filename("Фильм 2026.mp4") == "Фильм 2026.mp4"
    assert safe_filename("...") == "video.mp4"


# ── the whole job: link in, link out ─────────────────────────────────────────────────────────

@needs_ffmpeg
async def test_job_from_link_with_big_result(tmp_path, video_site, file_server, monkeypatch):
    monkeypatch.setattr(Config, "max_upload_bytes", property(lambda self: 1000))  # "too big for Telegram"
    bot = FakeBot(tmp_path / "unused.mp4")
    manager = JobManager(bot, _config(tmp_path), FakeOpenAI(tmp_path), file_server)
    manager.start(JobRequest(
        user_id=1, chat_id=1, status_message_id=5, lang="ru", file_id="", file_name="clip.mp4",
        source="auto", target="en", mode="subtitles", url=video_site,
    ))
    await manager.running[1]

    names = [name for name, _ in bot.calls]
    assert "send_video" not in names
    link_message = next(kw["text"] for name, kw in bot.calls if name == "send_message" and "⬇️" in kw["text"])
    url = link_message.split('href="')[1].split('"')[0]
    assert url.startswith(file_server.public_url + "/d/") and url.endswith("clip_en.mp4")
    async with aiohttp.ClientSession(trust_env=False) as http:
        async with http.get(url) as resp:
            assert resp.status == 200 and len(await resp.read()) > 1000
    assert "send_document" in names  # subtitles still come as a file
    assert bot.edits()[-1].startswith("✅")


@needs_ffmpeg
async def test_job_reports_link_problems(tmp_path, monkeypatch):
    async def blocked(*args, **kwargs):
        raise sources.SourceError("link_bot_check")

    monkeypatch.setattr(jobs_module.sources, "download", blocked)
    bot = FakeBot(tmp_path / "unused.mp4")
    manager = JobManager(bot, _config(tmp_path), FakeOpenAI(tmp_path))
    manager.start(JobRequest(
        user_id=1, chat_id=1, status_message_id=5, lang="ru", file_id="", file_name="x.mp4",
        source="auto", target="en", mode="subtitles", url="https://youtube.com/watch?v=x",
    ))
    await manager.running[1]
    assert bot.edits()[-1] == t("ru", "link_bot_check")



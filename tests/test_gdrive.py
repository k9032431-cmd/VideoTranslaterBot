"""Google Drive links, against a local stand-in for Google's download server."""

import socket

import pytest
from aiohttp import web

from bot import gdrive, sources


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.parametrize("url,fid", [
    ("https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv/view?usp=sharing", "1AbCdEfGhIjKlMnOpQrStUv"),
    ("https://drive.google.com/open?id=1AbCdEfGhIjKlMnOpQrStUv", "1AbCdEfGhIjKlMnOpQrStUv"),
    ("https://drive.google.com/uc?export=download&id=1AbCdEfGhIjKlMnOpQrStUv", "1AbCdEfGhIjKlMnOpQrStUv"),
    ("https://docs.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv/edit", "1AbCdEfGhIjKlMnOpQrStUv"),
    ("https://drive.google.com/a/company.com/file/d/1AbCdEfGhIjKlMnOpQrStUv/view", "1AbCdEfGhIjKlMnOpQrStUv"),
    ("https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOp", None),
])
def test_file_id(url, fid):
    assert gdrive.is_drive(url)
    assert gdrive.file_id(url) == fid


def test_other_sites_are_not_drive():
    assert not gdrive.is_drive("https://www.youtube.com/watch?v=x")
    assert not gdrive.is_drive("https://evil.example/drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv")
    assert gdrive.is_folder("https://drive.google.com/drive/u/0/folders/1abc")


VIDEO = bytes(range(256)) * 4096  # 1 MiB


@pytest.fixture
async def fake_drive(monkeypatch):
    state = {"requests": [], "drop_once": True}

    async def download(request: web.Request) -> web.StreamResponse:
        fid = request.query["id"]
        state["requests"].append(request.headers.get("Range"))
        if fid == "private":
            return web.Response(text="<html>Sign in</html>", content_type="text/html")
        start = 0
        if rng := request.headers.get("Range"):
            start, _, end = rng.removeprefix("bytes=").partition("-")
            start = int(start)
            if end == "0":
                return web.Response(body=VIDEO[:1], status=206, headers={
                    "Content-Type": "video/mp4", "Content-Range": f"bytes 0-0/{len(VIDEO)}",
                    "Content-Disposition": "attachment; filename*=UTF-8''%D0%A4%D0%B8%D0%BB%D1%8C%D0%BC.mp4",
                })
        resp = web.StreamResponse(status=206 if request.headers.get("Range") else 200, headers={
            "Content-Type": "video/mp4", "Content-Length": str(len(VIDEO) - start),
        })
        await resp.prepare(request)
        body = VIDEO[start:]
        if state["drop_once"] and not start:
            state["drop_once"] = False
            await resp.write(body[:300_000])
            request.transport.close()  # the connection breaks mid-download
            return resp
        await resp.write(body)
        return resp

    app = web.Application()
    app.router.add_get("/download", download)
    runner = web.AppRunner(app)
    await runner.setup()
    port = _free_port()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    monkeypatch.setattr(gdrive, "DOWNLOAD_URL", f"http://127.0.0.1:{port}/download?id={{id}}")
    monkeypatch.setattr(sources, "_media_duration", _no_duration)
    monkeypatch.setattr(gdrive.asyncio, "sleep", _instant)
    yield state
    await runner.cleanup()


async def _no_duration(url):
    return 600


async def _instant(_):
    pass


async def test_probe_shared_file(fake_drive):
    info = await sources.probe("https://drive.google.com/file/d/shared1234567/view", None, 10 * 1024 * 1024)
    assert (info.title, info.duration, info.site) == ("Фильм", 600, "GoogleDrive")


async def test_probe_private_file(fake_drive):
    with pytest.raises(sources.SourceError) as err:
        await sources.probe("https://drive.google.com/file/d/private/view", None)
    assert err.value.key == "link_drive_private"


async def test_probe_respects_size_limit(fake_drive):
    with pytest.raises(sources.SourceError) as err:
        await sources.probe("https://drive.google.com/file/d/shared1234567/view", None, 1000)
    assert err.value.key == "link_too_big"


async def test_download_resumes_after_dropped_connection(tmp_path, fake_drive):
    progress = []

    async def report(p):
        progress.append(p)

    path = await sources.download(
        "https://drive.google.com/file/d/shared1234567/view", tmp_path, None, 10 * 1024 * 1024, report,
    )
    assert path.name == "source.mp4"
    assert path.read_bytes() == VIDEO  # complete and in order despite the break
    resumed = [r for r in fake_drive["requests"] if r and r != "bytes=0-0"]
    assert resumed and int(resumed[0].removeprefix("bytes=").rstrip("-")) > 0  # continued, not restarted
    assert progress[-1] == 1.0


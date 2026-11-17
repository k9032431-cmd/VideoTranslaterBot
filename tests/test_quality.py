"""Choosing the output quality (360p…1080p or as the original)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from bot import keyboards, sources
from bot.pipeline import media, render

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not installed")


def _video(path: Path, size: str, rotate: int | None = None) -> Path:
    plain = path.with_name("plain_" + path.name) if rotate is not None else path
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size={size}:rate=25:duration=2",
                    "-f", "lavfi", "-i", "sine=duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-shortest", str(plain)], check=True, capture_output=True)
    if rotate is not None:  # how phones store vertical video: sideways pixels + a rotation flag
        subprocess.run(["ffmpeg", "-y", "-display_rotation:v:0", str(rotate), "-i", str(plain),
                        "-c", "copy", str(path)], check=True, capture_output=True)
    return path


async def _shown_size(path: Path) -> tuple[int, int]:
    info = await media.probe(path)
    stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    return render._display_size(stream)


async def _render(tmp_path: Path, source: Path, max_height: int | None, srt: Path | None = None) -> Path:
    out = tmp_path / f"out_{max_height}_{source.stem}.mp4"

    async def progress(_):
        pass

    await render.render(source, out, tmp_path, 2.0, progress, srt=srt, max_height=max_height)
    return out


async def test_landscape_is_downscaled(tmp_path):
    src = _video(tmp_path / "wide.mp4", "1920x1080")
    assert await _shown_size(await _render(tmp_path, src, 480)) == (854, 480)


async def test_vertical_video_keeps_orientation(tmp_path):
    src = _video(tmp_path / "tall.mp4", "1080x1920")
    assert await _shown_size(await _render(tmp_path, src, 720)) == (720, 1280)


async def test_rotated_phone_video(tmp_path):
    src = _video(tmp_path / "phone.mp4", "1920x1080", rotate=90)
    assert await _shown_size(src) == (1080, 1920)  # shown upright
    assert await _shown_size(await _render(tmp_path, src, 720)) == (720, 1280)


async def test_never_upscales_and_copies_untouched_picture(tmp_path):
    src = _video(tmp_path / "small.mp4", "640x360")
    out = await _render(tmp_path, src, 1080)
    assert await _shown_size(out) == (640, 360)
    # no subtitles and no scaling: the picture is copied bit for bit, not re-encoded
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "packet=size", "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout
    probe_out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "packet=size", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout
    assert probe == probe_out


async def test_original_quality_with_subtitles(tmp_path):
    src = _video(tmp_path / "hd.mp4", "1280x720")
    srt = tmp_path / "s.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,500\nПривет\n", encoding="utf-8")
    assert await _shown_size(await _render(tmp_path, src, None, srt)) == (1280, 720)


def test_link_download_prefers_chosen_quality():
    assert sources.format_options(480) == {"format": "bv*+ba/b", "format_sort": ["res:480", "ext:mp4:m4a"]}
    assert sources.format_options(None) == {"format": "bv*+ba/b", "format_sort": ["ext:mp4:m4a"]}


def test_quality_buttons():
    datas = [b.callback_data for row in keyboards.qualities("ru").inline_keyboard for b in row]
    for q in keyboards.QUALITIES:
        assert keyboards.QualityCb(quality=q).pack() in datas

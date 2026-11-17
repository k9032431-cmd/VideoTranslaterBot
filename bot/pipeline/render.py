from collections.abc import Awaitable, Callable
from pathlib import Path

from . import media

SUBTITLE_STYLE = (
    "FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
    "BorderStyle=1,Outline=1.5,Shadow=0.5,MarginV=18"
)
PASSTHROUGH_VIDEO_CODECS = {"h264", "hevc"}


def _display_size(stream: dict) -> tuple[int, int]:
    """Width and height as the video is shown (phone videos are often stored sideways + rotated)."""
    width, height = int(stream.get("width") or 0), int(stream.get("height") or 0)
    rotation = 0
    for side in stream.get("side_data_list", []):
        if "rotation" in side:
            rotation = int(side["rotation"])
    rotation = rotation or int(stream.get("tags", {}).get("rotate", 0) or 0)
    return (height, width) if abs(rotation) % 180 == 90 else (width, height)


def scale_filter(stream: dict, max_height: int | None) -> str | None:
    """Downscale so the short side is at most max_height ("720p" of a vertical video is 720×1280).
    Never upscales."""
    width, height = _display_size(stream)
    if not max_height or not width or min(width, height) <= max_height:
        return None
    return f"scale=-2:{max_height}" if width >= height else f"scale={max_height}:-2"


async def render(
    video: Path,
    output: Path,
    work_dir: Path,
    total_duration: float,
    on_progress: Callable[[float], Awaitable[None]],
    srt: Path | None = None,
    dub: Path | None = None,
    original_volume: float = 0.25,
    max_height: int | None = None,
) -> None:
    """Produce an mp4 with burned-in subtitles and/or the voice-over mixed in."""
    info = await media.probe(video)
    streams = info.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), {})
    v_codec = vstream.get("codec_name")
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    args: list[str | Path] = ["-i", video]
    if dub:
        args += ["-i", dub]

    filters = [scale_filter(vstream, max_height) or "scale=trunc(iw/2)*2:trunc(ih/2)*2"]
    if srt:
        # Run in work_dir and refer to the file by bare name: the subtitles filter's path escaping is fragile.
        filters.append(f"subtitles={srt.name}:force_style='{SUBTITLE_STYLE}'")
    if srt or scale_filter(vstream, max_height) or v_codec not in PASSTHROUGH_VIDEO_CODECS:
        args += ["-vf", ",".join(filters), "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p"]
    else:
        args += ["-c:v", "copy"]  # nothing to change in the picture: keep it bit for bit
    args += ["-map", "0:v:0"]

    if dub and has_audio:
        args += [
            "-filter_complex",
            f"[0:a:0]volume={original_volume}[orig];[orig][1:a:0]amix=inputs=2:duration=first:normalize=0[aout]",
            "-map", "[aout]", "-c:a", "aac", "-b:a", "192k",
        ]
    elif dub:
        args += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "192k"]
    elif has_audio:
        args += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k"]

    args += ["-t", f"{total_duration:.3f}", "-movflags", "+faststart", output]
    await media.ffmpeg_progress(args, total_duration, on_progress, cwd=work_dir)


async def export_audio(track: Path, output: Path) -> None:
    await media.ffmpeg("-i", track, "-c:a", "aac", "-b:a", "128k", output)

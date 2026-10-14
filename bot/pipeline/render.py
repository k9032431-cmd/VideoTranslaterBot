from collections.abc import Awaitable, Callable
from pathlib import Path

from . import media

SUBTITLE_STYLE = (
    "FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
    "BorderStyle=1,Outline=1.5,Shadow=0.5,MarginV=18"
)
PASSTHROUGH_VIDEO_CODECS = {"h264", "hevc"}


async def render(
    video: Path,
    output: Path,
    work_dir: Path,
    total_duration: float,
    on_progress: Callable[[float], Awaitable[None]],
    srt: Path | None = None,
    dub: Path | None = None,
    original_volume: float = 0.25,
) -> None:
    """Produce an mp4 with burned-in subtitles and/or the voice-over mixed in."""
    info = await media.probe(video)
    streams = info.get("streams", [])
    v_codec = next((s.get("codec_name") for s in streams if s.get("codec_type") == "video"), None)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    args: list[str | Path] = ["-i", video]
    if dub:
        args += ["-i", dub]

    if srt:
        # Run in work_dir and refer to the file by bare name: the subtitles filter's path escaping is fragile.
        args += [
            "-vf", f"scale=trunc(iw/2)*2:trunc(ih/2)*2,subtitles={srt.name}:force_style='{SUBTITLE_STYLE}'",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
        ]
    elif v_codec in PASSTHROUGH_VIDEO_CODECS:
        args += ["-c:v", "copy"]
    else:
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p"]
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

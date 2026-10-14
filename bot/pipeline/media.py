"""Thin async wrappers around ffmpeg / ffprobe."""

import asyncio
import json
import re
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

AUDIO_RATE = 24000  # TTS output rate; also used for the whole dub timeline


class MediaError(RuntimeError):
    pass


async def run(args: Sequence[str | Path], cwd: Path | None = None) -> str:
    """Run a command, return stderr (ffmpeg logs there). Raise MediaError on failure."""
    proc = await asyncio.create_subprocess_exec(
        *map(str, args),
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await proc.communicate()
    except asyncio.CancelledError:
        proc.kill()
        await proc.wait()
        raise
    if proc.returncode != 0:
        tail = stderr.decode(errors="replace").strip().splitlines()[-15:]
        raise MediaError(f"{Path(str(args[0])).name} failed:\n" + "\n".join(tail))
    return stderr.decode(errors="replace") + stdout.decode(errors="replace")


async def ffmpeg(*args: str | Path, cwd: Path | None = None) -> str:
    return await run(["ffmpeg", "-hide_banner", "-nostdin", "-y", *args], cwd=cwd)


async def ffmpeg_progress(
    args: Sequence[str | Path],
    total_seconds: float,
    on_progress: Callable[[float], Awaitable[None]],
    cwd: Path | None = None,
) -> None:
    """Run ffmpeg and report progress (0..1) parsed from `-progress pipe:1`."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-nostdin", "-y", "-progress", "pipe:1", "-nostats", *map(str, args),
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stderr_chunks: list[bytes] = []

    async def drain_stderr() -> None:
        assert proc.stderr
        while chunk := await proc.stderr.read(65536):
            stderr_chunks.append(chunk)
            del stderr_chunks[:-8]

    drain = asyncio.create_task(drain_stderr())
    try:
        assert proc.stdout
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").strip()
            if line.startswith("out_time_us=") and total_seconds > 0:
                try:
                    done = int(line.split("=", 1)[1]) / 1_000_000
                except ValueError:
                    continue
                await on_progress(min(max(done / total_seconds, 0.0), 1.0))
        await proc.wait()
        await drain
    except asyncio.CancelledError:
        proc.kill()
        await proc.wait()
        drain.cancel()
        raise
    if proc.returncode != 0:
        tail = b"".join(stderr_chunks).decode(errors="replace").strip().splitlines()[-15:]
        raise MediaError("ffmpeg failed:\n" + "\n".join(tail))


async def probe(path: Path) -> dict:
    out = await run([
        "ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path,
    ])
    # run() concatenates stderr+stdout; with -v error stderr is empty on success.
    return json.loads(out[out.index("{"):])


async def duration(path: Path) -> float:
    info = await probe(path)
    value = info.get("format", {}).get("duration")
    if value is None:
        raise MediaError(f"Cannot determine duration of {path.name}")
    return float(value)


async def has_audio(path: Path) -> bool:
    info = await probe(path)
    return any(s.get("codec_type") == "audio" for s in info.get("streams", []))


async def has_video(path: Path) -> bool:
    info = await probe(path)
    return any(
        s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
        for s in info.get("streams", [])
    )


async def extract_speech_audio(src: Path, dst: Path) -> None:
    """Mono 16 kHz mp3 — what Whisper is trained on, and small enough to upload in chunks."""
    await ffmpeg("-i", src, "-vn", "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k", dst)


_SILENCE_RE = re.compile(r"silence_(start|end): (-?[\d.]+)")


async def detect_silences(path: Path, noise_db: int = -35, min_len: float = 0.4) -> list[tuple[float, float]]:
    log = await ffmpeg("-i", path, "-af", f"silencedetect=noise={noise_db}dB:d={min_len}", "-f", "null", "-")
    silences: list[tuple[float, float]] = []
    start: float | None = None
    for kind, value in _SILENCE_RE.findall(log):
        if kind == "start":
            start = max(float(value), 0.0)
        elif start is not None:
            silences.append((start, float(value)))
            start = None
    return silences


def plan_chunks(
    total: float,
    silences: list[tuple[float, float]],
    target: float = 600.0,
    window: float = 60.0,
) -> list[tuple[float, float]]:
    """Split [0, total] into ~`target`-second chunks, cutting in the middle of a pause
    near each boundary so no word is cut in half."""
    chunks: list[tuple[float, float]] = []
    start = 0.0
    while total - start > target + window:
        ideal = start + target
        candidates = [
            (s + e) / 2 for s, e in silences
            if ideal - window <= (s + e) / 2 <= ideal + window
        ]
        cut = min(candidates, key=lambda c: abs(c - ideal)) if candidates else ideal
        chunks.append((start, cut))
        start = cut
    chunks.append((start, total))
    return chunks


async def cut_audio(src: Path, dst: Path, start: float, end: float) -> None:
    await ffmpeg("-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", src, "-c", "copy", dst)


async def to_wav(src: Path, dst: Path, tempo: float = 1.0) -> None:
    """Normalize a clip to the dub timeline format, optionally speeding it up."""
    filters = []
    remaining = tempo
    while remaining > 2.0:  # atempo accepts 0.5..2.0 per instance
        filters.append("atempo=2.0")
        remaining /= 2.0
    if abs(remaining - 1.0) > 1e-3:
        filters.append(f"atempo={remaining:.4f}")
    args: list[str | Path] = ["-i", src]
    if filters:
        args += ["-af", ",".join(filters)]
    args += ["-ac", "1", "-ar", str(AUDIO_RATE), "-c:a", "pcm_s16le", dst]
    await ffmpeg(*args)

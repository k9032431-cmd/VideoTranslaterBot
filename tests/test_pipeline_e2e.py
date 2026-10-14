"""Runs the full pipeline on a generated video with a fake OpenAI client (needs ffmpeg)."""

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from bot.config import Config
from bot.pipeline import media
from bot.pipeline.job import JobParams, NoSpeechError, SameLanguageError, run_job

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not installed"),
]

DURATION = 6


def _make_video(path: Path, audio: bool = True) -> None:
    args = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size=321x241:rate=25:duration={DURATION}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={DURATION}"]
    # Odd frame size + 4:4:4 on purpose: rendering must still produce a valid yuv420p video.
    args += ["-c:v", "libx264", "-pix_fmt", "yuv444p", "-shortest", path]
    subprocess.run(list(map(str, args)), check=True, capture_output=True)


class FakeOpenAI:
    def __init__(self, tmp: Path, language: str = "russian", segments=None):
        self.tts_sample = tmp / "tts_sample.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=1.6", str(self.tts_sample)],
            check=True, capture_output=True,
        )
        self.language = language
        self.segments = segments if segments is not None else [
            SimpleNamespace(start=0.5, end=2.0, text="Привет, как дела?", no_speech_prob=0.01,
                            avg_logprob=-0.2, compression_ratio=1.2),
            SimpleNamespace(start=2.2, end=3.0, text="Хорошо.", no_speech_prob=0.01,
                            avg_logprob=-0.2, compression_ratio=1.1),
            # hallucination in silence — must be dropped
            SimpleNamespace(start=4.0, end=5.5, text="Продолжение следует...", no_speech_prob=0.9,
                            avg_logprob=-1.5, compression_ratio=1.0),
        ]
        self.audio = SimpleNamespace(
            transcriptions=SimpleNamespace(create=self._transcribe),
            speech=SimpleNamespace(create=self._speech),
        )
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))
        self.tts_inputs: list[str] = []

    async def _transcribe(self, **kwargs):
        return SimpleNamespace(language=self.language, segments=self.segments)

    async def _speech(self, **kwargs):
        self.tts_inputs.append(kwargs["input"])
        return SimpleNamespace(content=self.tts_sample.read_bytes())

    async def _chat(self, **kwargs):
        lines = json.loads(kwargs["messages"][1]["content"])["lines"]
        content = json.dumps({"translations": [{"id": l["id"], "text": f"EN: {l['text']}"} for l in lines]})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _config(tmp: Path) -> Config:
    return Config(
        bot_token="x", openai_api_key="x", openai_base_url=None, telegram_api_url=None,
        telegram_api_local=True, transcribe_model="whisper-1", translate_model="m", tts_model="gpt-4o-mini-tts",
        tts_voice="onyx", allowed_user_ids=frozenset(), max_video_minutes=180, max_concurrent_jobs=1,
        original_volume=0.25, data_dir=tmp,
    )


async def _report(stage, progress):
    pass


@pytest.mark.parametrize("mode", ["subtitles", "voice", "both"])
async def test_full_pipeline(tmp_path: Path, mode: str):
    video = tmp_path / "in.mp4"
    _make_video(video)
    work = tmp_path / "work"
    work.mkdir()
    client = FakeOpenAI(tmp_path)

    result = await run_job(client, _config(tmp_path), JobParams(video, work, "auto", "en", mode), _report)

    assert result.source.code == "ru"
    srt = result.srt.read_text(encoding="utf-8")
    assert "EN: Привет, как дела?" in srt and "EN: Хорошо." in srt
    assert "Продолжение" not in srt

    assert result.video and result.video.exists()
    info = await media.probe(result.video)
    kinds = sorted(s["codec_type"] for s in info["streams"])
    assert kinds == ["audio", "video"]
    assert abs(float(info["format"]["duration"]) - DURATION) < 0.3

    if mode == "subtitles":
        assert client.tts_inputs == []
    else:
        assert client.tts_inputs == ["EN: Привет, как дела?", "EN: Хорошо."]
        dub = await media.duration(work / "dub.wav")
        assert abs(dub - DURATION) < 0.05


async def test_explicit_source_same_as_target(tmp_path: Path):
    video = tmp_path / "in.mp4"
    _make_video(video)
    client = FakeOpenAI(tmp_path, language="english")
    with pytest.raises(SameLanguageError):
        await run_job(client, _config(tmp_path), JobParams(video, tmp_path, "auto", "en", "subtitles"), _report)


async def test_video_without_audio(tmp_path: Path):
    video = tmp_path / "in.mp4"
    _make_video(video, audio=False)
    with pytest.raises(NoSpeechError):
        await run_job(FakeOpenAI(tmp_path), _config(tmp_path), JobParams(video, tmp_path, "ru", "en", "voice"), _report)


async def test_no_speech_detected(tmp_path: Path):
    video = tmp_path / "in.mp4"
    _make_video(video)
    client = FakeOpenAI(tmp_path, segments=[])
    with pytest.raises(NoSpeechError):
        await run_job(client, _config(tmp_path), JobParams(video, tmp_path, "ru", "en", "both"), _report)

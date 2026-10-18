"""Local mode (faster-whisper + NLLB on the server) with the heavy models replaced by fakes."""

import asyncio
import shutil
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from bot import languages
from bot.pipeline import dubbing, local, media
from bot.pipeline.job import JobParams, run_job
from bot.pipeline.models import Segment

from .test_pipeline_e2e import DURATION, FakeOpenAI, _make_video, _report

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not installed")


def _seg(start, end, text, no_speech=0.01, logprob=-0.2):
    return SimpleNamespace(start=start, end=end, text=text, no_speech_prob=no_speech,
                           avg_logprob=logprob, compression_ratio=1.2)


class FakeWhisper:
    def __init__(self, segments, language="ru"):
        self.segments = segments
        self.language = language
        self.calls = []

    def transcribe(self, audio, **kwargs):
        self.calls.append((audio, kwargs))
        return iter(self.segments), SimpleNamespace(language=self.language, duration=DURATION)


class FakeTokenizer:
    def encode(self, text, add_special_tokens=False):
        return SimpleNamespace(tokens=text.split())

    def token_to_id(self, token):
        return {"</s>": 2}.get(token, hash(token) % 1000 + 10)


class FakeTranslator:
    def __init__(self):
        self.calls = []

    def translate_batch(self, sources, target_prefix, **kwargs):
        self.calls.append((sources, target_prefix))
        return [SimpleNamespace(hypotheses=[[prefix[0], "EN", *src[1:-1]]])
                for src, prefix in zip(sources, target_prefix)]


class DecodingTokenizer(FakeTokenizer):
    """Remembers which ids belong to which tokens so decode() can rebuild the text."""

    def __init__(self):
        self.vocab = {}

    def token_to_id(self, token):
        return self.vocab.setdefault(token, len(self.vocab) + 10)

    def decode(self, ids, skip_special_tokens=True):
        reverse = {v: k for k, v in self.vocab.items()}
        return " ".join(reverse[i] for i in ids)


@pytest.fixture
def fake_models(monkeypatch):
    whisper = FakeWhisper([
        _seg(0.5, 2.0, "Привет, как дела?"),
        _seg(2.2, 3.0, "Хорошо."),
        _seg(4.0, 5.5, "Субтитры сделал DimaTorzok", no_speech=0.9, logprob=-1.5),  # hallucination
    ])
    translator, tokenizer = FakeTranslator(), DecodingTokenizer()
    monkeypatch.setattr(local, "load_whisper", lambda name, models_dir: whisper)
    monkeypatch.setattr(local, "load_nllb", lambda repo, models_dir: (translator, tokenizer))
    return whisper, translator


def _local_config(tmp: Path):
    from bot.config import Config
    return Config(
        bot_token="x", provider="local", ai_api_key="", ai_base_url=None,
        telegram_api_url=None, telegram_api_local=True,
        transcribe_model="small", translate_model="nllb-test", translate_reasoning_effort="",
        tts_engine="edge", tts_model="", tts_voice="", tts_gender="male",
        allowed_user_ids=frozenset(), max_video_minutes=180, max_concurrent_jobs=1,
        original_volume=0.25, data_dir=tmp,
    )


async def test_local_pipeline(tmp_path: Path, monkeypatch, fake_models):
    whisper, translator = fake_models
    sample = FakeOpenAI(tmp_path).tts_sample  # just a short mp3

    class FakeCommunicate:
        def __init__(self, text, voice):
            self.voice = voice

        async def save(self, path):
            Path(path).write_bytes(sample.read_bytes())

    monkeypatch.setattr(dubbing.edge_tts, "Communicate", FakeCommunicate)
    video = tmp_path / "in.mp4"
    _make_video(video)
    work = tmp_path / "work"
    work.mkdir()

    result = await run_job(None, _local_config(tmp_path), JobParams(video, work, "auto", "en", "both"), _report)

    assert result.source.code == "ru"
    audio, kwargs = whisper.calls[0]
    assert kwargs["language"] is None and kwargs["vad_filter"] is True
    assert audio.dtype.name == "float32" and len(audio) == pytest.approx(DURATION * 16000, rel=0.02)
    sources, prefixes = translator.calls[0]
    assert sources[0][0] == "rus_Cyrl" and sources[0][-1] == "</s>"
    assert prefixes[0] == ["eng_Latn"]
    srt = result.srt.read_text(encoding="utf-8")
    assert "EN Привет, как дела?" in srt and "EN Хорошо." in srt
    assert "DimaTorzok" not in srt
    assert result.video and abs(float((await media.probe(result.video))["format"]["duration"]) - DURATION) < 0.3


async def test_local_translate_rejects_unknown_language(tmp_path, fake_models):
    unknown = languages.Language("xx", "🏳️", "X", "X")
    with pytest.raises(local.UnsupportedLanguageError):
        await local.translate([Segment(0, 1, "a")], unknown, languages.get("en"), "m", tmp_path, _noop)


async def test_cancelling_stops_the_worker_thread():
    started, finished = threading.Event(), threading.Event()

    def work(stop, report):
        started.set()
        while not stop.is_set():
            stop.wait(0.01)
        finished.set()

    task = asyncio.create_task(local._run_in_thread(work, _noop))
    await asyncio.to_thread(started.wait, 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await asyncio.to_thread(finished.wait, 5)


async def _noop(_):
    pass

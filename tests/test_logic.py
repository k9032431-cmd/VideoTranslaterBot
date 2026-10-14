import json
from types import SimpleNamespace

import pytest

from bot import i18n, keyboards, languages
from bot.pipeline import media, subtitles, translate
from bot.pipeline.dubbing import MAX_TEMPO, plan_timeline
from bot.pipeline.models import Segment
from bot.pipeline.transcribe import _merge_duplicates


def test_every_ui_language_has_every_key():
    keys = set(i18n.TEXTS["ru"])
    for lang, texts in i18n.TEXTS.items():
        assert set(texts) == keys, lang


def test_ui_texts_format_without_errors():
    sample = dict(max_mb=1, max_min=1, size_mb=1, minutes=1, name="x", duration="", source="a",
                  target="b", mode="m", progress="1%", error="e")
    for lang in i18n.TEXTS:
        for key in i18n.TEXTS[lang]:
            i18n.t(lang, key, **sample)


def test_mode_texts_exist_for_every_mode():
    for lang in i18n.TEXTS:
        for mode in keyboards.MODES:
            assert i18n.t(lang, f"mode_{mode}")


def test_callback_data_fits_telegram_limit():
    for markup in (keyboards.source_languages("ru"), keyboards.target_languages("ru", "ru"),
                   keyboards.modes("ru"), keyboards.confirm("ru"), keyboards.ui_languages()):
        for row in markup.inline_keyboard:
            for button in row:
                assert len(button.callback_data.encode()) <= 64


def test_target_keyboard_excludes_source():
    markup = keyboards.target_languages("en", "ru")
    datas = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert keyboards.TargetCb(lang="ru").pack() not in datas
    assert keyboards.TargetCb(lang="en").pack() in datas


def test_whisper_language_mapping():
    assert languages.from_whisper("russian").code == "ru"
    assert languages.from_whisper("English").code == "en"
    assert languages.from_whisper("chinese").code == "zh"
    assert languages.from_whisper("uk").code == "uk"
    assert languages.from_whisper("klingon") is None


def test_plan_chunks_cuts_in_silence():
    silences = [(590.0, 591.0), (610.0, 612.0), (1205.0, 1206.0)]
    chunks = media.plan_chunks(1500.0, silences)
    assert chunks[0] == (0.0, 590.5)
    assert chunks[1] == (590.5, 1205.5)
    assert chunks[-1][1] == 1500.0
    for (_, end), (start, _) in zip(chunks, chunks[1:]):
        assert end == start


def test_plan_chunks_short_audio_single_chunk():
    assert media.plan_chunks(300.0, []) == [(0.0, 300.0)]


def test_merge_duplicates():
    segs = [Segment(0, 2, "Hello"), Segment(2.1, 3, "Hello"), Segment(2.5, 5, "World")]
    merged = _merge_duplicates(segs)
    assert [s.text for s in merged] == ["Hello", "World"]
    assert merged[0].end == 3
    assert merged[1].start == 3


def test_srt_format():
    cues = subtitles.build_cues([Segment(1.5, 3.25, "x", "Привет, мир!")], "ru")
    srt = subtitles.to_srt(cues)
    assert srt == "1\n00:00:01,500 --> 00:00:03,250\nПривет, мир!\n"


def test_long_text_is_split_and_wrapped():
    text = ("This is a really long sentence that goes on and on, much longer than a subtitle line "
            "should ever be. And then another sentence follows it right away to make things worse.")
    cues = subtitles.build_cues([Segment(0, 12, "x", text)], "en")
    assert len(cues) >= 2
    for cue in cues:
        lines = cue.text.split("\n")
        assert len(lines) <= 2
        assert all(len(line) <= subtitles.LINE_CHARS for line in lines)
    assert cues[0].start == 0 and cues[-1].end == 12
    assert " ".join(c.text.replace("\n", " ") for c in cues) == text


def test_cjk_split():
    cues = subtitles.build_cues([Segment(0, 4, "x", "这是一个非常长的中文句子，需要被分成多行显示，否则观众很难阅读。")], "zh")
    for cue in cues:
        assert all(len(line) <= subtitles.LINE_CHARS_CJK for line in cue.text.split("\n"))


def test_timeline_fits_and_speeds_up():
    plan = plan_timeline(starts=[0.0, 3.0, 10.0], clip_lengths=[2.0, 9.0, 1.0], ends=[2.5, 9.0, 11.0])
    assert plan[0].silence_before == 0 and plan[0].tempo == 1.0
    assert plan[1].silence_before == pytest.approx(1.0)
    assert plan[1].tempo == pytest.approx(9.0 / 7.0)  # squeezed exactly into the 7 s until the next line
    assert plan[2].silence_before == pytest.approx(0.0, abs=1e-9)  # next line starts right on time


def test_timeline_caps_tempo():
    plan = plan_timeline(starts=[0.0, 3.0], clip_lengths=[12.0, 1.0], ends=[2.0, 4.0])
    assert plan[0].tempo == MAX_TEMPO
    assert plan[1].silence_before == 0  # runs late instead of sounding like a chipmunk


def test_timeline_overrun_is_absorbed():
    plan = plan_timeline(starts=[0.0, 1.0, 20.0], clip_lengths=[5.0, 1.0, 1.0], ends=[1.0, 2.0, 21.0])
    # first clip overruns into the second one's slot: second starts right after it, no negative gaps
    assert plan[1].silence_before == 0
    assert all(p.silence_before >= 0 for p in plan)


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.responses.pop(0)
        if callable(content):
            content = content(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _echo(kwargs):
    lines = json.loads(kwargs["messages"][1]["content"])["lines"]
    return json.dumps({"translations": [{"id": l["id"], "text": l["text"].upper()} for l in lines]})


async def _noop(_):
    pass


@pytest.mark.asyncio
async def test_translate_retries_on_missing_ids():
    segs = [Segment(i, i + 1, f"line {i}") for i in range(3)]
    completions = FakeCompletions([json.dumps({"translations": [{"id": 0, "text": "A"}]}), _echo])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    await translate.translate(client, "m", segs, languages.get("en"), languages.get("ru"), False, _noop)
    assert [s.translation for s in segs] == ["LINE 0", "LINE 1", "LINE 2"]
    assert len(completions.calls) == 2


@pytest.mark.asyncio
async def test_translate_splits_batch_after_repeated_failures():
    segs = [Segment(i, i + 1, f"l{i}") for i in range(4)]
    bad = json.dumps({"translations": []})
    completions = FakeCompletions([bad] * translate.ATTEMPTS + [_echo, _echo])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    await translate.translate(client, "m", segs, languages.get("en"), languages.get("ru"), True, _noop)
    assert [s.translation for s in segs] == ["L0", "L1", "L2", "L3"]
    # voice mode sends a length budget
    assert "max_chars" in completions.calls[0]["messages"][1]["content"]


def test_config_free_defaults(monkeypatch, tmp_path):
    from bot import config as cfg
    for key in ("PROVIDER", "TRANSCRIBE_MODEL", "TRANSLATE_MODEL", "TTS_ENGINE", "OPENAI_BASE_URL",
                "TRANSLATE_REASONING_EFFORT", "OPENAI_API_KEY", "TTS_GENDER"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BOT_TOKEN", "1:x")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    with pytest.raises(SystemExit, match="GROQ_API_KEY"):
        cfg.load_config()
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    c = cfg.load_config()
    assert (c.provider, c.ai_api_key, c.ai_base_url) == ("free", "gsk_x", cfg.GROQ_BASE_URL)
    assert (c.transcribe_model, c.tts_engine, c.tts_gender) == ("whisper-large-v3", "edge", "male")
    assert c.translate_reasoning_effort == "low"

    monkeypatch.setenv("PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    c = cfg.load_config()
    assert (c.ai_api_key, c.ai_base_url, c.tts_engine, c.transcribe_model) == ("sk-x", None, "openai", "whisper-1")

    monkeypatch.setenv("PROVIDER", "free")
    monkeypatch.setenv("TTS_ENGINE", "openai")
    with pytest.raises(SystemExit):
        cfg.load_config()


@pytest.mark.asyncio
async def test_translate_passes_reasoning_effort():
    segs = [Segment(0, 1, "a")]
    completions = FakeCompletions([_echo])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    await translate.translate(client, "m", segs, languages.get("en"), languages.get("ru"), False, _noop,
                              reasoning_effort="low")
    assert completions.calls[0]["reasoning_effort"] == "low"


def test_every_language_has_edge_voices():
    for lang in languages.LANGUAGES:
        assert lang.edge_male.startswith(lang.code + "-") and lang.edge_female.startswith(lang.code + "-")

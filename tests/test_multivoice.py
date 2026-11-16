"""Multi-voice voice-over: telling speakers apart, guessing gender and handing out voices."""

import numpy as np

from bot import keyboards, languages
from bot.pipeline import speakers, voices
from bot.pipeline.local import merge_sentences
from bot.pipeline.models import Segment
from bot.pipeline.speakers import Speaker


def _voice(seed: int, dim: int = 64):
    rng = np.random.default_rng(seed)
    base = rng.normal(size=dim)
    return base / np.linalg.norm(base)


def _sample(base, seed: int, noise: float = 0.35):
    rng = np.random.default_rng(1000 + seed)
    emb = base + rng.normal(size=base.shape) * noise / np.sqrt(base.shape[0])
    return emb / np.linalg.norm(emb)


def test_cluster_separates_voices_and_orders_by_talk_time():
    a, b, c = _voice(1), _voice(2), _voice(3)
    truth = list("ABACBCAABA")
    embs = [_sample({"A": a, "B": b, "C": c}[s], i) for i, s in enumerate(truth)]
    labels = speakers.cluster(embs, [2.0] * len(truth))
    mapping = dict(zip(truth, labels))
    assert len(set(mapping.values())) == 3
    assert [mapping[s] for s in truth] == labels  # every line got its own speaker's label
    assert mapping["A"] == 0  # A talks the most


def test_cluster_folds_tiny_noise_cluster():
    a, noise = _voice(1), _voice(9)
    embs = [_sample(a, i) for i in range(5)] + [noise]
    labels = speakers.cluster(embs, [2.0] * 5 + [0.5])
    assert set(labels) == {0}


def test_pitch_tells_male_from_female():
    sr = speakers.SAMPLE_RATE
    t = np.arange(sr) / sr

    def voice(f0):  # harmonics, like a voiced sound
        return (0.3 * sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 6))).astype(np.float32)

    assert 100 < speakers.pitch(voice(120)) < 140
    assert 200 < speakers.pitch(voice(220)) < 240
    assert speakers.pitch(np.zeros(sr, dtype=np.float32)) == 0.0


def test_short_lines_take_neighbours_speaker():
    segs = [Segment(0, 2, "a"), Segment(2.1, 2.4, "ok"), Segment(5, 7, "b")]
    assert speakers._fill_short([0, None, 1], segs) == [0, 0, 1]


async def test_each_speaker_gets_a_distinct_voice():
    segs = [Segment(0, 1, "x", speaker=0), Segment(1, 2, "y", speaker=1),
            Segment(2, 3, "z", speaker=2), Segment(3, 4, "w", speaker=0)]
    found = {0: Speaker(0, "male", 30), 1: Speaker(1, "female", 20), 2: Speaker(2, "male", 10)}
    result = await voices.per_segment("edge", languages.get("ru"), segs, found, "onyx")
    assert result[0] == result[3] == "ru-RU-DmitryNeural"  # main male speaker: the native voice
    assert result[1] == "ru-RU-SvetlanaNeural"
    assert result[2] not in (result[0], result[1])
    assert "Multilingual" in result[2]  # Russian has one male voice; a multilingual one fills in


async def test_pool_has_no_two_voices_of_the_same_person():
    pool = await voices.edge_pool(languages.get("en"), "male")
    assert len({voices.persona(v) for v in pool}) == len(pool)
    assert pool[0] == "en-US-AndrewMultilingualNeural"  # the configured one comes first


async def test_retired_configured_voice_is_replaced():
    # Microsoft retired de-DE-ConradNeural; another German voice must be used instead.
    pool = await voices.edge_pool(languages.get("de"), "male")
    assert "de-DE-ConradNeural" not in pool
    assert pool[0] == "de-DE-KillianNeural"  # de-DE before de-AT


async def test_turkmen_uses_turkish_voices_only():
    assert await voices.edge_pool(languages.get("tk"), "female") == ["tr-TR-EmelNeural"]


async def test_offline_falls_back_to_configured_voice(monkeypatch):
    async def broken():
        return []
    monkeypatch.setattr(voices, "_edge_list", broken)
    assert await voices.edge_pool(languages.get("de"), "female") == ["de-DE-KatjaNeural"]


async def test_openai_voices_per_gender():
    segs = [Segment(0, 1, "x", speaker=0), Segment(1, 2, "y", speaker=1)]
    found = {0: Speaker(0, "female", 5), 1: Speaker(1, "male", 4)}
    assert await voices.per_segment("openai", languages.get("en"), segs, found, "onyx") == ["nova", "onyx"]


def test_sentences_of_different_speakers_are_not_glued():
    segs = [Segment(0, 1, "Ты пойдёшь", speaker=0), Segment(1.1, 2, "нет", speaker=1)]
    assert len(merge_sentences(segs)) == 2


def test_multi_voice_modes_offered():
    assert {"multi", "multi_both"} <= set(keyboards.MODES)
    datas = [b.callback_data for row in keyboards.modes("ru").inline_keyboard for b in row]
    assert keyboards.ModeCb(mode="multi").pack() in datas

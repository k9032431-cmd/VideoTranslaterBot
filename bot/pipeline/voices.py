"""Which voice reads which line.

Microsoft's voice list changes over time (voices get retired), so Edge voices are picked from the
live list, preferring the ones configured in `languages.py`. "Multilingual" voices speak any of
our languages fluently, which gives several distinct voices even where Microsoft has only two.
"""

import logging

from ..languages import Language
from .models import Segment
from .speakers import Speaker

log = logging.getLogger(__name__)

OPENAI_VOICES = {
    "male": ["onyx", "echo", "ash", "ballad", "verse"],
    "female": ["nova", "shimmer", "coral", "sage"],
}

_edge_cache: list[dict] | None = None


async def _edge_list() -> list[dict]:
    global _edge_cache
    if _edge_cache is None:
        import edge_tts

        try:
            _edge_cache = await edge_tts.list_voices()
        except Exception:
            log.warning("Could not fetch the Edge voice list; using configured voices only", exc_info=True)
            return []
    return _edge_cache


def persona(voice: str) -> str:
    """'en-US-AndrewMultilingualNeural' and 'en-US-AndrewNeural' are the same person: 'andrew'."""
    name = voice.split("-")[-1]
    for suffix in ("Neural", "Multilingual", "Expressive"):
        name = name.replace(suffix, "")
    return name.lower()


def _distinct(voices: list[str]) -> list[str]:
    seen, result = set(), []
    for voice in voices:
        if persona(voice) not in seen:
            seen.add(persona(voice))
            result.append(voice)
    return result


def _voice_lang(target: Language) -> str:
    # No Turkmen voices exist: the closely related Turkish ones read it (see dubbing.speakable).
    return "tr" if target.code == "tk" else target.code


async def edge_pool(target: Language, gender: str) -> list[str]:
    """Voices for `target` of one gender, best first. Never empty."""
    preferred = target.edge_female if gender == "female" else target.edge_male
    lang = _voice_lang(target)
    voices = await _edge_list()
    wanted = "Female" if gender == "female" else "Male"
    same_gender = [v for v in voices if v.get("Gender") == wanted]
    native = [v["ShortName"] for v in same_gender if v.get("Locale", "").split("-")[0].lower() == lang]
    # Main locale first (ru-RU before ru-…, de-DE before de-AT), then the rest.
    main_locale = "-".join(preferred.split("-")[:2])
    native.sort(key=lambda name: not name.startswith(main_locale + "-"))
    multilingual = [] if target.code == "tk" else [
        v["ShortName"] for v in same_gender if "Multilingual" in v["ShortName"] and v["ShortName"] not in native
    ]
    pool = native + multilingual
    if voices and preferred in pool:
        pool.remove(preferred)
        pool.insert(0, preferred)
    elif not voices or not pool:
        pool = [preferred] + pool  # offline, or nothing listed: trust the configured voice
    return _distinct(pool)


async def single_voice(engine: str, target: Language, gender: str, openai_voice: str) -> str:
    if engine == "openai":
        return openai_voice
    return (await edge_pool(target, gender))[0]


async def per_segment(
    engine: str,
    target: Language,
    segments: list[Segment],
    speakers: dict[int, Speaker],
    openai_voice: str,
) -> list[str]:
    """A distinct voice per speaker (by gender, most talkative first); one entry per segment."""
    pools: dict[str, list[str]] = {}
    for gender in ("male", "female"):
        if engine == "openai":
            pool = list(OPENAI_VOICES[gender])
            if openai_voice in pool:  # the configured voice goes to the main speaker of its gender
                pool.remove(openai_voice)
                pool.insert(0, openai_voice)
        else:
            pool = await edge_pool(target, gender)
        pools[gender] = pool

    used = {"male": 0, "female": 0}
    voice_of: dict[int, str] = {}
    for speaker in sorted(speakers.values(), key=lambda s: -s.seconds):
        pool = pools[speaker.gender]
        voice_of[speaker.id] = pool[used[speaker.gender] % len(pool)]
        used[speaker.gender] += 1
    log.info("Voices: %s", voice_of)
    return [voice_of.get(seg.speaker if seg.speaker is not None else -1, pools["male"][0]) for seg in segments]

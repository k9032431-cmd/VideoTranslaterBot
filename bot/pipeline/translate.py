import json
import logging
from collections.abc import Awaitable, Callable

from openai import AsyncOpenAI

from ..languages import Language
from .models import Segment

log = logging.getLogger(__name__)

BATCH_SIZE = 40
CONTEXT_LINES = 8
ATTEMPTS = 3
# Typical comfortable speaking rate, used to tell the model how long a line may be.
CHARS_PER_SECOND = 15


class TranslationError(RuntimeError):
    pass


def _system_prompt(source: Language, target: Language, for_voice: bool) -> str:
    rules = [
        f"You are a professional film and video translator from {source.english} into {target.english}.",
        "You receive numbered lines of a video transcript (speech recognition output, in order).",
        f"Translate every line into natural, fluent, idiomatic {target.english}, the way a professional "
        "subtitler or dubbing studio would: convey meaning, tone, humour and emotion, not word-for-word.",
        "Use the surrounding lines for context so pronouns, gender, formality and terminology stay consistent.",
        "Keep personal names, brand names and places as is or in their standard transliteration.",
        "Keep the register: slang stays slang, swearing stays swearing, formal stays formal.",
        "If a line is cut mid-sentence, translate it so that it joins naturally with the next line.",
        "Fix obvious speech-recognition mistakes silently using the context.",
        "Never merge, split, skip or reorder lines: return exactly one translation per input id.",
        "Do not add notes, explanations, quotes or transliterations of the original.",
    ]
    if for_voice:
        rules.append(
            "The translation will be voiced over the original, so each line has a time budget in "
            "`max_chars`. Keep the translation within it by phrasing concisely while keeping the meaning."
        )
    rules.append(
        'Answer with JSON only: {"translations": [{"id": <id>, "text": "<translation>"}, ...]}'
    )
    return "\n".join(rules)


async def _translate_batch(
    client: AsyncOpenAI,
    model: str,
    system: str,
    batch: list[tuple[int, Segment]],
    context: list[Segment],
    for_voice: bool,
) -> dict[int, str]:
    lines = []
    for idx, seg in batch:
        line: dict = {"id": idx, "text": seg.text}
        if for_voice:
            line["max_chars"] = max(int(seg.duration * CHARS_PER_SECOND), 12)
        lines.append(line)
    payload = {
        "previous_lines_for_context": [{"original": s.text, "translation": s.translation} for s in context],
        "lines": lines,
    }
    expected = {idx for idx, _ in batch}

    last_error = ""
    for attempt in range(1, ATTEMPTS + 1):
        response = await client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        content = response.choices[0].message.content or ""
        try:
            items = json.loads(content)["translations"]
            result = {int(item["id"]): str(item["text"]).strip() for item in items}
        except (ValueError, KeyError, TypeError) as exc:
            last_error = f"bad JSON: {exc}"
        else:
            missing = expected - result.keys()
            empty = [i for i in expected & result.keys() if not result[i]]
            if not missing and not empty:
                return {i: result[i] for i in expected}
            last_error = f"missing ids {sorted(missing)}, empty ids {sorted(empty)}"
        log.warning("Translation batch attempt %d/%d failed: %s", attempt, ATTEMPTS, last_error)

    if len(batch) > 1:
        # Smaller batches are much easier for the model to get exactly right.
        half = len(batch) // 2
        first = await _translate_batch(client, model, system, batch[:half], context, for_voice)
        for idx, seg in batch[:half]:
            seg.translation = first[idx]
        second = await _translate_batch(
            client, model, system, batch[half:], (context + [s for _, s in batch[:half]])[-CONTEXT_LINES:], for_voice
        )
        return first | second
    raise TranslationError(last_error)


async def translate(
    client: AsyncOpenAI,
    model: str,
    segments: list[Segment],
    source: Language,
    target: Language,
    for_voice: bool,
    on_progress: Callable[[float], Awaitable[None]],
) -> None:
    """Fill `translation` on every segment, in place."""
    system = _system_prompt(source, target, for_voice)
    indexed = list(enumerate(segments))
    for offset in range(0, len(indexed), BATCH_SIZE):
        batch = indexed[offset:offset + BATCH_SIZE]
        context = segments[max(0, offset - CONTEXT_LINES):offset]
        result = await _translate_batch(client, model, system, batch, context, for_voice)
        for idx, seg in batch:
            seg.translation = result[idx]
        await on_progress(min(offset + BATCH_SIZE, len(indexed)) / len(indexed))

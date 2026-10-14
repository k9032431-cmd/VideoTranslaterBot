"""Turn translated segments into readable SRT cues (≤ 2 lines, sensible duration)."""

import re
from dataclasses import dataclass

from .models import Segment

# Netflix-style limits.
LINE_CHARS = 42
LINE_CHARS_CJK = 16
MAX_LINES = 2
MAX_CUE_SECONDS = 7.0

CJK_LANGS = {"zh", "ja", "ko"}

_CLAUSE_RE = re.compile(r"(?<=[.!?…;:,。！？；：，、])\s*")


@dataclass
class Cue:
    start: float
    end: float
    text: str


def _timestamp(seconds: float) -> str:
    ms = max(int(round(seconds * 1000)), 0)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _split_long(piece: str, limit: int, cjk: bool) -> list[str]:
    """Split a single clause that is longer than `limit` at word boundaries."""
    if len(piece) <= limit:
        return [piece]
    if cjk:
        return [piece[i:i + limit] for i in range(0, len(piece), limit)]
    parts, current = [], ""
    for word in piece.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) > limit and current:
            parts.append(current)
            current = word
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def split_text(text: str, cue_chars: int, cjk: bool) -> list[str]:
    """Split text into pieces of ≤ cue_chars, preferring sentence/clause boundaries."""
    text = " ".join(text.split())
    if len(text) <= cue_chars:
        return [text]
    clauses = [c for c in _CLAUSE_RE.split(text) if c]
    pieces: list[str] = []
    for clause in clauses:
        pieces.extend(_split_long(clause, cue_chars, cjk))
    joiner = "" if cjk else " "
    cues: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}{joiner}{piece}" if current else piece
        if len(candidate) <= cue_chars:
            current = candidate
        else:
            if current:
                cues.append(current)
            current = piece
    if current:
        cues.append(current)
    return cues


def wrap(text: str, line_chars: int, cjk: bool) -> str:
    """Break a cue into at most two balanced lines."""
    if len(text) <= line_chars:
        return text
    middle = len(text) // 2
    if cjk:
        return text[:middle] + "\n" + text[middle:]
    spaces = [i for i, ch in enumerate(text) if ch == " "]
    if not spaces:
        return text
    cut = min(spaces, key=lambda i: abs(i - middle))
    return text[:cut] + "\n" + text[cut + 1:]


def build_cues(segments: list[Segment], target_lang: str) -> list[Cue]:
    cjk = target_lang in CJK_LANGS
    line_chars = LINE_CHARS_CJK if cjk else LINE_CHARS
    cue_chars = line_chars * MAX_LINES

    cues: list[Cue] = []
    for seg in segments:
        text = seg.translation or seg.text
        pieces = split_text(text, cue_chars, cjk)
        # More pieces if the segment is simply too long to read in one cue.
        while seg.duration / len(pieces) > MAX_CUE_SECONDS and len(pieces) < len(text.split()):
            smaller = split_text(text, max(len(text) // (len(pieces) + 1), 1), cjk)
            if len(smaller) <= len(pieces):
                break
            pieces = smaller
        total_chars = sum(len(p) for p in pieces) or 1
        cursor = seg.start
        for i, piece in enumerate(pieces):
            end = seg.end if i == len(pieces) - 1 else cursor + seg.duration * len(piece) / total_chars
            cues.append(Cue(cursor, end, wrap(piece, line_chars, cjk)))
            cursor = end
    return cues


def to_srt(cues: list[Cue]) -> str:
    blocks = [
        f"{i}\n{_timestamp(cue.start)} --> {_timestamp(cue.end)}\n{cue.text}\n"
        for i, cue in enumerate(cues, start=1)
    ]
    return "\n".join(blocks)

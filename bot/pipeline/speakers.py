"""Who speaks when: groups transcript segments by speaker and guesses each speaker's gender.

Each segment gets a voice "fingerprint" (3D-Speaker ERes2Net via sherpa-onnx, runs on the CPU,
no PyTorch); similar fingerprints are clustered into speakers. Gender comes from the median pitch.
"""

import logging
import os
import threading
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from .models import Segment

log = logging.getLogger(__name__)

MODEL_NAME = "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"
MODEL_URL = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/{MODEL_NAME}"
SAMPLE_RATE = 16000

# Cosine similarity of fingerprints: same person ≥ ~0.6, different people ≤ ~0.4 (measured on test dialogs).
SAME_SPEAKER = 0.5
MIN_EMBED_SECONDS = 0.8  # shorter segments give unreliable fingerprints; they take a neighbour's speaker
MIN_SPEAKER_SECONDS = 3.0  # "speakers" with less total speech are folded into the closest real one
MAX_SPEAKERS = 8
MALE_MAX_PITCH = 165.0  # Hz: typical male voices ~85–155, female ~165–255

_lock = threading.Lock()
_extractor = None


@dataclass
class Speaker:
    id: int
    gender: str  # male | female
    seconds: float


def ensure_model(models_dir: Path) -> Path:
    path = models_dir / "speaker" / MODEL_NAME
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        log.info("Downloading speaker model")
        urllib.request.urlretrieve(MODEL_URL, tmp)
        os.replace(tmp, path)
    return path


def _load_extractor(models_dir: Path):
    import sherpa_onnx

    global _extractor
    with _lock:
        if _extractor is None:
            config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(ensure_model(models_dir)), num_threads=max(os.cpu_count() or 1, 1),
            )
            _extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
        return _extractor


def pitch(samples) -> float:
    """Median fundamental frequency (Hz) of the voiced 40 ms frames, 0 if none."""
    import numpy as np

    frame, hop = int(0.04 * SAMPLE_RATE), int(0.01 * SAMPLE_RATE)
    lo, hi = SAMPLE_RATE // 400, SAMPLE_RATE // 60
    values = []
    for start in range(0, len(samples) - frame, hop):
        chunk = samples[start:start + frame]
        chunk = chunk - chunk.mean()
        if np.sqrt((chunk ** 2).mean()) < 0.02:
            continue
        corr = np.correlate(chunk, chunk, "full")[frame - 1:]
        lag = lo + int(np.argmax(corr[lo:hi]))
        if corr[lag] > 0.4 * corr[0]:
            values.append(SAMPLE_RATE / lag)
    return float(np.median(values)) if values else 0.0


def cluster(embeddings, weights: list[float], threshold: float = SAME_SPEAKER) -> list[int]:
    """Group L2-normalised embeddings: a greedy pass, then merging of similar clusters."""
    import numpy as np

    centroids: list = []
    totals: list[float] = []
    labels: list[int] = []
    for emb, weight in zip(embeddings, weights):
        if centroids:
            sims = np.array([c @ emb / np.linalg.norm(c) for c in centroids])
            best = int(np.argmax(sims))
            if sims[best] >= threshold:
                centroids[best] = centroids[best] + emb * weight
                totals[best] += weight
                labels.append(best)
                continue
        centroids.append(emb * weight)
        totals.append(weight)
        labels.append(len(centroids) - 1)

    # Merge clusters that ended up describing the same voice.
    mapping = list(range(len(centroids)))
    merged = True
    while merged:
        merged = False
        alive = sorted({mapping[i] for i in range(len(centroids))})
        best_pair, best_sim = None, threshold
        for i, a in enumerate(alive):
            for b in alive[i + 1:]:
                ca, cb = centroids[a], centroids[b]
                sim = float(ca @ cb / (np.linalg.norm(ca) * np.linalg.norm(cb)))
                if sim >= best_sim:
                    best_pair, best_sim = (a, b), sim
        if best_pair:
            a, b = best_pair
            centroids[a] = centroids[a] + centroids[b]
            totals[a] += totals[b]
            mapping = [a if m == b else m for m in mapping]
            merged = True

    # Fold tiny clusters (coughs, noise, a misheard word) and cap the number of speakers.
    alive = sorted(set(mapping), key=lambda c: -totals[c])
    keep = [c for c in alive if totals[c] >= MIN_SPEAKER_SECONDS][:MAX_SPEAKERS] or alive[:1]
    for c in alive:
        if c not in keep:
            target = max(keep, key=lambda k: float(
                centroids[k] @ centroids[c] / (np.linalg.norm(centroids[k]) * np.linalg.norm(centroids[c]))))
            mapping = [target if m == c else m for m in mapping]
    order = {c: i for i, c in enumerate(keep)}  # 0 = the person who talks the most
    return [order[mapping[label]] for label in labels]


def _fill_short(labels: list[int | None], segments: list[Segment]) -> list[int]:
    """Segments too short to fingerprint take the speaker of the nearest fingerprinted neighbour."""
    known = [i for i, label in enumerate(labels) if label is not None]
    if not known:
        return [0] * len(labels)
    result = []
    for i, label in enumerate(labels):
        if label is None:
            nearest = min(known, key=lambda k: min(abs(segments[k].start - segments[i].end),
                                                   abs(segments[i].start - segments[k].end)))
            label = labels[nearest]
        result.append(label)
    return result


async def assign(
    audio_path: Path,
    segments: list[Segment],
    models_dir: Path,
    on_progress: Callable[[float], Awaitable[None]],
) -> dict[int, Speaker]:
    """Set `segment.speaker` on every segment; return the speakers found."""
    import numpy as np

    from .local import _decode_audio, _run_in_thread, _Stopped

    def work(stop: threading.Event, report: Callable[[float], None]) -> dict[int, Speaker]:
        audio = _decode_audio(audio_path)
        extractor = _load_extractor(models_dir)
        embeddings, weights, owners = [], [], []
        for i, seg in enumerate(segments):
            if stop.is_set():
                raise _Stopped
            if seg.duration >= MIN_EMBED_SECONDS:
                stream = extractor.create_stream()
                stream.accept_waveform(SAMPLE_RATE, audio[int(seg.start * SAMPLE_RATE):int(seg.end * SAMPLE_RATE)])
                stream.input_finished()
                emb = np.array(extractor.compute(stream), dtype=np.float32)
                embeddings.append(emb / (np.linalg.norm(emb) or 1.0))
                weights.append(seg.duration)
                owners.append(i)
            report((i + 1) / len(segments) * 0.9)

        labels: list[int | None] = [None] * len(segments)
        for owner, label in zip(owners, cluster(embeddings, weights) if embeddings else []):
            labels[owner] = label
        for seg, label in zip(segments, _fill_short(labels, segments)):
            seg.speaker = label

        speakers: dict[int, Speaker] = {}
        for sid in sorted({seg.speaker for seg in segments}):
            own = [s for s in segments if s.speaker == sid]
            longest = sorted(own, key=lambda s: -s.duration)[:8]
            pitches = [p for s in longest
                       if (p := pitch(audio[int(s.start * SAMPLE_RATE):int(s.end * SAMPLE_RATE)])) > 0]
            median = float(np.median(pitches)) if pitches else 0.0
            gender = "female" if median > MALE_MAX_PITCH else "male"
            speakers[sid] = Speaker(sid, gender, sum(s.duration for s in own))
        report(1.0)
        log.info("Speakers: %s", {s.id: (s.gender, round(s.seconds)) for s in speakers.values()})
        return speakers

    return await _run_in_thread(work, on_progress)


def prefetch(models_dir: Path) -> None:
    print("Модель различения голосов…", flush=True)
    _load_extractor(models_dir)

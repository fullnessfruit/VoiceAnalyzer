"""Presence decision from speaker embeddings.

Scores are raw cosine similarity of L2-normalized vectors.
WeSpeaker's CLI rescales cosine to (cos+1)/2. That scale is not used here,
so ecapa_min and wespeaker_min sit on the same cosine axis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class Thresholds:
    ecapa_min: float = 0.70
    wespeaker_min: float = 0.65
    margin: float = 0.05


@dataclass
class SpeechSegment:
    start: float
    end: float
    ecapa: np.ndarray
    wespeaker: np.ndarray | None = None


@dataclass
class SpeakerCluster:
    label: str
    segments: list[SpeechSegment] = field(default_factory=list)


@dataclass(frozen=True)
class ReferenceEmbedding:
    name: str
    ecapa: np.ndarray
    wespeaker: np.ndarray | None = None


@dataclass
class Enrollment:
    ecapa: np.ndarray
    wespeaker: np.ndarray | None = None
    references: tuple[ReferenceEmbedding, ...] = ()


@dataclass
class MatchDecision:
    present: bool
    best: dict | None
    segments: list[dict]
    reason: str | None = None


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    a = np.asarray(left, dtype=np.float64).reshape(-1)
    b = np.asarray(right, dtype=np.float64).reshape(-1)
    if a.shape != b.shape:
        raise ValueError(f"embedding dimension mismatch: {a.shape} vs {b.shape}")
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    values = np.asarray(vector, dtype=np.float64).reshape(-1)
    norm = np.linalg.norm(values)
    if norm == 0.0:
        return values
    return values / norm


def average_embeddings(vectors: list[np.ndarray]) -> np.ndarray:
    if not vectors:
        raise ValueError("no embeddings to average")
    stacked = np.mean([l2_normalize(vector) for vector in vectors], axis=0)
    return l2_normalize(stacked)


def _round_time(value: float) -> float:
    return round(float(value), 3)


def _round_score(value: float) -> float:
    return round(float(value), 4)


def _segment_rank(ecapa: float, wespeaker: float | None, ensemble: bool) -> float:
    if ensemble and wespeaker is not None:
        return (ecapa + wespeaker) / 2.0
    return ecapa


def decide(
    clusters: list[SpeakerCluster],
    enrollments: dict[str, Enrollment],
    speaker_id: str,
    thresholds: Thresholds,
    ensemble: bool,
) -> MatchDecision:
    """Pick a cluster that clears every active threshold and the margin.

    A cluster is a candidate only when ECAPA is at least ecapa_min and, if
    WeSpeaker is loaded, WeSpeaker is at least wespeaker_min. With two or more
    enrolled speakers, the target score must also lead every other enrollment
    by margin on each active model. One enrolled speaker skips the margin.
    """
    if speaker_id not in enrollments:
        raise KeyError(speaker_id)

    others = [name for name in enrollments if name != speaker_id]
    candidates: list[dict] = []

    for cluster in clusters:
        if not cluster.segments:
            continue
        ecapa_mean = average_embeddings([segment.ecapa for segment in cluster.segments])
        wespeaker_mean = None
        if ensemble:
            wespeaker_vectors = []
            missing_wespeaker = False
            for segment in cluster.segments:
                if segment.wespeaker is None:
                    missing_wespeaker = True
                    break
                wespeaker_vectors.append(segment.wespeaker)
            if missing_wespeaker or not wespeaker_vectors:
                continue
            wespeaker_mean = average_embeddings(wespeaker_vectors)

        ecapa_scores = {
            name: cosine(ecapa_mean, enrollment.ecapa) for name, enrollment in enrollments.items()
        }
        target_ecapa = ecapa_scores[speaker_id]
        if target_ecapa < thresholds.ecapa_min:
            continue

        ws_scores: dict[str, float] | None = None
        target_ws: float | None = None
        if ensemble:
            if wespeaker_mean is None:
                continue
            ws_scores = {}
            for name, enrollment in enrollments.items():
                if enrollment.wespeaker is None:
                    raise RuntimeError(f"{name} has no wespeaker enrollment")
                ws_scores[name] = cosine(wespeaker_mean, enrollment.wespeaker)
            target_ws = ws_scores[speaker_id]
            if target_ws < thresholds.wespeaker_min:
                continue

        if others:
            if any(target_ecapa < ecapa_scores[name] + thresholds.margin for name in others):
                continue
            if ensemble and ws_scores is not None and target_ws is not None:
                if any(target_ws < ws_scores[name] + thresholds.margin for name in others):
                    continue

        per_segment = []
        for segment in cluster.segments:
            seg_ecapa = cosine(segment.ecapa, enrollments[speaker_id].ecapa)
            seg_ws = None
            if ensemble and segment.wespeaker is not None and enrollments[speaker_id].wespeaker is not None:
                seg_ws = cosine(segment.wespeaker, enrollments[speaker_id].wespeaker)
            per_segment.append(
                {
                    "start": _round_time(segment.start),
                    "end": _round_time(segment.end),
                    "ecapa": _round_score(seg_ecapa),
                    "wespeaker": None if seg_ws is None else _round_score(seg_ws),
                    "_rank": _segment_rank(seg_ecapa, seg_ws, ensemble),
                    "_start": segment.start,
                }
            )

        representative = min(per_segment, key=lambda item: (-item["_rank"], item["_start"]))
        candidates.append(
            {
                "start": representative["start"],
                "end": representative["end"],
                "ecapa": _round_score(target_ecapa),
                "wespeaker": None if target_ws is None else _round_score(target_ws),
                "_rank": _segment_rank(target_ecapa, target_ws, ensemble),
                "_start": representative["_start"],
                "segments": [
                    {key: value for key, value in item.items() if not key.startswith("_")}
                    for item in sorted(per_segment, key=lambda item: item["_start"])
                ],
            }
        )

    if not candidates:
        return MatchDecision(present=False, best=None, segments=[])

    winner = min(candidates, key=lambda item: (-item["_rank"], item["_start"]))
    best = {
        "start": winner["start"],
        "end": winner["end"],
        "ecapa": winner["ecapa"],
        "wespeaker": winner["wespeaker"],
    }
    return MatchDecision(present=True, best=best, segments=winner["segments"])


def decide_references(
    clusters: list[SpeakerCluster],
    enrollments: dict[str, Enrollment],
    speaker_id: str,
    thresholds: Thresholds,
    ensemble: bool,
) -> MatchDecision:
    """Compare each speaker cluster with each performance of the requested actor.

    Both active models must pass on the same reference. A cluster's multiple
    regions provide one pooled voice sample, while the reference performances
    remain separate. The strongest competing actor score supplies each margin.
    """
    if speaker_id not in enrollments:
        raise KeyError(speaker_id)
    target = enrollments[speaker_id]
    if not target.references:
        raise ValueError(f"{speaker_id} has no reference embeddings")

    others = {name: item for name, item in enrollments.items() if name != speaker_id}
    candidates: list[dict] = []
    for cluster in clusters:
        if not cluster.segments:
            continue
        ecapa_mean = average_embeddings([segment.ecapa for segment in cluster.segments])
        wespeaker_mean = None
        if ensemble:
            if any(segment.wespeaker is None for segment in cluster.segments):
                continue
            wespeaker_mean = average_embeddings(
                [segment.wespeaker for segment in cluster.segments]
            )

        for reference in target.references:
            ecapa = cosine(ecapa_mean, reference.ecapa)
            if ecapa < thresholds.ecapa_min:
                continue
            wespeaker = None
            if ensemble:
                if reference.wespeaker is None:
                    raise RuntimeError("missing wespeaker reference in ensemble decision")
                wespeaker = cosine(wespeaker_mean, reference.wespeaker)
                if wespeaker < thresholds.wespeaker_min:
                    continue

            passes_margin = True
            for other_name, other in others.items():
                other_refs = other.references or (
                    ReferenceEmbedding(other_name, other.ecapa, other.wespeaker),
                )
                other_ecapa = max(cosine(ecapa_mean, item.ecapa) for item in other_refs)
                if ecapa < other_ecapa + thresholds.margin:
                    passes_margin = False
                    break
                if ensemble:
                    if any(item.wespeaker is None for item in other_refs):
                        raise RuntimeError(f"{other_name} has no wespeaker enrollment")
                    other_wespeaker = max(
                        cosine(wespeaker_mean, item.wespeaker) for item in other_refs
                    )
                    if wespeaker < other_wespeaker + thresholds.margin:
                        passes_margin = False
                        break
            if not passes_margin:
                continue

            per_segment = []
            for segment in cluster.segments:
                segment_ecapa = cosine(segment.ecapa, reference.ecapa)
                segment_wespeaker = (
                    cosine(segment.wespeaker, reference.wespeaker) if ensemble else None
                )
                per_segment.append(
                    {
                        "start": _round_time(segment.start),
                        "end": _round_time(segment.end),
                        "ecapa": _round_score(segment_ecapa),
                        "wespeaker": (
                            None if segment_wespeaker is None else _round_score(segment_wespeaker)
                        ),
                        "reference": reference.name,
                        "_rank": _segment_rank(segment_ecapa, segment_wespeaker, ensemble),
                        "_start": segment.start,
                    }
                )
            representative = min(
                per_segment,
                key=lambda item: (-item["_rank"], item["_start"]),
            )
            candidates.append(
                {
                    "start": representative["start"],
                    "end": representative["end"],
                    "ecapa": _round_score(ecapa),
                    "wespeaker": None if wespeaker is None else _round_score(wespeaker),
                    "reference": reference.name,
                    "_rank": _segment_rank(ecapa, wespeaker, ensemble),
                    "_start": representative["_start"],
                    "segments": [
                        {key: value for key, value in item.items() if not key.startswith("_")}
                        for item in sorted(per_segment, key=lambda item: item["_start"])
                    ],
                }
            )

    if not candidates:
        return MatchDecision(present=False, best=None, segments=[])
    winner = min(
        candidates,
        key=lambda item: (-item["_rank"], item["_start"], item["reference"]),
    )
    return MatchDecision(
        present=True,
        best={
            key: value
            for key, value in winner.items()
            if key not in ("_rank", "_start", "segments")
        },
        segments=winner["segments"],
    )

"""Compare voice-actor embeddings on one raw-cosine scale."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ReferenceEmbedding:
    name: str
    vector: np.ndarray


@dataclass(frozen=True)
class Enrollment:
    mean: np.ndarray
    references: tuple[ReferenceEmbedding, ...]


@dataclass(frozen=True)
class WindowEmbedding:
    start: float
    end: float
    vector: np.ndarray


@dataclass(frozen=True)
class MatchDecision:
    present: bool
    best: dict | None
    segments: list[dict]


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    values = np.asarray(vector, dtype=np.float64).reshape(-1)
    norm = np.linalg.norm(values)
    return values if norm == 0.0 else values / norm


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    a = np.asarray(left, dtype=np.float64).reshape(-1)
    b = np.asarray(right, dtype=np.float64).reshape(-1)
    if a.shape != b.shape:
        raise ValueError(f"embedding dimension mismatch: {a.shape} vs {b.shape}")
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return 0.0 if norm == 0.0 else float(np.dot(a, b) / norm)


def average_embeddings(vectors: list[np.ndarray]) -> np.ndarray:
    if not vectors:
        raise ValueError("no embeddings to average")
    return l2_normalize(np.mean([l2_normalize(vector) for vector in vectors], axis=0))


def decide(windows: list[WindowEmbedding], enrollment: Enrollment, threshold: float) -> MatchDecision:
    """Take the strongest speech window against the equal-weight reference mean.

    Individual performances identify the nearest example for review; they do
    not vote independently and cannot turn a sub-threshold mean into a match.
    """
    if not -1.0 <= threshold <= 1.0:
        raise ValueError("cosine threshold must be within [-1, 1]")
    if not enrollment.references:
        raise ValueError("enrollment has no references")
    scored = []
    for window in windows:
        score = cosine(window.vector, enrollment.mean)
        nearest = max(enrollment.references,
                      key=lambda ref: cosine(window.vector, ref.vector))
        scored.append({"start": round(window.start, 3), "end": round(window.end, 3),
                       "score": round(score, 4), "reference": nearest.name,
                       "_score": score, "_start": window.start})
    if not scored:
        return MatchDecision(False, None, [])
    best = min(scored, key=lambda row: (-row["_score"], row["_start"]))
    shown = lambda row: {key: value for key, value in row.items() if not key.startswith("_")}
    passing = [shown(row) for row in scored if row["_score"] >= threshold]
    passing.sort(key=lambda row: row["start"])
    return MatchDecision(bool(passing), shown(best), passing)

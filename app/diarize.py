"""Turn VAD spans into speaker groups.

Pyannote labels an existing span. Without it, ECAPA vectors are grouped with
average-linkage agglomerative clustering on cosine distance.
"""

from __future__ import annotations

import numpy as np

from app.scoring import l2_normalize


def speech_regions_from_vad(
    samples: np.ndarray,
    sample_rate: int,
    vad_model,
    min_speech_sec: float,
    merge_silence_sec: float,
) -> list[tuple[float, float]]:
    import torch
    from silero_vad import get_speech_timestamps

    audio = torch.from_numpy(np.ascontiguousarray(samples, dtype=np.float32))
    stamps = get_speech_timestamps(
        audio,
        vad_model,
        sampling_rate=sample_rate,
        min_speech_duration_ms=int(round(min_speech_sec * 1000)),
        min_silence_duration_ms=int(round(merge_silence_sec * 1000)),
        # Neighboring speakers stay out of the cut. Silero's default pad is 30 ms.
        speech_pad_ms=0,
        return_seconds=True,
    )
    regions = []
    for stamp in stamps:
        start = float(stamp["start"])
        end = float(stamp["end"])
        if end - start + 1e-6 >= min_speech_sec:
            regions.append((start, end))
    return regions


def cluster_labels(embeddings: list[np.ndarray], distance_threshold: float) -> list[str]:
    count = len(embeddings)
    if count == 0:
        return []
    if count == 1:
        return ["c0"]

    from sklearn.cluster import AgglomerativeClustering

    matrix = np.stack([l2_normalize(vector) for vector in embeddings])
    common = dict(
        n_clusters=None,
        linkage="average",
        distance_threshold=float(distance_threshold),
    )
    try:
        model = AgglomerativeClustering(metric="cosine", **common)
    except TypeError:
        model = AgglomerativeClustering(affinity="cosine", **common)
    labels = model.fit_predict(matrix)
    return [f"c{int(label)}" for label in labels]


def _gaps(start: float, end: float, covered: list[tuple[float, float]]) -> list[tuple[float, float]]:
    cursor = start
    gaps = []
    for cut_start, cut_end in sorted(covered):
        cut_start = max(cut_start, start)
        cut_end = min(cut_end, end)
        if cut_end - cut_start <= 1e-3:
            continue
        if cut_start - cursor > 1e-3:
            gaps.append((cursor, cut_start))
        cursor = max(cursor, cut_end)
    if end - cursor > 1e-3:
        gaps.append((cursor, end))
    return gaps


def _merge_same_speaker(
    pieces: list[tuple[float, float, str]],
    merge_silence_sec: float,
) -> list[tuple[float, float, str]]:
    merged: list[tuple[float, float, str]] = []
    for start, end, speaker in sorted(pieces, key=lambda item: (item[0], item[1], item[2])):
        if merged and merged[-1][2] == speaker and start - merged[-1][1] <= merge_silence_sec:
            prev_start, _, prev_speaker = merged[-1]
            merged[-1] = (prev_start, max(merged[-1][1], end), prev_speaker)
        else:
            merged.append((start, end, speaker))
    return merged


def label_vad_with_turns(
    vad_regions: list[tuple[float, float]],
    turns: list[tuple[float, float, str]],
    min_speech_sec: float,
    merge_silence_sec: float,
) -> list[tuple[float, float, str]]:
    """Intersect VAD with diarization turns, then drop pieces under 3 seconds.

    The same speaker is joined across a silence of merge_silence_sec or less
    before that cut, so a short hole between two turns does not split them.
    VAD time that no turn covers is kept when it is still at least 3 seconds.
    """
    labeled: list[tuple[float, float, str]] = []
    for region_start, region_end in vad_regions:
        for turn_start, turn_end, speaker in turns:
            start = max(region_start, turn_start)
            end = min(region_end, turn_end)
            if end - start > 1e-3:
                labeled.append((start, end, speaker))

    merged = _merge_same_speaker(labeled, merge_silence_sec)
    pieces = list(merged)
    unassigned = 0
    for region_start, region_end in vad_regions:
        covered = [
            (start, end)
            for start, end, _speaker in merged
            if end > region_start and start < region_end
        ]
        for gap_start, gap_end in _gaps(region_start, region_end, covered):
            if gap_end - gap_start + 1e-6 < min_speech_sec:
                continue
            pieces.append((gap_start, gap_end, f"unassigned-{unassigned}"))
            unassigned += 1

    kept = [
        (start, end, speaker)
        for start, end, speaker in pieces
        if end - start + 1e-6 >= min_speech_sec
    ]
    kept.sort(key=lambda item: (item[0], item[1], item[2]))
    return kept

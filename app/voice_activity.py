"""Select the same start-aligned speech windows used in model evaluation."""

from __future__ import annotations

import numpy as np

from app.config import Config


def speech_regions(samples: np.ndarray, vad, config: Config) -> list[dict]:
    import torch
    from silero_vad import get_speech_timestamps

    waveform = torch.from_numpy(np.ascontiguousarray(samples, dtype=np.float32))
    return get_speech_timestamps(waveform, vad, sampling_rate=config.sample_rate,
                                 min_speech_duration_ms=config.vad_min_speech_ms,
                                 speech_pad_ms=0)


def fixed_windows(sample_count: int, regions: list[dict], config: Config) -> list[tuple[int, int, float]]:
    """Discard an incomplete tail and require at least half of each window to be speech."""
    size = round(config.window_sec * config.sample_rate)
    if size <= 0:
        raise ValueError("window size must be positive")
    chosen = []
    for first in range(0, sample_count - size + 1, size):
        last = first + size
        covered = sum(max(0, min(last, item["end"]) - max(first, item["start"]))
                      for item in regions)
        fraction = covered / size
        if fraction >= config.min_speech_fraction:
            chosen.append((first, last, fraction))
    return chosen

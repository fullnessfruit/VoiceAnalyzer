"""Resolve local storage and the frozen, experimentally selected voice model."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 2 * 1024**3
MAX_DURATION_SEC = 3 * 60 * 60
SAMPLE_RATE = 16000
WINDOW_SEC = 3.0
MIN_SPEECH_FRACTION = 0.5
VAD_MIN_SPEECH_MS = 250
REFERENCE_CHUNK_SEC = 30.0
MODEL_REPO = "litagin/anime_speaker_embedding_by_va_ecapa_tdnn_groupnorm"
MODEL_REVISION = "1677c9702cca7aca7dc5a74b3c76f3c8b05969b7"
MODEL_SHA256 = "41d5ad6b5c758a03e46ab53388f42394f40bf115aa9d9df25d4adff6e21072ef"
DEFAULT_COSINE_MIN = 0.38
logger = logging.getLogger("voiceanalyzer")


@dataclass(frozen=True)
class Config:
    root: Path
    data_dir: Path
    refs_dir: Path
    work_dir: Path
    cache_dir: Path
    cosine_min: float
    device: str
    demucs_model: str
    demucs_shifts: int
    sample_rate: int = SAMPLE_RATE
    max_bytes: int = MAX_BYTES
    max_duration_sec: float = MAX_DURATION_SEC
    window_sec: float = WINDOW_SEC
    min_speech_fraction: float = MIN_SPEECH_FRACTION
    vad_min_speech_ms: int = VAD_MIN_SPEECH_MS
    reference_chunk_sec: float = REFERENCE_CHUNK_SEC


def load_config(path: Path | None = None) -> Config:
    config_path = path or ROOT / "config.yaml"
    with config_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("config.yaml must contain a mapping")
    thresholds = raw.get("thresholds") or {}
    demucs = raw.get("demucs") or {}
    if not isinstance(thresholds, dict) or not isinstance(demucs, dict):
        raise ValueError("thresholds and demucs must be mappings")
    ignored = sorted(set(thresholds) & {"ecapa_min", "wespeaker_min", "margin"})
    if ignored:
        logger.warning("legacy voice thresholds ignored - keys=%s", ",".join(ignored))
    root = config_path.resolve().parent
    cosine_min = float(thresholds.get("voice_min", DEFAULT_COSINE_MIN))
    if not -1.0 <= cosine_min <= 1.0:
        raise ValueError("thresholds.voice_min must be within [-1, 1]")
    config = Config(
        root=root,
        data_dir=(root / "data").resolve(),
        refs_dir=(root / "refs").resolve(),
        work_dir=(root / "work").resolve(),
        cache_dir=(root / "cache").resolve(),
        cosine_min=cosine_min,
        device=str(raw.get("device", "auto")),
        demucs_model=str(demucs.get("model", "htdemucs_ft")),
        demucs_shifts=int(demucs.get("shifts", 0)),
    )
    for directory in (config.data_dir, config.refs_dir, config.work_dir, config.cache_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return config

"""Load config.yaml. Paths are resolved from the project root."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from app.scoring import Thresholds

ROOT = Path(__file__).resolve().parents[1]

# Spec limits. A file at exactly 2 GiB or exactly 3 hours is accepted.
MAX_BYTES = 2 * 1024 * 1024 * 1024
MAX_DURATION_SEC = 3 * 60 * 60
SAMPLE_RATE = 16000
MIN_SPEECH_SEC = 3.0
MERGE_SILENCE_SEC = 0.4


@dataclass(frozen=True)
class Config:
    root: Path
    thresholds: Thresholds
    cluster_distance: float
    demucs_model: str
    demucs_shifts: int
    ecapa_model: str
    wespeaker_model: str
    diarization_model: str
    device: str
    data_dir: Path
    refs_dir: Path
    work_dir: Path
    cache_dir: Path
    sample_rate: int = SAMPLE_RATE
    max_bytes: int = MAX_BYTES
    max_duration_sec: float = MAX_DURATION_SEC
    min_speech_sec: float = MIN_SPEECH_SEC
    merge_silence_sec: float = MERGE_SILENCE_SEC


def load_config(path: Path | None = None) -> Config:
    config_path = path or (ROOT / "config.yaml")
    with config_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    thresholds = raw.get("thresholds") or {}
    clustering = raw.get("clustering") or {}
    demucs = raw.get("demucs") or {}
    models = raw.get("models") or {}
    root = config_path.resolve().parent

    config = Config(
        root=root,
        thresholds=Thresholds(
            ecapa_min=float(thresholds.get("ecapa_min", 0.70)),
            wespeaker_min=float(thresholds.get("wespeaker_min", 0.65)),
            margin=float(thresholds.get("margin", 0.05)),
        ),
        cluster_distance=float(clustering.get("distance_threshold", 0.40)),
        demucs_model=str(demucs.get("model", "htdemucs_ft")),
        demucs_shifts=int(demucs.get("shifts", 0)),
        ecapa_model=str(models.get("ecapa", "speechbrain/spkrec-ecapa-voxceleb")),
        wespeaker_model=str(models.get("wespeaker", "english")),
        diarization_model=str(models.get("diarization", "pyannote/speaker-diarization-3.1")),
        device=str(raw.get("device", "auto")),
        data_dir=(root / "data").resolve(),
        refs_dir=(root / "refs").resolve(),
        work_dir=(root / "work").resolve(),
        cache_dir=(root / "cache").resolve(),
    )
    for directory in (config.data_dir, config.refs_dir, config.work_dir, config.cache_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return config

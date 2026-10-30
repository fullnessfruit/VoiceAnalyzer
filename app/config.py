"""Resolve local storage and the selected separation and speaker-verification policy."""

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
WESPEAKER_MODEL = "english"
WESPEAKER_SHA256 = "47d76239f1e865b273e31e30f691959061ff6565ed6c4e7be9639a65d9662eb5"
DEMUCS_MODEL = "htdemucs"
DEMUCS_SHA256 = "8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4"
DEFAULT_TOP3_MIN = 0.4771964776614425
TOP_WINDOW_COUNT = 3
logger = logging.getLogger("voiceanalyzer")


@dataclass(frozen=True)
class Config:
    root: Path
    data_dir: Path
    refs_dir: Path
    work_dir: Path
    cache_dir: Path
    log_dir: Path
    cosine_min: float
    device: str
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
    if not isinstance(thresholds, dict):
        raise ValueError("thresholds must be a mapping")
    ignored = sorted(set(thresholds) & {"ecapa_min", "wespeaker_min", "margin", "voice_min"})
    if ignored:
        logger.warning("legacy voice thresholds ignored - keys=%s", ",".join(ignored))
    if "demucs" in raw:
        logger.warning("legacy demucs settings ignored")
    root = config_path.resolve().parent
    cosine_min = float(thresholds.get("wespeaker_top3_min", DEFAULT_TOP3_MIN))
    if not -1.0 <= cosine_min <= 1.0:
        raise ValueError("thresholds.wespeaker_top3_min must be within [-1, 1]")
    config = Config(
        root=root,
        data_dir=(root / "data").resolve(),
        refs_dir=(root / "data").resolve(),
        work_dir=(root / "work").resolve(),
        cache_dir=(root / "cache").resolve(),
        log_dir=(root / "log").resolve(),
        cosine_min=cosine_min,
        device=str(raw.get("device", "auto")),
    )
    for directory in (config.data_dir, config.refs_dir, config.work_dir,
                      config.cache_dir, config.log_dir):
        directory.mkdir(parents=True, exist_ok=True)
    return config

"""Cache every performance separately and its equal-weight voice-actor mean."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import uuid
from pathlib import Path

import numpy as np

from app.audio import AudioReadError, FFmpegMissing, extract_mono, read_mono_pcm16
from app.config import Config, MODEL_SHA256
from app.models import ModelHub
from app.paths import PathRejected
from app.scoring import Enrollment, ReferenceEmbedding, average_embeddings

logger = logging.getLogger("voiceanalyzer")
_CACHE_VERSION = "anime-va-3s-mean-v1"


def list_speakers(config: Config) -> list[dict]:
    return [{"speaker_id": name, "num_samples": len(wavs)}
            for name, wavs in _reference_wavs(config).items()]


def load_enrollment(config: Config, hub: ModelHub, speaker_id: str, work: Path) -> Enrollment:
    """Load only the requested actor; caller owns hub.lock during inference."""
    available = _reference_wavs(config, speaker_id)
    if speaker_id not in available:
        raise PathRejected("speaker not enrolled")
    return _embed_or_cache(config, hub, speaker_id, available[speaker_id], work)


def embed_waveform(hub: ModelHub, samples: np.ndarray, sample_rate: int,
                   chunk_sec: float = 30.0) -> np.ndarray:
    """Use the same 30 s nonoverlap mean as the frozen comparison references."""
    if sample_rate != 16000 or not len(samples):
        raise ValueError("reference must be nonempty 16 kHz mono audio")
    parts = _windows(samples, sample_rate, chunk_sec)
    vectors = [hub.embed_many([part])[0] for part in parts]
    return average_embeddings(vectors)


def _windows(samples: np.ndarray, sample_rate: int,
             chunk_sec: float = 30.0) -> list[np.ndarray]:
    """Keep a short final chunk only when it contains at least 0.5 s."""
    chunk = round(chunk_sec * sample_rate)
    if chunk <= 0:
        raise ValueError("reference chunk must be positive")
    parts = [np.ascontiguousarray(samples[first:first + chunk])
             for first in range(0, len(samples), chunk)]
    if len(parts) > 1 and len(parts[-1]) < round(0.5 * sample_rate):
        parts.pop()
    return parts


def _reference_wavs(config: Config, speaker_id: str | None = None) -> dict[str, list[Path]]:
    if not config.refs_dir.is_dir():
        return {}
    directories = ([config.refs_dir / speaker_id] if speaker_id is not None else
                   [path for path in config.refs_dir.iterdir()
                    if path.is_dir() and not path.name.startswith(".")])
    found = {}
    for directory in sorted(directories, key=lambda path: path.name.lower()):
        if not directory.is_dir():
            continue
        wavs = sorted((path for path in directory.iterdir()
                       if path.is_file() and path.suffix.lower() in {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus"}),
                      key=lambda path: path.name.lower())
        if wavs:
            found[directory.name] = wavs
    return found


def _fingerprint(wavs: list[Path]) -> str:
    digest = hashlib.sha256((_CACHE_VERSION + MODEL_SHA256).encode())
    for path in wavs:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.stat().st_size.to_bytes(8, "big"))
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def _cache_path(config: Config, speaker_id: str) -> Path:
    return config.cache_dir / "enroll_anime_va_v1" / f"{speaker_id}.npz"


def _read_cache(path: Path, fingerprint: str) -> Enrollment | None:
    if not path.is_file():
        return None
    try:
        with np.load(path, allow_pickle=False) as data:
            if str(data["fingerprint"]) != fingerprint:
                return None
            names = [str(name) for name in data["names"]]
            vectors = np.asarray(data["vectors"], dtype=np.float64)
            mean = np.asarray(data["mean"], dtype=np.float64)
            if not names or vectors.shape != (len(names), 192) or mean.shape != (192,):
                return None
            if not np.isfinite(vectors).all() or not np.isfinite(mean).all():
                return None
            return Enrollment(mean, tuple(ReferenceEmbedding(name, vector)
                                          for name, vector in zip(names, vectors)))
    except Exception as exc:
        logger.error("ignoring unreadable enrollment cache - path=%s error=%r", path, exc)
        return None


def _write_cache(path: Path, fingerprint: str, enrollment: Enrollment) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with staged.open("wb") as stream:
            np.savez(stream, fingerprint=np.array(fingerprint),
                     names=np.asarray([ref.name for ref in enrollment.references]),
                     vectors=np.stack([ref.vector for ref in enrollment.references]).astype(np.float32),
                     mean=enrollment.mean.astype(np.float32))
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def _embed_or_cache(config: Config, hub: ModelHub, speaker_id: str,
                    wavs: list[Path], work: Path) -> Enrollment:
    fingerprint = _fingerprint(wavs)
    cache = _cache_path(config, speaker_id)
    found = _read_cache(cache, fingerprint)
    if found is not None:
        return found
    enrollment = _average_wavs(config, hub, wavs, work)
    _write_cache(cache, fingerprint, enrollment)
    return enrollment


def _average_wavs(config: Config, hub: ModelHub, wavs: list[Path], work: Path) -> Enrollment:
    work.mkdir(parents=True, exist_ok=True)
    references = []
    try:
        for index, wav in enumerate(wavs):
            dest = work / f"{index:03d}.wav"
            try:
                extract_mono(wav, dest, config.sample_rate)
                samples, sample_rate = read_mono_pcm16(dest)
            except FFmpegMissing as exc:
                raise PathRejected(str(exc)) from exc
            except AudioReadError as exc:
                raise PathRejected(f"cannot read media: {wav.name}") from exc
            vector = embed_waveform(hub, samples, sample_rate, config.reference_chunk_sec)
            references.append(ReferenceEmbedding(wav.name, vector))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return Enrollment(average_embeddings([ref.vector for ref in references]),
                      tuple(references))

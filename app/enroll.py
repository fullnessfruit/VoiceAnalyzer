"""Cache individual reference embeddings and their legacy mean for comparison.

Nothing here is trained. POST /v1/enroll rebuilds the cached vectors.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import uuid
from pathlib import Path

import numpy as np

from app.audio import AudioReadError, FFmpegMissing, extract_mono, read_mono_pcm16
from app.config import Config
from app.models import ModelHub
from app.paths import PathRejected
from app.scoring import Enrollment, ReferenceEmbedding, average_embeddings

logger = logging.getLogger("voiceanalyzer")

_CHUNK_SEC = 30.0


def list_speakers(config: Config) -> list[dict]:
    return [
        {"speaker_id": speaker_id, "num_wavs": len(wavs)}
        for speaker_id, wavs in _reference_wavs(config).items()
    ]


def speaker_has_wavs(config: Config, speaker_id: str) -> bool:
    return speaker_id in _reference_wavs(config, speaker_id)


def enroll_speakers(
    config: Config,
    hub: ModelHub,
    speaker_id: str | None,
    source_wavs: list[Path] | None,
) -> dict:
    """Rebuild cached means. source_wavs, when set, replace refs/{speaker_id}/."""
    if source_wavs is not None:
        if not speaker_id:
            raise PathRejected(400, "speaker_id is required when file_paths is set")
        if not source_wavs:
            raise PathRejected(400, "file_paths is empty")
        _replace_references(config, speaker_id, source_wavs)

    available = _reference_wavs(config, speaker_id)
    if speaker_id is not None and speaker_id not in available:
        raise PathRejected(404, "speaker not enrolled")

    work = config.work_dir / f"enroll-{uuid.uuid4().hex}"
    work.mkdir(parents=True, exist_ok=True)
    saved = []
    try:
        with hub.lock:
            ensemble = hub.ensemble()
            for name, wavs in available.items():
                enrollment = _embed_or_cache(config, hub, name, wavs, work, ensemble, force=True)
                saved.append(
                    {
                        "speaker_id": name,
                        "num_wavs": len(wavs),
                        "ensemble": enrollment.wespeaker is not None,
                    }
                )
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {"speakers": saved}


def load_enrollments(config: Config, hub: ModelHub, work: Path) -> dict[str, Enrollment]:
    """Cache hit when the wav set is unchanged. Caller holds hub.lock."""
    ensemble = hub.ensemble()
    loaded: dict[str, Enrollment] = {}
    for name, wavs in _reference_wavs(config).items():
        loaded[name] = _embed_or_cache(config, hub, name, wavs, work, ensemble, force=False)
    return loaded


def embed_wespeaker(hub: ModelHub, samples: np.ndarray, sample_rate: int) -> np.ndarray:
    if len(samples) == 0:
        raise RuntimeError("empty audio")
    parts = _windows(samples, sample_rate)
    return average_embeddings([hub.embed_wespeaker(part, sample_rate) for part in parts])


def embed_waveform(
    hub: ModelHub,
    samples: np.ndarray,
    sample_rate: int,
    ensemble: bool,
) -> tuple[np.ndarray, np.ndarray | None]:
    """One vector per model. Long audio is the mean of 30 s windows."""
    if len(samples) == 0:
        raise RuntimeError("empty audio")
    parts = _windows(samples, sample_rate)
    ecapa = average_embeddings([hub.embed_ecapa(part) for part in parts])
    if not ensemble:
        return ecapa, None
    wespeaker = average_embeddings(
        [hub.embed_wespeaker(part, sample_rate) for part in parts]
    )
    return ecapa, wespeaker


def _windows(samples: np.ndarray, sample_rate: int) -> list[np.ndarray]:
    chunk = int(_CHUNK_SEC * sample_rate)
    hop = chunk
    if len(samples) <= chunk:
        return [samples]
    parts: list[np.ndarray] = []
    start = 0
    min_tail = int(0.5 * sample_rate)
    while start < len(samples):
        piece = samples[start : start + chunk]
        if len(piece) < min_tail and parts:
            break
        parts.append(np.ascontiguousarray(piece))
        if start + chunk >= len(samples):
            break
        start += hop
    return parts


def _reference_wavs(config: Config, speaker_id: str | None = None) -> dict[str, list[Path]]:
    if not config.refs_dir.is_dir():
        return {}
    if speaker_id is None:
        directories = [
            path
            for path in config.refs_dir.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        ]
    else:
        directories = [config.refs_dir / speaker_id]
    found: dict[str, list[Path]] = {}
    for directory in sorted(directories, key=lambda path: path.name.lower()):
        if not directory.is_dir():
            continue
        wavs = [
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() == ".wav"
        ]
        wavs.sort(key=lambda path: path.name.lower())
        if wavs:
            found[directory.name] = wavs
    return found


def _fingerprint(wavs: list[Path]) -> str:
    lines = []
    for path in wavs:
        stat = path.stat()
        lines.append(f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _cache_path(config: Config, speaker_id: str) -> Path:
    return config.cache_dir / "enroll" / f"{speaker_id}.npz"


def _read_cache(path: Path, fingerprint: str, ensemble: bool) -> Enrollment | None:
    if not path.is_file():
        return None
    try:
        with np.load(path, allow_pickle=False) as data:
            required = {"fingerprint", "ecapa", "wespeaker", "reference_names", "reference_ecapa", "reference_wespeaker"}
            if not required.issubset(data.files) or str(data["fingerprint"]) != fingerprint:
                return None
            names = [str(name) for name in data["reference_names"]]
            ecapa_refs = np.asarray(data["reference_ecapa"], dtype=np.float64)
            wespeaker_refs = np.asarray(data["reference_wespeaker"], dtype=np.float64)
            if not names or ecapa_refs.ndim != 2 or ecapa_refs.shape[0] != len(names):
                return None
            if ensemble and (wespeaker_refs.ndim != 2 or wespeaker_refs.shape[0] != len(names)):
                return None
            references = tuple(
                ReferenceEmbedding(
                    name,
                    ecapa_refs[index],
                    wespeaker_refs[index] if ensemble else None,
                )
                for index, name in enumerate(names)
            )
            return Enrollment(
                ecapa=np.asarray(data["ecapa"], dtype=np.float64),
                wespeaker=np.asarray(data["wespeaker"], dtype=np.float64) if ensemble else None,
                references=references,
            )
    except Exception as exc:
        logger.error("ignoring unreadable enrollment cache %s - error=%r", path, exc)
        return None


def _write_cache(path: Path, fingerprint: str, enrollment: Enrollment) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    references = enrollment.references
    if not references:
        raise ValueError("cannot cache enrollment without references")
    with_wespeaker = [reference.wespeaker is not None for reference in references]
    if any(with_wespeaker) and not all(with_wespeaker):
        raise ValueError("inconsistent wespeaker reference embeddings")
    wespeaker = (
        np.zeros(0, dtype=np.float32)
        if enrollment.wespeaker is None
        else np.asarray(enrollment.wespeaker, dtype=np.float32)
    )
    reference_wespeaker = (
        np.stack([np.asarray(reference.wespeaker, dtype=np.float32) for reference in references])
        if all(with_wespeaker)
        else np.zeros(0, dtype=np.float32)
    )
    np.savez(
        path,
        ecapa=np.asarray(enrollment.ecapa, dtype=np.float32),
        wespeaker=wespeaker,
        reference_names=np.asarray([reference.name for reference in references]),
        reference_ecapa=np.stack([np.asarray(reference.ecapa, dtype=np.float32) for reference in references]),
        reference_wespeaker=reference_wespeaker,
        fingerprint=np.array(fingerprint),
    )


def _embed_or_cache(
    config: Config,
    hub: ModelHub,
    speaker_id: str,
    wavs: list[Path],
    work: Path,
    ensemble: bool,
    force: bool,
) -> Enrollment:
    fingerprint = _fingerprint(wavs)
    cache = _cache_path(config, speaker_id)
    if not force:
        cached = _read_cache(cache, fingerprint, ensemble)
        if cached is not None:
            return cached
    enrollment = _average_wavs(config, hub, wavs, work / speaker_id, ensemble)
    _write_cache(cache, fingerprint, enrollment)
    return enrollment


def _average_wavs(
    config: Config,
    hub: ModelHub,
    wavs: list[Path],
    work: Path,
    ensemble: bool,
) -> Enrollment:
    work.mkdir(parents=True, exist_ok=True)
    references: list[ReferenceEmbedding] = []
    try:
        for index, wav in enumerate(wavs):
            dest = work / f"{index:03d}.wav"
            try:
                extract_mono(wav, dest, config.sample_rate)
                samples, sample_rate = read_mono_pcm16(dest)
            except FFmpegMissing as exc:
                raise PathRejected(500, str(exc)) from exc
            except AudioReadError as exc:
                raise PathRejected(400, f"cannot read media: {wav.name}") from exc
            ecapa, wespeaker = embed_waveform(hub, samples, sample_rate, ensemble)
            references.append(ReferenceEmbedding(wav.name, ecapa, wespeaker))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return Enrollment(
        ecapa=average_embeddings([reference.ecapa for reference in references]),
        wespeaker=(
            average_embeddings([reference.wespeaker for reference in references])
            if ensemble else None
        ),
        references=tuple(references),
    )


def _replace_references(config: Config, speaker_id: str, sources: list[Path]) -> None:
    staging = config.refs_dir / f".{speaker_id}.staging"
    backup = config.refs_dir / f".{speaker_id}.bak"
    dest = config.refs_dir / speaker_id
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        for index, source in enumerate(sources):
            shutil.copyfile(source, staging / f"{index:03d}.wav")
        if backup.exists():
            shutil.rmtree(backup)
        if dest.exists():
            dest.rename(backup)
        staging.rename(dest)
    except Exception:
        if staging.exists() and not dest.exists() and backup.exists():
            backup.rename(dest)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

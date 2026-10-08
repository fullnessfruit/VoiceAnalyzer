"""ffmpeg extract to 16 kHz mono PCM, and WAV helpers for our own files."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np


class AudioReadError(Exception):
    pass


class FFmpegMissing(AudioReadError):
    pass


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FFmpegMissing("ffmpeg/ffprobe is not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioReadError("ffmpeg timed out") from exc


def probe_duration(path: Path) -> float:
    completed = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise AudioReadError(detail or "ffprobe failed")
    text = completed.stdout.strip()
    try:
        duration = float(text)
    except ValueError as exc:
        raise AudioReadError("media has no duration") from exc
    if duration < 0:
        raise AudioReadError("media has no duration")
    return duration


def extract_mono(source: Path, dest: Path, sample_rate: int) -> None:
    """Write 16-bit mono PCM. Video tracks are dropped."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    completed = _run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-c:a",
            "pcm_s16le",
            str(dest),
        ]
    )
    if completed.returncode != 0 or not dest.is_file():
        detail = (completed.stderr or completed.stdout or "").strip()
        raise AudioReadError(detail or "ffmpeg failed to extract audio")


def write_mono_pcm16(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    clipped = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def read_mono_pcm16(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        if handle.getsampwidth() != 2:
            raise AudioReadError(f"expected 16-bit PCM wav: {path}")
        sample_rate = handle.getframerate()
        channels = handle.getnchannels()
        frames = handle.readframes(handle.getnframes())
    data = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return np.ascontiguousarray(data), sample_rate

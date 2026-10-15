"""ffmpeg extract to 16 kHz mono PCM, and WAV helpers for our own files."""

from __future__ import annotations

import os
import math
import shutil
from functools import lru_cache
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

from app.diagnostics import one_line


class AudioReadError(Exception):
    def __init__(self, message: str, diagnostics: dict | None = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


class FFmpegMissing(AudioReadError):
    pass


class NoAudioStream(AudioReadError):
    """The media is readable but has no audio track to analyze."""


def _binary(name: str) -> str:
    """Prefer the verified pair installed alongside Windows venv Python."""
    if os.name == "nt":
        bin_dir = Path(sys.executable).parent
        if all((bin_dir / f"{tool}.exe").is_file() for tool in ("ffmpeg", "ffprobe")):
            return str(bin_dir / f"{name}.exe")
    return name


@lru_cache(maxsize=8)
def _tool_version(binary: str) -> str:
    # Only failed inputs need this extra subprocess; cache it for later failures.
    try:
        result = subprocess.run([binary, "-version"], capture_output=True, text=True,
                                errors="replace", timeout=5, check=False)
        return one_line((result.stdout or result.stderr).splitlines()[0], 200)
    except (OSError, subprocess.SubprocessError, IndexError) as exc:
        return f"unavailable: {one_line(exc, 100)}"


def _tool_details(command: list[str], completed=None, failure=None) -> dict:
    binary = shutil.which(command[0]) or command[0]
    source = completed if completed is not None else failure
    return {"tool": Path(command[0]).stem, "binary": binary,
            "version": _tool_version(binary),
            "exitCode": getattr(source, "returncode", None),
            "stderr": one_line(getattr(source, "stderr", "") or ""),
            "stdout": one_line(getattr(source, "stdout", "") or "", 200),
            **({"timeoutSec": failure.timeout} if isinstance(failure, subprocess.TimeoutExpired) else {})}


def _read_error(message: str, completed) -> AudioReadError:
    return AudioReadError(message, _tool_details(completed.args, completed=completed))


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=3600,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FFmpegMissing("ffmpeg/ffprobe is not available", _tool_details(command, failure=exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioReadError("media tool timed out", _tool_details(command, failure=exc)) from exc
    except OSError as exc:
        raise AudioReadError("media tool could not start", _tool_details(command, failure=exc)) from exc


def probe_duration(path: Path) -> float:
    completed = _run(
        [
            _binary("ffprobe"),
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
        raise _read_error(detail or "ffprobe failed", completed)
    text = completed.stdout.strip()
    try:
        duration = float(text)
    except ValueError as exc:
        raise _read_error("media has no duration", completed) from exc
    if not math.isfinite(duration) or duration < 0:
        raise _read_error("media has no duration", completed)
    return duration


def extract_mono(source: Path, dest: Path, sample_rate: int) -> None:
    """Write 16-bit mono PCM. Video tracks are dropped."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    completed = _run(
        [
            _binary("ffmpeg"),
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
        streams = None
        try:
            streams = _run([
                _binary("ffprobe"), "-v", "error", "-select_streams", "a",
                "-show_entries", "stream=index",
                "-of", "default=noprint_wrappers=1:nokey=1", str(source),
            ])
        except AudioReadError:
            # Keep the original ffmpeg failure if the diagnostic probe also fails.
            pass
        if streams is not None and streams.returncode == 0 and not streams.stdout.strip():
            raise NoAudioStream("media has no audio stream")
        raise _read_error(detail or "ffmpeg failed to extract audio", completed)


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

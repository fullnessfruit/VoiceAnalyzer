"""Reject media paths that leave data/, or that exceed the size and length caps."""

from __future__ import annotations

import os
from pathlib import Path

from app.audio import AudioReadError, FFmpegMissing, probe_duration
from app.config import Config


class PathRejected(Exception):
    """An input or reference cannot be analyzed."""


def validate_speaker_id(value: str) -> str:
    """Keep broker names safe as Windows sample-folder and cache filenames."""
    if value != value.strip() or not value or value.endswith("."):
        raise ValueError("invalid speaker_id")
    if any(char in value for char in '<>:"/\\|?*') or any(ord(char) < 32 for char in value):
        raise ValueError("invalid speaker_id")
    return value


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        pass
    if os.name != "nt":
        return False
    # Path.relative_to is case-sensitive, including on Windows.
    path_key = os.path.normcase(os.path.abspath(path))
    root_key = os.path.normcase(os.path.abspath(root))
    prefix = root_key if root_key.endswith(os.sep) else root_key + os.sep
    return path_key == root_key or path_key.startswith(prefix)


def resolve_media_path(file_path: str, config: Config) -> Path:
    """Return a decodable file under data/ within the size and duration limits."""
    raw = Path(file_path)
    if not raw.is_absolute():
        raw = config.root / raw
    try:
        candidate = raw.resolve(strict=False)
    except OSError as exc:
        raise PathRejected("invalid path") from exc

    if not _is_inside(candidate, config.data_dir):
        raise PathRejected("path is outside data/")
    if candidate == config.data_dir or not candidate.is_file():
        raise PathRejected("file not found")

    try:
        size = candidate.stat().st_size
    except OSError as exc:
        raise PathRejected("invalid path") from exc
    if size > config.max_bytes:
        raise PathRejected("file exceeds 2GB")

    try:
        duration = probe_duration(candidate)
    except FFmpegMissing as exc:
        raise PathRejected(str(exc)) from exc
    except AudioReadError as exc:
        raise PathRejected("cannot read media") from exc
    if duration > config.max_duration_sec:
        raise PathRejected("duration exceeds 3 hours")
    return candidate

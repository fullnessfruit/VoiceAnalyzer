"""Reject media paths that leave data/, or that exceed the size and length caps."""

from __future__ import annotations

import os
from pathlib import Path

from app.audio import AudioReadError, FFmpegMissing, probe_duration
from app.config import Config


class PathRejected(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


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
    """Return a file under data/. 403 outside, 404 missing, 400 too big or too long."""
    raw = Path(file_path)
    if not raw.is_absolute():
        raw = config.root / raw
    try:
        candidate = raw.resolve(strict=False)
    except OSError as exc:
        raise PathRejected(400, "invalid path") from exc

    if not _is_inside(candidate, config.data_dir):
        raise PathRejected(403, "path is outside data/")
    if candidate == config.data_dir or not candidate.is_file():
        raise PathRejected(404, "file not found")

    try:
        size = candidate.stat().st_size
    except OSError as exc:
        raise PathRejected(400, "invalid path") from exc
    if size > config.max_bytes:
        raise PathRejected(400, "file exceeds 2GB")

    try:
        duration = probe_duration(candidate)
    except FFmpegMissing as exc:
        raise PathRejected(500, str(exc)) from exc
    except AudioReadError as exc:
        raise PathRejected(400, "cannot read media") from exc
    if duration > config.max_duration_sec:
        raise PathRejected(400, "duration exceeds 3 hours")
    return candidate

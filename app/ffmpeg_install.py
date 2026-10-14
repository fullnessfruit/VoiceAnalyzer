"""Install a pinned Windows FFmpeg pair into the active virtual environment."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile


_ARCHIVE_URL = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip"
_ARCHIVE_SHA256 = "60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba"
_MAX_ARCHIVE_BYTES = 160 * 1024 * 1024
_PACKAGE_DIR = "ffmpeg-9.0.2-essentials_build"
_MEMBERS = {
    "ffmpeg.exe": f"{_PACKAGE_DIR}/bin/ffmpeg.exe",
    "ffprobe.exe": f"{_PACKAGE_DIR}/bin/ffprobe.exe",
    "ffmpeg-LICENSE.txt": f"{_PACKAGE_DIR}/LICENSE",
    "ffmpeg-README.txt": f"{_PACKAGE_DIR}/README.txt",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(path: Path) -> None:
    size = 0
    with urlopen(_ARCHIVE_URL, timeout=60) as response, path.open("wb") as output:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            size += len(chunk)
            if size > _MAX_ARCHIVE_BYTES:
                raise RuntimeError("FFmpeg archive exceeds expected size")
            output.write(chunk)


def install_archive(archive: Path, bin_dir: Path) -> None:
    """Verify the pinned archive, then publish only its tools and notices."""
    if _sha256(archive) != _ARCHIVE_SHA256:
        raise RuntimeError("FFmpeg archive SHA-256 mismatch")
    bin_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ffmpeg-install-", dir=bin_dir) as temporary:
        staging = Path(temporary)
        with ZipFile(archive) as package:
            for filename, member in _MEMBERS.items():
                with package.open(member) as source, (staging / filename).open("wb") as output:
                    shutil.copyfileobj(source, output)
        for filename in _MEMBERS:
            os.replace(staging / filename, bin_dir / filename)


def _works(command: str) -> bool:
    try:
        return subprocess.run([command, "-version"], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=15, check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main() -> int:
    if os.name != "nt":
        print("Windows FFmpeg installer must run with Windows Python", file=sys.stderr)
        return 1
    bin_dir = Path(sys.executable).parent
    local = [bin_dir / "ffmpeg.exe", bin_dir / "ffprobe.exe"]
    if all(_works(str(path)) for path in local):
        print(f"FFmpeg ready - source=venv, path={bin_dir}")
        return 0
    if not any(path.exists() for path in local):
        system = [shutil.which("ffmpeg"), shutil.which("ffprobe")]
        if all(system) and all(_works(path) for path in system):
            print("FFmpeg ready - source=PATH")
            return 0

    print("Downloading FFmpeg 9.0.2 essentials for Windows (about 109 MB)")
    try:
        with tempfile.TemporaryDirectory(prefix="voiceanalyzer-ffmpeg-") as temporary:
            archive = Path(temporary) / "ffmpeg.zip"
            _download(archive)
            install_archive(archive, bin_dir)
        if not all(_works(str(path)) for path in local):
            raise RuntimeError("installed ffmpeg/ffprobe failed version checks")
    except Exception as exc:
        print(f"FFmpeg installation failed - error={exc}", file=sys.stderr)
        return 1
    print(f"FFmpeg ready - source=venv, path={bin_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

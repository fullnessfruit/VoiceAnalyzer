"""Download public X media locally; ffmpeg never receives a remote playlist."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import re
import shutil
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid

from app.config import Config
from app.paths import PathRejected, resolve_media_path


def validate_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        valid = (parsed.scheme == "https" and parsed.hostname == "video.twimg.com"
                 and parsed.port in (None, 443) and not parsed.username and not parsed.password
                 and not any(ord(c) < 33 for c in url))
    except ValueError:
        valid = False
    if not valid:
        raise PathRejected("media URL must be HTTPS video.twimg.com without credentials")
    return url


class _MediaRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _Download:
    def __init__(self, max_bytes: int):
        self.remaining = max_bytes
        self.deadline = time.monotonic() + 900
        self.opener = build_opener(_MediaRedirect())

    def chunks(self, url: str):
        request = Request(validate_url(url), headers={"User-Agent": "VoiceAnalyzer"})
        with self.opener.open(request, timeout=60) as response:
            validate_url(response.url)
            while True:
                if time.monotonic() > self.deadline:
                    raise PathRejected("media download timed out")
                block = response.read(256 * 1024)
                if not block:
                    break
                self.remaining -= len(block)
                if self.remaining < 0:
                    raise PathRejected("media exceeds download size limit")
                yield block

    def playlist(self, url: str) -> str:
        parts = []
        size = 0
        for block in self.chunks(url):
            size += len(block)
            if size > 2 * 1024 * 1024:
                raise PathRejected("HLS playlist too large")
            parts.append(block)
        text = b"".join(parts).decode("utf-8-sig")
        if not text.startswith("#EXTM3U"):
            raise PathRejected("invalid HLS playlist")
        return text


def _hls_segments(download: _Download, url: str, depth: int = 0) -> list[str]:
    if depth > 3:
        raise PathRejected("nested HLS playlist limit")
    text = download.playlist(url)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    # Prefer the highest-rate audio-only rendition; otherwise take the best stream.
    audio = []
    streams = []
    for index, line in enumerate(lines):
        if line.startswith("#EXT-X-MEDIA:") and "TYPE=AUDIO" in line:
            match = re.search(r'URI="([^"]+)"', line)
            if match:
                rate = re.search(r"(?:^|/)mp4a/(\d+)/", match[1])
                audio.append((int(rate[1]) if rate else 0, urljoin(url, match[1])))
        if line.startswith("#EXT-X-STREAM-INF:") and index + 1 < len(lines):
            rate = re.search(r"(?:^|,)BANDWIDTH=(\d+)", line.split(":", 1)[1])
            streams.append((int(rate[1]) if rate else 0, urljoin(url, lines[index + 1])))
    choices = audio or streams
    if choices:
        return _hls_segments(download, max(choices, key=lambda item: item[0])[1], depth + 1)
    if "#EXT-X-ENDLIST" not in lines:
        raise PathRejected("live HLS streams are not supported")
    if any(line.startswith("#EXT-X-BYTERANGE") or
           (line.startswith("#EXT-X-KEY") and "METHOD=NONE" not in line) for line in lines):
        raise PathRejected("encrypted or byte-range HLS is not supported")
    segments = []
    for line in lines:
        if line.startswith("#EXT-X-MAP:"):
            match = re.search(r'URI="([^"]+)"', line)
            if not match or "BYTERANGE" in line:
                raise PathRejected("invalid HLS init segment")
            segments.append(urljoin(url, match[1]))
        elif not line.startswith("#"):
            segments.append(urljoin(url, line))
    if not segments:
        raise PathRejected("empty HLS stream")
    return [validate_url(segment) for segment in segments]


@contextmanager
def downloaded_media(config: Config, url: str):
    validate_url(url)
    folder = config.data_dir / ".incoming" / uuid.uuid4().hex
    folder.mkdir(parents=True)
    dest = folder / "media.bin"
    try:
        download = _Download(config.max_bytes)
        urls = (_hls_segments(download, url) if urlsplit(url).path.endswith(".m3u8") else [url])
        with dest.open("wb") as output:
            for segment in urls:
                for block in download.chunks(segment):
                    output.write(block)
        yield resolve_media_path(str(dest), config)
    finally:
        shutil.rmtree(folder, ignore_errors=True)

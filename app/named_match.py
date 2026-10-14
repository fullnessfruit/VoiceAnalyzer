"""Only explicitly requested data/<name>/ sample folders participate in a match."""

from __future__ import annotations

from app.config import Config
from app.enroll import list_speakers
from app.media_download import downloaded_media
from app.paths import resolve_media_path
from app.pipeline import match_files_for_names
from app.schemas import _speaker_id


def requested_speakers(config: Config, names: list[str]) -> tuple[list[str], list[str]]:
    requested = list(dict.fromkeys(_speaker_id(name) for name in names))
    available = {item["speaker_id"] for item in list_speakers(config)}
    return ([name for name in requested if name in available],
            [name for name in requested if name not in available])


def match_requested(config: Config, names: list[str], *, file_path: str | None = None,
                    media_url: str | None = None, separate_bgm: bool = False) -> dict:
    selected, skipped = requested_speakers(config, names)
    if not selected:
        return {"matches": [], "skippedNames": skipped, "reason": "no_registered_names"}
    if media_url:
        with downloaded_media(config, media_url) as media:
            matches = match_files_for_names(config, media, selected, separate_bgm)
    else:
        media = resolve_media_path(file_path or "", config)
        matches = match_files_for_names(config, media, selected, separate_bgm)
    return {"matches": matches, "skippedNames": skipped}

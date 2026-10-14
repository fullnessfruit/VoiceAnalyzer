"""Only explicitly requested data/<name>/ sample folders participate in a match."""

from __future__ import annotations

from app.config import Config
from app.enroll import list_speakers
from app.media_download import downloaded_media
from app.paths import validate_speaker_id
from app.pipeline import match_files_for_names


def requested_speakers(config: Config, names: list[str]) -> tuple[list[str], list[str]]:
    requested = list(dict.fromkeys(validate_speaker_id(name) for name in names))
    available = {item["speaker_id"] for item in list_speakers(config)}
    return ([name for name in requested if name in available],
            [name for name in requested if name not in available])


def match_requested(config: Config, names: list[str], media_url: str) -> dict:
    selected, skipped = requested_speakers(config, names)
    if not selected:
        return {"matches": [], "skippedNames": skipped, "reason": "no_registered_names"}
    with downloaded_media(config, media_url) as media:
        matches = match_files_for_names(config, media, selected)
    return {"matches": matches, "skippedNames": skipped}

"""HTTP bodies."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _speaker_id(value: str) -> str:
    if value != value.strip() or not value or value.endswith("."):
        raise ValueError("invalid speaker_id")
    # These characters are illegal in Windows directory names.
    if any(char in value for char in '<>:"/\\|?*') or any(ord(char) < 32 for char in value):
        raise ValueError("invalid speaker_id")
    return value


class MatchRequest(BaseModel):
    file_path: str = Field(min_length=1)
    speaker_id: str = Field(min_length=1, max_length=128)
    separate_bgm: bool = False

    @field_validator("speaker_id")
    @classmethod
    def check_speaker_id(cls, value: str) -> str:
        return _speaker_id(value)


class EnrollRequest(BaseModel):
    speaker_id: str | None = None
    file_paths: list[str] | None = None

    @field_validator("speaker_id")
    @classmethod
    def check_speaker_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _speaker_id(value)
